"""
Helper classes for LLM inference
"""

#########################
#    IMPORTS & LOGGER
#########################

from __future__ import annotations
import os

import requests

#########################
#      CONSTANTS
#########################

API_URI = os.environ.get("API_URI")

WS_SSL = (os.environ.get("WS_SSL", "True")) == "True"

#########################
#    HELPER FUNCTIONS
#########################


def sns_topic_publish(
    subject: str,
    message: str,
    access_token: str,
) -> dict:
    params = {"subject": subject, "message": message, "type": "PUBLISH"}

    try:
        response = requests.post(
            url=API_URI + "/sns/put",
            json=params,
            stream=False,
            headers={"Authorization": access_token},
            timeout=10,
        )
        response = response
        return True, response
    except requests.RequestException as e:
        raise ValueError(f"Error making request to SNS API: {str(e)}")


def sns_topic_subscribe_email(
    email: str,
    access_token: str,
) -> dict:
    params = {"email": email, "type": "SUBSCRIBE"}

    try:
        response = requests.post(
            url=API_URI + "/sns/put",
            json=params,
            stream=False,
            headers={"Authorization": access_token},
            timeout=20,
        )
        print(f"REPONSE: {response}")
        success = response.ok
        return success, response
    except requests.RequestException as e:
        raise ValueError(f"Error making request to SNS API: {str(e)}")
