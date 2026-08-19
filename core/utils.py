"""
Utility helpers for ListingForge
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "listings.db"


def init_db():
    """Initialize SQLite database for history."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'anonymous',
            product_name TEXT NOT NULL,
            primary_keyword TEXT,
            platform TEXT,
            category TEXT,
            best_title TEXT,
            description TEXT,
            tags TEXT,
            overall_score REAL,
            grade TEXT,
            full_json TEXT
        )
    """)
    cursor.execute("PRAGMA table_info(listings)")
    columns = {row[1] for row in cursor.fetchall()}
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE listings ADD COLUMN user_id TEXT NOT NULL DEFAULT 'anonymous'")
        cursor.execute("UPDATE listings SET user_id = 'anonymous' WHERE user_id IS NULL")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_listings_user_created_at ON listings(user_id, created_at DESC)")
    conn.commit()
    conn.close()


def save_listing(result: Dict, user_id: str = "anonymous") -> int:
    """Save a generated listing to history. Returns the new ID."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    overall = result["scores"]["overall"]
    cursor.execute("""
        INSERT INTO listings (
            created_at, user_id, product_name, primary_keyword, platform, category,
            best_title, description, tags, overall_score, grade, full_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().isoformat(),
        user_id,
        result["meta"]["product_name"],
        result["meta"]["primary_keyword"],
        result["platform"],
        result["meta"]["category"],
        result["best_title"],
        result["description"],
        json.dumps(result["tags"]),
        overall["overall"],
        overall["grade"],
        json.dumps(result),
    ))
    listing_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return listing_id


def get_history(limit: int = 50, user_id: Optional[str] = None) -> List[Dict]:
    """Retrieve recent listings."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if user_id is None:
        cursor.execute("""
            SELECT id, created_at, product_name, primary_keyword, platform,
                   category, best_title, overall_score, grade
            FROM listings
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
    else:
        cursor.execute("""
            SELECT id, created_at, product_name, primary_keyword, platform,
                   category, best_title, overall_score, grade
            FROM listings
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_listing_by_id(listing_id: int, user_id: Optional[str] = None) -> Optional[Dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if user_id is None:
        cursor.execute("SELECT full_json FROM listings WHERE id = ?", (listing_id,))
    else:
        cursor.execute("SELECT full_json FROM listings WHERE id = ? AND user_id = ?", (listing_id, user_id))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None


def delete_listing(listing_id: int, user_id: Optional[str] = None) -> bool:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if user_id is None:
        cursor.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
    else:
        cursor.execute("DELETE FROM listings WHERE id = ? AND user_id = ?", (listing_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def export_to_dataframe(results: List[Dict]) -> pd.DataFrame:
    """Convert listing results to a clean DataFrame for CSV export."""
    rows = []
    for r in results:
        rows.append({
            "Product Name": r["meta"]["product_name"],
            "Primary Keyword": r["meta"]["primary_keyword"],
            "Platform": r["platform"],
            "Best Title": r["best_title"],
            "Title Options": " | ".join(r["titles"]),
            "Description": r["description"],
            "Tags": ", ".join(r["tags"]),
            "Overall Score": r["scores"]["overall"]["overall"],
            "Grade": r["scores"]["overall"]["grade"],
            "Title Score": r["scores"]["title"]["score"],
            "Description Score": r["scores"]["description"]["score"],
            "Tags Score": r["scores"]["tags"]["score"],
        })
    return pd.DataFrame(rows)


def clean_keyword(text: str) -> str:
    """Normalize a keyword string."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s\-]', '', text)
    return re.sub(r'\s+', ' ', text)
