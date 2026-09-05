"""
structured_data/models.py
=========================
Pydantic data models and schemas for Kirana inventory items,
validation results, and ETL batch statistics.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


class InventoryItem(BaseModel):
    """
    Primary Inventory Item Model representing source-of-truth data.
    
    Static fields:
        item_id: Canonical unique SKU/item identifier (e.g. 'INV-100234')
        barcode: Global trade barcode / EAN (e.g. '8901030800012')
        canonical_name: Standardized human-readable name in Kirana context (e.g. 'Tata Salt 1kg')
        normalized_name: Lowercased, whitespace-stripped canonical name for entity resolution
        category: Inventory product classification (e.g. 'Spices & Cooking Essentials')
        brand: Manufacturer or brand name (e.g. 'Tata')
        unit_of_measure: Unit of measurement (e.g. 'kg', 'g', 'pack', 'liter')
        hsn_code: GST tax HSN code
        created_at: ISO-8601 creation timestamp
        
    Volatile fields:
        quantity: Current stock count in warehouse/store (>= 0)
        unit_price: Selling MRP in INR (> 0)
        cost_price: Purchase cost in INR (> 0)
        reorder_level: Minimum stock threshold triggering reorder alert
        is_active: Active status flag (1=Active, 0=Discontinued)
        updated_at: ISO-8601 last modified timestamp
    """
    # Static attributes
    item_id: str = Field(..., description="Canonical unique item ID")
    barcode: Optional[str] = Field(None, description="EAN/UPC Barcode string")
    canonical_name: str = Field(..., description="Original/display product name")
    normalized_name: str = Field(..., description="Cleaned, lowercased string for entity resolution")
    category: str = Field(..., description="Product category")
    brand: str = Field("Generic", description="Brand or manufacturer")
    unit_of_measure: str = Field("piece", description="Unit of measurement")
    hsn_code: Optional[str] = Field(None, description="HSN tax classification code")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Volatile attributes (stateful stock/pricing)
    quantity: float = Field(..., ge=0.0, description="Available stock quantity (must be non-negative)")
    unit_price: float = Field(..., gt=0.0, description="Selling price per unit in INR (must be > 0)")
    cost_price: float = Field(..., gt=0.0, description="Purchase cost per unit in INR (must be > 0)")
    reorder_level: int = Field(10, ge=0, description="Stock reorder alert threshold")
    is_active: int = Field(1, description="Active status flag (1 or 0)")
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("canonical_name", "category", "item_id")
    @classmethod
    def validate_non_empty_str(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Field '{info.field_name}' cannot be empty or whitespace.")
        return v.strip()

    @field_validator("quantity")
    @classmethod
    def validate_quantity_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Stock quantity cannot be negative.")
        return v

    @field_validator("unit_price", "cost_price")
    @classmethod
    def validate_price_positive(cls, v: float, info) -> float:
        if v <= 0:
            raise ValueError(f"Price field '{info.field_name}' must be greater than zero.")
        return v

    def to_db_tuple(self) -> tuple:
        """Convert model instance to tuple for SQLite parameterized insertion."""
        return (
            self.item_id,
            self.barcode,
            self.canonical_name,
            self.normalized_name,
            self.category,
            self.brand,
            self.unit_of_measure,
            self.hsn_code,
            self.created_at,
            self.quantity,
            self.unit_price,
            self.cost_price,
            self.reorder_level,
            self.is_active,
            self.updated_at
        )


class ValidationResult(BaseModel):
    """Result container for individual record validation."""
    is_valid: bool
    item: Optional[InventoryItem] = None
    errors: List[str] = Field(default_factory=list)
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class ETLBatchResult(BaseModel):
    """Execution statistics report for a bulk ETL load run."""
    batch_id: str
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0
    skipped_duplicates: int = 0
    failed_rows: int = 0
    processing_time_seconds: float = 0.0
    errors_summary: List[str] = Field(default_factory=list)

    def summary(self) -> str:
        return (
            f"--- ETL Batch Ingestion Summary [{self.batch_id}] ---\n"
            f"Total Processed     : {self.total_rows:,}\n"
            f"Valid Records       : {self.valid_rows:,}\n"
            f"Invalid Records     : {self.invalid_rows:,}\n"
            f"Inserted Rows       : {self.inserted_rows:,}\n"
            f"Updated Rows        : {self.updated_rows:,}\n"
            f"Skipped Duplicates  : {self.skipped_duplicates:,}\n"
            f"Failed Inserts      : {self.failed_rows:,}\n"
            f"Processing Time     : {self.processing_time_seconds:.3f} sec\n"
            f"Throughput          : {self.total_rows / max(self.processing_time_seconds, 0.001):,.0f} rows/sec\n"
            f"---------------------------------------------------"
        )
