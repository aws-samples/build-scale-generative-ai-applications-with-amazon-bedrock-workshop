"""
StreamLit app page: Prompt Catalog
"""

#########################
#    IMPORTS & LOGGER
#########################

import asyncio
import datetime
import json
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
from datetime import datetime


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
ASSISTANT_AVATAR = os.environ.get("ASSISTANT_AVATAR_URL")
TITLE = "Data Viewer"
DESCRIPTION = "Explore the data that comes from the source systems. "
PAGE_TITLE = "Data Viewer"
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
PAGE_NAME = "DataViewer"

#########################
# SESSION STATE VARIABLES
#########################

reset_session_state(page_name=PAGE_NAME)
st.session_state.setdefault("user_id", "AWS-User")
st.session_state.setdefault("df", pd.DataFrame())
st.session_state.setdefault("df_selected", pd.DataFrame())

#########################
#    HELPER FUNCTIONS
#########################


def load_data_from_source_systems():
    """
    Loads the data from the source systems into the session state
    """
    st.toast("Loading...")
    if "df" not in st.session_state or st.session_state["df"].shape[0] == 0:
        df = pd.read_csv(f"{path.parent.absolute()}/data/df_segment_data.csv")
        st.session_state["df"] = df
        st.session_state["df_name"] = "df_segment_data"
    else:
        df = st.session_state["df"]


def extract_session_id_string(s):
    pattern = r"^\d+\s+(.+)$"
    match = re.match(pattern, s)
    if match:
        return match.group(1)
    else:
        return None


def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a UI on top of a dataframe to let viewers filter columns
    Args: df (pd.DataFrame): Original dataframe
    Returns: pd.DataFrame: Filtered dataframe
    """
    modify = st.checkbox("Add filters")
    if not modify:
        return df
    st.toast("Adding filters...")
    df = df.copy()
    # Try to convert datetimes into a standard format (datetime, no timezone)
    for col in df.columns:
        if is_object_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception as e:
                logger.exception(f"Error converting column {col} to datetime: {e}")
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
    selected_rows = edited_df[edited_df.Select].drop("Select", axis=1)
    st.session_state["df_selected"] = selected_rows
    return selected_rows


#########################
#      MAIN APP PAGE
#########################
st.text("")
load_data_from_source_systems()

if st.session_state["df"].shape[0] == 0:
    st.info("No data retrieved yet. Please click on 'Load Data'")
    _, col = st.columns([6, 1], gap="large")
    if col.button("Load data"):
        load_data_from_source_systems()
else:
    df = st.session_state["df"]

    # instruction
    st.markdown("Select a user for prompt engineering experimentation.")

    selection = dataframe_with_selections(df)
    print(f"Selected user - {selection}")
    if not hasattr(st.session_state, "delete_prompt_clicked"):
        st.session_state.delete_prompt_clicked = False

    if len(selection) == 1:
        for name, content in selection.items():
            if name == "User.UserId":
                user_id_customer = content[content.index[0]]

        st.markdown(
            f"Selected user: {selection['User.UserAttributes.FirstName'].iloc[0]} {selection['User.UserAttributes.LastName'].iloc[0]} ({selection['Address'].iloc[0]})"
        )

        if st.button("Continue with selected user", type="primary"):
            st.session_state["df_selected"] = selection
            switch_page("Prompt Engineering")

    if len(selection) > 1:
        st.error("Please only select one user.")

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
