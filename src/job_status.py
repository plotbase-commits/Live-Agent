"""
Job Status Manager - tracks background job status across pages.
"""
import json
import os
from datetime import datetime

STATUS_FILE = "job_status.json"
LOG_FILE = "job_logs.txt"
MAX_LOG_LINES = 100

def get_status():
    """Returns current job statuses."""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def set_status(job_name, status, progress=0, message=""):
    """Updates status for a specific job."""
    all_status = get_status()
    all_status[job_name] = {
        "status": status,
        "progress": progress,
        "message": message,
        "updated_at": datetime.now().strftime("%H:%M:%S")
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(all_status, f, indent=2)
    
    # Also log to file
    add_log(f"[{job_name}] {status.upper()}: {message}")

def add_log(message):
    """Adds a log entry."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    
    # Read existing logs
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            logs = f.readlines()
    
    # Keep only last N lines
    logs.append(log_line)
    if len(logs) > MAX_LOG_LINES:
        logs = logs[-MAX_LOG_LINES:]
    
    # Write back
    with open(LOG_FILE, "w") as f:
        f.writelines(logs)

def get_logs():
    """Returns all logs (newest first)."""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            # Reverse to show newest first
            return "".join(reversed(lines))
    return "No logs yet."

def clear_logs():
    """Clears all logs."""
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

def clear_status(job_name):
    """Clears status for a specific job."""
    all_status = get_status()
    if job_name in all_status:
        del all_status[job_name]
        with open(STATUS_FILE, "w") as f:
            json.dump(all_status, f, indent=2)

def display_status_sidebar():
    """Legacy function - now just a passthrough."""
    pass  # Status is now in main content

def display_job_status():
    """Displays job status in main content with auto-refresh."""
    import streamlit as st
    
    @st.fragment(run_every=5)  # Auto-refresh every 5 seconds
    def _status_fragment():
        statuses = get_status()
        
        if not statuses:
            st.info("🔄 No background jobs running")
            return
        
        # Check if any job is running
        any_running = any(info.get("status") == "running" for info in statuses.values())
        
        # Create columns for better layout
        cols = st.columns(len(statuses))
        
        for i, (job_name, info) in enumerate(statuses.items()):
            with cols[i]:
                status = info.get("status", "idle")
                progress = info.get("progress", 0)
                message = info.get("message", "")
                updated = info.get("updated_at", "")
                
                if status == "running":
                    st.markdown(f"### {job_name} 🟢")
                    st.progress(progress / 100)
                    st.caption(f"{message}")
                    st.caption(f"Updated: {updated}")
                elif status == "completed":
                    st.markdown(f"### {job_name} ✅")
                    st.success(f"{message}")
                elif status == "error":
                    st.markdown(f"### {job_name} ❌")
                    st.error(f"{message}")
        
        if any_running:
            st.caption("⏳ Auto-refreshing every 5 seconds...")
    
    # Render the fragment
    st.subheader("🔄 Background Jobs")
    _status_fragment()

def display_log_window():
    """Displays scrollable log window."""
    import streamlit as st
    
    st.subheader("📋 Job Logs")
    
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🗑️ Clear Logs"):
            clear_logs()
            st.rerun()
    
    logs = get_logs()
    
    # Scrollable container with fixed height
    st.markdown("""
    <style>
    .log-container {
        background-color: #1e1e2e;
        color: #00ff00;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        padding: 10px;
        border-radius: 8px;
        height: 300px;
        overflow-y: auto;
        white-space: pre-wrap;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown(f'<div class="log-container">{logs}</div>', unsafe_allow_html=True)
