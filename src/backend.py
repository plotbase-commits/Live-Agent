import streamlit as st
import time
import json
import gspread
import os
from src.api import get_liveagent_tickets, get_ticket_messages
from src.utils import process_transcript, get_agents, get_users, convert_utc_to_local, is_human_interaction
from src.ai_service import AIService
from src.alerting import EmailService
from src.job_status import set_status, clear_status, add_log

class ETLService:
    def __init__(self, api_key, sheet_manager):
        self.api_key = api_key
        self.sheet_manager = sheet_manager

    def run_etl_cycle(self):
        """
        Runs the ETL cycle:
        1. Fetch last 100 tickets.
        2. Filter duplicates.
        3. Fetch transcripts.
        4. Save to Raw_Tickets.
        """
        set_status("ETL", "running", 0, "Starting...")
        
        try:
            st.write("Starting ETL Cycle...")
            
            # 0. Connect to Google Sheets
            if not self.sheet_manager.connect():
                st.error("Failed to connect to Google Sheets!")
                set_status("ETL", "error", 0, "Failed to connect")
                return
            
            # 1. Ensure Sheets Exist
            self.sheet_manager.ensure_qa_sheets()
            
            # 2. Get Existing IDs
            existing_ids = self.sheet_manager.get_raw_tickets_ids()
            st.write(f"Found {len(existing_ids)} existing tickets in Raw_Tickets.")
            
            # 3. Fetch Metadata (Agents/Users)
            agents_map = get_agents(self.api_key)
            users_map = get_users(self.api_key)
            
            # 4. Fetch New Tickets (Last 100)
            new_tickets_data = []
            set_status("ETL", "running", 20, "Fetching tickets...")
            
            for page in range(1, 6):
                tickets = get_liveagent_tickets(self.api_key, page=page, per_page=20)
                if not tickets:
                    break
                
                set_status("ETL", "running", 20 + page * 10, f"Page {page}/5...")
                add_log(f"ETL: Fetching page {page}...")
                
                for ticket in tickets:
                    ticket_id = str(ticket.get('id'))
                    
                    # Skip if already exists
                    if ticket_id in existing_ids:
                        continue
                    
                    # Skip if already processed in this cycle
                    if any(t[0] == ticket_id for t in new_tickets_data):
                        continue

                    # Fetch Transcript
                    time.sleep(0.1)
                    messages = get_ticket_messages(self.api_key, ticket_id)
                    
                    # Filter Non-Human Tickets
                    if not is_human_interaction(messages, agents_map):
                        add_log(f"ETL: Skipped {ticket_id} (no human)")
                        continue

                    transcript = process_transcript(messages, agents_map, users_map)
                    
                    # Prepare Row
                    agent_name = ticket.get('agent_name', 'Unknown')
                    if not agent_name or agent_name == 'Unknown':
                        agent_id = ticket.get('agent_id')
                        if agent_id and str(agent_id) in agents_map:
                            agent_name = agents_map[str(agent_id)]
                    
                    ticket_link = f"https://plotbase.ladesk.com/agent/#/Ticket;{ticket_id}"
                    
                    row = [
                        ticket_id,
                        ticket_link,
                        agent_name,
                        convert_utc_to_local(ticket.get('date_changed')),
                        convert_utc_to_local(ticket.get('date_created')),
                        transcript,
                        "FALSE",
                        "FALSE",
                        "",
                        "",
                        ""
                    ]
                    
                    new_tickets_data.append(row)
                    add_log(f"ETL: Added ticket {ticket_id} ({agent_name})")
                
                # Rate limit between pages
                time.sleep(0.5)
            
            # 5. Save to Sheet
            if new_tickets_data:
                set_status("ETL", "running", 90, f"Saving {len(new_tickets_data)} tickets...")
                st.write(f"Saving {len(new_tickets_data)} new tickets to Raw_Tickets...")
                self.sheet_manager.append_raw_tickets(new_tickets_data)
                set_status("ETL", "completed", 100, f"Done! {len(new_tickets_data)} new tickets.")
                st.success("ETL Cycle Completed Successfully.")
            else:
                set_status("ETL", "completed", 100, "No new tickets found.")
                st.info("No new tickets found.")
                
        except Exception as e:
            set_status("ETL", "error", 0, str(e))
            raise

