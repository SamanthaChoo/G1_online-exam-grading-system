"""Email utilities for sending password reset OTP codes."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


# Gmail SMTP configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "wms.management00@gmail.com"
EMAIL_PASSWORD = "qigc ghkx fjuu kefv"  # App Password


def send_otp_email(to_email: str, otp_code: str, user_name: Optional[str] = None) -> bool:
    """
    Send OTP code via email using Gmail SMTP.
    
    Args:
        to_email: Recipient email address
        otp_code: 6-digit OTP code
        user_name: Optional user name for personalization
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Create message
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = "Password Reset OTP Code"
        
        # Email body
        name = user_name or "User"
        body = f"""
Hello {name},

You have requested to reset your password for your Online Exam System account.

Your OTP code is: {otp_code}

This code will expire in 15 minutes. Please do not share this code with anyone.

If you did not request this password reset, please ignore this email.

Best regards,
Online Exam System Team
"""
        
        msg.attach(MIMEText(body, "plain"))
        
        # Connect to SMTP server and send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, to_email, text)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
