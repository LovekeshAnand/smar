"""
connectors/google/auth.py
=========================
Google Cloud & Workspace OAuth2 authentication manager for SMAR.
Handles token loading, token refreshing, and interactive authorization.
Supports loading directly from GOOGLE_REFRESH_TOKEN in .env.
"""

import os
import json
import logging
from typing import Optional, Any

logger = logging.getLogger("smar.connectors.google.auth")

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

# Scopes needed for full Workspace awareness & automation
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class GoogleAuthManager:
    def __init__(
        self,
        credentials_file: str = "credentials.json",
        token_file: str = "data/google_token.json",
    ):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.credentials_file = os.path.join(base_dir, credentials_file)
        self.token_file = os.path.join(base_dir, token_file)
        self.creds: Optional[Any] = None

    def is_authenticated(self) -> bool:
        """Check if valid credentials exist on disk or in environment."""
        if not GOOGLE_LIBS_AVAILABLE:
            return False
        
        # Check env credentials first
        if os.getenv("GOOGLE_REFRESH_TOKEN") and os.getenv("GOOGLE_CLIENT_ID"):
            return True

        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
                return creds and (creds.valid or creds.refresh_token)
            except Exception:
                return False
        return False

    def get_credentials(self):
        """
        Loads or refreshes credentials.
        Prioritizes GOOGLE_REFRESH_TOKEN from environment if present.
        """
        if not GOOGLE_LIBS_AVAILABLE:
            raise RuntimeError("Google API client libraries are not installed.")

        creds = None

        # 1. Try env-configured refresh token
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")

        if client_id and client_secret and refresh_token:
            try:
                creds = Credentials(
                    None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=SCOPES
                )
                creds.refresh(Request())
                logger.info("Authenticated Google APIs using environment refresh token.")
                self.creds = creds
                return creds
            except Exception as e:
                logger.warning(f"Failed to refresh Google token from .env: {e}")

        # 2. Check local token file
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            except Exception as e:
                logger.warning(f"Could not load token from {self.token_file}: {e}")

        # If no valid credentials, refresh or prompt user
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Refreshed Google OAuth token.")
                except Exception as e:
                    logger.error(f"Failed to refresh Google token: {e}")
                    creds = None

            if not creds:
                if not os.path.exists(self.credentials_file):
                    logger.warning(
                        f"Google credentials not configured. Please add GOOGLE_REFRESH_TOKEN to .env or place {self.credentials_file}."
                    )
                    return None

                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save token for next time
            os.makedirs(os.path.dirname(os.path.abspath(self.token_file)), exist_ok=True)
            with open(self.token_file, "w") as token:
                token.write(creds.to_json())

        self.creds = creds
        return creds

    def build_service(self, service_name: str, version: str):
        """Builds an authenticated Google API service client."""
        creds = self.get_credentials()
        if not creds:
            return None
        return build(service_name, version, credentials=creds)
