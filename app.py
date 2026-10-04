import streamlit as st
import smtplib
from email.mime.text import MIMEText

from google import genai
from google.genai import types

from prompts import (
    summary_request,
    system_prompt,
    welcome_message_template,
)

MODEL_NAME = "gemini-3.5-flash"

st.set_page_config(
    page_title="SpendLens AI",
    page_icon="💰"
)

# -----------------------------
# Secrets
# -----------------------------

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

GMAIL_ADDRESS = st.secrets["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]


# -----------------------------
# Gemini client
# -----------------------------

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


gemini_client = get_gemini_client()


# -----------------------------
# Gmail function
# -----------------------------

def send_email(to_address, subject, body):
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = GMAIL_ADDRESS
    message["To"] = to_address

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(message)

        return True, "Email sent successfully"

    except Exception as error:
        return False, str(error)


# -----------------------------
# Chat functions
# -----------------------------

def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.write(message["content"])
        elif message["kind"]=="image":
            st.image(message["content"])    


def add_message(role, kind, content):
    st.session_state.messages.append(
        {
            "role": role,
            "kind": kind,
            "content": content,
        }
    )

    render_message(st.session_state.messages[-1])


def ask_gemini(parts):
    try:
        return st.session_state.chat.send_message(parts).text

    except Exception as error:
        return f"Sorry, something went wrong: {error}"


# ============================================================
# Step 1: Onboarding
# ============================================================

if "onboarded" not in st.session_state:

    st.title("💰 SpendLens AI")

    st.caption(
        "Your smart AI-powered personal finance assistant"
    )

    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name",
            placeholder="Enter your name"
        )

        email = st.text_input(
            "Enter your email address",
            placeholder="yourname@gmail.com",
            help="SpendLens AI will send your spending summary to this email."
        )

        submitted = st.form_submit_button(
            "Let's go 🚀"
        )

        if submitted:

            if not name.strip() or not email.strip():

                st.warning(
                    "Please fill in both your name and email address."
                )

            else:

                st.session_state.name = name.strip()
                st.session_state.email = email.strip()

                st.session_state.chat = gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt
                    ),
                )

                st.session_state.messages = []

                st.session_state.onboarded = True

                st.rerun()

    st.stop()


# ============================================================
# Step 2: Chat Interface
# ============================================================

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center"
)


with header_col:
    st.title("💰 SpendLens AI")


with button_col:

    send_disabled = not any(
    message["role"] == "user"
    for message in st.session_state.messages)

    if st.button(
        "📧 Send Summary",
        disabled=send_disabled,
        use_container_width=True
    ):

        with st.spinner("Summarizing your spending..."):

            summary = ask_gemini(
                [summary_request]
            )

            success, info = send_email(
                st.session_state.email,
                "Your SpendLens AI Spending Summary",
                summary
            )

            if success:
                st.success(
                    "Summary sent! Check your email 📧"
                )
            else:
                st.error(
                    f"Couldn't send the summary: {info}"
                )


st.caption(
    f"Logged in as {st.session_state.name} - "
    f"updates go to {st.session_state.email}"
)


# -----------------------------
# Welcome message
# -----------------------------

if not st.session_state.messages:

    add_message(
        "assistant",
        "text",
        welcome_message_template.format(
            name=st.session_state.name
        )
    )

else:

    for message in st.session_state.messages:
        render_message(message)


# ============================================================
# Step 3: Spending Chat
# ============================================================

user_input = st.chat_input(
    "Enter an expense or upload a receipt",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"]
)

if user_input:

    photo = user_input.files[0] if user_input.files else None
    text = user_input.text

    parts = []

    if photo is not None:

        photo_bytes = photo.getvalue()

        add_message(
            "user",
            "image",
            photo_bytes
        )

        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type
            )
        )

        parts.append(
            """
            This is a receipt or spending document.

            Read the receipt carefully and identify:
            - Store or merchant name
            - Date if visible
            - Individual items if visible
            - Amounts
            - Total amount
            - Possible spending category

            Do not invent information that is not visible.
            Then provide a clear spending summary.
            """
        )

    if text:

        add_message(
            "user",
            "text",
            text
        )

        parts.append(text)

    if parts:

        with st.spinner("Analyzing your spending..."):

            answer = ask_gemini(parts)

        add_message(
            "assistant",
            "text",
            answer
        )