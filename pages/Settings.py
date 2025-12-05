import streamlit as st
import os
import json
import threading
from src.config import VAS_API_KLUC, LIVEAGENT_API_URL
from src.sheets_manager import SheetSyncManager
from src.backend import ETLService, AnalysisService, ArchivingService
from src.job_status import display_status_sidebar, display_log_window
from src.scheduler import SchedulerService, display_scheduler_status

st.set_page_config(page_title="Admin Settings", layout="wide")

# Display background job status in sidebar
display_status_sidebar()

st.title("⚙️ Admin Settings")

# --- Helper Functions ---
def run_in_background(func, *args):
    """Runs a function in a background thread."""
    thread = threading.Thread(target=func, args=args, daemon=True)
    thread.start()
    return thread

# --- Layout Containers (Order: Manual, Logs, Scheduler, Prompts, Email, Config) ---
cont_manual = st.container()
cont_logs = st.container()
cont_scheduler = st.container()
cont_prompts = st.container()
cont_email = st.container()
cont_config = st.container()

# ==========================================
# 1. Configuration (Runs first to define vars, Renders last)
# ==========================================
with cont_config:
    st.header("Configuration")
    with st.expander("API Keys & Connections", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            api_key = st.text_input("LiveAgent API Key", value=VAS_API_KLUC, type="password")
            sheet_name = st.text_input("Google Sheet Name", value="LiveAgent Tickets")
        with col2:
            creds_file = st.text_input("Credentials File", value="credentials.json")
            model_name = st.selectbox("AI Model", ["gemini-1.5-pro", "gpt-4o"])

# ==========================================
# 2. Prompt Editor (Runs second, Renders 4th)
# ==========================================
with cont_prompts:
    st.header("Prompt Editor")
    
    PROMPTS_FILE = "prompts.json"
    
    def load_prompts():
        if os.path.exists(PROMPTS_FILE):
            with open(PROMPTS_FILE, "r") as f:
                return json.load(f)
        return {
            "qa_prompt": "Analyze the agent's empathy...",
            "alert_prompt": "Identify any critical issues..."
        }
    
    def save_prompts(qa, alert):
        with open(PROMPTS_FILE, "w") as f:
            json.dump({"qa_prompt": qa, "alert_prompt": alert}, f, indent=4)
        st.success("Prompts saved successfully!")
    
    # Load current prompts
    current_prompts = load_prompts()
    
    with st.expander("Edit AI Prompts", expanded=True):
        prompt_qa = st.text_area("QA Prompt", value=current_prompts.get("qa_prompt", ""), height=200)
        prompt_alert = st.text_area("Alert Prompt", value=current_prompts.get("alert_prompt", ""), height=150)
        
        if st.button("💾 Save Prompts"):
            save_prompts(prompt_qa, prompt_alert)

# ==========================================
# 3. Email Config (Runs third, Renders 5th)
# ==========================================
with cont_email:
    st.header("📧 Email Alerts Configuration")
    
    EMAIL_CONFIG_FILE = "email_config.json"
    
    def load_email_config():
        if os.path.exists(EMAIL_CONFIG_FILE):
            with open(EMAIL_CONFIG_FILE, "r") as f:
                return json.load(f)
        return {
            "recipients": ["admin@example.com"],
            "subject_template": "🚨 Alert: Ticket {ticket_id}",
            "body_template": "Critical issue detected..."
        }
    
    def save_email_config(recipients, subject, body):
        # Split recipients by comma/newline and clean up
        recipient_list = [r.strip() for r in recipients.replace('\n', ',').split(',') if r.strip()]
        with open(EMAIL_CONFIG_FILE, "w") as f:
            json.dump({
                "recipients": recipient_list,
                "subject_template": subject,
                "body_template": body
            }, f, indent=4)
        st.success("Email configuration saved!")
    
    email_config = load_email_config()
    
    with st.expander("Configure Email Alerts"):
        recipients_input = st.text_area("Recipients (comma separated)", value=", ".join(email_config.get("recipients", [])))
        subject_input = st.text_input("Subject Template", value=email_config.get("subject_template", ""))
        body_input = st.text_area("Body Template", value=email_config.get("body_template", ""), height=200)
        
        st.caption("Variables: `{ticket_id}`, `{agent_name}`, `{alert_reason}`")
        
        if st.button("💾 Save Email Config"):
            save_email_config(recipients_input, subject_input, body_input)

# ==========================================
# 4. Manual Controls (Runs fourth, Renders 1st)
# ==========================================
with cont_manual:
    st.header("Manual Controls")
    col_etl, col_ai = st.columns(2)
    
    with col_etl:
        st.subheader("Data Pipeline (ETL)")
        st.write("Fetches new tickets and saves to Raw_Tickets.")
        if st.button("Run ETL Now"):
            if not os.path.exists(creds_file):
                st.error("Credentials file not found.")
            else:
                def etl_task_wrapper():
                    try:
                        sheet_manager_etl = SheetSyncManager(creds_file, sheet_name, None, None)
                        etl_service = ETLService(api_key, sheet_manager_etl)
                        etl_service.run_etl_cycle()
                        print("ETL completed successfully!")
                    except Exception as e:
                        print(f"ETL Error: {e}")
                
                run_in_background(etl_task_wrapper)
                st.success("✅ ETL beží na pozadí! Môžeš navigovať na iné stránky.")
    
    with col_ai:
        st.subheader("AI Analysis")
        st.write("Analyzes unprocessed tickets in Raw_Tickets.")
        if st.button("Run AI Analysis Now"):
            if not os.path.exists(creds_file):
                st.error("Credentials file not found.")
            else:
                def analysis_task_wrapper():
                    try:
                        sheet_manager_ai = SheetSyncManager(creds_file, sheet_name, None, None)
                        # Uses prompts defined above
                        analysis_service = AnalysisService(sheet_manager_ai, prompt_qa, prompt_alert)
                        analysis_service.run_analysis_cycle()
                        print("AI Analysis completed successfully!")
                    except Exception as e:
                        print(f"Analysis Error: {e}")
                
                run_in_background(analysis_task_wrapper)
                st.success("✅ AI Analysis beží na pozadí! Môžeš navigovať na iné stránky.")
    
    col_stats, col_archive = st.columns(2)
    
    with col_stats:
        st.subheader("Daily Stats Aggregation")
        st.write("Calculates daily stats and updates Daily_Stats.")
        if st.button("Run Daily Stats Now"):
            if not os.path.exists(creds_file):
                st.error("Credentials file not found.")
            else:
                status_text = st.empty()
                progress_bar = st.progress(0)
                sheet_manager_stats = SheetSyncManager(creds_file, sheet_name, status_text, progress_bar)
                
                analysis_service_stats = AnalysisService(sheet_manager_stats, "", "")
                
                with st.spinner("Aggregating Daily Stats..."):
                    analysis_service_stats.run_daily_aggregation()
    
    with col_archive:
        st.subheader("Data Archiving")
        st.write("Moves tickets older than 2 days to monthly sheets.")
        if st.button("Run Archiving Now"):
            if not os.path.exists(creds_file):
                st.error("Credentials file not found.")
            else:
                status_text = st.empty()
                progress_bar = st.progress(0)
                sheet_manager_arch = SheetSyncManager(creds_file, sheet_name, status_text, progress_bar)
                
                archiving_service = ArchivingService(sheet_manager_arch)
                
                with st.spinner("Archiving old tickets..."):
                    archiving_service.run_archiving()

# ==========================================
# 5. Job Logs (Renders 2nd)
# ==========================================
with cont_logs:
    st.markdown("---")
    display_log_window()

# ==========================================
# 6. Scheduler (Renders 3rd)
# ==========================================
with cont_scheduler:
    st.header("⏰ Scheduler")
    
    display_scheduler_status()
    
    col_start, col_stop = st.columns(2)
    
    with col_start:
        if st.button("▶️ Start Scheduler", type="primary"):
            scheduler_service = SchedulerService()
            
            # Define job functions for scheduler
            def run_etl_background_job():
                try:
                    from src.sheets_manager import SheetSyncManager as SM
                    from src.backend import ETLService as ETLS
                    # Re-instantiate to avoid thread issues with st-managed objects if any
                    sm = SM(creds_file, sheet_name, None, None)
                    etl = ETLS(api_key, sm)
                    etl.run_etl_cycle()
                except Exception as e:
                    print(f"ETL Error: {e}")
            
            def run_analysis_background_job():
                try:
                    from src.sheets_manager import SheetSyncManager as SM
                    from src.backend import AnalysisService as AS
                    import json as j
                    
                    # Load prompts fresh from file inside job
                    p_qa = "Analyze..."
                    p_alert = "Identify..."
                    if os.path.exists("prompts.json"):
                        with open("prompts.json", "r") as f:
                            data = j.load(f)
                            p_qa = data.get("qa_prompt", p_qa)
                            p_alert = data.get("alert_prompt", p_alert)
                    
                    sm = SM(creds_file, sheet_name, None, None)
                    analysis = AS(sm, p_qa, p_alert)
                    analysis.run_analysis_cycle()
                except Exception as e:
                    print(f"Analysis Error: {e}")
            
            scheduler_service.add_etl_job(run_etl_background_job)
            scheduler_service.add_analysis_job(run_analysis_background_job)
            st.success("Scheduler started! Jobs scheduled.")
            st.rerun()
    
    with col_stop:
        if st.button("⏹️ Stop Scheduler"):
            scheduler_service = SchedulerService()
            scheduler_service.remove_all_jobs()
            st.warning("All jobs removed.")
            st.rerun()
