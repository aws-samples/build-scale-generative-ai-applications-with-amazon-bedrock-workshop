"""
StreamLit app page: Prompt Catalog
"""

#########################
#    IMPORTS & LOGGER
#########################

import logging
import os
import sys
import re
from pathlib import Path
import pandas as pd
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)

import streamlit as st
from st_pages import show_pages_from_config
from streamlit_extras.switch_page_button import switch_page

path = Path(os.path.dirname(__file__))
sys.path.append(str(path.parent.parent.absolute()))

import components.authenticate as authenticate  # noqa: E402
import components.genai_api as genai_api  # noqa: E402
from components.utils import (
    display_cover_with_title,
    reset_session_state,
    set_page_styling,
    add_logo,
)  # noqa: E402
from components.utils_models import get_models_specs  # noqa: E402
from components.utils_models import FILTER_BEDROCK_MODELS, BEDROCK_MODELS
from components.utils import (
    FILTER_INDUSTRIES,
    FILTER_TECHNIQUES,
    FILTER_LANGUAGES,
    FILTER_INDUSTRIES,
    FILTER_TASKS,
)

LOGGER = logging.Logger("Prompt Catalog", level=logging.DEBUG)
HANDLER = logging.StreamHandler(sys.stdout)
HANDLER.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
LOGGER.addHandler(HANDLER)


#########################
#     COVER & CONFIG
#########################

# titles
COVER_IMAGE = os.environ.get("COVER_IMAGE_URL")
TITLE = "Prompt Catalog"
DESCRIPTION = "Explore your Prompt Catalog."
PAGE_TITLE = "Prompt Catalog"
PAGE_ICON = ":book:"

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
PAGE_NAME = "PromptCatalog"

#########################
# SESSION STATE VARIABLES
#########################

reset_session_state(page_name=PAGE_NAME)

MODELS_DISPLAYED, _ = get_models_specs(path=path)
st.session_state.setdefault("ai_model", MODELS_DISPLAYED[0])  # default model

# if "ai_model" not in st.session_state:
#     st.session_state["ai_model"] = MODELS_DISPLAYED[0]  # default model
LOGGER.debug("ai_model selected: %s", st.session_state["ai_model"])

st.session_state.setdefault("query", "")
st.session_state.setdefault("user_id", "AWS-User")
st.session_state.setdefault("prompt_df", pd.DataFrame())

#########################
#    HELPER FUNCTIONS
#########################


def extract_session_id_string(s):
    pattern = r"^\d+\s+(.+)$"
    match = re.match(pattern, s)
    if match:
        return match.group(1)
    else:
        return None


def get_all_user_prompts() -> None:
    """
    Runs API call to retrieve LLM answer and references
    """
    user_id = st.session_state["user_id"]

    ai_model_session = st.session_state.get("ai_model", "ALL")

    LOGGER.info("Retrieving all prompts for user: %s", user_id)

    with st.spinner("Retrieving prompts..."):
        response = genai_api.invoke_dynamo_get(
            params={
                "user_id": user_id,
                "ai_model_filter": ai_model_session,
            },
            access_token=st.session_state["access_token"],
        )

    prompt_dataframe = pd.DataFrame(response.json())
    st.session_state["prompt_df"] = prompt_dataframe


def delete_prompt(prompt_id: str) -> None:
    """
    Runs API call to retrieve LLM answer and references
    """
    LOGGER.debug("Deleting prompt: ####%s#####", prompt_id)
    with st.spinner("Generating content..."):
        response = genai_api.invoke_dynamo_delete(
            params={"session_id": prompt_id},
            access_token=st.session_state["access_token"],
        )

    if response.status_code == 200:
        st.success(f"Prompt {prompt_id} deleted successfully")
        prompt_df = st.session_state["prompt_df"]
        prompt_df.drop(
            prompt_df[prompt_df["session_id"] == prompt_id].index, inplace=True
        )
        st.session_state["prompt_df"] = prompt_df
    else:
        st.error(f"Prompt {prompt_id} deletion failed")


