"""
Application Configuration
Feature flags and settings for easy enable/disable of features

Created: December 1, 2025
"""

# =============================================================================
# FEATURE FLAGS
# =============================================================================
# Set to False to disable features without removing code

FEATURES = {
    # Phase 2 Features (all stable)
    'agent_dashboard': True,
    'commission_tracking': True,
    'gamification': True,
    'leaderboard': True,
    'notifications': True,
    'renewal_management': True,

    # Phase 3 Features
    'ai_insights': True,  # Sprint 3 - AI & Predictive Analytics
    'onedrive_documents': True,  # Sprint 5, Task 5.3 - Document Management
    'commission_reconciliation': True,  # Sprint 5, Task 5.2 - Automated Commission Reconciliation (NEW!)

    # Launch-phase toggles
    # Set to False to hide the Agency Signup tab during the solo-agent launch.
    # Flip to True when the agency tier is ready to open.
    'agency_signup': False,

    # Future Features (not yet implemented)
    'white_label': False,  # Sprint 6
    'multi_language': False,  # Sprint 6
}

# =============================================================================
# ONEDRIVE/SHAREPOINT CONFIGURATION
# =============================================================================
# These are read from environment variables for security
# Set in your environment or .env file:
#   - MICROSOFT_TENANT_ID
#   - MICROSOFT_CLIENT_ID
#   - MICROSOFT_CLIENT_SECRET

ONEDRIVE_CONFIG = {
    'enabled': FEATURES['onedrive_documents'],
    'root_folder': 'AMS Documents',  # Root folder in OneDrive
    'max_file_size_mb': 100,  # Max file size for uploads
    'allowed_extensions': ['.pdf', '.docx', '.xlsx', '.jpg', '.png', '.msg'],
}

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
# Read from environment variables

DATABASE_CONFIG = {
    'supabase_url': None,  # Set via SUPABASE_URL env var
    'supabase_key': None,  # Set via SUPABASE_KEY env var
}

# =============================================================================
# AI/ML CONFIGURATION
# =============================================================================

AI_CONFIG = {
    'enabled': FEATURES['ai_insights'],
    'renewal_prediction_days_ahead': 90,  # Predict renewals 90 days out
    'churn_risk_threshold': 60,  # Alert if churn risk >= 60
    'clv_discount_rate': 0.10,  # 10% discount rate for CLV present value
}

# =============================================================================
# SUBSCRIPTION OFFER COPY
# =============================================================================
# Edit these values to update the trial/offer presentation in the login UI
# without touching application logic in auth_helpers.py.

SUBSCRIPTION_OFFER = {
    # Heading shown at the top of the "Start Free Trial" tab
    'tab_heading': "Start Tracking Your Commissions",
    # One-line description shown below the heading
    'tab_tagline': (
        "Everything a solo agent needs to track policies, "
        "reconcile statements, and maximize earnings."
    ),
    # Feature bullet points — each item rendered with a leading ✅
    'features': [
        "Track All Your Policies & Commissions",
        "Automated Statement Reconciliation",
        "Earnings Reports & Analytics",
        "Excel Import & Export",
        "Carrier & MGA Management",
        "Email Support",
    ],
    # Trial length in days (must match Stripe checkout kwargs)
    'trial_days': 14,
    # Price string shown after the trial period headline
    'trial_price_monthly': "$19.99/month",
    # Fine-print caption under the price
    'trial_caption': (
        "No charge for 14 days. Cancel anytime. Secure payment via Stripe."
    ),
    # Version stamps recorded in Stripe checkout metadata for legal acceptance
    'terms_version': '2024-12-06',
    'privacy_version': '2024-12-06',
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# =============================================================================
# SUPPORT CONTACT CONFIG
# =============================================================================
# Used in the subscribe tab and post-checkout onboarding copy.
# Override at runtime via environment variables:
#   SUPPORT_EMAIL — contact address shown to users (overrides email_fallback)
#   FROM_EMAIL    — also accepted as a fallback when SUPPORT_EMAIL is not set
#   SUPPORT_URL   — optional; wraps the email in a Markdown link when set

SUPPORT_CONTACT = {
    # Shown when neither SUPPORT_EMAIL nor FROM_EMAIL env vars are configured
    'email_fallback': "support@agentcommissiontracker.com",
    # Label text prepended to the contact address in the subscribe tab
    'cta_text': "Questions? Email us",
    # Ordered steps shown under "What happens after checkout" in the subscribe tab
    'post_checkout_steps': [
        "You'll receive a setup email with your account link.",
        "Click the link to create your password — no card charged yet.",
        f"Your {SUBSCRIPTION_OFFER['trial_days']}-day free trial starts immediately.",
    ],
}


def is_feature_enabled(feature_name: str) -> bool:
    """Check if a feature is enabled."""
    return FEATURES.get(feature_name, False)


def get_onedrive_config():
    """Get OneDrive configuration."""
    return ONEDRIVE_CONFIG


def get_ai_config():
    """Get AI/ML configuration."""
    return AI_CONFIG


# =============================================================================
# EASY DISABLE INSTRUCTIONS
# =============================================================================
"""
To disable a feature:

1. Set the feature flag to False:
   FEATURES['onedrive_documents'] = False

2. Restart the Streamlit app

The feature will disappear from navigation and be inaccessible.
No code changes needed!

To completely remove a feature:
1. Delete the relevant files
2. Remove from navigation in commission_app.py
3. Drop database tables if needed
4. Commit changes to git
"""
