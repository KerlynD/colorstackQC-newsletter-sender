import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from datetime import date


def send_emails(from_email, from_password, user):
    smtpserver = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    smtpserver.ehlo()
    smtpserver.login(from_email, from_password)

    sent_from = from_email
    sent_to = user[0]
    subject = f"ColorStack Weekly Newsletter {date.today().strftime('%Y-%m-%d')}"
    # IDK HOW UR GONNA SEND OUT FUTURE NEWSLETTERS SO UPDATE THIS ACCORDINGLY
    # EITHER GET THE HTML CONTENT FROM GITHUB OR FROM A LOCAL FILE

    # get html content from github
    html_content = requests.get(
        "https://raw.githubusercontent.com/KerlynD/colorstack-newsletter/refs/heads/main/newsletter.html"
    ).text

    # # or as a local file
    # with open(
    #     "newsletter.txt",
    #     encoding="utf8",
    # ) as file:
    #     html_content = file.read()

    message = MIMEMultipart("alternative")
    message["From"] = sent_from
    message["To"] = sent_to
    message["Subject"] = subject

    message.attach(MIMEText(html_content, "html"))

    smtpserver.sendmail(sent_from, sent_to, message.as_string())

    smtpserver.close()