class AnalysisService:
    def __init__(self, sheet_manager, prompt_qa, prompt_alert):
        self.sheet_manager = sheet_manager
        self.ai_service = AIService()
        self.email_service = EmailService()
        self.prompt_qa = prompt_qa
        self.prompt_alert = prompt_alert

    def run_analysis_cycle(self):
        """
        Runs the AI Analysis cycle:
        1. Read unprocessed rows from Raw_Tickets.
        2. Analyze with AI.
        3. Update Sheet.
        4. Send Alerts.
        """
        set_status("Analysis", "running", 0, "Starting...")
        add_log("Analysis: Starting AI Analysis cycle")
        
        try:
            st.write("Starting AI Analysis Cycle...")
            
            # 0. Connect to Google Sheets
            if not self.sheet_manager.connect():
                st.error("Failed to connect to Google Sheets!")
                set_status("Analysis", "error", 0, "Failed to connect")
                return
            
            # 1. Get Unprocessed Tickets
            ws = self.sheet_manager.spreadsheet.worksheet("Raw_Tickets")
            all_values = ws.get_all_values()
            
            if not all_values:
                set_status("Analysis", "completed", 100, "No data in sheet")
                return
                
            headers = all_values[0]
            
            # Find column indices
            try:
                idx_id = headers.index("Ticket_ID")
                idx_transcript = headers.index("Transcript")
                idx_processed = headers.index("AI_Processed")
                idx_critical = headers.index("Is_Critical")
                idx_score = headers.index("QA_Score")
                idx_data = headers.index("QA_Data")
                idx_reason = headers.index("Alert_Reason")
            except ValueError as e:
                st.error(f"Headers missing in Raw_Tickets: {e}")
                set_status("Analysis", "error", 0, "Headers missing")
                return

            updates = []
            alerts_data = []
            processed_count = 0
            total_unprocessed = len([row for row in all_values[1:] if len(row) > idx_processed and row[idx_processed] != "TRUE"])
            
            add_log(f"Analysis: Found {total_unprocessed} unprocessed tickets")
            
            for i, row in enumerate(all_values):
                if i == 0:
                    continue
                
                # Check if processed
                if len(row) > idx_processed and row[idx_processed] == "TRUE":
                    continue
                
                # Get transcript
                transcript = row[idx_transcript] if len(row) > idx_transcript else ""
                ticket_id = row[idx_id] if len(row) > idx_id else "Unknown"
                
                if not transcript:
                    continue
                
                progress = int((processed_count / max(total_unprocessed, 1)) * 80) + 10
                set_status("Analysis", "running", progress, f"Analyzing {ticket_id}...")
                add_log(f"Analysis: Analyzing ticket {ticket_id}")
                
                st.write(f"Analyzing Ticket {ticket_id}...")
                result = self.ai_service.analyze_ticket(transcript, self.prompt_qa, self.prompt_alert)
                
                if result:
                    processed_count += 1
                    
                    qa_data = result.get("qa_data", {})
                    alert_data = result.get("alert_data", {})
                    
                    is_critical = str(alert_data.get("is_critical", False)).upper()
                    alert_reason = alert_data.get("reason", "") or ""
                    qa_score = qa_data.get("overall_score", 0)
                    qa_json = json.dumps(qa_data)
                    
                    row_num = i + 1
                    
                    updates.append({'range': gspread.utils.rowcol_to_a1(row_num, idx_processed + 1), 'values': [["TRUE"]]})
                    updates.append({'range': gspread.utils.rowcol_to_a1(row_num, idx_critical + 1), 'values': [[is_critical]]})
                    updates.append({'range': gspread.utils.rowcol_to_a1(row_num, idx_score + 1), 'values': [[qa_score]]})
                    updates.append({'range': gspread.utils.rowcol_to_a1(row_num, idx_data + 1), 'values': [[qa_json]]})
                    updates.append({'range': gspread.utils.rowcol_to_a1(row_num, idx_reason + 1), 'values': [[alert_reason]]})
                    
                    add_log(f"Analysis: Ticket {ticket_id} - Score: {qa_score}, Critical: {is_critical}")
                    
                    if is_critical == "TRUE":
                        alerts_data.append({
                            "ticket_id": ticket_id,
                            "agent_name": row[2] if len(row) > 2 else "Unknown",
                            "reason": alert_reason
                        })
            
            # Batch Update Sheet
            if updates:
                st.write(f"Updating {processed_count} tickets in Sheets...")
                ws.batch_update(updates)
            
            # Send Alerts
            if alerts_data:
                st.warning(f"Sending {len(alerts_data)} critical alerts...")
                email_config = {"recipients": [], "subject_template": "Alert: {ticket_id}", "body_template": "{alert_reason}"}
                if os.path.exists("email_config.json"):
                    with open("email_config.json", "r") as f:
                        email_config = json.load(f)
                
                recipients = email_config.get("recipients", [])
                if recipients:
                    for alert in alerts_data:
                        try:
                            subject = email_config.get("subject_template", "").format(**alert)
                            body = email_config.get("body_template", "").format(**alert)
                            self.email_service.send_alert(recipients, subject, body)
                            add_log(f"Analysis: Alert sent for {alert['ticket_id']}")
                        except Exception as e:
                            add_log(f"Analysis: Alert failed - {e}")
            
            set_status("Analysis", "completed", 100, f"Done! {processed_count} tickets analyzed.")
            add_log(f"Analysis: Completed. {processed_count} tickets processed.")
            st.success(f"Analysis Complete. Processed {processed_count} tickets.")
            
        except Exception as e:
            set_status("Analysis", "error", 0, str(e))
            add_log(f"Analysis: Error - {e}")
            st.error(f"Error in Analysis Cycle: {e}")

    def run_daily_aggregation(self):
        """
        Calculates daily statistics for agents and updates Daily_Stats sheet.
        Handles deduplication by overwriting entries for the same Date+Agent.
        """
        st.write("Starting Daily Stats Aggregation...")
        
        if not self.sheet_manager.connect():
            st.error("Failed to connect to Google Sheets!")
            return

        try:
            ws = self.sheet_manager.spreadsheet.worksheet("Raw_Tickets")
            data = ws.get_all_records()
            
            if not data:
                st.warning("No data in Raw_Tickets to aggregate.")
                return

            # Group by (Date, Agent)
            stats = {}
            
            for row in data:
                # Parse Date_Changed (YYYY-MM-DD HH:MM:SS) -> YYYY-MM-DD
                date_str = row.get("Date_Changed", "")
                if not date_str:
                    continue
                try:
                    date_key = date_str.split(" ")[0]
                except:
                    continue
                
                agent = row.get("Agent", "Unknown")
                
                key = (date_key, agent)
                if key not in stats:
                    stats[key] = {
                        "total_score": 0,
                        "count": 0,
                        "critical_count": 0,
                        "empathy_sum": 0,
                        "expertise_sum": 0,
                        "summaries": []
                    }
                
                # Parse Score & Critical
                try:
                    qa_data = json.loads(row.get("QA_Data", "{}"))
                    score = qa_data.get("overall_score", 0)
                    criteria = qa_data.get("criteria", {})
                    
                    stats[key]["total_score"] += score
                    stats[key]["empathy_sum"] += criteria.get("empathy", 0)
                    stats[key]["expertise_sum"] += criteria.get("expertise", 0)
                    
                    summary = qa_data.get("verbal_summary", "")
                    if summary:
                        stats[key]["summaries"].append(summary)
                        
                except:
                    pass
                
                stats[key]["count"] += 1
                if str(row.get("Is_Critical", "")).upper() == "TRUE":
                    stats[key]["critical_count"] += 1
            
            # Prepare rows for Daily_Stats
            # Headers: Date, Agent, Avg_Score, Critical_Count, Avg_Empathy, Avg_Expertise, Verbal_Summary
            new_rows = []
            for (date, agent), data in stats.items():
                count = data["count"]
                if count == 0: continue
                
                avg_score = data["total_score"] / count
                avg_empathy = data["empathy_sum"] / count
                avg_expertise = data["expertise_sum"] / count
                
                # Pick the last summary or combine? Let's pick the last one for now.
                verbal_summary = data["summaries"][-1] if data["summaries"] else ""
                
                new_rows.append([
                    date,
                    agent,
                    round(avg_score, 1),
                    data["critical_count"],
                    round(avg_empathy, 1),
                    round(avg_expertise, 1),
                    verbal_summary
                ])
            
            if new_rows:
                st.write(f"Updating {len(new_rows)} daily stats records...")
                self.sheet_manager.update_daily_stats(new_rows)
                st.success("Daily Stats Updated.")
            else:
                st.info("No valid stats calculated.")
                
        except Exception as e:
            st.error(f"Error in Daily Aggregation: {e}")


