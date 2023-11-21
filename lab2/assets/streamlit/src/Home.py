"""
StreamLit app with the search engine UI: landing page
"""

#########################
#       IMPORTS
#########################

import logging
import os
import sys

import streamlit as st
from components.utils import display_cover_with_title, generate_qrcode, set_page_styling
from dotenv import load_dotenv
from PIL import Image
from st_pages import show_pages_from_config
from streamlit_extras.switch_page_button import switch_page

# for local testing only
if "COVER_IMAGE_URL" not in os.environ:
    load_dotenv()

# Import required AFTER env loading
import components.authenticate as authenticate
from components.utils import add_logo
import components.sns_api as sns_api

LOGGER = logging.Logger("Home-Page", level=logging.DEBUG)
HANDLER = logging.StreamHandler(sys.stdout)
HANDLER.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
LOGGER.addHandler(HANDLER)


#########################
#    CHECK LOGIN (do not delete)
#########################

# check authentication
authenticate.set_st_state_vars()


#########################
#     COVER & CONFIG
#########################

# titles
COVER_IMAGE = (
    os.environ.get("COVER_IMAGE_URL")
    if "authenticated" in st.session_state and st.session_state["authenticated"]
    else os.environ.get("COVER_IMAGE_LOGIN_URL")
)
TITLE = " Build & Scale GenAi Apps using Amazon Bedrock"
DESCRIPTION = "Marketing Content Generation - Amazon Bedrock Workshop"
PAGE_TITLE = "Amazon Bedrock Workshop"
PAGE_ICON = ":ocean:"

# page config
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="centered",
    initial_sidebar_state="expanded"
    if "authenticated" in st.session_state and st.session_state["authenticated"]
    else "collapsed",
)

# page width, form borders, message styling
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
if "authenticated" in st.session_state and st.session_state["authenticated"]:
    show_pages_from_config()

add_logo()

#########################
#        SIDEBAR
#########################

# sidebar title
if st.session_state["authenticated"]:
    st.sidebar.markdown(
        """
        <style>
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
        </style>
        """,
        unsafe_allow_html=True,
    )
