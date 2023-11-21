import streamlit as st
import pandas as pd
import os
import sys
import re
import json
from pathlib import Path
from st_pages import show_pages_from_config
from components.utils import (
    display_cover_with_title,
    reset_session_state,
    add_logo,
    get_product_info,
    display_product_info,
)
import components.authenticate as authenticate  # noqa: E402
import components.genai_api as genai_api  # noqa: E402
import components.sns_api as sns_api

import logging
from streamlit_extras.switch_page_button import switch_page

# import s3fs

from components.utils_models import BEDROCK_MODELS


LOGGER = logging.Logger("AI-Chat", level=logging.DEBUG)
HANDLER = logging.StreamHandler(sys.stdout)
HANDLER.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
LOGGER.addHandler(HANDLER)

path = Path(os.path.dirname(__file__))
sys.path.append(str(path.parent.parent.absolute()))


#########################
#     COVER & CONFIG
#########################

# titles
COVER_IMAGE = os.environ.get("COVER_IMAGE_URL")
TITLE = "Email Generation Wizard"
DESCRIPTION = "Generate customized marketing emails."
PAGE_TITLE = "Email Generation Wizard"
PAGE_ICON = "🧙🏻‍♀️"

# page config
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="centered",
    initial_sidebar_state="expanded",
)