class ArchivingService:
    def __init__(self, sheet_manager):
        self.sheet_manager = sheet_manager

    def run_archiving(self):
        """
        Moves tickets older than 2 days from Raw_Tickets to monthly archive sheets.
        """
        st.write("Starting Archiving Process...")
        
        if not self.sheet_manager.connect():
            st.error("Failed to connect to Google Sheets!")
            return

        try:
            ws = self.sheet_manager.spreadsheet.worksheet("Raw_Tickets")
            all_values = ws.get_all_values()
            
            if len(all_values) < 2:
                st.info("Raw_Tickets is empty.")
                return
                
            headers = all_values[0]
            data_rows = all_values[1:]
            
            try:
                idx_date = headers.index("Date_Changed")
            except ValueError:
                st.error("Column 'Date_Changed' not found.")
                return

            from datetime import datetime, timedelta
            
            cutoff_date = datetime.now() - timedelta(days=2)
            
            rows_to_keep = []
            archive_batches = {} # Key: "YYYY-MM", Value: [rows]
            
            archived_count = 0
            
            for row in data_rows:
                date_str = row[idx_date]
                should_archive = False
                
                try:
                    # Parse date (Format: YYYY-MM-DD HH:MM:SS)
                    ticket_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    
                    if ticket_date < cutoff_date:
                        should_archive = True
                        month_key = ticket_date.strftime("%Y-%m")
                        
                        if month_key not in archive_batches:
                            archive_batches[month_key] = []
                        archive_batches[month_key].append(row)
                        archived_count += 1
                except:
                    # If date parse fails, keep it in Raw (safe fallback)
                    pass
                
                if not should_archive:
                    rows_to_keep.append(row)
            
            # 1. Write to Archives
            for month, rows in archive_batches.items():
                st.write(f"Archiving {len(rows)} tickets to sheet '{month}'...")
                self.sheet_manager.archive_rows_to_month(month, rows)
            
            # 2. Update Raw_Tickets (Delete archived)
            if archived_count > 0:
                st.write(f"Removing {archived_count} archived tickets from Raw_Tickets...")
                self.sheet_manager.rewrite_raw_tickets(rows_to_keep)
                st.success(f"Archiving Complete. Moved {archived_count} tickets.")
            else:
                st.info("No tickets older than 2 days found.")
                
        except Exception as e:
            st.error(f"Error in Archiving: {e}")
