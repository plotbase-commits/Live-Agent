import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
import re
from src.config import get_config_value, DEFAULT_GMAIL_USER, DEFAULT_GMAIL_PASSWORD

class EmailService:
    def __init__(self):
        self.user = get_config_value("GMAIL_USER", DEFAULT_GMAIL_USER)
        self.password = get_config_value("GMAIL_APP_PASSWORD", DEFAULT_GMAIL_PASSWORD)
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def _convert_to_html(self, text):
        """
        Convert plain text with markdown-like formatting to HTML.
        Supports: **bold**, *italic*, URLs, newlines
        """
        # First, find and protect URLs before escaping
        url_pattern = r'(https?://[^\s]+)'
        urls = re.findall(url_pattern, text)
        url_placeholders = {}
        for i, url in enumerate(urls):
            placeholder = f"__URL_PLACEHOLDER_{i}__"
            url_placeholders[placeholder] = url
            text = text.replace(url, placeholder, 1)
        
        # Escape HTML special chars
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Convert **bold** to <b>bold</b>
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        
        # Convert *italic* to <i>italic</i>
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
        
        # Restore URLs as clickable links
        for placeholder, url in url_placeholders.items():
            clickable_link = f'<a href="{url}" style="color: #1a73e8;">{url}</a>'
            text = text.replace(placeholder, clickable_link)
        
        # Convert newlines to <br>
        text = text.replace('\n', '<br>')
        
        # Wrap in basic HTML
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6;">
        {text}
        </body>
        </html>
        """
        return html

    def send_alert(self, recipients, subject, body):
        """
        Sends an HTML email alert to the specified recipients.
        Supports **bold** and *italic* formatting in body.
        recipients: list of email strings
        """
        if not self.user or not self.password:
            st.warning("Gmail credentials not configured. Skipping email alert.")
            return False

        if not recipients:
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.user
            msg['To'] = ", ".join(recipients)
            msg['Subject'] = f"[QA ALERT] {subject}"

            # Plain text fallback
            msg.attach(MIMEText(body, 'plain'))
            
            # HTML version with formatting
            html_body = self._convert_to_html(body)
            msg.attach(MIMEText(html_body, 'html'))

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

