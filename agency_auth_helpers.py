"""
Agency Platform Authentication Helpers
Handles agency owner signup, login, and onboarding
"""
import streamlit as st
from supabase import Client, create_client
import os
from datetime import datetime
import secrets
import string

def show_agency_signup_form():
    """Show agency owner signup form."""
    st.subheader("🏢 Start Your Agency Account")
    st.write("Create an agency account to manage your team of agents")

    # Use columns to control form width
    col1, col2 = st.columns([2, 3])
    with col1:
        with st.form("agency_signup_form"):
            agency_name = st.text_input("Agency Name*", key="agency_name",
                                       placeholder="e.g. ABC Insurance Agency")
            owner_name = st.text_input("Your Name*", key="owner_name",
                                      placeholder="e.g. John Smith")
            email = st.text_input("Email*", key="agency_email",
                                 autocomplete="email",
                                 placeholder="you@yourагency.com")
            password = st.text_input("Password*", type="password", key="agency_password",
                                    autocomplete="new-password")
            confirm_password = st.text_input("Confirm Password*", type="password",
                                            key="agency_confirm_password")

            st.caption("Password must be at least 8 characters")

            # Terms checkbox
            agree_terms = st.checkbox("I agree to the Terms of Service and Privacy Policy")

            submit = st.form_submit_button("Create Agency Account", type="primary",
                                          use_container_width=True)

            if submit:
                # Validation
                errors = []
                if not agency_name:
                    errors.append("Agency name is required")
                if not owner_name:
                    errors.append("Your name is required")
                if not email:
                    errors.append("Email is required")
                if not password:
                    errors.append("Password is required")
                elif len(password) < 8:
                    errors.append("Password must be at least 8 characters")
                if password != confirm_password:
                    errors.append("Passwords do not match")
                if not agree_terms:
                    errors.append("You must agree to the Terms of Service")

                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    # Create agency account
                    success, message = create_agency_account(
                        agency_name=agency_name,
                        owner_name=owner_name,
                        email=email,
                        password=password
                    )

                    if success:
                        st.success("🎉 Agency account created successfully!")
                        st.info("Logging you in...")
                        # Auto-login the user
                        st.session_state["password_correct"] = True
                        st.session_state["user_email"] = email
                        st.session_state["is_agency_owner"] = True
                        # Set agency_id in session (from message which contains the ID)
                        if "agency_id:" in message:
                            agency_id = message.split("agency_id:")[1].strip()
                            st.session_state["agency_id"] = agency_id
                        st.balloons()
                        # Trigger onboarding
                        st.session_state["show_onboarding"] = True
                        st.rerun()
                    else:
                        st.error(f"Error creating agency account: {message}")


def create_agency_account(agency_name: str, owner_name: str, email: str, password: str):
    """
    Create a new agency account with owner.

    Returns: (success: bool, message: str)
    """
    try:
        # Create Supabase client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")

        if not url or not key:
            return False, "Database not configured"

        supabase = create_client(url, key)

        # Check if email already exists
        existing_user = supabase.table('users').select('email').eq('email', email.lower()).execute()
        if existing_user.data:
            return False, "Email already registered. Please use a different email or login."

        # Create user record in Supabase Auth (if using Supabase Auth)
        # For now, we'll just create in users table

        from auth_helpers import _hash_password
        # Insert into users table
        user_data = {
            'email': email.lower(),
            'password_hash': _hash_password(password),
            'password_set': True,
            'full_name': owner_name,
            'is_active': True,
            'subscription_status': 'trial',  # Start with trial
            'created_at': datetime.utcnow().isoformat()
        }

        user_result = supabase.table('users').insert(user_data).execute()

        if not user_result.data:
            return False, "Error creating user account"

        user_id = user_result.data[0]['id']

        # Create agency record
        agency_data = {
            'agency_name': agency_name,
            'owner_user_id': user_id,  # Use user_id, not email!
            'is_demo': False,
            'created_at': datetime.utcnow().isoformat(),
            'settings': {
                'commission_rules': {
                    'new_business': 0.50,
                    'renewal': 0.25,
                    'service': 0.10
                },
                'features': {
                    'agent_rankings': True,
                    'white_label': False,
                    'api_access': False
                }
            }
        }

        agency_result = supabase.table('agencies').insert(agency_data).execute()

        if not agency_result.data:
            # Rollback: delete the user we just created
            supabase.table('users').delete().eq('id', user_id).execute()
            return False, "Error creating agency record"

        agency_id = agency_result.data[0]['id']

        return True, f"Success! agency_id:{agency_id}"

    except Exception as e:
        return False, str(e)


