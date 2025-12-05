import streamlit as st
import json
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.job_status import display_status_sidebar, add_log
from src.scheduler import SchedulerService

st.set_page_config(page_title="QA Dashboard", layout="wide", page_icon="📊")

# --- AUTO-START SCHEDULER ---
@st.cache_resource
def init_scheduler():
    """Initialize and start scheduler with default jobs."""
    from src.sheets_manager import SheetSyncManager
    from src.backend import ETLService, AnalysisService
    from src.config import VAS_API_KLUC
    
    scheduler = SchedulerService()
    
    # Only add jobs if not already present
    if not scheduler.get_scheduler().get_job("etl_job"):
        def etl_job():
            try:
                sm = SheetSyncManager("credentials.json", "LiveAgent Tickets", None, None)
                etl = ETLService(VAS_API_KLUC, sm)
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
                sm = SheetSyncManager("credentials.json", "LiveAgent Tickets", None, None)
                svc = AnalysisService(sm, qa, alert)
                svc.run_analysis_cycle()
            except Exception as e:
                add_log(f"Analysis Error: {e}")
        
        scheduler.add_etl_job(etl_job)
        scheduler.add_analysis_job(analysis_job)
        add_log("Scheduler auto-started with ETL and Analysis jobs")
    
    return scheduler

# Initialize scheduler on app load
init_scheduler()

# Display background job status in sidebar
display_status_sidebar()

# --- Helper Functions ---
def get_status_icon(score, critical_ratio):
    """Returns status icon based on score and critical ratio."""
    # Critical ratio thresholds override score
    if critical_ratio > 0.10:  # More than 10% critical = always red
        return "🔴"
    elif critical_ratio > 0.05:  # 5-10% critical = warning
        return "⚠️"
    # Otherwise use score
    elif score >= 80:
        return "✅"
    elif score >= 60:
        return "⚠️"
    else:
        return "🔴"

def get_status_color(score, critical_ratio):
    """Returns color based on score and critical ratio."""
    if critical_ratio > 0.10:
        return "#ff4b4b"  # Red
    elif critical_ratio > 0.05:
        return "#ffaa00"  # Orange
    elif score >= 80:
        return "#00cc66"  # Green
    elif score >= 60:
        return "#ffaa00"  # Orange
    else:
        return "#ff4b4b"  # Red