def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a UI on top of a dataframe to let viewers filter columns
    Args: df (pd.DataFrame): Original dataframe
    Returns: pd.DataFrame: Filtered dataframe
    """
    modify = st.checkbox("Add filters")
    if not modify:
        return df
    df = df.copy()
    # Try to convert datetimes into a standard format (datetime, no timezone)
    for col in df.columns:
        if is_object_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception as e:
                LOGGER.exception("Error converting column %s to datetime: %s", col, e)
        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)
    modification_container = st.container()
    with modification_container:
        to_filter_columns = st.multiselect("Filter dataframe on", df.columns)
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            # Treat columns with < 10 unique values as categorical
            if is_categorical_dtype(df[column]) or df[column].nunique() < 10:
                user_cat_input = right.multiselect(
                    f"Values for {column}",
                    df[column].unique(),
                    default=list(df[column].unique()),
                )
                df = df[df[column].isin(user_cat_input)]
            elif is_numeric_dtype(df[column]):
                _min = float(df[column].min())
                _max = float(df[column].max())
                step = (_max - _min) / 100
                user_num_input = right.slider(
                    f"Values for {column}",
                    min_value=_min,
                    max_value=_max,
                    value=(_min, _max),
                    step=step,
                )
                df = df[df[column].between(*user_num_input)]
            elif is_datetime64_any_dtype(df[column]):
                user_date_input = right.date_input(
                    f"Values for {column}",
                    value=(
                        df[column].min(),
                        df[column].max(),
                    ),
                )
                if len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df = df.loc[df[column].between(start_date, end_date)]
            else:
                user_text_input = right.text_input(
                    f"Substring or regex in {column}",
                )
                if user_text_input:
                    df = df[df[column].astype(str).str.contains(user_text_input)]
    return df


def dataframe_with_selections(df):
    df_with_selections = df.copy()
    df_with_selections.insert(0, "Select", False)

    # Get dataframe row-selections from user with st.data_editor
    edited_df = st.data_editor(
        df_with_selections,
        hide_index=True,
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=df.columns,
    )

    # Filter the dataframe using the temporary column, then drop the column
    selected_rows = edited_df[edited_df.Select]
    return selected_rows.drop("Select", axis=1)


#########################
#        SIDEBAR
#########################

# sidebar
with st.sidebar:
    MODEL_OPTIONS = ["ALL"] + MODELS_DISPLAYED
    ai_model = st.selectbox(
        label="Language model:",
        options=MODEL_OPTIONS,
        format_func=lambda x: "Sagemaker: " + x
        if not x.startswith("Bedrock:") and x != "ALL"
        else x,
        key="ai_model",
        help="The search app provides flexibility to choose a large language model used for AI answers.",
    )
    st.session_state["ai_model_filter"] = ai_model

#########################
#      MAIN APP PAGE
#########################
st.text("")
get_all_user_prompts()
if st.session_state["prompt_df"].shape[0] == 0:
    st.info("No prompts for this model. Select your model on the left bar.")
    get_all_user_prompts()
else:
    st.markdown("Select a prompt template from your prompt calalog.")
    prompt_df = st.session_state["prompt_df"]
    selection = dataframe_with_selections(prompt_df)
    if len(selection) == 1:
        if st.button("Continue with selected prompt template", type="primary"):
            st.session_state[
                "df_selected_prompt"
            ] = selection  # Todo - add it to session state
            switch_page("email generation wizard")
        st.markdown("## Details")
        prompt_content = None
        output_content = None
        prompt_template_content = None

        for name, content in selection.items():
            if name == "session_id":
                session_id_string = content[content.index[0]]
            elif name == "user_id":
                user_id_string_prompt_catalog = content[content.index[0]]
            elif name == "Prompt Template":
                prompt_template_content = content[content.index[0]]
            elif name == "Prompt":
                prompt_content = content[content.index[0]]
            elif name == "Output":
                output_content = content[content.index[0]]
            else:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**{name}:**")
                with col2:
                    st.markdown(content[content.index[0]])
        if prompt_template_content:
            st.markdown("**Prompt Template:**")
            st.markdown(prompt_template_content)

        if prompt_content:
            st.markdown("**Prompt:**")
            st.markdown(prompt_content)

        if output_content:
            st.markdown("**Output:**")
            st.markdown(output_content)


#########################
#      FOOTNOTE
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
