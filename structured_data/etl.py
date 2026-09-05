"""
structured_data/etl.py
======================
Reusable ETL Pipeline & Bulk Ingestion Engine for SMAR v2.
Handles Extract, Transform, Validate, and Load stages with high-performance
chunked transactions for 100,000+ Kirana inventory records.
"""

import csv
import uuid
import time
import logging
from typing import Generator, List, Dict, Any, Optional, Union, Iterable
from datetime import datetime, timezone
from pydantic import ValidationError

from .models import InventoryItem, ValidationResult, ETLBatchResult
from .db import InventoryDatabaseManager

logger = logging.getLogger("smar.structured_data.etl")


class InventoryETLPipeline:
    """
    Production ETL Pipeline for Kirana & Warehouse inventory.
    Provides Extract, Transform, Validate, and Chunked Load stages.
    """

    def __init__(self, db_manager: Optional[InventoryDatabaseManager] = None):
        self.db = db_manager or InventoryDatabaseManager()

    # --- STAGE 1: EXTRACT ---
    def extract_from_generator(self, records: Iterable[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
        """Extract raw records from an iterable or generator stream."""
        for item in records:
            yield item

    def extract_from_csv(self, csv_file_path: str) -> Generator[Dict[str, Any], None, None]:
        """Extract raw records from a CSV file."""
        with open(csv_file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield dict(row)

    # --- STAGE 2: TRANSFORM ---
    def transform_record(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transforms raw dictionary data:
        - Cleans leading/trailing whitespace
        - Computes lowercased normalized name for entity resolution
        - Fills defaults for missing brand/uom
        - Casts string numeric values to float/int
        """
        cleaned = {}
        for k, v in raw.items():
            if isinstance(v, str):
                cleaned[k] = v.strip()
            else:
                cleaned[k] = v

        # Compute normalized name
        canonical = str(cleaned.get("canonical_name", "")).strip()
        cleaned["normalized_name"] = canonical.lower()

        # Defaults
        if not cleaned.get("brand"):
            cleaned["brand"] = "Generic"
        if not cleaned.get("unit_of_measure"):
            cleaned["unit_of_measure"] = "piece"
        if not cleaned.get("created_at"):
            cleaned["created_at"] = datetime.now(timezone.utc).isoformat()
        if not cleaned.get("updated_at"):
            cleaned["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Numeric type casts
        try:
            cleaned["quantity"] = float(cleaned.get("quantity", 0.0))
        except (ValueError, TypeError):
            cleaned["quantity"] = -1.0  # Invalid indicator for validator

        try:
            cleaned["unit_price"] = float(cleaned.get("unit_price", 0.0))
        except (ValueError, TypeError):
            cleaned["unit_price"] = 0.0

        try:
            cleaned["cost_price"] = float(cleaned.get("cost_price", 0.0))
        except (ValueError, TypeError):
            cleaned["cost_price"] = 0.0

        try:
            cleaned["reorder_level"] = int(cleaned.get("reorder_level", 10))
        except (ValueError, TypeError):
            cleaned["reorder_level"] = 10

        try:
            cleaned["is_active"] = int(cleaned.get("is_active", 1))
        except (ValueError, TypeError):
            cleaned["is_active"] = 1

        return cleaned

    # --- STAGE 3: VALIDATE ---
    def validate_record(self, transformed: Dict[str, Any]) -> ValidationResult:
        """
        Validates transformed dictionary using the Pydantic InventoryItem schema.
        Enforces business rules (positive prices, non-negative quantities, non-empty names).
        """
        try:
            item = InventoryItem(**transformed)
            return ValidationResult(is_valid=True, item=item, raw_data=transformed)
        except ValidationError as ve:
            error_msgs = [f"{err['loc'][0]}: {err['msg']}" for err in ve.errors()]
            return ValidationResult(is_valid=False, item=None, errors=error_msgs, raw_data=transformed)
        except Exception as e:
            return ValidationResult(is_valid=False, item=None, errors=[str(e)], raw_data=transformed)

    # --- STAGE 4: BULK LOAD (CHUNKED TRANSACTION) ---
    def run_pipeline(
        self,
        source: Union[str, Iterable[Dict[str, Any]]],
        chunk_size: int = 5000,
        duplicate_mode: str = "UPSERT"  # "UPSERT" or "SKIP"
    ) -> ETLBatchResult:
        """
        Runs the end-to-end ETL pipeline over 100,000+ records.
        Processes items in chunks of `chunk_size` inside atomic SQLite transactions.
        
        Args:
            source: Path to CSV file or an iterable stream of dictionaries.
            chunk_size: Number of records per transaction commit batch (default 5,000).
            duplicate_mode: Strategy for primary key conflicts ("UPSERT" or "SKIP").
            
        Returns:
            ETLBatchResult with complete execution metrics.
        """
        start_time = time.time()
        batch_id = f"BATCH-{uuid.uuid4().hex[:8].upper()}"
        
        result = ETLBatchResult(batch_id=batch_id)

        # Select extraction source
        if isinstance(source, str):
            extractor = self.extract_from_csv(source)
        else:
            extractor = self.extract_from_generator(source)

        # SQL Query preparation
        if duplicate_mode.upper() == "UPSERT":
            sql = """
            INSERT INTO inventory_items (
                item_id, barcode, canonical_name, normalized_name, category, brand,
                unit_of_measure, hsn_code, created_at, quantity, unit_price,
                cost_price, reorder_level, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                barcode = excluded.barcode,
                canonical_name = excluded.canonical_name,
                normalized_name = excluded.normalized_name,
                category = excluded.category,
                brand = excluded.brand,
                unit_of_measure = excluded.unit_of_measure,
                hsn_code = excluded.hsn_code,
                quantity = excluded.quantity,
                unit_price = excluded.unit_price,
                cost_price = excluded.cost_price,
                reorder_level = excluded.reorder_level,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at;
            """
        else:
            sql = """
            INSERT OR IGNORE INTO inventory_items (
                item_id, barcode, canonical_name, normalized_name, category, brand,
                unit_of_measure, hsn_code, created_at, quantity, unit_price,
                cost_price, reorder_level, is_active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """

        valid_buffer: List[tuple] = []
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            for raw in extractor:
                result.total_rows += 1
                
                # Transform & Validate
                transformed = self.transform_record(raw)
                val_res = self.validate_record(transformed)

                if val_res.is_valid and val_res.item:
                    result.valid_rows += 1
                    valid_buffer.append(val_res.item.to_db_tuple())
                else:
                    result.invalid_rows += 1
                    if len(result.errors_summary) < 10:
                        result.errors_summary.append(f"Row {result.total_rows}: {', '.join(val_res.errors)}")

                # Execute Chunk Commit
                if len(valid_buffer) >= chunk_size:
                    cursor.execute("BEGIN TRANSACTION;")
                    cursor.executemany(sql, valid_buffer)
                    conn.commit()
                    result.inserted_rows += len(valid_buffer)
                    valid_buffer.clear()

            # Flush remaining buffer
            if valid_buffer:
                cursor.execute("BEGIN TRANSACTION;")
                cursor.executemany(sql, valid_buffer)
                conn.commit()
                result.inserted_rows += len(valid_buffer)
                valid_buffer.clear()

        except Exception as e:
            conn.rollback()
            result.failed_rows += len(valid_buffer)
            logger.error(f"ETL pipeline fatal transaction failure: {e}")
            result.errors_summary.append(f"Fatal error: {e}")
        finally:
            conn.close()

        result.processing_time_seconds = time.time() - start_time
        
        # Log to DB audit table
        self.db.record_etl_run(result)
        logger.info(f"ETL Execution complete in {result.processing_time_seconds:.2f}s: {result.inserted_rows:,} records loaded.")
        
        return result