# display cover immediately so that it does not pop in and out on every page refresh
cover_placeholder = st.empty()
with cover_placeholder:
    display_cover_with_title(
        title=TITLE,
        description=DESCRIPTION,
        image_url=COVER_IMAGE,
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
PAGE_NAME = "marketing_generator"

# default model specs
with open(f"{path.parent.absolute()}/components/bedrock_model_specs.json") as f:
    MODEL_SPECS = json.load(f)

# Hardcoded lists of available and non available models.
# If you want to add new available models make sure to update those lists as well as model_specs dict
MODELS_DISPLAYED = BEDROCK_MODELS
MODELS_UNAVAILABLE = [
    "LLAMA 2",
    "Falcon",
    "Flan T5",
]  # Models that are not available for deployment
MODELS_NOT_DEPLOYED = []  # Remove models from this list after deploying the models

BUCKET_NAME = os.environ.get("BUCKET_NAME")

#########################
# SESSION STATE VARIABLES
#########################

reset_session_state(page_name=PAGE_NAME)
st.session_state.setdefault("ai_model", MODELS_DISPLAYED[0])  # default model
# if "ai_model" not in st.session_state:
#     st.session_state["ai_model"] = MODELS_DISPLAYED[0]  # default model
st.session_state.setdefault("prompt_template", "")  # default prompt template
st.session_state.setdefault(
    "prompt_formatted", {}
)  # formatted prompt for each customer
st.session_state.setdefault("model_output", {})  # model output for each customer

if "df_selected_prompt" in st.session_state:
    st.session_state["ai_model"] = st.session_state["df_selected_prompt"].model.iloc[0]
    st.session_state["answer_length"] = int(
        st.session_state["df_selected_prompt"].answer_length.iloc[0]
    )
    st.session_state["temperature"] = float(
        st.session_state["df_selected_prompt"].temperature.iloc[0]
    )
    st.session_state["prompt_template"] = st.session_state["df_selected_prompt"][
        "Prompt Template"
    ].iloc[0]

LOGGER.log(logging.DEBUG, (f"ai_model selected: {st.session_state['ai_model']}"))
LOGGER.log(
    logging.DEBUG, (f"Selected Prompt Template: {st.session_state['prompt_template']}")
)

# Initialize session state
if "prompt" not in st.session_state:
    # If no prompt found, use the banking prompt
    st.session_state.prompt = """<INST>You are an marketing content creator assistant for First National Bank, a respectable financial institution with a reputation for being trustworthy and factual. 
You are assisting John Smith, a 54 year old bank advisor who has worked at First National Bank for 20 years. 
 
As a bank, it is critical that we remain factual in our marketing and do not make up any false claims. \n\nPlease write a {channel} marketing message to promote our new product to {name}. 

The goal is to highlight the key features and benefits of the product in a way that resonates with customers like {name}, who is {age} years old. 

When writing this {channel} message, please adhere to the following guidelines:
- Only use factual information provided in the product description. Do not make up any additional features or benefits.
- Emphasize how the product can help meet the typical financial needs of customers like {name}, based on their age demographic. 
- Use a warm, helpful tone that builds trust and demonstrates how First National Bank can assist customers like {name}.
- If unable to compose a factual {channel} message for {name}, indicate that more information is needed.
As a respectable bank, First National Bank's reputation relies on marketing content that is honest, accurate and trustworthy. Please ensure the {channel} message aligns with our brand identity. Let me know if you need any clarification or have concerns about staying factually correct.\n</INST>\n
         """

########################################################################################################################################################################
######################################################## Session States and CSS      ###################################################################################
########################################################################################################################################################################

if "df" not in st.session_state or st.session_state["df"] is None:
    st.session_state["df"] = None
    st.session_state["df_name"] = None
    df = st.session_state["df"]
else:
    df = st.session_state["df"]

# Initialize session state if not already done
if "button_clicked" not in st.session_state:
    st.session_state.button_clicked = False

# define what option labels and icons to display
option_data = [
    {"icon": "bi bi-hand-thumbs-up", "label": "Agree", "color": "green"},
    {"icon": "fa fa-question-circle", "label": "Unsure"},
    {"icon": "bi bi-hand-thumbs-down", "label": "Disagree"},
]

# Define the style of the box element
box_style = {
    "border": "1px solid #ccc",
    "padding": "10px",
    "border-radius": "5px",
    "margin": "10px",
}


########################################################################################################################################################################
######################################################## Functions    ##################################################################################################
########################################################################################################################################################################


def format_prompt_template(prompt_template, product_info, customer_details) -> str:
    """
    Replaces input parameter in prompt string with actual user values and product information.
    """
    LOGGER.debug("INSIDE format_prompt()")
    # Remove dots inside curly braces but keep dots outside.
    prompt_cleaned = re.sub(
        r"\{(.*?)\}", lambda x: x.group(0).replace(".", ""), prompt_template
    )
    LOGGER.debug(f"PROMPT TEMPLATE: {prompt_cleaned}")
    # Convert DataFrame to Series to Dictionary
    user_attributes_dict = customer_details.squeeze().to_dict()
    # Remove dots inside dictionary keys
    user_attributes_cleaned = {
        key.replace(".", ""): value for key, value in user_attributes_dict.items()
    }
    # LOGGER.debug(f"USER ATTRIBUTES: {user_attributes_cleaned}")
    # LOGGER.debug(f"PRODUCT INFO: {st.session_state['product_info']}")
    # Fix product info keys as displayed
    product_info_cleaned = {
        key.replace("Name", "Product"): value for key, value in product_info.items()
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


def generate_marketing_email() -> str:
    """
    Runs API call to retrieve LLM answer and references
    """
    with st.spinner("Generating content..."):
        if not st.session_state["prompt_formatted"].get(
            st.session_state["customer_counter"]
        ):
            st.session_state["prompt_formatted"][
                st.session_state["customer_counter"]
            ] = format_prompt_template(
                st.session_state["prompt_template"],
                st.session_state["product_info"],
                st.session_state["customer_details"],
            )
        content = ""
        if st.session_state["prompt_formatted"].get(
            st.session_state["customer_counter"]
        ):
            content = genai_api.invoke_content_creation(
                prompt=st.session_state["prompt_formatted"][
                    st.session_state["customer_counter"]
                ],
                model_id=st.session_state["ai_model"],
                access_token=st.session_state["access_token"],
                answer_length=st.session_state["answer_length"],
                temperature=st.session_state["temperature"],
            )
        st.session_state["model_output"][st.session_state["customer_counter"]] = content
        return content


# Convert attributes that are lists based on their content
def convert_value(val):
    if isinstance(val, list) and val:  # Check if it's a non-empty list
        item = val[0]
        try:
            # Convert to int if possible
            return int(item)
        except ValueError:
            pass  # Continue to the next check

        try:
            # Convert to float if possible
            return float(item)
        except ValueError:
            pass  # Continue to the next check

        # If none of the above, return as string
        return str(item)

    elif isinstance(val, list) and not val:  # Handle empty lists
        return None

    return val


def process_df(df):
    """
    Process the received df
    """

    # Convert attributes that are lists to strings
    df = df.applymap(convert_value)
    # Group the user attributes, attributes and metrics columns
    user_attribute_columns = [
        col for col in df.columns if col.startswith("User.UserAttributes.")
    ]
    attribute_columns = [col for col in df.columns if col.startswith("Attributes.")]
    metric_columns = [col for col in df.columns if col.startswith("Metrics.")]
    other_columns = [
        col
        for col in df.columns
        if col not in user_attribute_columns + attribute_columns + metric_columns
    ]
    # Start with an empty list for the ordered columns
    ordered_columns = []

    # Check if 'FirstName' and 'LastName' columns are present and add them first
    if "User.UserAttributes.FirstName" in df.columns:
        ordered_columns.append("User.UserAttributes.FirstName")
        user_attribute_columns.remove("User.UserAttributes.FirstName")

    if "User.UserAttributes.LastName" in df.columns:
        ordered_columns.append("User.UserAttributes.LastName")
        user_attribute_columns.remove("User.UserAttributes.LastName")

    # Concatenate the lists in the desired order
    ordered_columns += (
        user_attribute_columns + attribute_columns + metric_columns + other_columns
    )

    # Reorder the DataFrame columns
    df = df[ordered_columns]

    return df, user_attribute_columns, attribute_columns, metric_columns, other_columns


def send_message_sns() -> None:
    """
    Send a marketing mail
    """
    LOGGER.log(logging.DEBUG, ("Inside send_email()"))

    subject = st.session_state.get("message_subject_alt", "")
    body_text = st.session_state.get("message_body_text_alt", "")

    if subject != "" and body_text != "":
        send_success, message = sns_api.sns_topic_publish(
            subject=subject,
            message=body_text,
            access_token=st.session_state["access_token"],
        )
        if not send_success:
            st.session_state["error_message"] = message
        else:
            st.session_state.pop("error_message", None)
    else:
        st.session_state[
            "error_message"
        ] = "Error sending message. Message or Subject is missing."


def extract_content(text_area):
    """
    Extract content generated by AI
    """
    # print("text_area", text_area)
    # if channel is not "EMAIL":
    #     return None, text_area
    try:
        # Extracting the content for each part
        message_subject = None
        if "###SUBJECT###" in text_area:
            message_subject = (
                text_area.split("###SUBJECT###")[1].split("###END###")[0].strip()
            )

        message_body_text = (
            text_area.split("###TEXTBODY###")[1].split("###END###")[0].strip()
        )

        return message_subject, message_body_text

    except IndexError:
        # If the format is not properly parsed, raise an error in Streamlit
        st.error(
            f"The provided content does not follow the expected format. Please check the 'Prompt Details' below."
        )
        return None, None
    except AttributeError:
        # Catching AttributeError: 'dict' object has no attribute 'split'
        st.error(
            f"The provided content does not follow the expected format. Please check the 'Prompt Details' below."
        )
        return None, None


def increment_counter():
    """
    Increment Customer Counter
    """
    st.session_state["customer_counter"] = min(
        len(df) - 1, st.session_state["customer_counter"] + 1
    )


def set_button_clicked():
    """
    Set button as clicked and send out content
    """
    # Send Content to Amazon SNS
    send_message_sns()
    st.session_state.button_clicked = True


########################################################################################################################################################################
######################################################## PAGE CODE    ##################################################################################################
########################################################################################################################################################################

if df is None:
    df = pd.read_csv(f"{path.parent.absolute()}/data/df_segment_data.csv")
    st.session_state["df_name"] = "df_segment_data"
    st.session_state["df"] = df

else:
    #########################
    #       SIDEBAR MODEL SELECTION
    #########################
    with st.sidebar:
        st.header("Prompt Settings")
        # language model
        st.markdown("Language model:")
        st.code(st.session_state["ai_model"], language="text")

        st.markdown(f"Max answer length: {st.session_state.get('answer_length','')}")
        st.markdown(f"Temperature: {st.session_state.get('temperature', '')}")

        if st.session_state["ai_model"] in MODELS_UNAVAILABLE:
            st.error(f'{st.session_state["ai_model"]} not available', icon="⚠️")
            st.stop()
        elif st.session_state["ai_model"] in MODELS_NOT_DEPLOYED:
            st.error(f'{st.session_state["ai_model"]} has been shut down', icon="⚠️")
            st.stop()

    #########################
    #       NAVIGATION
    #########################

    st.write("")
    if "customer_counter" not in st.session_state:
        st.session_state["customer_counter"] = 0

    _, col2, col3, col4, _ = st.columns([1, 1, 1, 1, 1], gap="small")

    with col2:
        if st.button(
            ":arrow_backward:", key="prev_customer", help="Go to the previous customer"
        ):
            st.session_state["customer_counter"] = max(
                0, st.session_state["customer_counter"] - 1
            )
            st.session_state.button_clicked = False

    with col4:
        if st.button(
            ":arrow_forward:", key="next_customer", help="Go to the next customer"
        ):
            st.session_state["customer_counter"] = min(
                len(df) - 1, st.session_state["customer_counter"] + 1
            )
            st.session_state.button_clicked = False

    with col3:
        st.markdown(
            f"{st.session_state['customer_counter']+1}/{len(df)}",
            unsafe_allow_html=True,
        )

    print("Datafetch counter", st.session_state["customer_counter"])

    #########################
    #       PAGE CONTENT
    #########################
    # Check the session state variable at the beginning of the script
    if st.session_state.button_clicked:
        st.success("Message sent! Click to Proceed to next customer.")
        # st.stop()
    (
        df,
        user_attribute_columns,
        attribute_columns,
        metric_columns,
        other_columns,
    ) = process_df(df)

    # Get the specific customer's details
    customer_details = df.iloc[st.session_state["customer_counter"]]
    customer_details_df = customer_details.to_frame()

    # channel = "EMAIL" # Todo: customer_details.loc["User.UserAttributes.PreferredChannel"]
    channel = customer_details.loc["User.UserAttributes.PreferredChannel"]

    # #### GET PRODUCT DATA FOR CONTENT GENERATION
    product_info = get_product_info(customer_details["User.UserAttributes.Product"])

    if (
        "prompt_template" not in st.session_state
        or st.session_state["prompt_template"] == ""
    ):
        st.error("Please select a prompt template from the 'Prompt Catalog'")
        if st.button("Go to Prompt Catalog"):
            switch_page("Prompt Catalog")
    else:
        # Format the prompt template
        st.session_state["prompt_formatted"][
            st.session_state["customer_counter"]
        ] = format_prompt_template(
            st.session_state["prompt_template"], product_info, customer_details
        )

        run_button = st.button(
            f"Generate {channel}", type="primary", on_click=generate_marketing_email
        )

        # Show the generated text in a text box
        if st.session_state["model_output"].get(st.session_state["customer_counter"]):
            (
                st.session_state.message_subject,
                st.session_state.message_body_text,
            ) = extract_content(
                st.session_state["model_output"][st.session_state["customer_counter"]]
            )
            if st.session_state.message_subject and st.session_state.message_body_text:
                st.markdown(f"#### Generated {channel}")
                message_input = st.text_input(
                    "**Subject**", 
                    value=st.session_state.message_subject, 
                    key="message_subject_alt"
                )
                message_text = st.text_area(
                    "**Message Body**", 
                    value=st.session_state.message_body_text,
                    key="message_body_text_alt",
                    height=400
                )
                send_button = st.button(f"Send {channel}", on_click=set_button_clicked)

        # Customer Details Expander
        with st.expander("#### Customer Details", expanded=False):
            st.dataframe(customer_details_df, use_container_width=True)

        with st.expander("#### Product Details", expanded=False):
            display_product_info(product_info)

        with st.expander("#### Prompt Details", expanded=False):
            prompt_template_tab, prompt_tab, model_output_tab = st.tabs(
                ["Prompt Template", "Prompt", "Model Output"]
            )

            with prompt_template_tab:
                st.code(st.session_state["prompt_template"], language="text")
            with prompt_tab:
                prompt_area = st.code(
                    st.session_state["prompt_formatted"][
                        st.session_state["customer_counter"]
                    ],
                    language="text",
                )
            with model_output_tab:
                if (
                    st.session_state["customer_counter"]
                    not in st.session_state["model_output"]
                ):
                    st.info(
                        f"**Note:** Click on 'Generate {channel}' to get the model output."
                    )
                else:
                    st.code(
                        st.session_state["model_output"].get(
                            st.session_state["customer_counter"], ""
                        ),
                        language="text",
                    )
#########################
#      FOOTNOTE
#########################

# footnote
st.text("")
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
