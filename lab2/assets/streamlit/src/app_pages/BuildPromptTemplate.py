"""
Build Prompt Template Page
"""

#########################
#    IMPORTS & LOGGER
#########################
import logging
import os
import sys
from pathlib import Path
import boto3
import re

from datetime import datetime

# import dynamodb_json as djson

import streamlit as st
from st_pages import show_pages_from_config
from streamlit_extras.switch_page_button import switch_page

path = Path(os.path.dirname(__file__))
sys.path.append(str(path.parent.parent.parent.absolute()))

import components.authenticate as authenticate  # noqa: E402
import components.genai_api as genai_api  # noqa: E402
from components.utils import (
    display_cover_with_title,
    reset_session_state,
    set_page_styling,
    get_product_info,
    display_product_info,
)  # noqa: E402
from components.utils_models import get_models_specs  # noqa: E402
from components.utils_models import BEDROCK_MODELS
from components.utils import TASKS, TECHNIQUES, LANGUAGES, INDUSTRIES, add_logo

LOGGER = logging.Logger("Q&A", level=logging.DEBUG)
HANDLER = logging.StreamHandler(sys.stdout)
HANDLER.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
LOGGER.addHandler(HANDLER)


#########################
#     COVER & CONFIG
#########################


# titles
COVER_IMAGE = os.environ.get("COVER_IMAGE_URL")
TITLE = "Build Prompt Template"
DESCRIPTION = "Build your own prompt template to generate marketing emails."
PAGE_TITLE = "Build Prompt Template"
PAGE_ICON = ":robot:"
REGION = os.environ.get("REGION")
# page config
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="centered",
    initial_sidebar_state="expanded",
)

# page width, form borders, message styling
style_placeholder = st.empty()
with style_placeholder:
    set_page_styling()

# display cover immediately so that it does not pop in and out on every page refresh
cover_placeholder = st.empty()
with cover_placeholder:
    display_cover_with_title(
        title=TITLE,
        description=DESCRIPTION,
        image_url=COVER_IMAGE,
        max_width="100%",
    )

# custom page names in the sidebar
show_pages_from_config()

add_logo()


#########################
#  CHECK LOGIN (do not delete)
#########################

# switch to home page if not authenticated
authenticate.set_st_state_vars()
if not st.session_state["authenticated"]:
    switch_page("Home")


#########################
#       CONSTANTS
#########################

# page name for caching
PAGE_NAME = "run_prompt"

SM_ENDPOINTS = {}  # json.loads(os.environ.get("SM_ENDPOINTS"))
MODELS_DISPLAYED, MODEL_SPECS = get_models_specs(path=path)
# MODELS_DISPLAYED, MODEL_SPECS = get_models_specs({}, path=path)

#########################
# SESSION STATE VARIABLES
#########################

reset_session_state(page_name=PAGE_NAME)

st.session_state.setdefault("ai_model", MODELS_DISPLAYED[0])  # default model
LOGGER.log(logging.DEBUG, (f"ai_model selected: {st.session_state['ai_model']}"))

st.session_state.setdefault("query", "")


#########################
#    HELPER FUNCTIONS
#########################
def generate_session_id(user_id: str = "AWS") -> None:
    """
    Generates unique chat id based on user name and timestamp
    """
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    session_id = f"{user_id}-{timestamp}"
    st.session_state["session_id"] = session_id
    LOGGER.log(logging.DEBUG, (f"session_id: {session_id}"))
    return session_id, timestamp


def format_prompt(prompt: str) -> str:
    """
    Replaces input parameter in prompt string with actual user values and product information.
    """
    LOGGER.debug("INSIDE format_prompt()")
    # Remove dots inside curly braces but keep dots outside.
    prompt_cleaned = re.sub(r"\{(.*?)\}", lambda x: x.group(0).replace(".", ""), prompt)
    LOGGER.debug(f"PROMPT TEMPLATE: {prompt_cleaned}")
    # Convert DataFrame to Series to Dictionary
    user_attributes_dict = st.session_state["df_selected"].squeeze().to_dict()
    # Remove dots inside dictionary keys
    user_attributes_cleaned = {
        key.replace(".", ""): value for key, value in user_attributes_dict.items()
    }
    product_info_cleaned = {
        key.replace("Name", "Product"): value
        for key, value in st.session_state["product_info"].items()
    }
    product_info_cleaned = {
        key.replace("Title", "Campaign Phrase"): value
        for key, value in product_info_cleaned.items()
    }

    prompt_formatted = ""
    try:
        prompt_formatted = prompt_cleaned.format(
            **user_attributes_cleaned, **product_info_cleaned
        )
    except KeyError as e:
        LOGGER.error(f"Invalid input parameter in prompt: {e}")
        st.error(f"Invalid input parameter in prompt: {e}")
    LOGGER.debug(f"PROMPT FORMATTED: {prompt_formatted}")
    return prompt_formatted


def run_genai_prompt(ai_model, prompt, answer_length=4096, temperature=0) -> str:
    """
    Runs API call to retrieve LLM answer and references
    """
    with st.spinner("Generating content..."):
        prompt_formatted = format_prompt(prompt)
        content = ""
        if prompt_formatted != "":
            content = genai_api.invoke_content_creation(
                prompt=prompt_formatted,
                model_id=ai_model,
                access_token=st.session_state["access_token"],
                answer_length=answer_length,
                temperature=temperature,
            )
        return content