else:
    st.sidebar.markdown(
        """
        <style>
            [data-testid="collapsedControl"] {
                display: none
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

#########################
#       CONSTANTS
#########################

GENERATED_QRCODES_PATH = "tmp/"


#########################
# SESSION STATE VARIABLES
#########################

st.session_state.setdefault("username", "")
st.session_state.setdefault("password", "")
st.session_state.setdefault("password_repeat", "")
st.session_state.setdefault("new_password", "")
st.session_state.setdefault("new_password_repeat", "")
st.session_state.setdefault("email", "")
st.session_state.setdefault("register", False)
st.session_state.setdefault("account_created", False)
st.session_state.setdefault("email_verified", False)


#########################
#   HELPER FUNCTIONS
#########################


def subscribe_email() -> None:
    """
    Subscribe email to SNS topic
    """
    LOGGER.log(logging.DEBUG, ("Inside subscribe_email()"))
    if "user_email" in st.session_state and st.session_state["user_email"] != "":
        print(f"EMAIL: {st.session_state['user_email']}")
        print(f"TOKEN: {st.session_state['access_token']}")
        subscribe_success, message = sns_api.sns_topic_subscribe_email(
            st.session_state["user_email"], st.session_state["access_token"]
        )
        if not subscribe_success:
            st.session_state["error_message"] = message
        else:
            st.session_state.pop("error_message", None)
    else:
        st.session_state["error_message"] = "Could not subscribe email."


def toggle_register() -> None:
    """
    Toggle register flag
    """
    st.session_state["register"] = not st.session_state["register"]


def create_account() -> None:
    """
    Perform registration
    """
    LOGGER.log(logging.DEBUG, ("Inside create_account()"))

    st.session_state["account_created"] = False
    st.session_state["email_verified"] = False

    if (
        (st.session_state["username"] != "")
        & (st.session_state["password"] != "")
        & (st.session_state["password_repeat"] != "")
        & (st.session_state["email"] != "")
    ):
        if st.session_state["password"] == st.session_state["password_repeat"]:
            register_success, message = authenticate.create_user(
                st.session_state["username"],
                st.session_state["password"],
                st.session_state["email"],
            )
            if not register_success:
                st.session_state["error_message"] = message
            else:
                st.session_state.pop("error_message", None)
                st.session_state["account_created"] = True
                st.session_state["user_to_verify"] = st.session_state["username"]
        else:
            st.session_state["error_message"] = "Entered passwords do not match."
        del st.session_state["password"]
        del st.session_state["password_repeat"]
    else:
        st.session_state[
            "error_message"
        ] = "Please enter a username, an email and a password first."


def verify_email() -> None:
    """
    Verify email
    """
    LOGGER.log(logging.DEBUG, ("Inside verify_email()"))

    if st.session_state["verification_code"] != "":
        email_verify_success, message = authenticate.confirm_sign_up(
            st.session_state["user_to_verify"], st.session_state["verification_code"]
        )
        if not email_verify_success:
            st.session_state["error_message"] = message
        else:
            st.session_state.pop("error_message", None)
            st.session_state["email_verified"] = True
            del st.session_state["verification_code"]
            del st.session_state["user_to_verify"]
            toggle_register()
    else:
        st.session_state["error_message"] = "Please enter a code from your email first."


def run_login() -> None:
    """
    Perform login
    """
    LOGGER.log(logging.DEBUG, ("Inside run_login()"))

    st.session_state["account_created"] = False
    st.session_state["email_verified"] = False

    # authenticate
    if (st.session_state["username"] != "") & (st.session_state["password"] != ""):
        authenticate.sign_in(st.session_state["username"], st.session_state["password"])

        # check authentication
        if not st.session_state["authenticated"] and st.session_state[
            "challenge"
        ] not in [
            "NEW_PASSWORD_REQUIRED",
            "MFA_SETUP",
            "SOFTWARE_TOKEN_MFA",
        ]:
            st.session_state[
                "error_message"
            ] = "Username or password are wrong. Please try again."
        else:
            st.session_state.pop("error_message", None)

    # ask to enter credentials
    else:
        st.session_state[
            "error_message"
        ] = "Please enter a username and a password first."


def reset_password() -> None:
    """
    Reset password
    """
    LOGGER.log(logging.DEBUG, ("Inside reset_password()"))

    if st.session_state["challenge"] == "NEW_PASSWORD_REQUIRED":
        if (st.session_state["new_password"] != "") & (
            st.session_state["new_password_repeat"] != ""
        ):
            if (
                st.session_state["new_password"]
                == st.session_state["new_password_repeat"]
            ):
                reset_success, message = authenticate.reset_password(
                    st.session_state["new_password"]
                )
                if not reset_success:
                    st.session_state["error_message"] = message
                else:
                    st.session_state.pop("error_message", None)
            else:
                st.session_state["error_message"] = "Entered passwords do not match."
        else:
            st.session_state["error_message"] = "Please enter a new password first."


def setup_mfa() -> None:
    """
    Setup MFA
    """
    LOGGER.log(logging.DEBUG, ("Inside setup_mfa()"))

    if st.session_state["challenge"] == "MFA_SETUP":
        if st.session_state["mfa_verify_token"] != "":
            token_valid, message = authenticate.verify_token(
                st.session_state["mfa_verify_token"]
            )
            if token_valid:
                mfa_setup_success, message = authenticate.setup_mfa()
                if not mfa_setup_success:
                    st.session_state["error_message"] = message
                else:
                    st.session_state.pop("error_message", None)
            else:
                st.session_state["error_message"] = message
        else:
            st.session_state[
                "error_message"
            ] = "Please enter a code from your MFA app first."


def sign_in_with_token() -> None:
    """
    Verify MFA Code
    """
    LOGGER.log(logging.DEBUG, ("Inside sign_in_with_token()"))

    if st.session_state["challenge"] == "SOFTWARE_TOKEN_MFA":
        if st.session_state["mfa_token"] != "":
            success, message = authenticate.sign_in_with_token(
                st.session_state["mfa_token"]
            )
            if not success:
                st.session_state["error_message"] = message
            else:
                st.session_state.pop("error_message", None)
        else:
            st.session_state[
                "error_message"
            ] = "Please enter a code from your MFA App first."


#########################
#      MAIN APP PAGE
#########################

# page if authenticated
if st.session_state["authenticated"]:
    st.markdown("")
    subscribe_email()
    st.info(
        """
        ## Welcome - Build & Scale GenAi Apps using Amazon Bedrock Workshop 🚀
        """
    )
    _, col, _ = st.columns([2, 1, 2], gap="large")
    with col:
        if st.button("Get Started", type="primary"):
            switch_page("Data Viewer")

# page if password needs to be reset
elif st.session_state["challenge"] == "NEW_PASSWORD_REQUIRED":
    st.markdown("")
    st.warning("Please reset your password to use the app.")

    with st.form("password_reset_form"):
        # password input field
        new_password = st.text_input(
            key="new_password",
            placeholder="Enter your new password here",
            label="New Password",
            type="password",
        )

        # password repeat input field
        new_password_repeat = st.text_input(
            key="new_password_repeat",
            placeholder="Please repeat the new password",
            label="Repeat New Password",
            type="password",
        )

        # reset button
        reset_button = st.form_submit_button("Reset Password", on_click=reset_password)

# page if user need to setup MFA
elif st.session_state["challenge"] == "MFA_SETUP":
    st.markdown("")
    st.warning(
        "Scan the QR code with an MFA application such as [Authy](https://authy.com/) to access the app."
    )

    # generate QR code
    with st.spinner("Generating QR Code..."):
        qrcode_path = generate_qrcode(
            url=str(st.session_state["mfa_setup_link"]), path=GENERATED_QRCODES_PATH
        )

    # display QR code
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(" ")
    with col2:
        image = Image.open(qrcode_path)
        st.image(image, caption="MFA Setup QR Code")
    with col3:
        st.write(" ")

    # token input field
    with st.form("mfa_submit_form"):
        setup_mfa_token = st.text_input(
            key="mfa_verify_token",
            placeholder="Enter the verification code here",
            label="Verification Code",
        )

        # submit button
        mfa_setup_button = st.form_submit_button("Verify Token", on_click=setup_mfa)

# page if user needs to enter MFA token
elif st.session_state["challenge"] == "SOFTWARE_TOKEN_MFA":
    st.markdown("")
    st.warning("Please provide a token from your MFA application.")

    # token input field
    with st.form("password_reset_form"):
        setup_mfa_token = st.text_input(
            key="mfa_token",
            placeholder="Enter the verification code here",
            label="Verification Token",
        )

        # verification button
        mfa_submit_button = st.form_submit_button(
            "Verify Token", on_click=sign_in_with_token
        )

# page if user is logged out
else:
    st.markdown("")
    st.warning("You are logged out, please log in.")

    if st.session_state["account_created"] and st.session_state["email_verified"]:
        st.success(
            f"User {st.session_state['username']} created successfuly!", icon="✅"
        )

    # Show email verification page
    if (
        st.session_state["register"]
        and st.session_state["account_created"]
        and not st.session_state["email_verified"]
    ):
        st.markdown("---")
        st.markdown("### Complete registration")
        st.markdown(
            "A verification code was sent to your email address. Please enter the code below to verify your email address."
        )

        with st.form("text_input_form"):
            # verification code input field
            verification_code = st.text_input(
                key="verification_code",
                placeholder="Enter the verification code here",
                label="Verification Code",
            )

            # verification button
            verification_button = st.form_submit_button(
                "Verify Email", on_click=verify_email
            )
    # Show register page
    elif st.session_state["register"]:
        st.markdown("---")
        st.markdown("### Create new account")
        with st.form("text_input_form"):
            # username input field
            username = st.text_input(
                key="username",
                placeholder="Enter your username here",
                label="Username",
            )

            email = st.text_input(
                key="email",
                placeholder="Enter your email here",
                label="Email",
            )
            st.session_state["user_email"] = email
            # password input field
            password = st.text_input(
                key="password",
                placeholder="Enter your password here",
                label="Password",
                type="password",
            )

            # password input field
            password_repeat = st.text_input(
                key="password_repeat",
                placeholder="Repeat your password here",
                label="Repeat Password",
                type="password",
            )

            # register button
            register_button = st.form_submit_button(
                "Create account", type="primary", on_click=create_account
            )

        st.markdown("---")
        st.markdown("Already have an account?")
        login_button = st.button(
            "Log in here", type="secondary", on_click=toggle_register
        )
    # Show Login page
    else:
        st.markdown("---")
        st.markdown("### Log in")
        with st.form("text_input_form"):
            # username input field
            username = st.text_input(
                key="username",
                placeholder="Enter your username here",
                label="Username",
            )

            # password input field
            password = st.text_input(
                key="password",
                placeholder="Enter your password here",
                label="Password",
                type="password",
            )

            # login button
            login_button = st.form_submit_button(
                "Log in", type="primary", on_click=run_login
            )

        st.markdown("---")
        register_button = st.button(
            "Create new account", type="secondary", on_click=toggle_register
        )


# show error message
if "error_message" in st.session_state:
    st.error(st.session_state["error_message"])
    del st.session_state["error_message"]


#########################
#        FOOTNOTE
#########################

# footnote

st.text("")

st.markdown("---")
footer_col1, footer_col2 = st.columns(2)

# log out button
with footer_col1:
    st.button("Sign out", on_click=authenticate.sign_out)

# copyright
with footer_col2:
    st.markdown(
        "<div style='text-align: right'> © 2023 Amazon Web Services </div>",
        unsafe_allow_html=True,
    )
