"""
Google Workspace connector suite for SMAR
"""

from .auth import GoogleAuthManager
from .gmail import GmailConnector
from .calendar import CalendarConnector
from .docs_sheets import GoogleDocsSheetsConnector

__all__ = [
    "GoogleAuthManager",
    "GmailConnector",
    "CalendarConnector",
    "GoogleDocsSheetsConnector",
]
