import streamlit as st
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from bs4 import BeautifulSoup
import time
import datetime
from zoneinfo import ZoneInfo
import schedule
import os
import re
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
LIVEAGENT_API_URL = "https://plotbase.ladesk.com/api/v3"
VAS_API_KLUC = os.getenv("LIVEAGENT_API_KEY", "")  # Set in .env file
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# --- Helper Functions ---

# Timezone configuration
LOCAL_TIMEZONE = ZoneInfo('Europe/Bratislava')
UTC_TIMEZONE = ZoneInfo('UTC')

def convert_utc_to_local(utc_datetime_str):
    """Converts UTC datetime string to local timezone."""
    if not utc_datetime_str:
        return None
    
    try:
        # Parse the datetime string (format: 2025-12-04 09:48:23)
        dt = datetime.datetime.strptime(utc_datetime_str, '%Y-%m-%d %H:%M:%S')
        # Assume it's UTC and convert to local timezone
        dt_utc = dt.replace(tzinfo=UTC_TIMEZONE)
        dt_local = dt_utc.astimezone(LOCAL_TIMEZONE)
        # Return as string without timezone info
        return dt_local.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError) as e:
        # If parsing fails, return original
        return utc_datetime_str

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

def get_agents(api_key):
    """Fetches list of agents from LiveAgent API."""
    headers = {"apikey": api_key}
    try:
        response = requests.get(f"{LIVEAGENT_API_URL}/agents", headers=headers)
        response.raise_for_status()
        agents_data = response.json()
        # Create a mapping of agent ID to full name
        agents_map = {}
        if isinstance(agents_data, list):
            for agent in agents_data:
                agent_id = agent.get('id') or agent.get('userid')
                if agent_id:
                    # Try to get full name, fallback to firstname + lastname, then email
                    full_name = agent.get('name') or agent.get('full_name')
                    if not full_name:
                        firstname = agent.get('firstname', '')
                        lastname = agent.get('lastname', '')
                        full_name = f"{firstname} {lastname}".strip()
                    if not full_name:
                        full_name = agent.get('email', f"Agent {agent_id}")
                    agents_map[str(agent_id)] = full_name
        return agents_map
    except requests.exceptions.RequestException as e:
        st.warning(f"Error fetching agents: {e}")
        return {}

def get_users(api_key):
    """Fetches list of users/contacts from LiveAgent API."""
    headers = {"apikey": api_key}
    try:
        response = requests.get(f"{LIVEAGENT_API_URL}/contacts", headers=headers)
        response.raise_for_status()
        users_data = response.json()
        # Create a mapping of user ID to full name
        users_map = {}
        if isinstance(users_data, list):
            for user in users_data:
                user_id = user.get('id') or user.get('contactid')
                if user_id:
                    # Try to get full name, fallback to firstname + lastname, then email
                    full_name = user.get('name') or user.get('full_name')
                    if not full_name:
                        firstname = user.get('firstname', '')
                        lastname = user.get('lastname', '')
                        full_name = f"{firstname} {lastname}".strip()
                    if not full_name:
                        full_name = user.get('email', f"User {user_id}")
                    users_map[str(user_id)] = full_name
        return users_map
    except requests.exceptions.RequestException as e:
        st.warning(f"Error fetching users: {e}")
        return {}

def get_author_name(userid, agents_map, users_map):
    """Get author name from userid using agents and users maps."""
    if not userid:
        return "Unknown"
    
    userid_str = str(userid)
    
    # Check if it's an agent first
    if userid_str in agents_map:
        return agents_map[userid_str]
    
    # Then check if it's a user/contact
    if userid_str in users_map:
        return users_map[userid_str]
    
    # If not found in either, return the ID
    return f"User {userid_str}"

def extract_author_from_message(message_html):
    """Extract author name from From: header in message HTML."""
    if not message_html:
        return None
    
    try:
        soup = BeautifulSoup(message_html, 'html.parser')
        text = soup.get_text()
        
        # Look for 'From:' pattern
        from_match = re.search(r'From:\s*(.+?)(?:\n|$)', text)
        if from_match:
            from_value = from_match.group(1).strip()
            
            # Extract name from format like 'Name <email@example.com>'
            name_match = re.match(r'^([^<]+)', from_value)
            if name_match:
                name = name_match.group(1).strip()
                if name:
                    return name
            
            # If no name part, return the whole From value
            return from_value
    except Exception:
        pass
    
    return None