def put_prompt(item) -> None:
    """
    Runs API call to retrieve LLM answer and references
    """
    with st.spinner("Saving prompt template..."):
        success = genai_api.invoke_dynamo_put(
            item=item,
            access_token=st.session_state["access_token"],
        )

    return success


#########################
#        SIDEBAR
#########################

# sidebar
with st.sidebar:
    st.header("Prompt Settings")

    ai_model = st.selectbox(
        label="Language model:",
        options=MODELS_DISPLAYED,
        format_func=lambda x: "Sagemaker: " + x if not x.startswith("Bedrock:") else x,
        key="ai_model",
        help="The search app provides flexibility to choose a large language model used for AI answers.",
    )

    answer_length = st.slider(
        label="Max answer length:",
        value=MODEL_SPECS[st.session_state["ai_model"]]["ANSWER_LENGTH_DEFAULT"],
        min_value=10,
        max_value=4000,
        key="answer_length",
    )
    temperature = st.slider(
        label="Temperature:",
        value=MODEL_SPECS[st.session_state["ai_model"]]["TEMPERATURE_DEFAULT"],
        min_value=0.0,
        max_value=1.0,
        key="temperature",
    )

    with st.expander("Read more"):
        st.markdown(
            """
- **Max answer length**: maximum number of characters in the generated answer. Longer answers are more descriptive, but may require more time to be generated.
- **Temperature**: temperature controls model creativity. Higher values results in more creative answers, while lower values make them more deterministic."""
        )


#########################
#      MAIN APP PAGE
#########################

# chat history
# st.markdown("Selected User:")


if (
    "df_selected" not in st.session_state
    or st.session_state["df_selected"].shape[0] == 0
):
    st.error("Please select a user on the 'Customer List' page first")
    if st.button("Go to Customer List"):
        switch_page("Customer List")

else:
    st.markdown(
        """
        This is your selected user from **Customer List** page. You can find different user attributes in the table displayed below. 
        """
    )

    st.data_editor(
        st.session_state["df_selected"],
        hide_index=True,
        disabled=st.session_state["df_selected"].columns,
        height=84,
        use_container_width=True,
    )
    st.markdown(
        "Based on the selected user, here is the recommended product to be promoted. "
    )

    with st.expander("### Product Details", expanded=False):
        # todo: make it compatible with other available user-data i.e. personalized with ItemId
        # show default product
        product_info = get_product_info(
            st.session_state.df_selected["User.UserAttributes.Product"].item()
        )
        st.session_state["product_info"] = product_info
        display_product_info(product_info)

    prompt_col, output_col = st.columns(2, gap="small")
    model_output = ""

    with prompt_col:
        prompt_area = st.text_area(
            "Your Prompt Template",
            key="prompt",
            height=400,
        )

        _, col1 = st.columns([3, 1], gap="small")
        with col1:
            run_button = st.button("Run Prompt")
        if run_button:
            model_output = run_genai_prompt(
                ai_model=ai_model,
                prompt=prompt_area,
                answer_length=answer_length,
                temperature=temperature,
            )
            st.session_state["model_output"] = model_output

    with output_col:
        model_output = st.text_area(
            "Model Output ", model_output, key="generated_content", height=400
        )
        _, col = st.columns([3, 2], gap="large")
        with col:
            save_button = st.button(
                "Save to Catalog",
                key="save",
                help="Save this prompt template to the catalog",
            )
        if save_button:
            user_id = st.session_state["user_id"]

            session_id, timestamp = generate_session_id(user_id=user_id)
            session_id = st.session_state["session_id"]
            if st.session_state["ai_model"] != "Bedrock: LLama2":
                model_output = st.session_state["model_output"]
            else:
                model_output = prompt_area
            item = {
                "session_id": session_id,
                "user_id": user_id,
                "timestamp": str(timestamp),
                "model": ai_model,
                "answer_length": str(answer_length),
                "temperature": str(temperature),
                # "Language": language,     #TODO - AFTER REINVENT - UNCOMMENT
                # "Industry": industry,
                # "Task": task,
                # "Technique": technique,
                "Prompt Template": prompt_area,
                "Prompt": format_prompt(prompt_area),
                "Output": model_output,
            }

            success = put_prompt(item=item)
            print(success)

            if success:
                st.success("Prompt saved to the catalog successfully.")
            else:
                st.error("Failed to save prompt.")

    st.markdown(
        "If you like the output, save the prompt to the catalog which is ready to be applied for more customers in further steps."
    )
    with st.expander("Show Logs for the Bedrock invocation!"):
        regions = ["us-west-2", "us-east-1"]
        selected_region = st.selectbox("Select Region", regions)
        st.markdown(
            f"""
            To see the logs for the prompt, click on the link below:
            [Cloudwatch Logs](https://console.aws.amazon.com/cloudwatch/home#logsV2:log-groups/log-group/$252Faws$252Flambda$252FbdrkWorkshop-bedrock-content-generation-lambda/)
            """
        )

    st.session_state["model_output"] = model_output

#########################
#        FOOTNOTE
#########################

# footnote
st.markdown("---")
footer_col1, footer_col2 = st.columns(2)

# log out button
with footer_col1:
    if st.button("Sign out"):
        authenticate.sign_out()
        st.experimental_rerun()

# copyright
with footer_col2:
    st.markdown(
        "<div style='text-align: right'> © 2023 Amazon Web Services </div>",
        unsafe_allow_html=True,
    )
