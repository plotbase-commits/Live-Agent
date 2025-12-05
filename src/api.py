import requests
import time
import streamlit as st
from src.config import LIVEAGENT_API_URL

# --- API Request Configuration ---
API_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # seconds between retries


def _make_api_request(url, headers, params=None, description="API request"):
    """
    Makes an API request with retry logic and exponential backoff.
    Returns tuple (success: bool, data: dict/list or None)
    """
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                url, 
                headers=headers, 
                params=params, 
                timeout=API_TIMEOUT
            )
            response.raise_for_status()
            return True, response.json()
            
        except requests.exceptions.Timeout as e:
            last_error = f"Timeout after {API_TIMEOUT}s"
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_BACKOFF[attempt]
                time.sleep(wait_time)
                
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {e}"
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_BACKOFF[attempt]
                time.sleep(wait_time)
                
        except requests.exceptions.HTTPError as e:
            last_error = f"HTTP error: {e}"
            # Don't retry on HTTP errors (4xx, 5xx) - they're usually not transient
            break
            
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_BACKOFF[attempt]
                time.sleep(wait_time)
    
    return False, last_error


def get_liveagent_tickets(api_key, page=1, per_page=20):
    """Fetches a page of tickets from LiveAgent API with retry logic."""
    headers = {"apikey": api_key}
    params = {
        "_page": page,
        "_perPage": per_page,
        "_sortField": "date_changed",
        "_sortDir": "DESC"
    }
    
    success, result = _make_api_request(
        f"{LIVEAGENT_API_URL}/tickets",
        headers,
        params,
        f"fetching tickets page {page}"
    )
    
    if success:
        return result
    else:
        st.error(f"Error fetching tickets (page {page}): {result}")
        return None


def get_ticket_messages(api_key, ticket_id):
    """Fetches messages for a specific ticket with retry logic."""
    headers = {"apikey": api_key}
    params = {"_perPage": 300}
    
    success, result = _make_api_request(
        f"{LIVEAGENT_API_URL}/tickets/{ticket_id}/messages",
        headers,
        params,
        f"fetching messages for ticket {ticket_id}"
    )
    
    if success:
        return result
    else:
        st.warning(f"Failed to fetch messages for ticket {ticket_id}: {result}")
        return []
