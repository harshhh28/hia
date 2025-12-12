import streamlit as st
from supabase import create_client
from datetime import datetime
import time
import re


class AuthService:
    def __init__(self):
        try:
            # Initialize Supabase client directly
            # This ensures a fresh client for each session, preventing state leakage
            self.supabase = create_client(
                st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
            )
        except Exception as e:
            st.error(f"Failed to initialize services: {str(e)}")
            raise e

        # Try to restore session from Supabase if no current session
        self.try_restore_session()

        # Validate session on initialization
        if "auth_token" in st.session_state:
            if not self.validate_session_token():
                # Don't sign out immediately on failure during init to avoid loop
                pass

    def try_restore_session(self):
        """Try to restore session from Supabase stored session."""
        try:
            # First try to restore from Streamlit session state tokens
            if "auth_token" in st.session_state and "refresh_token" in st.session_state:
                try:
                    self.supabase.auth.set_session(
                        st.session_state.auth_token, st.session_state.refresh_token
                    )
                except Exception as e:
                    # print(f"Set session failed: {e}")
                    pass

            # Check if Supabase has a stored session
            session = self.supabase.auth.get_session()
            if session and session.access_token:
                # If we have a session but it's not in state, restore it
                # Or if the token in state is stale/different, update it
                current_token = st.session_state.get("auth_token")
                if not current_token or current_token != session.access_token:
                    user = self.supabase.auth.get_user()
                    if user and user.user:
                        user_data = self.get_user_data(user.user.id)
                        if user_data:
                            st.session_state.auth_token = session.access_token
                            st.session_state.refresh_token = session.refresh_token
                            st.session_state.user = user_data
        except Exception:
            # If restoration fails, continue without session
            pass

    def validate_email(self, email):
        """Validate email format."""
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return bool(re.match(pattern, email))

    def check_existing_user(self, email):
        """Check if user already exists."""
        try:
            result = (
                self.supabase.table("users").select("id").eq("email", email).execute()
            )
            return len(result.data) > 0
        except Exception:
            return False

    def sign_up(self, email, password, name):
        try:
            auth_response = self.supabase.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"data": {"name": name}},
                }
            )

            if not auth_response.user:
                return False, "Failed to create user account"

            user_data = {
                "id": auth_response.user.id,
                "email": email,
                "name": name,
                "created_at": datetime.now().isoformat(),
            }

            # Insert user data into users table
            self.supabase.table("users").insert(user_data).execute()

            # If we got a session immediately (email confirmation off), store it
            if auth_response.session:
                st.session_state.auth_token = auth_response.session.access_token
                st.session_state.refresh_token = auth_response.session.refresh_token
                st.session_state.user = user_data

            return True, user_data

        except Exception as e:
            error_msg = str(e).lower()
            if "duplicate" in error_msg or "already registered" in error_msg:
                return False, "Email already registered"
            return False, f"Sign up failed: {str(e)}"

    def sign_in(self, email, password):
        try:
            # Clear any existing session data first
            # But don't call sign_out() which destroys auth_service in session_state
            # Just clear the supabase client session locally
            try:
                self.supabase.auth.sign_out()
            except Exception:
                pass

            auth_response = self.supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )

            if auth_response and auth_response.user:
                # Get user data
                user_data = self.get_user_data(auth_response.user.id)
                if not user_data:
                    return False, "User data not found"

                # Store session info
                st.session_state.auth_token = auth_response.session.access_token
                st.session_state.refresh_token = auth_response.session.refresh_token
                st.session_state.user = user_data
                return True, user_data

            return False, "Invalid login response"
        except Exception as e:
            return False, str(e)

    def sign_out(self):
        """Sign out and clear all session data."""
        try:
            self.supabase.auth.sign_out()
        except Exception:
            pass

        try:
            from auth.session_manager import SessionManager

            SessionManager.clear_session_state()
            return True, None
        except Exception as e:
            return False, str(e)

    def get_user(self):
        try:
            return self.supabase.auth.get_user()
        except Exception:
            return None

    def create_session(self, user_id, title=None):
        try:
            current_time = datetime.now()
            default_title = f"{current_time.strftime('%d-%m-%Y')} | {current_time.strftime('%H:%M:%S')}"

            session_data = {
                "user_id": user_id,
                "title": title or default_title,
                "created_at": current_time.isoformat(),
            }
            result = self.supabase.table("chat_sessions").insert(session_data).execute()
            return True, result.data[0] if result.data else None
        except Exception as e:
            return False, str(e)

    def get_user_sessions(self, user_id):
        try:
            result = (
                self.supabase.table("chat_sessions")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return True, result.data
        except Exception as e:
            st.error(f"Error fetching sessions: {str(e)}")
            return False, []

    def save_chat_message(self, session_id, content, role="user"):
        try:
            message_data = {
                "session_id": session_id,
                "content": content,
                "role": role,
                "created_at": datetime.now().isoformat(),
            }
            result = self.supabase.table("chat_messages").insert(message_data).execute()
            return True, result.data[0] if result.data else None
        except Exception as e:
            return False, str(e)

    def get_session_messages(self, session_id):
        try:
            result = (
                self.supabase.table("chat_messages")
                .select("*")
                .eq("session_id", session_id)
                .order("created_at")
                .execute()
            )
            return True, result.data
        except Exception as e:
            return False, str(e)

    def delete_session(self, session_id):
        try:
            self.supabase.table("chat_messages").delete().eq(
                "session_id", session_id
            ).execute()

            self.supabase.table("chat_sessions").delete().eq("id", session_id).execute()

            return True, None
        except Exception as e:
            st.error(f"Failed to delete session: {str(e)}")
            return False, str(e)

    def validate_session_token(self):
        """Validate existing session token on startup."""
        try:
            session = self.supabase.auth.get_session()
            if not session or not session.access_token:
                # If no session in Supabase client, but we have tokens in state, try to set session again
                if (
                    "auth_token" in st.session_state
                    and "refresh_token" in st.session_state
                ):
                    try:
                        self.supabase.auth.set_session(
                            st.session_state.auth_token, st.session_state.refresh_token
                        )
                        session = self.supabase.auth.get_session()
                    except Exception:
                        pass

            if not session or not session.access_token:
                return None

            # Relaxed validation: If we have a valid Supabase session, update our state instead of failing
            # This handles token refreshes or slight mismatches
            if session.access_token != st.session_state.get("auth_token"):
                st.session_state.auth_token = session.access_token
                if session.refresh_token:
                    st.session_state.refresh_token = session.refresh_token

            user = self.supabase.auth.get_user()
            if not user or not user.user:
                return None

            return self.get_user_data(user.user.id)
        except Exception:
            return None

    def get_user_data(self, user_id):
        """Get user data from database."""
        try:
            response = (
                self.supabase.table("users")
                .select("*")
                .eq("id", user_id)
                .single()
                .execute()
            )
            return response.data if response else None
        except Exception:
            return None
