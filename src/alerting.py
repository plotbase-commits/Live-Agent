import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
from src.config import get_config_value, DEFAULT_GMAIL_USER, DEFAULT_GMAIL_PASSWORD

class EmailService:
    def __init__(self):
        self.user = get_config_value("GMAIL_USER", DEFAULT_GMAIL_USER)
        self.password = get_config_value("GMAIL_APP_PASSWORD", DEFAULT_GMAIL_PASSWORD)
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def send_alert(self, recipients, subject, body):
        """
        Sends an email alert to the specified recipients.
        recipients: list of email strings
        """
        if not self.user or not self.password:
            st.warning("Gmail credentials not configured. Skipping email alert.")
            return False

        if not recipients:
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.user
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = f"[QA ALERT] {subject}"

            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.user, self.password)
            text = msg.as_string()
            server.sendmail(self.user, recipients, text)
            server.quit()
            
            return True
        except Exception as e:
            st.error(f"Failed to send email alert: {e}")
            return False
