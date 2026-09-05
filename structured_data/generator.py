"""
structured_data/generator.py
=============================
Synthetic Kirana Inventory Generator for SMAR v2.
Generates 100,000+ realistic inventory records representing Indian Kirana store
and warehouse items (FMCG, spices, grain, personal care, dairy, cleaning supplies).
Supports streaming generator batches, CSV export, and synthetic edge-case injection.
"""

import os
import csv
import json
import random
import logging
from typing import Generator, List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("smar.structured_data.generator")

# Categories & Brands definition
KIRANA_CATALOG = {
    "Spices & Cooking Essentials": {
        "brands": ["Tata", "MDH", "Everest", "Catch", "Rajdhani", "Aashirvaad", "Fortune", "Sundrop"],
        "items": [
            ("Salt Vacuum Evaporated Iodised 1kg", "kg", "25010010", 28.0, 20.0),
            ("Black Pepper Powder / Kali Mirch 100g", "g", "09041200", 120.0, 95.0),
            ("Turmeric Powder / Haldi 250g", "g", "09103020", 65.0, 48.0),
            ("Red Chilli Powder / Lal Mirch 200g", "g", "09042211", 85.0, 62.0),
            ("Coriander Powder / Dhaniya 500g", "g", "09092200", 110.0, 85.0),
            ("Garam Masala Pack 100g", "g", "09109100", 95.0, 70.0),
            ("Mustard Oil / Sarson Tel 1L", "L", "15149120", 165.0, 135.0),
            ("Refined Sunflower Oil 1L Pouch", "L", "15129100", 145.0, 118.0),
            ("Pure Cow Ghee 500ml Jar", "ml", "04059020", 340.0, 290.0),
            ("Cumin Seeds / Jeera Whole 200g", "g", "09093200", 140.0, 105.0)
        ]
    },
    "Atta, Rice & Grains": {
        "brands": ["Aashirvaad", "Fortune", "India Gate", "Daawat", "Patanjali", "Nature Fresh", "Engine"],
        "items": [
            ("Whole Wheat Atta 5kg Bag", "kg", "11010000", 245.0, 195.0),
            ("Sharbati Whole Wheat Atta 10kg", "kg", "11010000", 480.0, 395.0),
            ("Rozana Basmati Rice 5kg", "kg", "10063020", 420.0, 330.0),
            ("Classic Basmati Rice 1kg Pack", "kg", "10063020", 135.0, 105.0),
            ("Toor Dal / Arhar Dal Premium 1kg", "kg", "07136000", 160.0, 125.0),
            ("Moong Dal Washed 1kg Pouch", "kg", "07133100", 130.0, 100.0),
            ("Chana Dal / Bengal Gram 1kg", "kg", "07139010", 95.0, 72.0),
            ("Suji / Semolina Fine 500g", "g", "11031110", 38.0, 27.0),
            ("Maida / Refined Wheat Flour 1kg", "kg", "11010010", 48.0, 34.0),
            ("Poha / Thick Flattened Rice 500g", "g", "11041900", 42.0, 30.0)
        ]
    },
    "Snacks, Biscuits & Bakery": {
        "brands": ["Britannia", "Parle", "Sunfeast", "Haldiram", "Bikaji", "Lays", "Kurkure", "Cadbury"],
        "items": [
            ("Good Day Cashew Cookies 200g", "pack", "19053100", 45.0, 32.0),
            ("Parle-G Gold Biscuit 150g", "pack", "19053100", 15.0, 11.0),
            ("Marie Gold Tea Biscuits 250g", "pack", "19053100", 35.0, 25.0),
            ("Bhujia Sev Spicy नमकीन 400g", "pack", "21069099", 110.0, 82.0),
            ("Alloo Bhujia Crunchy 200g", "pack", "21069099", 55.0, 40.0),
            ("Magic Masala Potato Chips 52g", "pack", "20052000", 20.0, 14.5),
            ("Masala Munch Corn Crisp 90g", "pack", "21069099", 20.0, 14.5),
            ("Dairy Milk Silk Chocolate 150g", "piece", "18063200", 175.0, 140.0),
            ("Bourbon Chocolate Cream Biscuits 150g", "pack", "19053100", 30.0, 21.0),
            ("Rusk Crunchy Toast 300g", "pack", "19054000", 50.0, 36.0)
        ]
    },
    "Beverages & Tea / Coffee": {
        "brands": ["Red Label", "Taj Mahal", "Tata Tea", "Nescafe", "Bru", "Real", "Tropicana", "Thums Up", "Sprite"],
        "items": [
            ("Brooke Bond Red Label Tea 500g", "g", "09023020", 270.0, 215.0),
            ("Tata Tea Premium Leaf 1kg", "kg", "09023020", 460.0, 370.0),
            ("Classic Instant Coffee Powder 100g Jar", "g", "21011110", 320.0, 250.0),
            ("Instant South Indian Coffee 200g Pouch", "g", "21011110", 195.0, 150.0),
            ("Mixed Fruit Juice 1L Tetrapack", "L", "20099000", 115.0, 88.0),
            ("Cold Drink Soft Beverage 2L Bottle", "bottle", "22021010", 90.0, 68.0),
            ("Carbonated Lemon Drink 750ml", "bottle", "22021020", 40.0, 30.0),
            ("Bournvita Health Drink 500g Jar", "g", "19011090", 265.0, 210.0),
            ("Horlicks Malted Milk Food 500g", "g", "19011090", 255.0, 200.0),
            ("Glucose-D Energy Drink Powder 500g", "g", "17023010", 110.0, 80.0)
        ]
    },
    "Personal Care & Hygiene": {
        "brands": ["Dettol", "Lifebuoy", "Dove", "Colgate", "Pepsodent", "Sunsilk", "Clinic Plus", "Nivea", "Vim"],
        "items": [
            ("Antiseptic Soap Bar 125g Pack of 3", "pack", "34011110", 135.0, 102.0),
            ("Original Bath Soap 100g", "piece", "34011110", 40.0, 30.0),
            ("Strong Teeth Dental Paste 150g", "piece", "33061020", 98.0, 72.0),
            ("Germi Check Toothpaste 200g", "piece", "33061020", 115.0, 85.0),
            ("Strong & Long Hair Shampoo 650ml", "bottle", "33051090", 380.0, 285.0),
            ("Nourishing Body Lotion 200ml", "bottle", "33049910", 225.0, 165.0),
            ("Handwash Liquid Refill Pouch 750ml", "ml", "34013000", 119.0, 88.0),
            ("Coconut Hair Oil 250ml Bottle", "ml", "33059011", 105.0, 80.0),
            ("Shaving Cream Lemon Fresh 90g", "g", "33071010", 85.0, 62.0),
            ("Deodorant Body Spray 150ml", "can", "33072000", 220.0, 160.0)
        ]
    },
    "Household & Cleaning": {
        "brands": ["Surf Excel", "Ariel", "Rin", "Vim", "Harpic", "Lizol", "Colin", "Goodknight", "Odonil"],
        "items": [
            ("Easy Wash Detergent Powder 1kg", "kg", "34022010", 145.0, 110.0),
            ("Matic Liquid Detergent 1L Bottle", "L", "34022020", 230.0, 175.0),
            ("Dishwash Gel Lemon Bottle 500ml", "ml", "34022090", 120.0, 88.0),
            ("Dishwash Bar Tub 500g", "pack", "34011940", 55.0, 40.0),
            ("Disinfectant Toilet Cleaner 1L", "bottle", "38089400", 195.0, 145.0),
            ("Disinfectant Floor Cleaner Citrus 1L", "bottle", "38089400", 185.0, 138.0),
            ("Glass and Surface Cleaner Spray 500ml", "bottle", "34029090", 110.0, 82.0),
            ("Mosquito Liquid Refill 45ml Twin Pack", "pack", "38089191", 150.0, 112.0),
            ("Air Freshener Block Citrus 50g", "piece", "33074900", 65.0, 45.0),
            ("Scrub Pad Heavy Duty Pack of 3", "pack", "68053000", 45.0, 30.0)
        ]
    },
    "Dairy, Frozen & Fresh": {
        "brands": ["Amul", "Mother Dairy", "Nandini", "Verka", "Kwality Wall's", "McCain"],
        "items": [
            ("Pasteurised Butter 500g Pack", "pack", "04051000", 275.0, 235.0),
            ("Fresh Paneer Block 200g Pouch", "g", "04061000", 90.0, 72.0),
            ("Processed Cheese Slices 200g Pack", "pack", "04063000", 140.0, 112.0),
            ("Full Cream Milk 1L Poly Pouch", "L", "04012000", 66.0, 58.0),
            ("Fresh Dahi Cup 400g", "g", "04031000", 50.0, 40.0),
            ("French Fries Crispy Frozen 750g", "pack", "20041000", 185.0, 135.0),
            ("Alloo Tikki Frozen Snacks 400g", "pack", "20049000", 125.0, 90.0),
            ("Vanilla Gold Ice Cream Tub 750ml", "ml", "21050000", 210.0, 155.0),
            ("Sweet Condensed Milk 400g Can", "can", "04029920", 145.0, 115.0),
            ("Fresh Cream 250ml Pack", "ml", "04014000", 68.0, 54.0)
        ]
    }
}