def get_user_role(user_email: str, supabase: Client = None) -> dict:
    """
    Determine the user's role: agency_owner, agent, or solo_agent.

    This is the primary authentication function for Phase 2 that routes users
    to the appropriate dashboard based on their role.

    Returns: {
        'role': 'agency_owner' | 'agent' | 'solo_agent',
        'user_id': str,
        'agency_id': str or None,
        'agent_id': str or None,
        'agency_name': str or None,
        'agent_name': str or None
    }
    """
    try:
        if not supabase:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_ANON_KEY")
            supabase = create_client(url, key)

        # Get user_id from email
        user_result = supabase.table('users').select('id, full_name').eq('email', user_email.lower()).execute()

        if not user_result.data:
            return {
                'role': 'solo_agent',
                'user_id': None,
                'agency_id': None,
                'agent_id': None,
                'agency_name': None,
                'agent_name': None
            }

        user_id = user_result.data[0]['id']
        user_name = user_result.data[0].get('full_name', '')

        # Check if user owns an agency (agency_owner role)
        agency_result = supabase.table('agencies').select('id, agency_name').eq('owner_user_id', user_id).execute()

        if agency_result.data and len(agency_result.data) > 0:
            agency = agency_result.data[0]
            return {
                'role': 'agency_owner',
                'user_id': user_id,
                'agency_id': agency['id'],
                'agent_id': None,
                'agency_name': agency['agency_name'],
                'agent_name': user_name
            }

        # Check if user is an agent in an agency (agent role)
        agent_result = supabase.table('agents').select('id, agency_id, full_name, is_active').eq('user_id', user_id).execute()

        if agent_result.data and len(agent_result.data) > 0:
            agent = agent_result.data[0]

            # Get agency name
            agency_info = supabase.table('agencies').select('agency_name').eq('id', agent['agency_id']).execute()
            agency_name = agency_info.data[0]['agency_name'] if agency_info.data else None

            return {
                'role': 'agent',
                'user_id': user_id,
                'agency_id': agent['agency_id'],
                'agent_id': agent['id'],
                'agency_name': agency_name,
                'agent_name': agent.get('full_name', user_name),
                'is_active': agent.get('is_active', True)
            }

        # Default: solo agent (no agency affiliation)
        return {
            'role': 'solo_agent',
            'user_id': user_id,
            'agency_id': None,
            'agent_id': None,
            'agency_name': None,
            'agent_name': user_name
        }

    except Exception as e:
        print(f"Error determining user role: {e}")
        return {
            'role': 'solo_agent',
            'user_id': None,
            'agency_id': None,
            'agent_id': None,
            'agency_name': None,
            'agent_name': None
        }


def check_if_agency_owner(user_email: str, supabase: Client = None) -> dict:
    """
    Check if the logged-in user is an agency owner.

    DEPRECATED: Use get_user_role() instead for Phase 2.
    This function is kept for backward compatibility with Phase 1 code.

    Returns: {
        'is_agency_owner': bool,
        'agency_id': str or None,
        'agency_name': str or None
    }
    """
    role_info = get_user_role(user_email, supabase)

    return {
        'is_agency_owner': role_info['role'] == 'agency_owner',
        'agency_id': role_info['agency_id'],
        'agency_name': role_info['agency_name']
    }


