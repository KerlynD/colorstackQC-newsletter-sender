from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import shutil
from datetime import datetime, timedelta
import psycopg2
from dotenv import load_dotenv
from src.emailer import send_emails
import threading
import time
from werkzeug.utils import secure_filename
import uuid
import cloudinary
import cloudinary.uploader

load_dotenv()

# Configure Cloudinary
cloudinary.config(secure=True)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Startup logging for debugging deployment
print("=" * 50)
print("ColorStack Newsletter Sender - Starting Up")
print("=" * 50)
print(f"SECRET_KEY set: {'Yes' if os.getenv('SECRET_KEY') else 'No'}")
print(f"POSTGRES_URL set: {'Yes' if os.getenv('POSTGRES_URL') else 'No'}")
print(f"EMAIL set: {'Yes' if os.getenv('EMAIL') else 'No'}")
print(f"EMAIL_PASSWORD set: {'Yes' if os.getenv('EMAIL_PASSWORD') else 'No'}")
print(f"CLOUDINARY_URL set: {'Yes' if os.getenv('CLOUDINARY_URL') else 'No'}")
print(f"FLASK_ENV: {os.getenv('FLASK_ENV', 'not set')}")
print(f"PORT: {os.getenv('PORT', '5000')}")
print("=" * 50)

# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static', exist_ok=True)

# Copy the ColorStack logo to static folder for email use (for production deployment)
if os.path.exists('assets/colorstack-logo.png') and not os.path.exists('static/colorstack-logo.png'):
    shutil.copy('assets/colorstack-logo.png', 'static/colorstack-logo.png')

# Global variable to store scheduled newsletters
scheduled_newsletters = []

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_cloudinary(image_file):
    """Upload image to Cloudinary and return the public URL"""
    try:
        # Check if Cloudinary is configured
        if not os.getenv('CLOUDINARY_URL'):
            print("Warning: CLOUDINARY_URL not found. Add it to your .env file.")
            return None
        
        # Upload the image to Cloudinary
        upload_result = cloudinary.uploader.upload(image_file)
        
        # Get the secure URL
        secure_url = upload_result.get('secure_url')
        
        if secure_url:
            print(f"Image uploaded successfully to Cloudinary: {secure_url}")
            return secure_url
        else:
            print("Upload successful, but secure_url was not found in the response.")
            return None
            
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        return None

def get_subscriber_count():
    """Get the number of newsletter subscribers"""
    try:
        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM newsletter_subs;")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        print(f"Error getting subscriber count: {e}")
        return 0

