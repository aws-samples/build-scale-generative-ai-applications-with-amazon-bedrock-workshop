"""
Lambda that performs summarization with Bedrock
"""

#########################
#   LIBRARIES & LOGGER
#########################
import ast
import json
import logging
import os
import sys

import boto3

LOGGER = logging.Logger("DDB LAMBDA", level=logging.DEBUG)
HANDLER = logging.StreamHandler(sys.stdout)
HANDLER.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
LOGGER.addHandler(HANDLER)


def remove_dynamodb_type_descriptors(item):
    return {k: list(v.values())[0] for k, v in item.items()}


#########################
#        HANDLER
#########################


def lambda_handler(event, context):
    """
    Lambda handler
    """
    LOGGER.info("Starting execution of lambda_handler()")

    ### PREPARATIONS
    # Convert the 'body' string to a dictionary
    LOGGER.info(f"The incoming payload event:{event}")

    body = json.loads(event["body"])

    payload_type = body.get("type", {})
    LOGGER.info(f"Payload type: {payload_type}")

    LOGGER.info(f"The incoming payload body:{body}")

    LOGGER.info("Standing up DDB connection!")
    dynamodb = boto3.client("dynamodb")

    # Get the DynamoDB table name from environment variable
    table_name = os.environ["TABLE_NAME"]
    LOGGER.info("boto3 dynamo established!")

    if payload_type == "PUT":
        # Extract the 'item' dictionary from the body
        item = body.get("item", {})
        # Construct the item data as a dictionary
        item_data = {
            "session_id": {"S": item.get("session_id", "")},
            "user_id": {"S": item.get("user_id", "")},
            "timestamp": {"S": item.get("timestamp", "")},
            "model": {"S": item.get("model", "")},
            "answer_length": {"N": item.get("answer_length", "")},
            "temperature": {"N": item.get("temperature", "")},
            "Prompt Template": {"S": item.get("Prompt Template", "")},
            "Prompt": {"S": item.get("Prompt", "")},
            "Output": {"S": item.get("Output", "")},
        }
        LOGGER.info(f"Item data: {item_data}")

        # Put the item into DynamoDB table
        try:
            response = dynamodb.put_item(TableName=table_name, Item=item_data)

            LOGGER.info(f"successfully put item!")
            return {"statusCode": 200, "body": json.dumps("Item successfully added to DynamoDB table")}
        except Exception as e:
            LOGGER.info(f"Unuccessful! Exception: {e}")
            return {"statusCode": 500, "body": json.dumps("Error adding item to DynamoDB table: {}".format(str(e)))}

    if payload_type == "GET":
        # Extract filter parameters
        filter_params = body.get("filter_params", {})
        print(filter_params)
        user_ids_filter_str = filter_params.get("user_ids_filter", "")
        if user_ids_filter_str != "":
            user_ids_filter = ast.literal_eval(user_ids_filter_str)
        else:
            user_ids_filter = []

        # retrieving filter values
        industry_filter = filter_params.get("industry_filter")
        language_filter = filter_params.get("language_filter")
        task_filter = filter_params.get("task_filter")
        technique_filter = filter_params.get("technique_filter")
        ai_model_filter = filter_params.get("ai_model_filter")

        user_id = filter_params.get("user_id")
        user_ids_filter.append(user_id)
        # Create FilterExpression and ExpressionAttributeValues
        filter_expressions = []
        expression_attribute_values = {}
        # Use an expression attribute names dictionary to handle reserved words
        expression_attribute_names = {}

        # Incorporating user_ids_filter for possiblle filter expansion in UI
        if user_ids_filter:
            user_id_placeholders = [f":user_id_{i}" for i, _ in enumerate(user_ids_filter)]
            filter_expressions.append(f"user_id IN ({', '.join(user_id_placeholders)})")
            for placeholder, user_id in zip(user_id_placeholders, user_ids_filter):
                expression_attribute_values[placeholder] = {"S": user_id}

        if industry_filter and industry_filter != "ALL":
            filter_expressions.append("Industry = :industry")
            expression_attribute_values[":industry"] = {"S": industry_filter}

        # Incorporating language_filter
        if language_filter and language_filter != "ALL":
            filter_expressions.append("#Language = :language")
            expression_attribute_values[":language"] = {"S": language_filter}
            expression_attribute_names["#Language"] = "Language"

        # Incorporating task_filter
        if task_filter and task_filter != "ALL":
            filter_expressions.append("Task = :task")
            expression_attribute_values[":task"] = {"S": task_filter}

        # Incorporating technique_filter
        if technique_filter and technique_filter != "ALL":
            filter_expressions.append("Technique = :technique")
            expression_attribute_values[":technique"] = {"S": technique_filter}

        # Incorporating ai_model_filter
        if ai_model_filter and ai_model_filter != "ALL":
            filter_expressions.append("model = :model")
            expression_attribute_values[":model"] = {"S": ai_model_filter}

        filter_expression_string = " AND ".join(filter_expressions)
        print(f"FilterExpressions = {filter_expression_string}")
        print(f"Expression Attributes: {expression_attribute_values}")
        try:
            if expression_attribute_names != {}:
                response = dynamodb.scan(
                    TableName=table_name,
                    Limit=1000,
                    FilterExpression=filter_expression_string if filter_expressions else None,
                    ExpressionAttributeValues=expression_attribute_values if expression_attribute_values else None,
                    ExpressionAttributeNames=expression_attribute_names if expression_attribute_names else None,
                )
            else:
                # Use scan with FilterExpression to get items. Limit to 1000 items.
                response = dynamodb.scan(
                    TableName=table_name,
                    Limit=1000,
                    FilterExpression=filter_expression_string if filter_expressions else None,
                    ExpressionAttributeValues=expression_attribute_values if expression_attribute_values else None,
                )

            items = response.get("Items", {})
            LOGGER.info(f"Retrieved {len(items)} items")
            clean_item_list = []
            for item in items:
                clean_item = remove_dynamodb_type_descriptors(item)
                clean_item_list.append(clean_item)

            # Return items in response
            return {"statusCode": 200, "body": json.dumps(clean_item_list)}
        except Exception as e:
            LOGGER.error(f"Error retrieving items: {e}")
            return {"statusCode": 500, "body": json.dumps(f"Error retrieving items from DynamoDB: {str(e)}")}

    elif payload_type == "DELETE":
        # Extract the 'session_id' from the body
        print("made it into the delete section! ")
        session_id = body["item"]["session_id"]
        LOGGER.debug(f"session_id {session_id}, {type(session_id)}")

        if not session_id:
            LOGGER.error("session_id is required for DELETE operation")
            return {"statusCode": 400, "body": json.dumps("session_id is required for DELETE operation")}

        try:
            response = dynamodb.delete_item(
                TableName=table_name,
                Key={"session_id": {"S": session_id}},  # "S" indicates that the datatype is a string.
            )

            LOGGER.info(f"Deleted item with session_id: {session_id}")

            return {"statusCode": 200, "body": json.dumps(f"Item with session_id {session_id} successfully deleted")}
        except Exception as e:
            LOGGER.error(f"Error deleting item: {e}")
            return {"statusCode": 500, "body": json.dumps(f"Error deleting item from DynamoDB: {str(e)}")}

    else:
        return {"statusCode": 400, "body": json.dumps("Invalid payload type")}
