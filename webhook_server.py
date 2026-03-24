import os
import stripe
import json
from flask import Flask, request, jsonify
from supabase import create_client, Client
from datetime import datetime, timedelta
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from email_utils import send_welcome_email

# Initialize Flask app
app = Flask(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Initialize Supabase (production database)
def get_supabase_client():
    """Get Supabase client for production database."""
    url = os.getenv("PRODUCTION_SUPABASE_URL", os.getenv("SUPABASE_URL"))
    key = os.getenv("PRODUCTION_SUPABASE_ANON_KEY", os.getenv("SUPABASE_ANON_KEY"))
    if not url or not key:
        print("Warning: Supabase credentials not configured")
        return None
    return create_client(url, key)

@app.route('/')
def home():
    """Root endpoint."""
    return jsonify({
        'service': 'Commission Tracker Webhook Handler',
        'version': '1.1',
        'status': 'running'
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render."""
    return jsonify({'status': 'healthy', 'version': '1.1'}), 200

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events."""
    app.logger.info("="*50)
    app.logger.info("WEBHOOK TRIGGERED - Version 1.1")
    app.logger.info("="*50)
    
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    # Log webhook received
    print(f"\n{'='*50}")
    print(f"Webhook received at {datetime.now()}")
    print(f"Signature header present: {'Yes' if sig_header else 'No'}")
    
    # Check if webhook secret is configured
    if not webhook_secret:
        print("WARNING: STRIPE_WEBHOOK_SECRET not configured!")
        # For testing, parse without verification
        try:
            event = json.loads(payload)
        except Exception as e:
            print(f"Failed to parse payload: {e}")
            return jsonify({'error': 'Invalid JSON'}), 400
    else:
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            print(f"Invalid payload: {e}")
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError as e:
            print(f"Invalid signature: {e}")
            return jsonify({'error': 'Invalid signature'}), 400
    
    # Log event type
    print(f"Event type: {event['type']}")
    print(f"Event ID: {event.get('id', 'Unknown')}")
    
    # Initialize debug info
    debug_info = {
        'status': 'success',
        'event_received': event.get('type', 'unknown'),
        'timestamp': datetime.now().isoformat()
    }
    
    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        try:
            session = event['data']['object']
            
            # Extract relevant data
            stripe_customer_id = session.get('customer')
            customer_email = session.get('customer_details', {}).get('email')
            subscription_id = session.get('subscription')
            
            app.logger.info(f"Payment successful:")
            app.logger.info(f"  Customer ID: {stripe_customer_id}")
            app.logger.info(f"  Email: {customer_email}")
            app.logger.info(f"  Subscription ID: {subscription_id}")
        except Exception as e:
            app.logger.error(f"Error processing session: {e}")
            return jsonify({'error': str(e)}), 500
        
        # Update database (if Supabase is configured)
        supabase = get_supabase_client()
        print(f"Supabase client: {'Connected' if supabase else 'Not connected'}")
        
        # Track database operations in response
        db_result = {'attempted': False, 'success': False, 'error': None}
        
        if supabase and customer_email:
            db_result['attempted'] = True
            try:
                # Check if user exists
                print(f"Checking if user exists: {customer_email}")
                result = supabase.table('users').select("*").eq('email', customer_email).execute()
                
                if result.data:
                    # Update existing user
                    print(f"User exists, updating...")
                    update_data = {
                        'stripe_customer_id': stripe_customer_id,
                        'subscription_id': subscription_id,
                        'subscription_status': 'active',
                        'subscription_tier': 'legacy',  # All current users are legacy
                        'subscription_updated_at': datetime.now().isoformat()
                    }
                    update_result = supabase.table('users').update(update_data).eq('email', customer_email).execute()
                    print(f"Updated user: {customer_email}")
                    db_result['success'] = True
                    db_result['action'] = 'updated'
                    
                    # Check if this is a reactivation (was cancelled before)
                    if result.data[0].get('subscription_status') != 'active':
                        # Send welcome back email
                        try:
                            print(f"Sending welcome back email to {customer_email}")
                            email_sent = send_welcome_email(customer_email)
                            if email_sent:
                                print("Welcome back email sent successfully!")
                        except Exception as e:
                            print(f"Error sending welcome back email: {e}")
                else:
                    # Create new user
                    print(f"Creating new user...")
                    user_data = {
                        'email': customer_email.lower() if customer_email else '',  # Store lowercase
                        'stripe_customer_id': stripe_customer_id,
                        'subscription_id': subscription_id,
                        'subscription_status': 'active',
                        'subscription_tier': 'legacy',  # All current users are legacy
                        'created_at': datetime.now().isoformat()
                    }
                    insert_result = supabase.table('users').insert(user_data).execute()
                    print(f"Created new user: {customer_email}")
                    print(f"Insert result: {insert_result}")
                    db_result['success'] = True
                    db_result['action'] = 'created'
                    
                    # Generate setup token for password creation
                    from auth_helpers import generate_setup_token
                    setup_token = generate_setup_token()
                    
                    # Store token in database (expires in 1 hour)
                    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
                    
                    token_data = {
                        'email': customer_email.lower() if customer_email else '',  # Store lowercase
                        'token': setup_token,
                        'expires_at': expires_at,
                        'used': False
                    }
                    
                    try:
                        # Store the setup token (reusing password_reset_tokens table)
                        supabase.table('password_reset_tokens').insert(token_data).execute()
                        print(f"Setup token stored for {customer_email}")
                        
                        # Generate setup link
                        app_url = os.getenv("RENDER_APP_URL", "https://commission-tracker-app.onrender.com")
                        setup_link = f"{app_url}?setup_token={setup_token}"
                        
                        # Send password setup email to new subscriber
                        from email_utils import send_password_setup_email
                        print(f"Sending password setup email to {customer_email}")
                        email_sent = send_password_setup_email(customer_email, setup_link)
                        if email_sent:
                            print("Password setup email sent successfully!")
                        else:
                            print("Failed to send password setup email")
                    except Exception as e:
                        print(f"Error setting up password flow: {e}")
                        # Don't fail the webhook if email fails
                    
            except Exception as e:
                error_msg = f"Database error: {str(e)}"
                print(error_msg)
                app.logger.error(error_msg)
                db_result['success'] = False
                db_result['error'] = str(e)
        
        # Add database result to response
        debug_info['db_operation'] = db_result
    
    # Handle subscription updated
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        status = subscription.get('status')
        customer_id = subscription.get('customer')
        
        print(f"Subscription updated: Customer {customer_id}, Status: {status}")
        
        # Update subscription status in database
        supabase = get_supabase_client()
        if supabase:
            try:
                supabase.table('users').update({
                    'subscription_status': status,
                    'subscription_updated_at': datetime.now().isoformat()
                }).eq('stripe_customer_id', customer_id).execute()
            except Exception as e:
                print(f"Database error: {e}")
    
    # Handle subscription deleted
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        
        print(f"Subscription cancelled: Customer {customer_id}")
        
        # Update subscription status to cancelled
        supabase = get_supabase_client()
        if supabase:
            try:
                supabase.table('users').update({
                    'subscription_status': 'cancelled',
                    'subscription_updated_at': datetime.now().isoformat()
                }).eq('stripe_customer_id', customer_id).execute()
            except Exception as e:
                print(f"Database error: {e}")
    
    # Handle payment failed
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        customer_id = invoice.get('customer')
        attempt_count = invoice.get('attempt_count', 0)

        print(f"Payment failed: Customer {customer_id}, attempt #{attempt_count}")

        # Mark user as past_due so they are blocked from logging in after retries exhausted.
        # Stripe also fires customer.subscription.updated with status='past_due', but updating
        # here as well ensures the DB is correct even if that event is delayed or missed.
        supabase = get_supabase_client()
        if supabase and customer_id:
            try:
                supabase.table('users').update({
                    'subscription_status': 'past_due',
                    'subscription_updated_at': datetime.now().isoformat()
                }).eq('stripe_customer_id', customer_id).execute()
                print(f"Marked customer {customer_id} as past_due")
            except Exception as e:
                print(f"Database error updating past_due status: {e}")
    
    # Add additional info for checkout events
    if event['type'] == 'checkout.session.completed':
        debug_info['checkout_processed'] = True
        # Safely check if variables exist
        if 'customer_email' in locals():
            debug_info['customer_email'] = customer_email
        if 'supabase' in locals():
            debug_info['supabase_connected'] = supabase is not None
        if 'db_result' in locals():
            debug_info['db_operation'] = db_result
    
    return jsonify(debug_info), 200

@app.route('/test', methods=['GET', 'POST'])
def test_endpoint():
    """Test endpoint to verify deployment."""
    print("\n" + "="*50)
    print("TEST ENDPOINT CALLED")
    print("="*50)
    return jsonify({
        'message': 'Test endpoint working',
        'version': '1.1',
        'method': request.method,
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Webhook server starting on port {port}")
    print("Environment variables:")
    print(f"  STRIPE_SECRET_KEY: {'Set' if os.getenv('STRIPE_SECRET_KEY') else 'Not set'}")
    print(f"  STRIPE_WEBHOOK_SECRET: {'Set' if os.getenv('STRIPE_WEBHOOK_SECRET') else 'Not set'}")
    print(f"  PRODUCTION_SUPABASE_URL: {'Set' if os.getenv('PRODUCTION_SUPABASE_URL') else 'Not set'}")
    app.run(host='0.0.0.0', port=port, debug=False)