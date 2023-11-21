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

    # get fixed model params
    MODEL_ID = MODELS_MAPPING[model_params_value["model_id"]]
    LOGGER.info(f"MODEL_ID: {MODEL_ID}")

    with open(f"model_configs/{MODEL_ID}.json") as f:
        fixed_params = json.load(f)

    # load variable model params
    amazon_flag = False
    model_params = {}
    if MODEL_ID.startswith("amazon"):
        model_params = {
            "maxTokenCount": model_params_value["answer_length"],
            "stopSequences": fixed_params["STOP_WORDS"],
            "temperature": model_params_value["temperature"],
            "topP": fixed_params["TOP_P"],
        }
        amazon_flag = True
    elif MODEL_ID.startswith("anthropic"):
        model_params = {
            "max_tokens_to_sample": model_params_value["answer_length"],
            "temperature": model_params_value["temperature"],
            "top_p": fixed_params["TOP_P"],
            "stop_sequences": fixed_params["STOP_WORDS"],
        }
        query_value = f"\n\nHuman:{query_value}\n\nAssistant:"

    LOGGER.info(f"MODEL_PARAMS: {model_params}")

    if not verify_bedrock_client():
        LOGGER.info("Bedrock client expired, will refresh token.")
        global BEDROCK_CLIENT, EXPIRATION
        BEDROCK_CLIENT, EXPIRATION = create_bedrock_client()

    accept = "application/json"
    contentType = "application/json"

    if amazon_flag == True:
        input_data = json.dumps(
            {
                "inputText": query_value,
                "textGenerationConfig": model_params,
            }
        )
        print(input_data)
        response = BEDROCK_CLIENT.invoke_model(
            body=input_data, modelId=MODEL_ID, accept=accept, contentType=contentType
        )

    else:
        body = json.dumps({"prompt": query_value, **model_params})
        response = BEDROCK_CLIENT.invoke_model(body=body, modelId=MODEL_ID, accept=accept, contentType=contentType)

    response_body = json.loads(response.get("body").read())

    if "amazon" in MODEL_ID:
        response = response_body.get("results")[0].get("outputText")
    elif "anthropic" in MODEL_ID:
        response = response_body.get("completion")
    else:
        LOGGER.info("Unknown model type!")
    print("Responese: ", response)

    return json.dumps(response)