def load_agent_stats():
    """Load agent statistics from Raw_Tickets sheet - CURRENT MONTH ONLY."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds_file = "credentials.json"
        if not os.path.exists(creds_file):
            return {}
        
        credentials = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        client = gspread.authorize(credentials)
        
        spreadsheet = client.open("LiveAgent Tickets")
        
        try:
            ws = spreadsheet.worksheet("Raw_Tickets")
        except:
            return {}
        
        data = ws.get_all_records()
        
        # Get current month for filtering
        current_month = datetime.now().strftime("%Y-%m")
        
        # Aggregate by agent
        agent_stats = {}
        for row in data:
            # Filter by current month (based on Date_Changed)
            date_changed = row.get("Date_Changed", "")
            if date_changed:
                try:
                    # Try to parse date and check if it's current month
                    # Format could be "2024-12-05 14:30" or similar
                    row_month = date_changed[:7]  # Get "YYYY-MM"
                    if row_month != current_month:
                        continue  # Skip tickets from other months
                except:
                    pass  # If date parsing fails, include the row
            
            agent = row.get("Agent", "Unknown")
            if not agent or agent == "Unknown" or agent == "Nepriradený":
                continue
            
            if agent not in agent_stats:
                agent_stats[agent] = {
                    "tickets": 0,
                    "analyzed_tickets": 0,
                    "total_score": 0,
                    "critical_count": 0,
                    "criteria": {"empathy": [], "expertise": [], "problem_solving": [], "error_rate": []},
                    "summaries": []
                }
            
            agent_stats[agent]["tickets"] += 1
            
            # Parse QA data
            qa_data_str = row.get("QA_Data", "")
            if qa_data_str:
                try:
                    qa_data = json.loads(qa_data_str)
                    score = qa_data.get("overall_score", 0)
                    agent_stats[agent]["total_score"] += score
                    agent_stats[agent]["analyzed_tickets"] += 1
                    
                    criteria = qa_data.get("criteria", {})
                    for key in ["empathy", "expertise", "problem_solving", "error_rate"]:
                        if key in criteria:
                            agent_stats[agent]["criteria"][key].append(criteria[key])
                    
                    summary = qa_data.get("verbal_summary", "")
                    if summary:
                        agent_stats[agent]["summaries"].append(summary)
                except:
                    pass
            
            # Check critical
            if str(row.get("Is_Critical", "")).upper() == "TRUE":
                agent_stats[agent]["critical_count"] += 1
        
        # Calculate averages
        for agent in agent_stats:
            stats = agent_stats[agent]
            if stats["analyzed_tickets"] > 0:
                stats["avg_score"] = stats["total_score"] / stats["analyzed_tickets"]
            else:
                stats["avg_score"] = 0
            
            for key in stats["criteria"]:
                if stats["criteria"][key]:
                    stats["criteria"][key] = sum(stats["criteria"][key]) / len(stats["criteria"][key])
                else:
                    stats["criteria"][key] = 0
            
            stats["has_critical"] = stats["critical_count"] > 0
            stats["critical_ratio"] = stats["critical_count"] / stats["tickets"] if stats["tickets"] > 0 else 0
        
        return agent_stats
    except Exception as e:
        st.error(f"Error loading stats: {e}")
        return {}

def create_agent_card(agent_name, stats):
    """Create an agent card with stats."""
    score = stats.get("avg_score", 0)
    tickets = stats.get("tickets", 0)
    analyzed = stats.get("analyzed_tickets", 0)
    critical_count = stats.get("critical_count", 0)
    critical_ratio = stats.get("critical_ratio", 0)
    criteria = stats.get("criteria", {})
    summaries = stats.get("summaries", [])
    
    status_icon = get_status_icon(score, critical_ratio)
    status_color = get_status_color(score, critical_ratio)
    critical_pct = critical_ratio * 100
    
    with st.container():
        # Header
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%); 
                    border-radius: 12px; padding: 20px; margin-bottom: 10px;
                    border-left: 4px solid {status_color};">
            <h3 style="margin: 0; color: white;">{status_icon} {agent_name}</h3>
            <p style="color: #888; margin: 5px 0;">Analyzed: {analyzed}/{tickets} | Critical: {critical_count} ({critical_pct:.0f}%)</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Score progress bar
        st.progress(int(score) / 100 if score > 0 else 0)
        st.markdown(f"**Overall Score: {score:.0f}%**")
        
        # Criteria bar chart
        if any(criteria.values()):
            fig = go.Figure(data=[
                go.Bar(
                    x=list(criteria.keys()),
                    y=list(criteria.values()),
                    marker_color=['#4CAF50', '#2196F3', '#FF9800', '#9C27B0']
                )
            ])
            fig.update_layout(
                height=200,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(range=[0, 100], gridcolor='#333'),
                xaxis=dict(tickfont=dict(size=10))
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Summary expander
        with st.expander("📝 Latest Summary"):
            if summaries:
                st.write(summaries[-1])
            else:
                st.write("No summary available yet.")

# --- Main Dashboard ---
current_month_name = datetime.now().strftime("%B %Y")

# Last sync info
col_title, col_sync = st.columns([3, 1])
with col_title:
    st.caption(f"📅 Zobrazené dáta: **{current_month_name}**")
with col_sync:
    st.caption(f"Last update: {datetime.now().strftime('%H:%M')}")
    if st.button("🔄 Refresh"):
        st.rerun()

# Load data
with st.spinner("Loading agent statistics..."):
    agent_stats = load_agent_stats()

if not agent_stats:
    st.info("No agent data available yet. Run ETL and AI Analysis first from the Settings page.")
    st.page_link("pages/Settings.py", label="⚙️ Go to Settings", icon="⚙️")
else:
    # Summary metrics - FIXED CALCULATIONS
    st.markdown("---")
    total_agents = len(agent_stats)
    total_tickets = sum(s["tickets"] for s in agent_stats.values())
    total_analyzed = sum(s["analyzed_tickets"] for s in agent_stats.values())
    total_critical = sum(s["critical_count"] for s in agent_stats.values())
    total_score_sum = sum(s["total_score"] for s in agent_stats.values())
    
    # FIXED: Weighted average score (per ticket, not per agent)
    avg_score = total_score_sum / total_analyzed if total_analyzed > 0 else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👥 Agents", total_agents)
    m2.metric("🎫 Tickets Analyzed", f"{total_analyzed}/{total_tickets}")
    m3.metric("🔴 Critical Issues", total_critical)
    m4.metric("📈 Avg Score", f"{avg_score:.0f}%")
    
    st.markdown("---")
    
    # Agent Cards Grid - SORTED ALPHABETICALLY
    agents = sorted(agent_stats.keys())  # FIXED: Sort alphabetically
    
    # Create rows of 4 agents
    for i in range(0, len(agents), 4):
        cols = st.columns(4)
        for j, col in enumerate(cols):
            if i + j < len(agents):
                agent = agents[i + j]
                with col:
                    create_agent_card(agent, agent_stats[agent])

# --- Footer ---
st.markdown("---")
st.caption(f"QA Dashboard v1.0 | Powered by Gemini AI | {current_month_name}")
