import os
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# --- Configuration ---
LIVEAGENT_API_URL = "https://plotbase.ladesk.com/api/v3"

# Default values from Environment Variables
DEFAULT_LIVEAGENT_KEY = os.getenv("LIVEAGENT_API_KEY", "ixlp2t3emrrh63pplvrb1eb6zsymv59ajk7pk0msgp")
DEFAULT_GOOGLE_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
DEFAULT_GOOGLE_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
DEFAULT_GMAIL_USER = os.getenv("GMAIL_USER", "")
DEFAULT_GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

def get_config_value(key_name, default_value=""):
    """
    Returns configuration value with priority:
    1. Session State (UI Override)
    2. Environment Variable
    3. Default Value
    """
    # Check session state (UI override)
    session_key = f"config_{key_name.lower()}"
    if session_key in st.session_state and st.session_state[session_key]:
        return st.session_state[session_key]
    
    # Return default (which comes from env var or hardcoded fallback)
    return default_value

# Simple variable for backward compatibility
VAS_API_KLUC = DEFAULT_LIVEAGENT_KEY

# Google Sheets Scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
