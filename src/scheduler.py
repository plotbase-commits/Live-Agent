import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import threading

# Global scheduler instance
_scheduler = None
_scheduler_lock = threading.Lock()

class SchedulerService:
    """Manages scheduled ETL and Analysis jobs."""
    
    def __init__(self):
        global _scheduler
        with _scheduler_lock:
            if _scheduler is None:
                _scheduler = BackgroundScheduler()
                _scheduler.start()
            self.scheduler = _scheduler
    
    def get_scheduler(self):
        return self.scheduler
    
    def add_etl_job(self, etl_func):
        """Add ETL job: Mon-Fri, 07:30-18:00, every hour at :30"""
        job_id = "etl_job"
        
        # Remove existing job if any
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        
        # Add new job
        self.scheduler.add_job(
            etl_func,
            CronTrigger(
                day_of_week='mon-fri',
                hour='7-18',
                minute=30
            ),
            id=job_id,
            name="ETL - Fetch Tickets",
            replace_existing=True
        )
        return job_id
    
    def add_analysis_job(self, analysis_func):
        """Add Analysis job: Mon-Fri, 07:35-18:00, every hour at :35 (5 mins after ETL)"""
        job_id = "analysis_job"
        
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        
        self.scheduler.add_job(
            analysis_func,
            CronTrigger(
                day_of_week='mon-fri',
                hour='7-18',
                minute=35
            ),
            id=job_id,
            name="AI Analysis",
            replace_existing=True
        )
        return job_id
    
    def add_daily_aggregation_job(self, aggregation_func):
        """Add daily aggregation job: Mon-Fri at 17:00"""
        job_id = "aggregation_job"
        
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        
        self.scheduler.add_job(
            aggregation_func,
            CronTrigger(
                day_of_week='mon-fri',
                hour=17,
                minute=0
            ),
            id=job_id,
            name="Daily Stats Aggregation",
            replace_existing=True
        )
        return job_id
    
    def remove_all_jobs(self):
        """Remove all scheduled jobs."""
        for job_id in ["etl_job", "analysis_job", "aggregation_job"]:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
    
    def get_jobs(self):
        """Get all scheduled jobs."""
        return self.scheduler.get_jobs()
    
    def get_next_run_time(self, job_id):
        """Get next run time for a job."""
        job = self.scheduler.get_job(job_id)
        if job:
            return job.next_run_time
        return None
    
    def is_running(self):
        """Check if scheduler is running."""
        return self.scheduler.running
    
    def pause(self):
        """Pause all jobs."""
        self.scheduler.pause()
    
    def resume(self):
        """Resume all jobs."""
        self.scheduler.resume()


def display_scheduler_status():
    """Display scheduler status in Streamlit UI."""
    service = SchedulerService()
    
    st.subheader("⏰ Scheduler Status")
    
    if service.is_running():
        st.success("Scheduler is **RUNNING**")
    else:
        st.warning("Scheduler is **PAUSED**")
    
    jobs = service.get_jobs()
    
    if jobs:
        st.write("**Scheduled Jobs:**")
        for job in jobs:
            next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M") if job.next_run_time else "N/A"
            st.markdown(f"- **{job.name}** → Next: `{next_run}`")
    else:
        st.info("No jobs scheduled. Click 'Start Scheduler' to begin.")