def store_latest_image_url(cloudinary_url):
    """Store the latest Cloudinary URL for simple retrieval"""
    try:
        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        cursor = conn.cursor()
        
        # Simple approach: just store the latest image URL
        cursor.execute(
            "INSERT INTO latest_newsletter_image (cloudinary_url, uploaded_at) VALUES (%s, CURRENT_TIMESTAMP) ON CONFLICT (id) DO UPDATE SET cloudinary_url = %s, uploaded_at = CURRENT_TIMESTAMP",
            (cloudinary_url, cloudinary_url)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Latest image URL stored: {cloudinary_url}")
        return True
        
    except Exception as e:
        print(f"Error storing latest image URL: {e}")
        return False

def get_latest_image_url():
    """Get the latest uploaded image URL"""
    try:
        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        cursor = conn.cursor()
        cursor.execute("SELECT cloudinary_url FROM latest_newsletter_image ORDER BY uploaded_at DESC LIMIT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error getting latest image URL: {e}")
        return None

def get_newsletter_html(image_filename=None):
    """Generate newsletter HTML with the uploaded image"""
    if image_filename:
        image_url = url_for('static', filename=f'uploads/{image_filename}', _external=True)
    else:
        # Default image
        image_url = "https://raw.githubusercontent.com/KerlynD/colorstack-newsletter/refs/heads/main/events/ColorStack__QC_May_Newsletter.png"
    
    html_template = f'''<!DOCTYPE html>
<html>
<head>
  <title>ColorStack Newsletter</title>
</head>
<body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4;">
  <center>
    <div style="width: 100%; max-width: 600px; margin: 0 auto; background: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);">
      <header style="text-align: center; padding: 10px 0; color: #000000; border-radius: 8px 8px 0 0;">
          <img src="{url_for('static', filename='colorstack-logo.png', _external=True)}" alt="ColorStack Logo" width="60px">
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

def send_newsletter_to_subscribers_background(send_time):
    """Background function to wait and send newsletter to all subscribers"""
    try:
        # Wait until the scheduled time (only if in future)
        if send_time > datetime.now():
            wait_seconds = (send_time - datetime.now()).total_seconds()
            print(f"Waiting {wait_seconds} seconds until {send_time}")
            time.sleep(wait_seconds)
        
        print(f"Starting newsletter send at {datetime.now()}")
        
        # Get all subscribers
        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM newsletter_subs;")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        print(f"Sending newsletter to {len(users)} subscribers")
        
        # Send email to each user
        success_count = 0
        fail_count = 0
        for user in users:
            try:
                # Send using latest image
                send_emails(os.getenv("EMAIL"), os.getenv("EMAIL_PASSWORD"), user)
                print(f"Newsletter sent to {user[0]}")
                success_count += 1
            except Exception as e:
                print(f"Error sending to {user[0]}: {e}")
                fail_count += 1
        
        print(f"Newsletter sending completed at {datetime.now()}")
        print(f"Success: {success_count}, Failed: {fail_count}")
        
        # Remove from scheduled list
        global scheduled_newsletters
        scheduled_newsletters = [n for n in scheduled_newsletters if n['send_time'] != send_time]
        
    except Exception as e:
        print(f"Error in scheduled newsletter sending: {e}")
        import traceback
        traceback.print_exc()

@app.route('/health')
def health():
    """Health check endpoint for Railway"""
    return {'status': 'ok', 'service': 'colorstack-newsletter-sender'}, 200

@app.route('/')
def index():
    try:
        subscriber_count = get_subscriber_count()
        print(f"Successfully got subscriber count: {subscriber_count}")
        return render_template('index.html', 
                             subscriber_count=subscriber_count,
                             scheduled_newsletters=scheduled_newsletters)
    except Exception as e:
        print(f"ERROR in index route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error loading page: {str(e)}", 500

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        # Upload to Cloudinary
        cloudinary_url = upload_to_cloudinary(file)
        
        if cloudinary_url:
            # Store the latest image URL
            if store_latest_image_url(cloudinary_url):
                flash('Image uploaded successfully to Cloudinary and ready for email!', 'success')
                return redirect(url_for('preview', image_url=cloudinary_url))
            else:
                flash('Image uploaded to Cloudinary but failed to save URL', 'warning')
                return redirect(url_for('preview', image_url=cloudinary_url))
        else:
            flash('Failed to upload image to Cloudinary. Check CLOUDINARY_URL in .env', 'error')
            return redirect(url_for('index'))
    else:
        flash('Invalid file type. Please upload PNG, JPG, JPEG, or GIF files.', 'error')
        return redirect(url_for('index'))

@app.route('/preview')
def preview():
    try:
        print("Preview route started")
        image_url = request.args.get('image_url')
        if not image_url:
            print("No image_url in query params, fetching from database")
            # Get the latest image URL if none provided
            image_url = get_latest_image_url()
        else:
            print(f"Using image_url from query params: {image_url[:50]}...")
        
        print("Fetching subscriber count...")
        subscriber_count = get_subscriber_count()
        print(f"Subscriber count retrieved: {subscriber_count}")
        
        logo_url = "https://raw.githubusercontent.com/KerlynD/colorstack-newsletter/refs/heads/main/assets/colorstack-logo.png"
        
        print("Rendering preview.html template")
        return render_template('preview.html', 
                             image_url=image_url,
                             logo_url=logo_url,
                             subscriber_count=subscriber_count)
    except Exception as e:
        print(f"ERROR in preview route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error loading preview: {str(e)}", 500

@app.route('/schedule', methods=['POST'])
def schedule_newsletter():
    send_date = request.form.get('send_date')
    send_time = request.form.get('send_time')
    
    if not all([send_date, send_time]):
        flash('Please provide date and time', 'error')
        return redirect(url_for('preview'))
    
    try:
        # Parse the datetime
        send_datetime_str = f"{send_date} {send_time}"
        send_datetime = datetime.strptime(send_datetime_str, "%Y-%m-%d %H:%M")
        
        if send_datetime <= datetime.now():
            flash('Send time must be in the future', 'error')
            return redirect(url_for('preview'))
        
        # Add to scheduled newsletters
        newsletter_info = {
            'send_time': send_datetime,
            'scheduled_at': datetime.now()
        }
        scheduled_newsletters.append(newsletter_info)
        
        # Start background thread to send the newsletter (non-blocking)
        thread = threading.Thread(target=send_newsletter_to_subscribers_background, 
                                args=(send_datetime,))
        thread.daemon = True
        thread.start()
        
        print(f"Newsletter scheduled for {send_datetime} - background thread started")
        flash(f'Newsletter scheduled for {send_datetime.strftime("%Y-%m-%d at %H:%M")}', 'success')
        return redirect(url_for('index'))
        
    except ValueError:
        flash('Invalid date/time format', 'error')
        return redirect(url_for('preview'))

@app.route('/send_now', methods=['POST'])
def send_now():
    try:
        # Send immediately in background (non-blocking)
        thread = threading.Thread(target=send_newsletter_to_subscribers_background, 
                                args=(datetime.now(),))
        thread.daemon = True
        thread.start()
        
        print("Newsletter send initiated - background thread started")
        flash('Newsletter is being sent now! Check logs for progress.', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        print(f"Error starting newsletter send: {e}")
        flash(f'Error starting newsletter send: {str(e)}', 'error')
        return redirect(url_for('preview'))

@app.route('/test_email', methods=['POST'])
def test_email():
    test_email_addr = request.form.get('test_email')
    
    if not test_email_addr:
        flash('Please provide test email', 'error')
        return redirect(url_for('preview'))
    
    # Send test email in background thread (non-blocking)
    def send_test_email_background():
        try:
            print(f"Sending test email to {test_email_addr}...")
            send_emails(os.getenv("EMAIL"), os.getenv("EMAIL_PASSWORD"), (test_email_addr,))
            print(f"Test email successfully sent to {test_email_addr}")
        except Exception as e:
            print(f"Error sending test email to {test_email_addr}: {e}")
            import traceback
            traceback.print_exc()
    
    # Start background thread
    thread = threading.Thread(target=send_test_email_background, daemon=True)
    thread.start()
    
    print(f"Test email initiated for {test_email_addr} - background thread started")
    flash(f'Test email is being sent to {test_email_addr}. Check your inbox in a few moments.', 'success')
    return redirect(url_for('preview'))

if __name__ == '__main__':
    # Copy the ColorStack logo to static folder for email use
    if os.path.exists('assets/colorstack-logo.png'):
        shutil.copy('assets/colorstack-logo.png', 'static/colorstack-logo.png')
    
    # Use PORT environment variable for deployment platforms
    port = int(os.environ.get('PORT', 5000))
    # Set debug to False in production
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=port)
