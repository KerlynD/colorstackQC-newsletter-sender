import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import requests
from datetime import date
from flask import url_for
import os
import psycopg2


def send_emails(from_email, from_password, user):
    smtpserver = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    smtpserver.ehlo()
    smtpserver.login(from_email, from_password)

    sent_from = from_email
    sent_to = user[0]
    subject = f"ColorStack Weekly Newsletter {date.today().strftime('%Y-%m-%d')}"
    
    # Generate HTML content with Cloudinary URLs
    html_content = get_newsletter_html_with_cloudinary()

    message = MIMEMultipart("alternative")
    message["From"] = sent_from
    message["To"] = sent_to
    message["Subject"] = subject

    message.attach(MIMEText(html_content, "html"))

    smtpserver.sendmail(sent_from, sent_to, message.as_string())
    smtpserver.close()


def get_newsletter_html_with_cloudinary():
    """Generate newsletter HTML for email using latest Cloudinary image"""
    try:
        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        cursor = conn.cursor()
        
        # Get the latest image URL from Cloudinary
        cursor.execute("SELECT cloudinary_url FROM latest_newsletter_image ORDER BY uploaded_at DESC LIMIT 1")
        image_result = cursor.fetchone()
        
        # Use Cloudinary URL if available, otherwise fallback
        if image_result and image_result[0]:
            image_url = image_result[0]
        else:
            # Fallback to GitHub image
            image_url = "https://raw.githubusercontent.com/KerlynD/colorstack-newsletter/refs/heads/main/events/ColorStack__QC_May_Newsletter.png"
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error getting image URL from database: {e}")
        # Fallback to GitHub image
        image_url = "https://raw.githubusercontent.com/KerlynD/colorstack-newsletter/refs/heads/main/events/ColorStack__QC_May_Newsletter.png"
    
    # Use GitHub logo
    logo_url = "https://raw.githubusercontent.com/KerlynD/colorstack-newsletter/refs/heads/main/assets/colorstack-logo.png"
    
    html_template = f'''<!DOCTYPE html>
<html>
<head>
  <title>ColorStack Newsletter</title>
</head>
<body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4;">
  <center>
    <div style="width: 100%; max-width: 600px; margin: 0 auto; background: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);">
      <header style="text-align: center; padding: 10px 0; color: #000000; border-radius: 8px 8px 0 0;">
          <img src="{logo_url}" alt="ColorStack Logo" width="60px">
          <h1>ColorStack Newsletter</h1>
      </header>
      <div style="color: #000000; text-align: center; margin: 20px 0;">
      </div>  
      <img src="{image_url}" style="max-width: 100%; height: auto; display: block; margin: 0 auto;">      
      <div style="text-align: center; font-size: 12px; color: #666666; margin-top: 20px;">
        <p>You're receiving this email as a member of the ColorStack QC Club.</p>
      </div>
    </div>
  </center>
</body>
</html>'''
    return html_template
