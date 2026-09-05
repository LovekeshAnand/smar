"""
structured_data/adapters/base.py
================================
Abstract base class for all storage adapters in SMAR v2.
Defines unified interface for connecting to any data source (SQL database,
CSV, Excel, DuckDB, etc.), introspecting its schema, and running optimized queries.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class BaseStorageAdapter(ABC):
    """
    Abstract interface for database and tabular file storage adapters.
    """

    @abstractmethod
    def get_source_name(self) -> str:
        """Human-readable identifier for this data source."""
        pass

    @abstractmethod
    def get_source_type(self) -> str:
        """Type of source (e.g., 'sqlite', 'csv', 'excel', 'postgres')."""
        pass

    @abstractmethod
    def introspect_schema(self) -> Dict[str, Any]:
        """
        Introspect the dataset schema and return metadata:
        {
            "source_name": str,
            "source_type": str,
            "tables": [
                {
                    "table_name": str,
                    "columns": [
                        {"name": str, "type": str, "is_primary_key": bool, "is_volatile": bool, "sample_values": list}
                    ],
                    "row_count": int,
                    "indexes": list
                }
            ]
        }
        """
        pass

    @abstractmethod
    def get_item_by_id(self, item_id: str, table_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Exact lookup by primary key/item code."""
        pass

    @abstractmethod
    def search_by_text(self, query: str, limit: int = 20, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fast indexed full-text / prefix search across string attributes."""
        pass

    @abstractmethod
    def filter_items(
        self,
        filters: Dict[str, Any],
        limit: int = 50,
        table_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filter items by exact columnar matches (e.g. category, brand, active status)."""
        pass

    @abstractmethod
    def get_aggregations(
        self,
        group_by: Optional[str] = None,
        table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compute aggregated metrics (total records, category breakdowns, stock values)."""
        pass

    @abstractmethod
    def get_total_count(self, table_name: Optional[str] = None) -> int:
        """Return total record count."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Release any database connections or temporary memory structures."""
        pass
