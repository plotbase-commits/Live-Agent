import streamlit as st
import os
import json
import threading
from src.config import VAS_API_KLUC
from src.sheets_manager import SheetSyncManager
from src.backend import ETLService, AnalysisService, ArchivingService
from src.job_status import get_status, get_logs, clear_logs, add_log, display_log_window
from src.scheduler import SchedulerService, display_scheduler_status

st.set_page_config(page_title="Admin Settings", layout="wide")
st.title("⚙️ Admin Settings")

# --- Helper Functions ---
def run_in_background(func, *args):
    """Runs a function in a background thread."""
    thread = threading.Thread(target=func, args=args, daemon=True)
    thread.start()
    return thread

# --- Config vars ---
creds_file = "credentials.json"
sheet_name = "LiveAgent Tickets"
api_key = VAS_API_KLUC

# ==========================================
# JOB STATUS BAR (Always visible at top)
# ==========================================
st.header("📊 Job Status")

status_col1, status_col2 = st.columns([3, 1])

with status_col1:
    statuses = get_status()
    if statuses:
        for job_name, info in statuses.items():
            status = info.get("status", "idle")
            progress = info.get("progress", 0)
            message = info.get("message", "")
            updated = info.get("updated_at", "")
            
            col_a, col_b = st.columns([1, 4])
            with col_a:
                if status == "running":
                    st.markdown(f"**{job_name}** 🟢")
                elif status == "completed":
                    st.markdown(f"**{job_name}** ✅")
                elif status == "error":
                    st.markdown(f"**{job_name}** ❌")
                else:
                    st.markdown(f"**{job_name}** ⚪")
            with col_b:
                if status == "running":
                    st.progress(progress / 100)
                st.caption(f"{message} ({updated})" if updated else message)
    else:
        st.info("Žiadne aktívne joby")

with status_col2:
    if st.button("🔄 Refresh"):
        st.rerun()

st.markdown("---")

# ==========================================
# TABS
# ==========================================
tab_manual, tab_scheduler, tab_logs, tab_config = st.tabs([
    "🎮 Manual Controls", 
    "⏰ Scheduler", 
    "📋 Logs",
    "⚙️ Configuration"
])

# ==========================================
# TAB 1: MANUAL CONTROLS
# ==========================================
with tab_manual:
    col_etl, col_ai = st.columns(2)
    
    with col_etl:
        with st.container(border=True):
            st.subheader("📥 ETL Pipeline")
            st.caption("Stiahne nové tikety z LiveAgent do Raw_Tickets")
            if st.button("▶️ Run ETL", use_container_width=True, key="btn_etl"):
                if not os.path.exists(creds_file):
                    st.error("Credentials file not found.")
                else:
                    def etl_task():
                        try:
                            sm = SheetSyncManager(creds_file, sheet_name, None, None)
                            etl = ETLService(api_key, sm)
                            etl.run_etl_cycle()
                        except Exception as e:
                            add_log(f"ETL Error: {e}")
                    run_in_background(etl_task)
                    st.success("✅ ETL spustený na pozadí!")

    with col_ai:
        with st.container(border=True):
            st.subheader("🤖 AI Analysis")
            st.caption("Analyzuje nespracované tikety pomocou AI")
            if st.button("▶️ Run Analysis", use_container_width=True, key="btn_ai"):
                if not os.path.exists(creds_file):
                    st.error("Credentials file not found.")
                else:
                    qa, alert = "", ""
                    if os.path.exists("prompts.json"):
                        with open("prompts.json", "r") as f:
                            data = json.load(f)
                            qa = data.get("qa_prompt", "")
                            alert = data.get("alert_prompt", "")
                    
                    def analysis_task():
                        try:
                            sm = SheetSyncManager(creds_file, sheet_name, None, None)
                            svc = AnalysisService(sm, qa, alert)
                            svc.run_analysis_cycle()
                        except Exception as e:
                            add_log(f"Analysis Error: {e}")
                    run_in_background(analysis_task)
                    st.success("✅ AI Analysis spustený na pozadí!")

    col_stats, col_archive = st.columns(2)

    with col_stats:
        with st.container(border=True):
            st.subheader("📈 Daily Stats")
            st.caption("Agreguje denné štatistiky agentov")
            if st.button("▶️ Run Stats", use_container_width=True, key="btn_stats"):
                with st.spinner("Agregácia..."):
                    try:
                        sm = SheetSyncManager(creds_file, sheet_name, None, None)
                        svc = AnalysisService(sm, "", "")
                        svc.run_daily_aggregation()
                        st.success("✅ Hotovo!")
                    except Exception as e:
                        st.error(f"Error: {e}")

    with col_archive:
        with st.container(border=True):
            st.subheader("🗄️ Archiving")
            st.caption("Presunie staré tikety do mesačných archívov")
            if st.button("▶️ Run Archive", use_container_width=True, key="btn_archive"):
                with st.spinner("Archivácia..."):
                    try:
                        sm = SheetSyncManager(creds_file, sheet_name, None, None)
                        svc = ArchivingService(sm)
                        svc.run_archiving()
                        st.success("✅ Hotovo!")
                    except Exception as e:
                        st.error(f"Error: {e}")

