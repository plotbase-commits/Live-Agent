import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import datetime
import time
import re
from src.utils import convert_utc_to_local, process_transcript
from src.api import get_liveagent_tickets, get_ticket_messages
from src.config import SCOPES

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
        
        # New QA System Headers
        self.raw_tickets_headers = [
            'Ticket_ID', 'Agent', 'Date_Created', 'Transcript', 
            'AI_Processed', 'Is_Critical', 'QA_Score', 'QA_Data', 'Alert_Reason'
        ]
        self.daily_stats_headers = [
            'Date', 'Agent', 'Avg_Score', 'Critical_Count', 
            'Avg_Empathy', 'Avg_Expertise', 'Verbal_Summary'
        ]

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

    def ensure_qa_sheets(self):
        """Ensures Raw_Tickets and Daily_Stats sheets exist."""
        # 1. Raw_Tickets
        try:
            ws = self.spreadsheet.worksheet("Raw_Tickets")
            # Check if empty (no headers)
            if not ws.get_all_values():
                ws.append_row([
                    "Ticket_ID", 
                    "Link",
                    "Agent", 
                    "Date_Changed",
                    "Date_Created", 
                    "Transcript", 
                    "AI_Processed", 
                    "Is_Critical", 
                    "QA_Score", 
                    "QA_Data", 
                    "Alert_Reason"
                ])
                ws.freeze(rows=1)
        except:
            ws = self.spreadsheet.add_worksheet("Raw_Tickets", 1000, 20)
            ws.append_row([
                "Ticket_ID", 
                "Link",
                "Agent", 
                "Date_Changed",
                "Date_Created", 
                "Transcript", 
                "AI_Processed", 
                "Is_Critical", 
                "QA_Score", 
                "QA_Data", 
                "Alert_Reason"
            ])
            ws.freeze(rows=1)
            
        # Daily_Stats
        try:
            ws = self.spreadsheet.worksheet("Daily_Stats")
            if not ws.get_all_values():
                ws.append_row(self.daily_stats_headers)
                ws.freeze(rows=1)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet("Daily_Stats", rows=1000, cols=len(self.daily_stats_headers))
            ws.append_row(self.daily_stats_headers)
            ws.freeze(rows=1)

    def get_raw_tickets_ids(self):
        """Returns a set of Ticket IDs already in Raw_Tickets."""
        try:
            ws = self.spreadsheet.worksheet("Raw_Tickets")
            # Assuming Ticket_ID is the first column
            ids = ws.col_values(1)
            return set(ids[1:]) # Skip header
        except gspread.WorksheetNotFound:
            return set()

    def append_raw_tickets(self, tickets_data):
        """
        Appends new tickets to Raw_Tickets sheet.
        tickets_data: list of lists matching raw_tickets_headers
        """
        if not tickets_data:
            return
            
        try:
            ws = self.spreadsheet.worksheet("Raw_Tickets")
            ws.append_rows(tickets_data)
        except Exception as e:
            st.error(f"Error appending to Raw_Tickets: {e}")

    def archive_rows_to_month(self, month_str, rows):
        """Appends rows to a specific monthly sheet (YYYY-MM)."""
        ws = self._ensure_sheet_exists(month_str)
        if rows:
            ws.append_rows(rows)

    def rewrite_raw_tickets(self, rows):
        """Overwrites Raw_Tickets with the provided rows (keeping headers)."""
        ws = self.spreadsheet.worksheet("Raw_Tickets")
        ws.clear()
        
        headers = [
            "Ticket_ID", "Link", "Agent", "Date_Changed", "Date_Created", 
            "Transcript", "AI_Processed", "Is_Critical", "QA_Score", 
            "QA_Data", "Alert_Reason"
        ]
        
        data_to_write = [headers] + rows
        ws.update("A1", data_to_write)
        ws.freeze(rows=1)

    def update_daily_stats(self, new_stats):
        """
        Updates Daily_Stats. 
        Removes existing entries for the same Date+Agent to avoid duplicates.
        new_stats: list of lists [Date, Agent, Avg_Score, ...]
        """
        try:
            ws = self.spreadsheet.worksheet("Daily_Stats")
        except:
            self.ensure_qa_sheets()
            ws = self.spreadsheet.worksheet("Daily_Stats")
            
        existing_data = ws.get_all_values()
        if not existing_data:
            return

        headers = existing_data[0]
        data_rows = existing_data[1:]
        
        # Create a set of (Date, Agent) from new stats for quick lookup
        # Assuming Date is col 0, Agent is col 1
        keys_to_update = set((row[0], row[1]) for row in new_stats)
        
        # Filter out rows that match the keys we are updating
        filtered_rows = []
        for row in data_rows:
            if len(row) >= 2:
                key = (row[0], row[1])
                if key not in keys_to_update:
                    filtered_rows.append(row)
        
        # Combine filtered old rows with new rows
        final_rows = [headers] + filtered_rows + new_stats
        
        # Write back
        ws.clear()
        ws.update("A1", final_rows)
        ws.freeze(rows=1)
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
                # Filter logic - only email tickets with specific statuses
                if t.get('status') in ['A', 'R', 'W'] and t.get('channel_type') == 'E':
                    all_tickets.append(t)
            
            page += 1
            self.status_text.text(f"Fetching page {page}... ({len(all_tickets)} tickets so far)")
            time.sleep(1.0)  # Rate limit between pages

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
        
        for sheet_name, ops in operations.items():
            if not ops['delete'] and not ops['update'] and not ops['append']:
                continue
                
            ws = self._ensure_sheet_exists(sheet_name)
            
            # Batch Delete
            if ops['delete']:
                # Sort descending to delete from bottom up
                rows_to_delete = sorted(list(set(ops['delete'])), reverse=True)
                
                # Construct batch request for deletion
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
