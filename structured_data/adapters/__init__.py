"""
structured_data/adapters package for SMAR v2
"""

from .base import BaseStorageAdapter
from .sqlite_adapter import SQLiteStorageAdapter
from .file_adapter import FileStorageAdapter
from .registry import AdapterRegistry

__all__ = [
    "BaseStorageAdapter",
    "SQLiteStorageAdapter",
    "FileStorageAdapter",
    "AdapterRegistry",
]
