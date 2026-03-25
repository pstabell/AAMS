"""Email utilities for the Agent Commission Tracker app."""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)

def send_email(to_email: str, subject: str, html_body: str, text_body: str = None):
    """Send an email using SendGrid or SMTP."""
    
    # Check for SendGrid first (preferred)
    sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("FROM_EMAIL", "support@agentcommissiontracker.com")
    
    if sendgrid_api_key:
        # Use SendGrid
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=sendgrid_api_key)
            
            from_email_obj = Email(from_email, "Agent Commission Tracker")
            to_email_obj = To(to_email)
            
            mail = Mail(from_email_obj, to_email_obj, subject)
            
            if text_body:
                mail.content = [Content("text/plain", text_body), Content("text/html", html_body)]
            else:
                mail.content = Content("text/html", html_body)
            
            response = sg.send(mail)
            
            logger.info(f"Email sent successfully via SendGrid to {to_email} (status: {response.status_code})")
            return response.status_code in [200, 201, 202]
            
        except ImportError:
            logger.error("SendGrid library not installed. Run: pip install sendgrid")
            return False
        except Exception as e:
            logger.error(f"SendGrid email failed: {e}")
            return False
    
    # Fall back to SMTP
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    
    if not smtp_user or not smtp_pass:
        logger.error("Email configuration missing. Set SENDGRID_API_KEY or SMTP credentials.")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"Agent Commission Tracker <{from_email}>"
        msg['To'] = to_email
        
        # Add text and HTML parts
        if text_body:
            msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            
        logger.info(f"Email sent successfully via SMTP to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send SMTP email: {e}")
        return False

