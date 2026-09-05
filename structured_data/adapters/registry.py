"""
structured_data/adapters/registry.py
====================================
Adapter Registry for SMAR v2.
Maintains active database and file storage adapters, handles dynamic loading,
and routes queries to the active primary data source.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from .base import BaseStorageAdapter
from .sqlite_adapter import SQLiteStorageAdapter
from .file_adapter import FileStorageAdapter

logger = logging.getLogger("smar.structured_data.adapters.registry")


class AdapterRegistry:
    """
    Registry and coordinator for active storage adapters.
    """

    def __init__(self):
        self._adapters: Dict[str, BaseStorageAdapter] = {}
        self._primary_key: Optional[str] = None

    def register(self, key: str, adapter: BaseStorageAdapter, set_as_primary: bool = False) -> None:
        """Register a storage adapter under a unique key."""
        self._adapters[key] = adapter
        logger.info(f"Registered adapter '{key}' ({adapter.get_source_name()}).")
        if set_as_primary or self._primary_key is None:
            self._primary_key = key

    def get(self, key: str) -> Optional[BaseStorageAdapter]:
        """Retrieve adapter by key."""
        return self._adapters.get(key)

    def get_primary(self) -> BaseStorageAdapter:
        """Get currently active primary storage adapter."""
        if not self._primary_key or self._primary_key not in self._adapters:
            # Fallback to default SQLite adapter
            default_sqlite = SQLiteStorageAdapter()
            self.register("primary_sqlite", default_sqlite, set_as_primary=True)
            return default_sqlite
        return self._adapters[self._primary_key]

    def set_primary(self, key: str) -> bool:
        """Set the active primary adapter by key."""
        if key in self._adapters:
            self._primary_key = key
            logger.info(f"Primary adapter set to '{key}'.")
            return True
        return False

    def list_adapters(self) -> List[Dict[str, Any]]:
        """Return list of all registered adapters with status metadata."""
        out = []
        for k, adapter in self._adapters.items():
            out.append({
                "key": k,
                "name": adapter.get_source_name(),
                "type": adapter.get_source_type(),
                "is_primary": (k == self._primary_key),
                "total_records": adapter.get_total_count()
            })
        return out

    def load_file_adapter(self, file_path: str, key: Optional[str] = None, set_as_primary: bool = True) -> BaseStorageAdapter:
        """Load and index a CSV or Excel file as an active adapter."""
        k = key or f"file_{os.path.basename(file_path)}"
        adapter = FileStorageAdapter(file_path=file_path)
        self.register(k, adapter, set_as_primary=set_as_primary)
        return adapter