def process_transcript(message_groups, agents_map, users_map):
    """Processes message groups into a structured transcript."""
    transcript_parts = []
    
    # Process each group to extract From: header and associate it with message body
    processed_messages = []
    
    if isinstance(message_groups, list):
        for group in message_groups:
            if 'messages' in group and isinstance(group['messages'], list):
                group_messages = group['messages']
                
                # Extract From: header from Type H messages in this group
                group_from_author = None
                for msg in group_messages:
                    if msg.get('type') == 'H':  # Header type
                        from_author = extract_author_from_message(msg.get('message', ''))
                        if from_author:
                            group_from_author = from_author
                            break
                
                # Add group_from_author to each message in the group
                for msg in group_messages:
                    # Copy the message and add extracted author
                    msg_copy = msg.copy()
                    if group_from_author:
                        msg_copy['_extracted_from_author'] = group_from_author
                    
                    # Also copy user_full_name from group if missing
                    if 'user_full_name' not in msg_copy and 'user_full_name' in group:
                        msg_copy['user_full_name'] = group['user_full_name']
                    
                    processed_messages.append(msg_copy)
            else:
                # Fallback if it's a flat structure or different format
                processed_messages.append(group)
    
    # Sort by datecreated
    try:
        sorted_messages = sorted(processed_messages, key=lambda x: x.get('datecreated', ''))
    except Exception:
        sorted_messages = processed_messages

    for msg in sorted_messages:
        # Try to get readable name from the message first
        author = msg.get('user_full_name')
        
        # If not available, try to get it from userid using our maps
        if not author:
            userid = msg.get('userid')
            author = get_author_name(userid, agents_map, users_map)
        
        # If author is still just a user ID, try to use extracted From: from group headers
        if author and author.startswith('User '):
            extracted_author = msg.get('_extracted_from_author')
            if extracted_author:
                author = extracted_author
            else:
                # Fallback: try to extract from this specific message
                body_html = msg.get('message', '')
                extracted_author = extract_author_from_message(body_html)
                if extracted_author:
                    author = extracted_author
            
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

# --- Google Sheets Logic (Senior Implementation) ---

