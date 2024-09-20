"""
Lambda that performs email content generation with Bedrock
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
from botocore.config import Config

LOGGER = logging.Logger("Content-generation", level=logging.DEBUG)
HANDLER = logging.StreamHandler(sys.stdout)
HANDLER.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
LOGGER.addHandler(HANDLER)


#########################
#        HELPER
#########################
BEDROCK_ROLE_ARN = os.environ["BEDROCK_ROLE_ARN"]
BEDROCK_CONFIG = Config(connect_timeout=60, read_timeout=60, retries={"max_attempts": 10})

MODELS_MAPPING = {
    "Bedrock: Amazon Titan": "amazon.titan-text-express-v1",
    "Bedrock: Claude V2": "anthropic.claude-v2",
    "Bedrock: Claude 3 Sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
}


def create_bedrock_client():
    """
    Creates a Bedrock client using the specified region and configuration.

    Returns:
        A tuple containing the Bedrock client and the expiration time (which is None).
    """
    LOGGER.info("Using bedrock client from same account.")
    bedrock_client = boto3.client(
        service_name="bedrock-runtime",
        region_name=os.environ["BEDROCK_REGION"],
        config=BEDROCK_CONFIG,
    )
    expiration = None
    LOGGER.info("Successfully set bedrock client")

    return bedrock_client, expiration


BEDROCK_CLIENT, EXPIRATION = create_bedrock_client()


def verify_bedrock_client():
    """
    Verifies the Bedrock client by checking if the token has expired or not.

    Returns:
        bool: True if the Bedrock client is verified, False otherwise.
    """
    if EXPIRATION is not None:
        now = datetime.now(timezone.utc)
        LOGGER.info(f"Bedrock token expires in {(EXPIRATION - now).total_seconds()}s")
        if (EXPIRATION - now).total_seconds() < 60:
            return False
    return True


def invoke_bedrock_model(client, id, prompt, max_tokens=2000, temperature=0, top_p=0.9):
    response = ""
    try:
        response = client.converse(
            modelId=id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": temperature, "maxTokens": max_tokens, "topP": top_p},
            # additionalModelRequestFields={
            # }
        )
    except Exception as e:
        print(e)
        result = "Model invocation error"
    try:
        result = (
            response["output"]["message"]["content"][0]["text"]
            + "\n--- Latency: "
            + str(response["metrics"]["latencyMs"])
            + "ms - Input tokens:"
            + str(response["usage"]["inputTokens"])
            + " - Output tokens:"
            + str(response["usage"]["outputTokens"])
            + " ---\n"
        )
        return result
    except Exception as e:
        print(e)
        result = "Output parsing error"
    return result


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
    body_data = json.loads(event["body"])

    # Extract the 'query' value
    query_value = body_data["query"]

    # Extract the 'model_params' value
    model_params_value = body_data["model_params"]
    max_tokens = model_params_value["answer_length"]
    temperature = model_params_value["temperature"]

    # get model id but check if the model is available in the mapping
    model_id = model_params_value["model_id"]
    if model_id not in MODELS_MAPPING:
        return {
            "statusCode": 400,
            "body": json.dumps("Invalid model ID"),
        }
    MODEL_ID = MODELS_MAPPING[model_params_value["model_id"]]
    LOGGER.info(f"MODEL_ID: {MODEL_ID}")

    if not verify_bedrock_client():
        LOGGER.info("Bedrock client expired, will refresh token.")
        global BEDROCK_CLIENT, EXPIRATION
        BEDROCK_CLIENT, EXPIRATION = create_bedrock_client()

    response = invoke_bedrock_model(BEDROCK_CLIENT, MODEL_ID, query_value, max_tokens, temperature)

    return json.dumps(response)
