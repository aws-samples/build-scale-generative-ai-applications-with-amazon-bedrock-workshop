"""
Helper functions with StreamLit UI utils
"""

import os
import json
from pathlib import Path
from datetime import datetime

import qrcode
import streamlit as st
from qrcode.image.styledpil import StyledPilImage


def generate_qrcode(url: str, path: str) -> str:
    """
    Generate QR code for MFA

    Parameters
    ----------
    url : str
        URL for the QR code
    path : str
        Folder to save generated codes

    Returns
    -------
    str
        Local path to the QR code
    """

    # create folder if needed
    if not os.path.exists(path):
        os.mkdir(path)

    # generate image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(image_factory=StyledPilImage)

    # save locally
    current_ts = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
    qrcode_path = path + "qrcode_" + str(current_ts) + ".png"
    img.save(qrcode_path)
    return qrcode_path


def set_page_styling() -> None:
    """
    Set the page layout
    """
    st.session_state[
        "css_code"
    ] = """<style>
section.main > div {max-width:800px}
[data-testid="stSidebarNav"]::before {
    content: "Application Tabs";
    margin-left: 20px;
    margin-top: 20px;
    margin-bottom: 20px;
    font-size: 22px;
    font-weight: bold;
    position: relative;
    top: 100px;
}
[data-testid="stExpander"] div:has(>.streamlit-expanderContent) {
        overflow: scroll;
        max-height: 500px;
    }
[data-testid="stForm"] {border: 0px; margin:0px; padding:0px; display:inline;}
.stChatMessage.css-1c7y2kd.eeusbqq4 {
    text-align: right;
    width: 60%;
    margin-left: 40%;
    text-align: justify;
}
.stChatMessage.css-4oy321.eeusbqq4 {
    text-align: left;
    max-width: 100%;
    margin-right: 0%;
    padding-right: 5%;
    width=max-content;
    text-align: justify;
    background-color: rgba(180,200,250,0.15);
}
</style>
"""
    st.markdown(st.session_state["css_code"], unsafe_allow_html=True)


def generate_ai_summary_callback() -> None:
    """
    Summary generation button callback
    """
    st.session_state["generating_summary"] = True


def display_search_result(
    documents: list,
    idx: int,
) -> None:
    """
    Shows search result in the UI

    Parameters
    ----------
    documents : list
        list of documents
    idx : int
        Index of the relevant document
    """
    # extract document
    doc = documents[idx]

    # show document
    if "location_ref" in doc and "not found" not in doc["location_ref"]:
        st.markdown(f"[{doc['doc_name']}]({doc['doc_url']}) ({doc['location_ref']})")
    else:
        st.markdown(f"[{doc['doc_name']}]({doc['doc_url']})")
    st.markdown(doc["text_with_highlights"])

    # show meta-data
    meta1_col, meta2_col, meta3_col = st.columns(3)
    with meta1_col:
        if "type" in doc:
            st.markdown(
                f"<div style='text-align: left'> <b>Type</b>: {doc['type'].lower()} </div>",
                unsafe_allow_html=True,
            )
    with meta2_col:
        if "LANGUAGE" in doc:
            st.markdown(
                f"<div style='text-align: center'> <b>Language</b>: {doc['LANGUAGE'][0].lower()} </div>",
                unsafe_allow_html=True,
            )
    with meta3_col:
        if "relevance" in doc:
            st.markdown(
                f"<div style='text-align: right'> <b>Relevance</b>: {doc['relevance'].lower().replace('_', ' ')} </div>",  # noqa: E501
                unsafe_allow_html=True,
            )


def get_product_info(product_id, return_dict=True):
    path = Path(os.path.dirname(__file__))
    with open(f"{path.parent.absolute()}/data/products.json", "r") as f:
        data = json.load(f)

        if return_dict:
            for product in data["products"]:
                if product["id"] == product_id:
                    return product
        else:
            return data