class SheetSyncManager:
    def __init__(self, creds_file, sheet_identifier, status_text_element, progress_bar_element):
        self.creds_file = creds_file
        self.sheet_identifier = sheet_identifier
        self.status_text = status_text_element
        self.progress_bar = progress_bar_element
        self.client = None
        self.spreadsheet = None
        self.log_sheet = None
        self.headers = ['Ticket ID', 'Link', 'Date Created', 'Date Changed', 'Date Resolved', 'Status', 'Subject', 'Transcript']
        self.log_headers = ['Ticket ID', 'From Sheet', 'To Sheet', 'Moved At', 'Reason']

    def connect(self):
        """Connects to Google Sheets."""
        try:
            creds = Credentials.from_service_account_file(self.creds_file, scopes=SCOPES)
            self.client = gspread.authorize(creds)
            
            if self.sheet_identifier.startswith("https://"):
                self.spreadsheet = self.client.open_by_url(self.sheet_identifier)
            else:
                self.spreadsheet = self.client.open(self.sheet_identifier)
            return True
        except Exception as e:
            st.error(f"Error connecting to Google Sheets: {e}")
            return False

    def _get_sheet_name_from_date(self, date_str):
        """Converts 'YYYY-MM-DD HH:MM:SS' to 'YYYY-MM'."""
        if not date_str:
            return datetime.datetime.now().strftime("%Y-%m")
        try:
            # Parse date (handling potential timezone offsets if present, though we stripped them earlier)
            dt = datetime.datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
            return dt.strftime("%Y-%m")
        except ValueError:
            return datetime.datetime.now().strftime("%Y-%m")

    def _ensure_log_sheet(self):
        """Ensures _LOG sheet exists."""
        try:
            self.log_sheet = self.spreadsheet.worksheet("_LOG")
        except gspread.WorksheetNotFound:
            self.log_sheet = self.spreadsheet.add_worksheet("_LOG", rows=1000, cols=10)
            self.log_sheet.append_row(self.log_headers)

    def _cleanup_old_sheets(self):
        """Deletes sheets older than 12 months."""
        self.status_text.text("Cleaning up old sheets...")
        worksheets = self.spreadsheet.worksheets()
        current_date = datetime.datetime.now()
        
        for ws in worksheets:
            title = ws.title
            # Match format YYYY-MM
            if re.match(r'^\d{4}-\d{2}$', title):
                try:
                    sheet_date = datetime.datetime.strptime(title, "%Y-%m")
                    # Calculate age in months
                    age_months = (current_date.year - sheet_date.year) * 12 + (current_date.month - sheet_date.month)
                    
                    if age_months > 12:
                        self.status_text.text(f"Deleting old sheet: {title}")
                        self.spreadsheet.del_worksheet(ws)
                        # Log the deletion
                        self.log_sheet.append_row(["N/A", title, "DELETED", current_date.strftime("%Y-%m-%d %H:%M:%S"), "Older than 12 months"])
                except ValueError:
                    continue

    def _get_recent_sheets(self):
        """Returns list of sheet names for the last 3 months + current month."""
        sheets = []
        current = datetime.datetime.now()
        for i in range(4): # Current + 3 previous
            d = current - datetime.timedelta(days=30*i) # Approx
            sheets.append(d.strftime("%Y-%m"))
        return sheets

    def _get_existing_tickets_map(self):
        """
        Scans relevant sheets (last 3 months) and builds a map of existing tickets.
        Returns: {ticket_id: {'sheet': sheet_name, 'row': row_number}}
        """
        self.status_text.text("Indexing existing tickets (last 3 months)...")
        ticket_map = {}
        target_sheets = self._get_recent_sheets()
        
        all_worksheets = {ws.title: ws for ws in self.spreadsheet.worksheets()}
        
        for sheet_name in target_sheets:
            if sheet_name in all_worksheets:
                try:
                    ws = all_worksheets[sheet_name]
                    # Get all values (batch read)
                    rows = ws.get_all_values()
                    if not rows: continue
                    
                    # Assume header is row 1
                    for i, row in enumerate(rows):
                        if i == 0: continue # Skip header
                        if row and len(row) > 0:
                            t_id = str(row[0])
                            ticket_map[t_id] = {'sheet': sheet_name, 'row': i + 1}
                except Exception as e:
                    print(f"Error reading sheet {sheet_name}: {e}")
        
        return ticket_map

    def _ensure_sheet_exists(self, sheet_name):
        """Creates a monthly sheet if it doesn't exist."""
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(sheet_name, rows=1000, cols=10)
            ws.append_row(self.headers)
            return ws

    def sync(self, api_key, url_base, agents_map, users_map):
        """Main sync execution flow."""
        if not self.connect():
            return

        self._ensure_log_sheet()
        self._cleanup_old_sheets()
        
        existing_tickets = self._get_existing_tickets_map()
        
        # --- Fetch Tickets from API ---
        self.status_text.text("Fetching tickets from LiveAgent...")
        all_tickets = []
        page = 1
        MAX_PAGES = 250 # 250 pages * 20 tickets = 5000 tickets max
        
        while page <= MAX_PAGES:
            tickets = get_liveagent_tickets(api_key, page)
            if not tickets: break
            
            for t in tickets:
                # Filter logic
                if t.get('status') in ['A', 'R', 'W']:
                    all_tickets.append(t)
            
            page += 1
            self.status_text.text(f"Fetching page {page}... ({len(all_tickets)} tickets so far)")
            time.sleep(1.0)  # Rate limit between pages (increased from 0.2s)

        total_tickets = len(all_tickets)
        self.status_text.text(f"Processing {total_tickets} tickets...")
        
        # --- Prepare Batch Operations ---
        # Structure: {sheet_name: {'rows_to_append': [], 'rows_to_update': [], 'rows_to_delete': []}}
        operations = {}
        log_entries = []
        
        processed_count = 0
        
        for ticket in all_tickets:
            processed_count += 1
            if processed_count % 5 == 0:
                self.progress_bar.progress(min(processed_count / total_tickets, 1.0))
                self.status_text.text(f"Processing ticket {processed_count}/{total_tickets}...")
            
            ticket_id = str(ticket.get('id'))
            
            # Rate limit before fetching messages
            time.sleep(0.3)  # Delay between message fetches
            
            # Fetch full details (transcript)
            messages = get_ticket_messages(api_key, ticket_id)
            transcript = process_transcript(messages, agents_map, users_map)
            
            # Prepare Data Row
            date_changed_local = convert_utc_to_local(ticket.get('date_changed'))
            status_code = ticket.get('status')
            STATUS_MAP = {'A': 'Answered', 'P': 'Calling', 'T': 'Chatting', 'X': 'Deleted', 'B': 'Spam', 'I': 'Init', 'C': 'Open', 'R': 'Resolved', 'N': 'New', 'W': 'Postponed'}
            
            row_data = [
                ticket_id,
                f"{url_base}{ticket_id}",
                convert_utc_to_local(ticket.get('date_created')),
                date_changed_local,
                convert_utc_to_local(ticket.get('date_resolved')),
                STATUS_MAP.get(status_code, status_code),
                ticket.get('subject'),
                transcript
            ]
            
            # Determine Target Sheet
            target_sheet_name = self._get_sheet_name_from_date(date_changed_local)
            
            # Initialize ops list for target sheet
            if target_sheet_name not in operations:
                operations[target_sheet_name] = {'append': [], 'update': [], 'delete': []}
            
            # Check existence
            if ticket_id in existing_tickets:
                current_location = existing_tickets[ticket_id]
                current_sheet = current_location['sheet']
                current_row = current_location['row']
                
                if current_sheet == target_sheet_name:
                    # UPDATE in place
                    # Note: gspread batch_update uses A1 notation. We'll handle this in execution.
                    operations[target_sheet_name]['update'].append({
                        'range': f"A{current_row}:H{current_row}",
                        'values': [row_data]
                    })
                else:
                    # MOVE (Delete from old, Append to new)
                    if current_sheet not in operations:
                        operations[current_sheet] = {'append': [], 'update': [], 'delete': []}
                    
                    operations[current_sheet]['delete'].append(current_row)
                    operations[target_sheet_name]['append'].append(row_data)
                    
                    # Log the move
                    log_entries.append([
                        ticket_id, current_sheet, target_sheet_name, 
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                        "Date changed - Moved to new monthly sheet"
                    ])
            else:
                # INSERT (Append)
                operations[target_sheet_name]['append'].append(row_data)

        # --- Execute Batch Operations ---
        self.status_text.text("Executing batch updates to Google Sheets...")
        
        # 1. Execute Deletes first (to avoid row shifting issues, we must sort descending)
        # Note: Deleting rows via gspread one-by-one is slow. 
        # Efficient way: Batch update with deleteDimension request.
        
        for sheet_name, ops in operations.items():
            if not ops['delete'] and not ops['update'] and not ops['append']:
                continue
                
            ws = self._ensure_sheet_exists(sheet_name)
            
            # Batch Delete
            if ops['delete']:
                # Sort descending to delete from bottom up
                rows_to_delete = sorted(list(set(ops['delete'])), reverse=True)
                
                # Construct batch request for deletion
                # We use the spreadsheet.batch_update method for atomic deletion
                sheet_id = ws.id
                requests = []
                for row_num in rows_to_delete:
                    requests.append({
                        "deleteDimension": {
                            "range": {
                                "sheetId": sheet_id,
                                "dimension": "ROWS",
                                "startIndex": row_num - 1, # 0-based inclusive
                                "endIndex": row_num      # 0-based exclusive
                            }
                        }
                    })
                
                if requests:
                    try:
                        self.spreadsheet.batch_update({'requests': requests})
                        st.write(f"Deleted {len(requests)} rows from {sheet_name}")
                    except Exception as e:
                        st.error(f"Failed to batch delete in {sheet_name}: {e}")

            # Batch Update
            if ops['update']:
                try:
                    # gspread batch_update takes a list of objects with range and values
                    ws.batch_update(ops['update'])
                except Exception as e:
                    st.error(f"Failed to batch update in {sheet_name}: {e}")

            # Batch Append
            if ops['append']:
                try:
                    ws.append_rows(ops['append'])
                except Exception as e:
                    st.error(f"Failed to batch append to {sheet_name}: {e}")

        # Write Logs
        if log_entries:
            self.log_sheet.append_rows(log_entries)
            
        st.success(f"Sync complete! Processed {total_tickets} tickets.")


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
        
        # Initialize Manager
        manager = SheetSyncManager(creds_file_input, sheet_name_input, status_text, progress_bar)
        
        # Load metadata first
        status_text.text("Loading agents and users...")
        agents_map = get_agents(api_key_input)
        users_map = get_users(api_key_input)
        st.info(f"Loaded {len(agents_map)} agents and {len(users_map)} users for name mapping.")
        
        # Run Sync
        manager.sync(api_key_input, url_base, agents_map, users_map)

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