def send_password_reset_email(to_email: str, reset_link: str):
    """Send password reset email."""
    
    subject = "Reset Your Agent Commission Tracker Password"
    
    # TODO: Replace with actual hosted logo URL
    logo_url = os.getenv("LOGO_URL", "https://your-domain.com/logo.png")
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .logo {{ max-width: 200px; height: auto; margin: 0 auto 20px; display: block; }}
            .content {{ background-color: #f9f9f9; padding: 30px; }}
            .button {{ display: inline-block; padding: 12px 30px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="{logo_url}" alt="Agent Commission Tracker" class="logo">
                <h1>Agent Commission Tracker</h1>
            </div>
            <div class="content">
                <h2>Password Reset Request</h2>
                <p>Hi there,</p>
                <p>We received a request to reset your password. Click the button below to create a new password:</p>
                <p style="text-align: center;">
                    <a href="{reset_link}" class="button">Reset Password</a>
                </p>
                <p>This link will expire in 1 hour for security reasons.</p>
                <p>If you didn't request a password reset, please ignore this email.</p>
                <p><strong>Direct link:</strong><br>
                <a href="{reset_link}">{reset_link}</a></p>
            </div>
            <div class="footer">
                <p>© 2024 Metro Technology Solutions LLC. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    Agent Commission Tracker - Password Reset Request
    
    Hi there,
    
    We received a request to reset your password. Visit the link below to create a new password:
    
    {reset_link}
    
    This link will expire in 1 hour for security reasons.
    
    If you didn't request a password reset, please ignore this email.
    
    © 2024 Metro Technology Solutions LLC. All rights reserved.
    """
    
    return send_email(to_email, subject, html_body, text_body)

def send_welcome_email(to_email: str):
    """Send welcome email after subscription."""
    
    subject = "Your 14-Day Free Trial Has Started - Agent Commission Tracker"
    app_url = os.getenv("RENDER_APP_URL", "https://commission-tracker-app.onrender.com")
    
    # TODO: Replace with actual hosted logo URL
    logo_url = os.getenv("LOGO_URL", "https://your-domain.com/logo.png")
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .logo {{ max-width: 200px; height: auto; margin: 0 auto 20px; display: block; }}
            .content {{ background-color: #f9f9f9; padding: 30px; }}
            .button {{ display: inline-block; padding: 12px 30px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .feature {{ background-color: white; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="{logo_url}" alt="Agent Commission Tracker" class="logo">
                <h1 style="margin: 0; padding: 0;">Welcome to Agent</h1>
                <h1 style="margin: 0; padding: 0;">Commission Tracker! 🎉</h1>
            </div>
            <div class="content">
                <h2>Your 14-day free trial has started!</h2>
                <p>Welcome to Agent Commission Tracker! You have full access to all features for the next 14 days.</p>
                <p><strong>No charges until your trial ends.</strong> You can cancel anytime.</p>
                
                <p style="text-align: center;">
                    <a href="{app_url}" class="button">Login to Your Account</a>
                </p>
                
                <h3>Getting Started:</h3>
                <div class="feature">
                    <strong>1. Add Your First Policy</strong><br>
                    Navigate to "Add New Policy Transaction" to start tracking commissions.
                </div>
                <div class="feature">
                    <strong>2. Import Existing Data</strong><br>
                    Use the "Tools" page to bulk import your existing policies via CSV.
                </div>
                <div class="feature">
                    <strong>3. Set Up Reconciliation</strong><br>
                    Use the "Reconciliation" feature to match carrier statements automatically.
                </div>
                
                <h3>Need Help?</h3>
                <p>Visit the Help section in the app for detailed guides and troubleshooting.</p>
                
                <h3>Your Account:</h3>
                <p>
                    <strong>Email:</strong> {to_email}<br>
                    <strong>Plan:</strong> Professional (Free for 14 days, then $19.99/month)<br>
                    <strong>Trial Ends:</strong> 14 days from today<br>
                    <strong>Billing:</strong> Your card will be charged after the trial unless you cancel
                </p>
            </div>
            <div class="footer">
                <p>© 2024 Metro Technology Solutions LLC. All rights reserved.</p>
                <p>You're receiving this because you signed up for Agent Commission Tracker.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    Welcome to Agent Commission Tracker! 🎉
    
    Your 14-day free trial has started!
    
    Welcome to Agent Commission Tracker! You have full access to all features for the next 14 days.
    
    No charges until your trial ends. You can cancel anytime.
    
    Login here: {app_url}
    
    Getting Started:
    1. Add Your First Policy - Navigate to "Add New Policy Transaction" to start tracking commissions.
    2. Import Existing Data - Use the "Tools" page to bulk import your existing policies via CSV.
    3. Set Up Reconciliation - Use the "Reconciliation" feature to match carrier statements automatically.
    
    Need Help?
    Visit the Help section in the app for detailed guides and troubleshooting.
    
    Your Account:
    Email: {to_email}
    Plan: Professional (Free for 14 days, then $19.99/month)
    Trial Ends: 14 days from today
    Billing: Your card will be charged after the trial unless you cancel
    
    © 2024 Metro Technology Solutions LLC. All rights reserved.
    """
    
    return send_email(to_email, subject, html_body, text_body)

def send_password_setup_email(to_email: str, setup_link: str):
    """Send password setup email for new users."""
    
    subject = "Set Your Password - Agent Commission Tracker"
    
    # TODO: Replace with actual hosted logo URL
    logo_url = os.getenv("LOGO_URL", "https://your-domain.com/logo.png")
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .logo {{ max-width: 200px; height: auto; margin: 0 auto 20px; display: block; }}
            .content {{ background-color: #f9f9f9; padding: 30px; }}
            .button {{ display: inline-block; padding: 15px 30px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            .warning {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="{logo_url}" alt="Agent Commission Tracker" class="logo">
                <h1 style="margin: 0; padding: 0;">Welcome to Agent</h1>
                <h1 style="margin: 0; padding: 0;">Commission Tracker!</h1>
            </div>
            <div class="content">
                <h2>Your 14-day free trial is ready! 🎉</h2>
                <p>Hi there,</p>
                <p>Thank you for starting your free trial of Agent Commission Tracker. You now have full access to all features for the next 14 days.</p>
                
                <p><strong>To get started, you need to set your password:</strong></p>
                
                <p style="text-align: center;">
                    <a href="{setup_link}" class="button">Set Your Password</a>
                </p>
                
                <div class="warning">
                    <strong>⚠️ Important:</strong> This link expires in 24 hours for security reasons. If it expires, you can request a new one from the login page.
                </div>
                
                <h3>What happens next?</h3>
                <ul>
                    <li>Click the button above to set your password</li>
                    <li>You'll be automatically logged into your account</li>
                    <li>Start tracking your commissions immediately</li>
                    <li>No payment until your 14-day trial ends</li>
                </ul>
                
                <p>If the button doesn't work, copy and paste this link into your browser:</p>
                <p style="word-break: break-all; background-color: #e9ecef; padding: 10px; border-radius: 5px;">
                    {setup_link}
                </p>
                
                <h3>Your Trial Details:</h3>
                <p>
                    <strong>Email:</strong> {to_email}<br>
                    <strong>Plan:</strong> Professional (14-day free trial)<br>
                    <strong>Price after trial:</strong> $19.99/month<br>
                    <strong>Cancel anytime:</strong> No questions asked
                </p>
            </div>
            <div class="footer">
                <p>© 2025 Metro Technology Solutions LLC. All rights reserved.</p>
                <p>You're receiving this because you signed up for Agent Commission Tracker.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
    Welcome to Agent Commission Tracker!
    
    Your 14-day free trial is ready! 🎉
    
    Thank you for starting your free trial of Agent Commission Tracker. You now have full access to all features for the next 14 days.
    
    To get started, you need to set your password:
    
    {setup_link}
    
    ⚠️ Important: This link expires in 24 hours for security reasons. If it expires, you can request a new one from the login page.
    
    What happens next?
    - Click the link above to set your password
    - You'll be automatically logged into your account
    - Start tracking your commissions immediately
    - No payment until your 14-day trial ends
    
    Your Trial Details:
    Email: {to_email}
    Plan: Professional (14-day free trial)
    Price after trial: $19.99/month
    Cancel anytime: No questions asked
    
    © 2025 Metro Technology Solutions LLC. All rights reserved.
    """
    
    return send_email(to_email, subject, html_body, text_body)