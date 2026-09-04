"""
connectors/base.py
==================
Abstract base connector interface for SMAR.
All external integrations (WhatsApp, Google Workspace, Notion) adhere to this contract.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseConnector(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the connector service."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if service is configured, authenticated, and reachable."""
        pass

    @abstractmethod
    async def fetch_context(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch recent events/messages/records from the service to be normalized
        and ingested into the Context Layer.
        """
        pass

    @abstractmethod
    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an automated action (e.g. send message, send email, create event).
        """
        pass
