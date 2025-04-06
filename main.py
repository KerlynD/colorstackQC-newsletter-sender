import psycopg2
from emailer import send_emails
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(os.getenv("POSTGRES_URL"))

query = "SELECT email FROM newsletter_subs;"
cursor = conn.cursor()
cursor.execute(query)
users = cursor.fetchall()
cursor.close()
conn.close()

TESTING = False
# PUT YOUR EMAIL HERE TO TEST THE EMAILS
TEST_EMAIL = "#"
# UNCOMMENT LINE 30 TO TEST THE EMAILS
# PLEASE TEST IT AND CHECK FORMATTING BEFORE SENDING TO EVERYONE
# this will only send the email to whatever email is on line 26
TESTING = True

# send email to each user
for user in users:
    if TESTING:
        if TEST_EMAIL == user[0]:
            print(f"Testing emails with {TEST_EMAIL}")
            send_emails(os.getenv("EMAIL"), os.getenv("EMAIL_PASSWORD"), user)
    else:
        print("sending to everyone subbed")
        send_emails(os.getenv("EMAIL"), os.getenv("EMAIL_PASSWORD"), user)
