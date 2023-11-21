
"""
Lambda that performs summarization with Bedrock
"""

#########################
#   LIBRARIES & LOGGER
#########################
import os
import json
import logging
import sys

import boto3

LOGGER = logging.Logger("SNS TOPIC LAMBDA", level=logging.DEBUG)
HANDLER = logging.StreamHandler(sys.stdout)
HANDLER.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
LOGGER.addHandler(HANDLER)


#########################
#        HANDLER
#########################


def lambda_handler(event, context):
    topic_arn = os.environ["SNS_TOPIC_ARN"]
    body = json.loads(event["body"])
    client = boto3.client("sns")
    if body["type"] == "PUBLISH":
        LOGGER.info(f"Publishing to topic: {topic_arn}")
        client.publish(TopicArn=topic_arn, Message=body["message"], Subject=body["subject"])
    elif body["type"] == "SUBSCRIBE":
        # check if subscription already exists
        subs = client.list_subscriptions_by_topic(TopicArn=topic_arn)
        for sub in subs["Subscriptions"]:
            if sub["Endpoint"] == body["email"]:
                LOGGER.info(f"Subscription already exists for {body['email']}")
                return {'statusCode': 200}
        # Else subscribe email to topic
        LOGGER.info(f"Subscribing to topic: {topic_arn}")
        client.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=body["email"])
    else:
        LOGGER.error(f"Invalid request type: {body['type']}")
        LOGGER.error("Valid request types: PUBLISH, SUBSCRIBE")
        return {'statusCode': 400}
    return {'statusCode': 200}