class KiranaInventoryDataGenerator:
    """Generates synthetic Kirana Inventory records (~100,000+ items)."""

    def __init__(self, seed: int = 42):
        random.seed(seed)

    def generate_records(
        self,
        total_records: int = 100000,
        invalid_ratio: float = 0.0
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Yields raw inventory dictionary records one by one up to `total_records`.
        
        Args:
            total_records: Total count of records to yield (default 100,000).
            invalid_ratio: Fraction of records to deliberately generate as malformed/invalid (for testing).
        """
        categories = list(KIRANA_CATALOG.keys())
        now = datetime.now(timezone.utc)

        for i in range(1, total_records + 1):
            item_num = i
            item_id = f"INV-{item_num:06d}"
            
            # Select random category
            cat_name = random.choice(categories)
            cat_data = KIRANA_CATALOG[cat_name]
            brand = random.choice(cat_data["brands"])
            name_suffix, uom, hsn, base_mrp, base_cost = random.choice(cat_data["items"])
            
            # Variant modifier (e.g. Size, Pack Type, Variant #)
            variant_id = (i % 15) + 1
            canonical_name = f"{brand} {name_suffix} (Variant #{variant_id})"
            
            # Barcode: Indian EAN-13 prefix (890) + 10 digits
            barcode = f"8901030{item_num:06d}"
            
            # Dynamic price variations (+/- 15%)
            price_variance = random.uniform(0.85, 1.15)
            unit_price = round(base_mrp * price_variance, 2)
            cost_price = round(base_cost * price_variance, 2)
            
            # Dynamic stock quantities (0 to 500 units)
            quantity = float(random.randint(0, 500))
            reorder_lvl = random.choice([5, 10, 15, 20, 25, 50])
            is_active = 1 if random.random() > 0.02 else 0

            # Created / Updated timestamps (past 180 days)
            days_ago = random.randint(1, 180)
            created_dt = now - timedelta(days=days_ago)
            updated_dt = created_dt + timedelta(days=random.randint(0, days_ago))

            record = {
                "item_id": item_id,
                "barcode": barcode,
                "canonical_name": canonical_name,
                "normalized_name": canonical_name.lower().strip(),
                "category": cat_name,
                "brand": brand,
                "unit_of_measure": uom,
                "hsn_code": hsn,
                "created_at": created_dt.isoformat(),
                "quantity": quantity,
                "unit_price": unit_price,
                "cost_price": cost_price,
                "reorder_level": reorder_lvl,
                "is_active": is_active,
                "updated_at": updated_dt.isoformat(),
            }

            # Optional edge-case invalid data injection for testing
            if invalid_ratio > 0.0 and random.random() < invalid_ratio:
                defect_type = random.choice(["negative_qty", "invalid_price", "missing_name", "empty_id"])
                if defect_type == "negative_qty":
                    record["quantity"] = -25.0
                elif defect_type == "invalid_price":
                    record["unit_price"] = 0.0
                elif defect_type == "missing_name":
                    record["canonical_name"] = "  "
                elif defect_type == "empty_id":
                    record["item_id"] = ""

            yield record

    def export_to_csv(self, file_path: str, total_records: int = 100000, invalid_ratio: float = 0.0) -> str:
        """Generate records and save directly to CSV file."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        fieldnames = [
            "item_id", "barcode", "canonical_name", "normalized_name",
            "category", "brand", "unit_of_measure", "hsn_code", "created_at",
            "quantity", "unit_price", "cost_price", "reorder_level", "is_active", "updated_at"
        ]

        logger.info(f"Generating {total_records:,} synthetic inventory records to CSV '{file_path}'...")
        count = 0
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in self.generate_records(total_records, invalid_ratio):
                writer.writerow(record)
                count += 1
                if count % 25000 == 0:
                    logger.info(f"Generated {count:,} / {total_records:,} records...")

        logger.info(f"Exported {count:,} records successfully to '{file_path}'.")
        return file_path
