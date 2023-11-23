"""
Helper classes for LLM inference
"""

#########################
#    IMPORTS & LOGGER
#########################

from __future__ import annotations

import json
import os
from typing import Callable

import requests

#########################
#      CONSTANTS
#########################

API_URI = os.environ.get("API_URI")

# DEFAULT_NEGATIVE_ANSWER_QUESTION = "Could not answer based on the provided documents. Please rephrase your question, reduce the relevance threshold, or ask another question."  # noqa: E501
# DEFAULT_NEGATIVE_ANSWER_SUMMARY = "Could not summarize the document."  # noqa: E501
# WS_SSL = (os.environ.get("WS_SSL", "True")) == "True"

#########################
#    HELPER FUNCTIONS
#########################


def invoke_content_creation(
    prompt: str,
    model_id: int,
    access_token: str,
    answer_length: int = 4096,
    temperature: float = 0.0,
) -> str:
    """
    Run LLM to generate content via API
    """

    params = {
        "query": prompt,
        "type": "content_generation",
        "model_params": {
            "model_id": model_id,
            "answer_length": answer_length,
            "temperature": temperature,
        },
    }
    try:
        response = requests.post(
            url=API_URI + "/content/bedrock",
            json=params,
            stream=False,
            headers={"Authorization": access_token},
            timeout=60,  # add a timeout parameter of 10 seconds
        )
        print(response)
        # response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code
        response = json.loads(response.text)
        return response
    except requests.RequestException as e:
        # Handle exception as needed
        raise ValueError(f"Error making request to LLM API: {str(e)}")


def invoke_dynamo_put(
    item: dict,
    access_token: str,
) -> str:
    """
    Put the json item into DynamoDB via an API endpoint.
    """

    data = {
        "item": item,
        "type": "PUT",
    }

    headers = {"Authorization": access_token}

    try:
        response = requests.post(
            url=API_URI + "/dynamo/put",
            json=data,  # Use json=data to send as JSON payload
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code
        return response.json()
    except requests.RequestException as e:
        # Handle exception as needed
        raise ValueError(f"Error making request to Dynamo API: {str(e)}")

    except json.JSONDecodeError:
        # Handle JSON parsing exception as needed
        raise ValueError("Received a non-JSON response from the server.")


def invoke_dynamo_get(
    params: dict,
    access_token: str,
) -> str:
    """
    Get the elements from DynamoDB via an API endpoint.
    """

    data = {
        "filter_params": params,
        "type": "GET",
    }

    headers = {"Authorization": access_token}

    try:
        response = requests.get(
            url=API_URI + "/dynamo/get", json=data, headers=headers, timeout=10
        )
        response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code
        return response
    except requests.RequestException as e:
        # Handle exception as needed
        raise ValueError(f"Error making request to Dynamo API: {str(e)}")


def invoke_dynamo_delete(
    params: dict,
    access_token: str,
) -> dict:
    """
    Delete the specified elements from DynamoDB via an API endpoint.
    """
    print("invoke_dynamo_delete")
    print(params["session_id"], type(params))
    data = {
        "item": params,
        "type": "DELETE",
    }

    headers = {"Authorization": access_token}

    try:
        response = requests.delete(
            url=f"{API_URI}/dynamo/delete", json=data, headers=headers, timeout=10
        )
        response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code
        return response
    except requests.RequestException as e:
        # Handle exception as needed
        raise ValueError(f"Error making request to Dynamo API: {str(e)}")
