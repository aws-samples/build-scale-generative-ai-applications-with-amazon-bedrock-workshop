"""
Lambda that performs summarization with Bedrock
"""

#########################
#   LIBRARIES & LOGGER
#########################
import json
import logging
import os
import sys
from datetime import datetime, timezone

import boto3
import boto3.dynamodb
import boto3.dynamodb.table
import boto3.dynamodb.types

LOGGER = logging.Logger("DDB LAMBDA", level=logging.DEBUG)
HANDLER = logging.StreamHandler(sys.stdout)
HANDLER.setFormatter(logging.Formatter(
    "%(levelname)s | %(name)s | %(message)s"))
LOGGER.addHandler(HANDLER)

MODELS_MAPPING = {
    "Bedrock: Amazon Titan": "amazon.titan-text-express-v1",
    "Bedrock: Claude V2": "anthropic.claude-v2",
    "Bedrock: Claude 3 Sonnet": "anthropic.claude-3-sonnet-20240229-v1:0"
}


def create_bedrock_agent_client():
    """
    Creates a Bedrock Agent client using the specified region and configuration.

    Returns:
        A tuple containing the Bedrock client and the expiration time (which is None).
    """
    LOGGER.info("Using bedrock agent client from same account.")
    bedrock_client = boto3.client(
        service_name="bedrock-agent",
        region_name=os.environ["BEDROCK_REGION"]
    )
    expiration = None
    LOGGER.info("Successfully set bedrock agent client")

    return bedrock_client, expiration


BEDROCK_AGENT_CLIENT, EXPIRATION = create_bedrock_agent_client()