def display_product_info(card_info):
    # Extract the product name, title, and description
    product_name = card_info["Name"]
    product_title = card_info["Title"]
    product_description = card_info["Description"]

    # Extract the key features and great for sections
    key_features = card_info["Key Features"]
    great_for = card_info["Great For"]

    col1, col2 = st.columns([1, 1])
    # Display the product name, title, and description
    with col1:
        st.write(f"**Product**:\n\n{product_name}")
        st.write(f"**Campaign Phrase**:\n\n{product_title}")
        # Display the key features and great for sections as lists
    with col2:
        st.write(f"**Description**:\n\n{product_description}")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.write("**Key Features**:")
        for feature in key_features:
            st.write("- " + feature)
    with col2:
        st.write("**Great For**:")
        for use_case in great_for:
            st.write("- " + use_case)


def reset_session_state(page_name: str) -> None:
    """
    Resets session state variables
    """
    st.session_state.setdefault("last_page", "None")

    st.session_state["current_page"] = page_name
    if st.session_state["current_page"] != st.session_state["last_page"]:
        for key in st.session_state.keys():
            if key not in [
                "authenticated",
                "access_token",
                "css_code",
                "username",
                "user_id",
                "user_email",
                "email",
                "df",
                "df_name",
                "df_selected",
                "df_selected_prompt",
            ]:
                del st.session_state[key]

    st.session_state["last_page"] = page_name


def button_with_url(
    url: str,
    text: str,
) -> str:
    """
    Create button with URL link
    """
    return f"""
    <a href={url}><button style="
    fontWeight: 400;
    fontSize: 0.85rem;
    padding: 0.25rem 0.75rem;
    borderRadius: 0.25rem;
    margin: 0px;
    lineHeight: 1;
    width: auto;
    userSelect: none;
    backgroundColor: #FFFFFF;
    border: 1px solid rgba(49, 51, 63, 0.2);">{text}</button></a>
    """


def display_cover_with_title(
    title: str,
    description: str,
    image_url: str,
    max_width: str = "100%",
    text_color: str = "#FFFFFF",
) -> None:
    """
    Display cover with title

    Parameters
    ----------
    title : str
        Title to display over the image (upper part)
    description : str
        Description to display over the image (lower part)
    image_url : str
        URL to the cover image
    """

    html_code = f"""
    <div class="container" align="center">
    <img src={image_url} alt="Cover" style="max-width:{max_width};">
    <div style="position: absolute; top: 8px; left: 32px; font-size: 3rem; font-weight: bold; color: {text_color}" align="center">{title}</div>
    <div style="position: absolute; bottom: 8px; left: 32px; font-size: 1.5rem; color: {text_color}" align="center">{description}</div>
    </div>
    """  # noqa: E501

    st.markdown(
        html_code,
        unsafe_allow_html=True,
    )


INDUSTRIES = [
    "Automotive",
    "FinServ",
    "Gaming",
    "HCLS",
    "Hospitality",
    "M&E",
    "MFG",
    "P&U",
    "PS (Education, Government, etc.)",
    "R/CPG",
    "Telco",
    "Transport",
    "Travel",
]

LANGUAGES = [
    "English",
    "German",
    "French",
    "Italian",
    "Spanish",
    "Polish",
    "Romanian",
    "Dutch",
    "Russian",
    "Portuguese",
]

TECHNIQUES = [
    "Zero-shot",
    "Few-shot",
    "Chain of Thoughts (CoT)",
    "Reasoning Acting (ReAct)",
    "Other",
]

TASKS = [
    "Classification",
    "Code Gen or refactoring",
    "Summarization",
    "Q&A",
    "Chatbots",
    "Other",
]


FILTER_INDUSTRIES = ["ALL"] + INDUSTRIES

FILTER_LANGUAGES = ["ALL"] + LANGUAGES

FILTER_TECHNIQUES = ["ALL"] + TECHNIQUES

FILTER_TASKS = ["ALL"] + TASKS


#########################
#    LOGO Placement & Title
#########################


def add_logo():
    st.markdown(
        """
        <style>
            [data-testid="stSidebarNav"] {
                background-image: url(https://raw.githubusercontent.com/aws-samples/amazon-bedrock-prompting/main/prompts_catalogue/AWS_logo_RGB.png);
                background-repeat: no-repeat;
                padding-top: 120px;
                background-position: 20px 20px;
            }
            [data-testid="stSidebarNav"]::before {
                content: "Application Tabs";
                margin-left: 20px;
                margin-top: 20px;
                font-size: 30px;
                position: relative;
                top: 100px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
