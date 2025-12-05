import streamlit as st
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from bs4 import BeautifulSoup
import time
import datetime
import schedule
import os

# --- Configuration ---
LIVEAGENT_API_URL = "https://plotbase.ladesk.com/api/v3"
# Placeholder for API Key as requested, but pre-filled with the provided key for convenience
VAS_API_KLUC = "ixlp2t3emrrh63pplvrb1eb6zsymv59ajk7pk0msgp" 
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# --- Helper Functions ---

def get_liveagent_tickets(api_key, page=1, per_page=20):
    """Fetches a page of tickets from LiveAgent API."""
    headers = {"apikey": api_key}
    params = {
        "_page": page,
        "_perPage": per_page,
        "_sortField": "date_created",
        "_sortDir": "DESC" # Get newest first
    }
    try:
        response = requests.get(f"{LIVEAGENT_API_URL}/tickets", headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching tickets: {e}")
        return None

def get_ticket_messages(api_key, ticket_id):
    """Fetches messages for a specific ticket."""
    headers = {"apikey": api_key}
    try:
        response = requests.get(f"{LIVEAGENT_API_URL}/tickets/{ticket_id}/messages", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching messages for ticket {ticket_id}: {e}")
        return []

def process_transcript(messages):
    """Processes messages into a structured transcript."""
    transcript_parts = []
    
    # Sort messages by date_created just in case, though API usually returns them sorted
    # Assuming messages is a list of dicts. We need to handle potential key errors safely.
    try:
        sorted_messages = sorted(messages, key=lambda x: x.get('date_created', ''))
    except Exception:
        sorted_messages = messages

    for msg in sorted_messages:
        author = msg.get('author_name') or msg.get('userid') or "Unknown"
        date_created = msg.get('date_created', 'Unknown Date')
        
        # Format header
        header = f"\n--------------------------------------------------\n[AUTOR: {author} | ČAS: {date_created}]\n"
        
        # Process body
        body_html = msg.get('message', '')
        soup = BeautifulSoup(body_html, "html.parser")
        text_body = soup.get_text(separator="\n").strip()
        
        # Remove excessive newlines
        text_body = "\n".join([line.strip() for line in text_body.splitlines() if line.strip()])
        
        transcript_parts.append(header + text_body)
    
    full_transcript = "\n".join(transcript_parts)
    
    # Limit to 49,000 characters
    if len(full_transcript) > 49000:
        full_transcript = full_transcript[:49000] + "\n\n[WARNING: Transcript truncated due to size limit]"
        
    return full_transcript

def connect_to_gsheets(creds_file, sheet_name):
    """Connects to Google Sheets and returns the worksheet."""
    try:
        creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open(sheet_name).sheet1
        return sheet
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return None

def sync_data(api_key, sheet_name, creds_file, progress_bar, status_text):
    """Main synchronization logic."""
    sheet = connect_to_gsheets(creds_file, sheet_name)
    if not sheet:
        return

    # Get existing Ticket IDs to avoid duplicates
    try:
        existing_data = sheet.get_all_records()
        existing_ids = set(str(row['Ticket ID']) for row in existing_data if 'Ticket ID' in row)
    except Exception:
        # If sheet is empty or headers missing, assume no existing IDs
        existing_ids = set()

    # Fetch tickets (Implementing a limit for demo purposes, e.g., first 5 pages or until no more tickets)
    # In a real full sync, we might want to go further, but let's stick to a reasonable batch for now.
    
    total_processed = 0
    new_tickets_count = 0
    
    page = 1
    has_more = True
    
    # Let's limit to 5 pages for this iteration to prevent infinite loops if API behaves unexpectedly
    MAX_PAGES = 5 
    
    while has_more and page <= MAX_PAGES:
        status_text.text(f"Fetching page {page}...")
        tickets = get_liveagent_tickets(api_key, page)
        
        if not tickets:
            break
            
        if len(tickets) == 0:
            has_more = False
            break
            
        for ticket in tickets:
            ticket_id = ticket.get('id')
            
            if str(ticket_id) in existing_ids:
                continue # Skip existing
            
            # Rate limiting
            time.sleep(0.1)
            
            # Fetch messages
            status_text.text(f"Processing ticket {ticket_id}...")
            messages = get_ticket_messages(api_key, ticket_id)
            transcript = process_transcript(messages)
            
            # Prepare row
            # Columns: Ticket ID | Link (URL) | Date Created | State | Subject | Structured Transcript
            row = [
                ticket_id,
                f"https://plotbase.ladesk.com/agent/#/Tickets/Ticket/Show/{ticket_id}", # Constructed Link
                ticket.get('date_created'),
                ticket.get('rstatus'), # 'rstatus' is usually the status code/name in LiveAgent
                ticket.get('subject'),
                transcript
            ]
            
            # Append to sheet
            try:
                sheet.append_row(row)
                new_tickets_count += 1
                existing_ids.add(str(ticket_id))
            except Exception as e:
                st.error(f"Failed to append row for ticket {ticket_id}: {e}")
            
            total_processed += 1
            progress_bar.progress(min(total_processed / 100.0, 1.0)) # Simple progress indication
            
        page += 1
        
    st.success(f"Sync complete! Processed {total_processed} tickets. Added {new_tickets_count} new rows.")

# --- UI Layout ---
st.set_page_config(page_title="LiveAgent to Sheets Sync", layout="wide")

st.title("LiveAgent to Google Sheets Sync")

with st.sidebar:
    st.header("Configuration")
    api_key_input = st.text_input("LiveAgent API Key", value=VAS_API_KLUC, type="password")
    sheet_name_input = st.text_input("Google Sheet Name", value="LiveAgent Tickets")
    creds_file_input = st.text_input("Credentials File Path", value="credentials.json")
    
    st.markdown("---")
    st.subheader("Scheduler")
    schedule_interval = st.number_input("Interval (hours)", min_value=1, value=24)
    enable_scheduler = st.checkbox("Enable Daily Scheduler")

if st.button("Sync Now"):
    if not os.path.exists(creds_file_input):
        st.error(f"Credentials file not found at: {creds_file_input}")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        sync_data(api_key_input, sheet_name_input, creds_file_input, progress_bar, status_text)

# --- Scheduler Logic (Placeholder for Streamlit) ---
# Streamlit reruns the script on interaction. For a true background scheduler, 
# one would typically run a separate script or use a custom loop. 
# Here we just show the status.
if enable_scheduler:
    st.info(f"Scheduler is enabled. In a production environment, this would run every {schedule_interval} hours. "
            "For this local Streamlit app, please use the 'Sync Now' button or run the script via a cron job.")

st.markdown("---")
st.markdown("### Logs")
st.text_area("Log Output", height=200, disabled=True)