def verify_bedrock_agent_client():
    """
    Verifies the Bedrock client by checking if the token has expired or not.

    Returns:
        bool: True if the Bedrock client is verified, False otherwise.
    """
    if EXPIRATION is not None:
        now = datetime.now(timezone.utc)
        LOGGER.info(
            f"Bedrock token expires in {(EXPIRATION - now).total_seconds()}s")
        if (EXPIRATION - now).total_seconds() < 60:
            return False
    return True


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
    LOGGER.info(f"Boto version: {boto3.__version__}")

    # PREPARATIONS
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

    if not verify_bedrock_agent_client():
        LOGGER.info("Bedrock agent client expired, will refresh token.")
        global BEDROCK_AGENT_CLIENT, EXPIRATION
        BEDROCK_AGENT_CLIENT, EXPIRATION = create_bedrock_agent_client()

    if payload_type == "PUT":
        # Extract the 'item' dictionary from the body
        item = body.get("item")
        # get fixed model params
        MODEL_ID = MODELS_MAPPING[item.get("model")]
        LOGGER.info(f"MODEL_ID: {MODEL_ID}")
        # create the prompt in bedrock
        created_prompt = BEDROCK_AGENT_CLIENT.create_prompt(
            name=f"{item.get('session_id')}",
            variants=[
                {
                    "name": "variant-001",
                    "modelId": MODEL_ID,
                    "templateType": "TEXT",
                    "inferenceConfiguration": {
                        "text": {
                            "temperature": float(item.get("temperature")),
                            "maxTokens": int(item.get("answer_length")),
                        }
                    },
                    "templateConfiguration": {
                        "text": {
                            "text": item.get("Prompt Template")
                        }
                    }
                }
            ],
            defaultVariant="variant-001"
        )
        prompt_id = created_prompt.get("id")
        # Create a version
        versioned_prompt = BEDROCK_AGENT_CLIENT.create_prompt_version(
            promptIdentifier=prompt_id
        )

        # Construct the item data as a dictionary
        item_data = {
            "user_id": {"S": item.get("user_id")},
            "prompt_id": {"S": prompt_id},
            "prompt_version": {"S": versioned_prompt.get("version")},
            "prompt": {"S": item.get("Prompt")},
            "output": {"S": item.get("Output")}
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

        user_id = filter_params.get("user_id")
        ai_model_filter = filter_params.get("ai_model_filter")
        MODEL_ID = MODELS_MAPPING[ai_model_filter]
        LOGGER.info(f"user_id: {user_id}, ai_model_filter: {MODEL_ID}")

        try:
            # query all items from dynamodb using the user_id partition
            response = dynamodb.query(
                TableName=table_name,
                KeyConditionExpression="user_id = :user_id",
                ExpressionAttributeValues={
                    ":user_id": {"S": user_id}
                }
            )

            items = response.get("Items")
            LOGGER.info(f"Retrieved {len(items)} items")
            LOGGER.info(f"Items {items}")

            # iterate through prompt_ids, user_ids, prompt_versions to get the prompts and put them in a json object
            prompts = []
            for item in items:
                # get the prompt from bedrock agent using the prompt_id and version
                prompt_id = item.get("prompt_id").get("S")
                prompt_version = item.get("prompt_version").get("S")
                bedrock_prompt_catalog = BEDROCK_AGENT_CLIENT.get_prompt(
                    promptIdentifier=prompt_id, promptVersion=prompt_version)
                LOGGER.info(
                    f"bedrock_prompt_catalog: {json.dumps(bedrock_prompt_catalog, indent=4, sort_keys=True, default=str)}")
                defaultVariants = [variant for variant in bedrock_prompt_catalog['variants'] if variant["name"]
                                   == bedrock_prompt_catalog["defaultVariant"] and variant["modelId"] == MODEL_ID]
                # when array is 0 continue to next else extract default variant
                if len(defaultVariants) == 0:
                    continue
                defaultVariant = defaultVariants[0]
                prompt_template_string = defaultVariant['templateConfiguration']['text']['text']
                prompts.append({
                    "Prompt Template": prompt_template_string,
                    "Prompt": item.get("prompt").get("S"),
                    "Output": item.get("output").get("S"),
                    "model": ai_model_filter,
                    "answer_length": defaultVariant['inferenceConfiguration']['text']['maxTokens'],
                    "temperature": defaultVariant['inferenceConfiguration']['text']['temperature'],
                })

            LOGGER.info(
                f"bedrock_prompt: {json.dumps(prompts)}")
            # Return items in response
            return {"statusCode": 200, "body": json.dumps(prompts)}
        except Exception as e:
            LOGGER.error(f"Error retrieving items: {e}")
            return {"statusCode": 500, "body": json.dumps(f"Error retrieving items from DynamoDB: {str(e)}")}

    elif payload_type == "DELETE":
        # Extract the 'session_id' from the body
        print("made it into the delete section! ")
        user_id = body["item"]["user_id"]
        prompt_id = body["item"]["prompt_id"]
        prompt_version = body["item"]["prompt_version"]

        if not user_id:
            LOGGER.error("user_id is required for DELETE operation")
            return {"statusCode": 400, "body": json.dumps("user_id is required for DELETE operation")}

        try:
            bedrock_prompt_catalog = BEDROCK_AGENT_CLIENT.delete_prompt_version(
                promptId=prompt_id,
                version=prompt_version
            )
            dynamodb_response = dynamodb.delete_item(
                TableName=table_name,
                # "S" indicates that the datatype is a string.
                Key={"user_id": {"S": user_id}, "prompt_id": {"S": prompt_id}},
            )

            LOGGER.info(
                f"Deleted item with user_id: {user_id} and prompt_id {prompt_id}")

            return {"statusCode": 200, "body": json.dumps(f"Item with user_id {user_id} and prompt_id {prompt_id} successfully deleted")}
        except Exception as e:
            LOGGER.error(f"Error deleting item: {e}")
            return {"statusCode": 500, "body": json.dumps(f"Error deleting item from DynamoDB: {str(e)}")}

    else:
        return {"statusCode": 400, "body": json.dumps("Invalid payload type")}
