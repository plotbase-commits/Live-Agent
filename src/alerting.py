import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
import os
from dotenv import load_dotenv
from src.job_status import add_log

# Ensure .env is loaded
load_dotenv()

class EmailService:
    def __init__(self):
        # Load directly from environment
        self.user = os.getenv("GMAIL_USER", "")
        self.password = os.getenv("GMAIL_APP_PASSWORD", "")
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        
        # Log configuration status
        if self.user and self.password:
            add_log(f"Email: Configured for {self.user}")
        else:
            add_log("Email: Gmail credentials NOT configured!")

    def send_alert(self, recipients, subject, body):
        """
        Sends an email alert to the specified recipients.
        recipients: list of email strings
        """
        if not self.user or not self.password:
            st.warning("Gmail credentials not configured. Skipping email alert.")
            add_log("Email: Skipped - no credentials")
            return False

        if not recipients:
            add_log("Email: Skipped - no recipients")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.user
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = f"[QA ALERT] {subject}"

            msg.attach(MIMEText(body, 'plain'))

            add_log(f"Email: Connecting to {self.smtp_server}...")
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.user, self.password)
            text = msg.as_string()
            server.sendmail(self.user, recipients, text)
            server.quit()
            
            add_log(f"Email: Successfully sent to {recipients}")
            return True
        except Exception as e:
            add_log(f"Email: FAILED - {e}")
            st.error(f"Failed to send email alert: {e}")
            return False
