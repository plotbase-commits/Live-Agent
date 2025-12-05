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

# LiveAgent Message Group Types (podľa API dokumentácie)
# Typy s reálnou komunikáciou:
COMMUNICATION_TYPES = {
    '3': 'Incoming Email (nový tiket)',      # Zákazník vytvoril tiket
    '4': 'Outgoing Email (agent odpoveď)',   # Agent odpovedal
    '5': 'Offline (kontaktný formulár)',     # Zákazník cez formulár
    '7': 'Incoming Email (odpoveď)',         # Zákazník odpovedal
}
# Typy zákazníka (incoming)
CUSTOMER_TYPES = ['3', '5', '7']
# Typy agenta (outgoing)
AGENT_TYPES = ['4']

# --- Helper Functions ---

def get_liveagent_tickets(api_key, page=1, per_page=20):
    """Fetches a page of tickets from LiveAgent API."""
    headers = {"apikey": api_key}
    params = {
        "_page": page,
        "_perPage": per_page,
        "_sortField": "date_changed",
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

def filter_communication_groups(message_groups):
    """Filters message groups to only include real communication (not system notifications)."""
    if not isinstance(message_groups, list):
        return []
    return [g for g in message_groups if g.get('type') in COMMUNICATION_TYPES]

def has_real_communication(message_groups):
    """Checks if ticket has both customer message AND agent response."""
    group_types = [g.get('type') for g in message_groups]
    has_customer = any(t in CUSTOMER_TYPES for t in group_types)
    has_agent = any(t in AGENT_TYPES for t in group_types)
    return has_customer and has_agent

def process_transcript(message_groups):
    """Processes message groups into a structured transcript."""
    transcript_parts = []
    
    # Flatten the list of messages from groups
    all_messages = []
    if isinstance(message_groups, list):
        for group in message_groups:
            # Each group usually has a 'messages' list
            if 'messages' in group and isinstance(group['messages'], list):
                for msg in group['messages']:
                    # Sometimes the inner message doesn't have the author name, so we might want to grab it from the group
                    # if it's missing in the msg. But usually userid is there.
                    if 'user_full_name' not in msg and 'user_full_name' in group:
                        msg['user_full_name'] = group['user_full_name']
                    all_messages.append(msg)
            else:
                # Fallback if it's a flat structure or different format
                all_messages.append(group)
    
    # Sort by datecreated
    try:
        sorted_messages = sorted(all_messages, key=lambda x: x.get('datecreated', ''))
    except Exception:
        sorted_messages = all_messages

    for msg in sorted_messages:
        # Try to get readable name, fall back to userid
        author = msg.get('user_full_name') 
        if not author:
            author = msg.get('userid') or "Unknown"
            
        date_created = msg.get('datecreated', 'Unknown Date')
        
        # Process body
        body_html = msg.get('message', '')
        
        # Skip completely empty messages (sometimes system messages are empty)
        if not body_html:
            continue

        # Format header
        header = f"\n--------------------------------------------------\n[AUTOR: {author} | ČAS: {date_created}]\n"
        
        soup = BeautifulSoup(body_html, "html.parser")
        text_body = soup.get_text(separator="\n").strip()
        
        # Remove excessive newlines
        text_body = "\n".join([line.strip() for line in text_body.splitlines() if line.strip()])
        
        transcript_parts.append(header + text_body)
    
    full_transcript = "\n".join(transcript_parts)
    
    # Limit to 49,000 characters (Google Sheets cell limit is 50k)
    if len(full_transcript) > 49000:
        full_transcript = full_transcript[:49000] + "\n\n[WARNING: Transcript truncated due to size limit]"
        
    return full_transcript

def connect_to_gsheets(creds_file, sheet_identifier):
    """Connects to Google Sheets and returns the worksheet."""
    try:
        creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        if sheet_identifier.startswith("https://"):
            sheet = client.open_by_url(sheet_identifier).sheet1
        else:
            sheet = client.open(sheet_identifier).sheet1
            
        return sheet
    except Exception as e:
        st.error("Error connecting to Google Sheets. Please check permissions and sheet name/URL.")
        st.exception(e) # Show full traceback for debugging
        return None

def sync_data(api_key, sheet_name, creds_file, progress_bar, status_text, url_base):
    """Main synchronization logic."""
    sheet = connect_to_gsheets(creds_file, sheet_name)
    if not sheet:
        return

    HEADERS = ['Ticket ID', 'Link', 'Date Created', 'Date Changed', 'Date Resolved', 'Status', 'Subject', 'Transcript']

    # Check and setup headers
    try:
        all_values = sheet.get_all_values()
        existing_tickets_map = {} # Map ID -> Row Number (1-based)
        
        if not all_values:
            # Sheet is empty, add headers
            sheet.append_row(HEADERS)
            next_row = 2
        else:
            first_row = all_values[0]
            # Check if headers match roughly (at least the first one)
            if not first_row or first_row[0] != HEADERS[0]:
                # Headers missing or incorrect, insert them at the top
                sheet.insert_row(HEADERS, index=1)
                # Re-read values after insertion to ensure correct row indices
                all_values = sheet.get_all_values()
            
            # Build map of existing tickets
            # Row 1 is header. Data starts at Row 2 (index 1).
            for i, row in enumerate(all_values):
                if i == 0: continue # Skip header
                if row and len(row) > 0:
                    t_id = str(row[0])
                    existing_tickets_map[t_id] = i + 1
            
            next_row = len(all_values) + 1
                
    except Exception as e:
        st.error(f"Error reading sheet data: {e}")
        return

    # Fetch tickets
    total_processed = 0
    new_tickets_count = 0
    updated_tickets_count = 0
    
    page = 1
    has_more = True
    
    # Limit to 100 tickets (5 pages * 20 tickets per page)
    MAX_PAGES = 5 
    
    start_time = time.time()
    
    while has_more and page <= MAX_PAGES:
        status_text.text(f"Fetching page {page}...")
        tickets = get_liveagent_tickets(api_key, page)
        
        if not tickets:
            break
            
        if len(tickets) == 0:
            has_more = False
            break
            
        for ticket in tickets:
            ticket_id = str(ticket.get('id'))
            
            # Rate limiting
            time.sleep(0.1)
            
            # Filter by status: Answered (A), Resolved (R), Postponed (W)
            status_code = ticket.get('status')
            if status_code not in ['A', 'R', 'W']:
                continue

            # Fetch messages
            status_text.text(f"Processing ticket {ticket_id}...")
            messages = get_ticket_messages(api_key, ticket_id)
            
            # Filter to only communication groups (skip system notifications)
            communication_groups = filter_communication_groups(messages)
            
            # Skip tickets without real communication (customer + agent)
            if not has_real_communication(communication_groups):
                status_text.text(f"Skipping ticket {ticket_id} (no real communication)...")
                continue
            
            transcript = process_transcript(communication_groups)
            
            # Status Mapping
            STATUS_MAP = {
                'A': 'Answered',
                'P': 'Calling',
                'T': 'Chatting',
                'X': 'Deleted',
                'B': 'Spam',
                'I': 'Init',
                'C': 'Open',
                'R': 'Resolved',
                'N': 'New',
                'W': 'Postponed'
            }
            
            status_code = ticket.get('status')
            ticket_status_label = STATUS_MAP.get(status_code, status_code)

            # Prepare row
            # Columns: Ticket ID | Link (URL) | Date Created | Date Changed | Date Resolved | State | Subject | Structured Transcript
            row = [
                ticket_id,
                f"{url_base}{ticket_id}", # Constructed Link
                ticket.get('date_created'),
                ticket.get('date_changed'),
                ticket.get('date_resolved'),
                ticket_status_label, 
                ticket.get('subject'),
                transcript
            ]
            
            # Update or Append
            try:
                if ticket_id in existing_tickets_map:
                    # Update existing row
                    row_num = existing_tickets_map[ticket_id]
                    sheet.update(range_name=f"A{row_num}", values=[row])
                    updated_tickets_count += 1
                else:
                    # Append new row
                    sheet.update(range_name=f"A{next_row}", values=[row])
                    existing_tickets_map[ticket_id] = next_row
                    new_tickets_count += 1
                    next_row += 1
            except Exception as e:
                st.error(f"Failed to save ticket {ticket_id}: {e}")
            
            total_processed += 1
            progress_bar.progress(min(total_processed / 100.0, 1.0)) # Simple progress indication
            
        page += 1
        
    end_time = time.time()
    duration_seconds = end_time - start_time
    duration_minutes = duration_seconds / 60
    
    st.success(f"Sync complete! Processed {total_processed} tickets in {duration_minutes:.2f} minutes. Added {new_tickets_count} new, Updated {updated_tickets_count} existing rows.")

# --- UI Layout ---
st.set_page_config(page_title="LiveAgent to Sheets Sync", layout="wide")

st.title("LiveAgent to Google Sheets Sync")

with st.sidebar:
    st.header("Configuration")
    api_key_input = st.text_input("LiveAgent API Key", value=VAS_API_KLUC, type="password")
    sheet_name_input = st.text_input("Google Sheet Name or URL", value="LiveAgent Tickets")
    creds_file_input = st.text_input("Credentials File Path", value="credentials.json")
    
    st.markdown("---")
    st.subheader("Scheduler")
    schedule_time = st.time_input("Run at time", value=datetime.time(9, 0))
    enable_scheduler = st.checkbox("Enable Daily Scheduler")

    # Allow user to override URL format if needed
    url_base = st.text_input("Ticket URL Base", value="https://plotbase.ladesk.com/agent/#Conversation;id=")

if st.button("Sync Now"):
    if not os.path.exists(creds_file_input):
        st.error(f"Credentials file not found at: {creds_file_input}")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        sync_data(api_key_input, sheet_name_input, creds_file_input, progress_bar, status_text, url_base)

# --- Scheduler Logic (Placeholder for Streamlit) ---
# Streamlit reruns the script on interaction. For a true background scheduler, 
# one would typically run a separate script or use a custom loop. 
# Here we just show the status.
if enable_scheduler:
    st.info(f"Scheduler is enabled. In a production environment, this would run every day at {schedule_time}. "
            "For this local Streamlit app, please use the 'Sync Now' button or run the script via a cron job.")

st.markdown("---")
st.markdown("### Logs")
st.text_area("Log Output", height=200, disabled=True)