# ==========================================
# TAB 2: SCHEDULER
# ==========================================
with tab_scheduler:
    sched_col1, sched_col2, sched_col3 = st.columns([2, 1, 1])

    with sched_col1:
        display_scheduler_status()

    with sched_col2:
        if st.button("▶️ Start Scheduler", type="primary", use_container_width=True, key="btn_start_sched"):
            scheduler = SchedulerService()
            
            def etl_job():
                try:
                    sm = SheetSyncManager(creds_file, sheet_name, None, None)
                    etl = ETLService(api_key, sm)
                    etl.run_etl_cycle()
                except Exception as e:
                    add_log(f"ETL Error: {e}")
            
            def analysis_job():
                try:
                    qa, alert = "", ""
                    if os.path.exists("prompts.json"):
                        with open("prompts.json", "r") as f:
                            d = json.load(f)
                            qa = d.get("qa_prompt", "")
                            alert = d.get("alert_prompt", "")
                    sm = SheetSyncManager(creds_file, sheet_name, None, None)
                    svc = AnalysisService(sm, qa, alert)
                    svc.run_analysis_cycle()
                except Exception as e:
                    add_log(f"Analysis Error: {e}")
            
            scheduler.add_etl_job(etl_job)
            scheduler.add_analysis_job(analysis_job)
            st.success("Scheduler started!")
            st.rerun()

    with sched_col3:
        if st.button("⏹️ Stop Scheduler", use_container_width=True, key="btn_stop_sched"):
            scheduler = SchedulerService()
            scheduler.remove_all_jobs()
            st.warning("Scheduler stopped.")
            st.rerun()

# ==========================================
# TAB 3: LOGS (original style)
# ==========================================
with tab_logs:
    display_log_window()

# ==========================================
# TAB 4: CONFIGURATION
# ==========================================
with tab_config:
    st.subheader("📝 AI Prompts")
    
    PROMPTS_FILE = "prompts.json"
    
    def load_prompts():
        if os.path.exists(PROMPTS_FILE):
            with open(PROMPTS_FILE, "r") as f:
                return json.load(f)
        return {"qa_prompt": "", "alert_prompt": ""}
    
    prompts = load_prompts()
    
    prompt_qa = st.text_area("QA Prompt", value=prompts.get("qa_prompt", ""), height=150, key="qa_prompt")
    prompt_alert = st.text_area("Alert Prompt", value=prompts.get("alert_prompt", ""), height=150, key="alert_prompt")
    
    if st.button("💾 Save Prompts", key="btn_save_prompts"):
        with open(PROMPTS_FILE, "w") as f:
            json.dump({"qa_prompt": prompt_qa, "alert_prompt": prompt_alert}, f, indent=4, ensure_ascii=False)
        st.success("Prompts saved!")
    
    st.markdown("---")
    st.subheader("📧 Email Alerts")
    
    EMAIL_CONFIG_FILE = "email_config.json"
    
    def load_email():
        if os.path.exists(EMAIL_CONFIG_FILE):
            with open(EMAIL_CONFIG_FILE, "r") as f:
                return json.load(f)
        return {"recipients": [], "subject_template": "", "body_template": ""}
    
    email_cfg = load_email()
    
    recipients = st.text_area("Recipients (comma separated)", value=", ".join(email_cfg.get("recipients", [])), key="email_recipients")
    subject = st.text_input("Subject Template", value=email_cfg.get("subject_template", ""), key="email_subject")
    body = st.text_area("Body Template", value=email_cfg.get("body_template", ""), height=100, key="email_body")
    
    st.caption("Variables: `{ticket_id}`, `{agent_name}`, `{alert_reason}`, `{ticket_url}`")
    
    if st.button("💾 Save Email Config", key="btn_save_email"):
        recipient_list = [r.strip() for r in recipients.replace('\n', ',').split(',') if r.strip()]
        with open(EMAIL_CONFIG_FILE, "w") as f:
            json.dump({"recipients": recipient_list, "subject_template": subject, "body_template": body}, f, indent=4)
        st.success("Email config saved!")
    
    st.markdown("---")
    st.subheader("🔑 API & Connections")
    
    st.text_input("LiveAgent API Key", value=VAS_API_KLUC, type="password", disabled=True, key="api_key")
    st.text_input("Google Sheet Name", value=sheet_name, disabled=True, key="sheet_name")
    st.text_input("Credentials File", value=creds_file, disabled=True, key="creds_file")
    st.caption("⚠️ Tieto hodnoty sú načítané z konfigurácie a nie sú editovateľné v UI.")