def show_agency_onboarding_wizard():
    """Show onboarding wizard for new agency owners."""
    st.title("🎉 Welcome to Your Agency Platform!")

    # Initialize onboarding step
    if 'onboarding_step' not in st.session_state:
        st.session_state.onboarding_step = 1

    step = st.session_state.onboarding_step

    # Progress indicator
    st.progress(step / 4)
    st.caption(f"Step {step} of 4")

    if step == 1:
        show_onboarding_step_1()
    elif step == 2:
        show_onboarding_step_2()
    elif step == 3:
        show_onboarding_step_3()
    elif step == 4:
        show_onboarding_step_4()


def show_onboarding_step_1():
    """Step 1: Welcome and Agency Info confirmation."""
    st.subheader("Step 1: Confirm Your Agency Details")

    agency_name = st.session_state.get('agency_name', 'Your Agency')
    st.write(f"**Agency Name:** {agency_name}")
    st.write(f"**Owner Email:** {st.session_state.get('user_email', '')}")

    st.info("✅ Your agency account has been created!")

    st.markdown("""
    ### What's Next?

    We'll help you get started with:
    1. ✅ Your agency dashboard
    2. 👥 Adding your first agent (optional)
    3. 🔗 Choosing integrations
    4. 📊 Importing your first statement (optional)
    """)

    if st.button("Continue →", type="primary"):
        st.session_state.onboarding_step = 2
        st.rerun()

    if st.button("Skip Onboarding"):
        st.session_state.show_onboarding = False
        del st.session_state.onboarding_step
        st.rerun()


def show_onboarding_step_2():
    """Step 2: Add first agent (optional)."""
    st.subheader("Step 2: Add Your First Agent (Optional)")

    st.write("You can add agents now or skip and do it later from Team Management.")

    with st.form("add_first_agent"):
        agent_name = st.text_input("Agent Name", placeholder="e.g. Jane Doe")
        agent_email = st.text_input("Agent Email", placeholder="jane@youragency.com")
        agent_role = st.selectbox("Role", ["agent", "manager", "admin"])

        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Add Agent", type="primary")
        with col2:
            skip = st.form_submit_button("Skip for Now")

        if submit:
            if agent_name and agent_email:
                # TODO: Implement add agent logic
                st.success(f"Agent {agent_name} added! (Feature coming soon)")
                st.session_state.onboarding_step = 3
                st.rerun()
            else:
                st.error("Please enter agent name and email")

        if skip:
            st.session_state.onboarding_step = 3
            st.rerun()


def show_onboarding_step_3():
    """Step 3: Choose integrations."""
    st.subheader("Step 3: Choose Your Integrations")

    st.write("Select the systems you'd like to integrate with:")

    # Popular integrations
    integrations = [
        {"name": "Applied Epic", "type": "AMS", "icon": "🏢"},
        {"name": "QuickBooks Online", "type": "Accounting", "icon": "💰"},
        {"name": "EZLynx", "type": "Rater", "icon": "📊"},
        {"name": "Salesforce", "type": "CRM", "icon": "👥"},
    ]

    selected = []
    for integration in integrations:
        if st.checkbox(f"{integration['icon']} {integration['name']} ({integration['type']})", key=f"int_{integration['name']}"):
            selected.append(integration['name'])

    st.caption("Don't worry, you can add more integrations later!")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back"):
            st.session_state.onboarding_step = 2
            st.rerun()
    with col2:
        if st.button("Continue →", type="primary"):
            if selected:
                st.success(f"Selected {len(selected)} integrations")
            st.session_state.onboarding_step = 4
            st.rerun()


def show_onboarding_step_4():
    """Step 4: All done!"""
    st.subheader("🎉 You're All Set!")

    st.success("Your agency platform is ready to use!")

    st.markdown("""
    ### Quick Start Guide:

    1. **Dashboard** - View your agency metrics and rankings
    2. **Team Management** - Add and manage your agents
    3. **Reconciliation** - Import carrier statements
    4. **Integrations** - Configure your selected integrations
    5. **Settings** - Customize your agency preferences
    """)

    st.info("💡 **Tip:** Start by adding your agents, then import your first carrier statement to see the platform in action!")

    if st.button("Go to Dashboard →", type="primary"):
        # Mark onboarding as complete
        st.session_state.show_onboarding = False
        if 'onboarding_step' in st.session_state:
            del st.session_state.onboarding_step
        st.rerun()
