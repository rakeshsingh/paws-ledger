#!/usr/bin/env python3
"""
PawsLedger Database Migration Script
=====================================

Migrates an existing SQLite database to match the current models.py schema.
Safe to run multiple times — each migration checks if it's already been applied.

Usage:
    python migrate.py                     # Uses DATABASE_URL from .env
    python migrate.py path/to/db.sqlite   # Explicit database path

What this script does:
    1. Adds new columns to existing tables (user, pet, nudgesession, sharedaccess)
    2. Creates new tables (subscription, ownershiptransfer, vaccinationalert, etc.)
    3. Creates indexes on new columns

This script does NOT:
    - Delete any data
    - Drop any columns or tables
    - Modify existing data
"""

import os
import sys
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
env = os.getenv("APP_ENV", "beta")
load_dotenv(f".env.{env}")


def get_db_path() -> str:
    """Determine the database file path."""
    if len(sys.argv) > 1:
        return sys.argv[1]

    db_url = os.getenv("DATABASE_URL", "sqlite:///./pawsledger.db")
    # Parse sqlite:///path or sqlite:////absolute/path
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "", 1)
    return "pawsledger.db"


def get_existing_columns(cursor: sqlite3.Cursor, table: str) -> set:
    """Get the set of column names for an existing table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def get_existing_tables(cursor: sqlite3.Cursor) -> set:
    """Get the set of existing table names."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cursor.fetchall()}


def add_column_if_missing(cursor: sqlite3.Cursor, table: str, column: str, col_type: str, default=None):
    """Add a column to a table if it doesn't already exist."""
    existing = get_existing_columns(cursor, table)
    if column not in existing:
        default_clause = ""
        if default is not None:
            default_clause = f" DEFAULT {default}"
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"
        cursor.execute(sql)
        print(f"  ✓ Added column: {table}.{column} ({col_type})")
    else:
        print(f"  · Column already exists: {table}.{column}")


def create_table_if_missing(cursor: sqlite3.Cursor, table: str, create_sql: str):
    """Create a table if it doesn't already exist."""
    existing = get_existing_tables(cursor)
    if table not in existing:
        cursor.execute(create_sql)
        print(f"  ✓ Created table: {table}")
    else:
        print(f"  · Table already exists: {table}")


def create_index_if_missing(cursor: sqlite3.Cursor, index_name: str, table: str, columns: str, unique: bool = False):
    """Create an index if it doesn't already exist."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    if not cursor.fetchone():
        unique_str = "UNIQUE " if unique else ""
        cursor.execute(f"CREATE {unique_str}INDEX {index_name} ON {table} ({columns})")
        print(f"  ✓ Created index: {index_name}")
    else:
        print(f"  · Index already exists: {index_name}")


def migrate(db_path: str):
    """Run all migrations."""
    if not Path(db_path).exists():
        print(f"Database not found at: {db_path}")
        print("The app will create it automatically on first run. No migration needed.")
        sys.exit(0)

    print(f"Migrating database: {db_path}")
    print(f"{'=' * 60}")

    # Create a backup first
    backup_path = f"{db_path}.backup"
    if not Path(backup_path).exists():
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path}")
    else:
        print(f"Backup already exists: {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable WAL mode for safety
    cursor.execute("PRAGMA journal_mode=WAL")

    # ─────────────────────────────────────────────────────────
    print("\n[1/8] Adding new columns to 'user' table...")
    # ─────────────────────────────────────────────────────────
    add_column_if_missing(cursor, "user", "profile_updated_at", "TIMESTAMP", "NULL")
    add_column_if_missing(cursor, "user", "contact_reminded_at", "TIMESTAMP", "NULL")

    # ─────────────────────────────────────────────────────────
    print("\n[2/8] Creating 'subscription' table...")
    # ─────────────────────────────────────────────────────────
    create_table_if_missing(cursor, "subscription", """
        CREATE TABLE subscription (
            id VARCHAR NOT NULL PRIMARY KEY,
            user_id VARCHAR NOT NULL UNIQUE,
            stripe_customer_id VARCHAR NOT NULL,
            stripe_subscription_id VARCHAR,
            tier VARCHAR NOT NULL DEFAULT 'free',
            status VARCHAR NOT NULL DEFAULT 'inactive',
            current_period_start TIMESTAMP,
            current_period_end TIMESTAMP,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user (id)
        )
    """)
    create_index_if_missing(cursor, "ix_subscription_user_id", "subscription", "user_id", unique=True)
    create_index_if_missing(cursor, "ix_subscription_stripe_customer_id", "subscription", "stripe_customer_id")
    create_index_if_missing(cursor, "ix_subscription_stripe_subscription_id", "subscription", "stripe_subscription_id")

    # ─────────────────────────────────────────────────────────
    print("\n[3/8] Creating 'ownershiptransfer' table...")
    # ─────────────────────────────────────────────────────────
    create_table_if_missing(cursor, "ownershiptransfer", """
        CREATE TABLE ownershiptransfer (
            id VARCHAR NOT NULL PRIMARY KEY,
            pet_id VARCHAR NOT NULL,
            from_owner_id VARCHAR NOT NULL,
            to_owner_email VARCHAR NOT NULL,
            to_owner_id VARCHAR,
            transfer_token VARCHAR NOT NULL UNIQUE,
            status VARCHAR NOT NULL DEFAULT 'pending',
            initiated_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP,
            notes VARCHAR,
            FOREIGN KEY (pet_id) REFERENCES pet (id),
            FOREIGN KEY (from_owner_id) REFERENCES user (id),
            FOREIGN KEY (to_owner_id) REFERENCES user (id)
        )
    """)
    create_index_if_missing(cursor, "ix_ownershiptransfer_pet_id", "ownershiptransfer", "pet_id")
    create_index_if_missing(cursor, "ix_ownershiptransfer_transfer_token", "ownershiptransfer", "transfer_token", unique=True)

    # ─────────────────────────────────────────────────────────
    print("\n[4/8] Creating 'vaccinationalert' table...")
    # ─────────────────────────────────────────────────────────
    create_table_if_missing(cursor, "vaccinationalert", """
        CREATE TABLE vaccinationalert (
            id VARCHAR NOT NULL PRIMARY KEY,
            pet_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            vaccination_id VARCHAR,
            alert_type VARCHAR NOT NULL DEFAULT 'vaccination_expiry',
            alert_date TIMESTAMP NOT NULL,
            title VARCHAR NOT NULL,
            description VARCHAR,
            is_sent BOOLEAN NOT NULL DEFAULT 0,
            sent_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL,
            FOREIGN KEY (pet_id) REFERENCES pet (id),
            FOREIGN KEY (user_id) REFERENCES user (id),
            FOREIGN KEY (vaccination_id) REFERENCES vaccination (id)
        )
    """)
    create_index_if_missing(cursor, "ix_vaccinationalert_pet_id", "vaccinationalert", "pet_id")
    create_index_if_missing(cursor, "ix_vaccinationalert_user_id", "vaccinationalert", "user_id")

    # ─────────────────────────────────────────────────────────
    print("\n[5/8] Creating 'careinstruction' table...")
    # ─────────────────────────────────────────────────────────
    create_table_if_missing(cursor, "careinstruction", """
        CREATE TABLE careinstruction (
            id VARCHAR NOT NULL PRIMARY KEY,
            pet_id VARCHAR NOT NULL,
            category VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            content VARCHAR NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            FOREIGN KEY (pet_id) REFERENCES pet (id)
        )
    """)
    create_index_if_missing(cursor, "ix_careinstruction_pet_id", "careinstruction", "pet_id")

    # ─────────────────────────────────────────────────────────
    print("\n[6/8] Creating 'vaccinationdocument' table...")
    # ─────────────────────────────────────────────────────────
    create_table_if_missing(cursor, "vaccinationdocument", """
        CREATE TABLE vaccinationdocument (
            id VARCHAR NOT NULL PRIMARY KEY,
            pet_id VARCHAR NOT NULL,
            filename VARCHAR NOT NULL,
            original_filename VARCHAR NOT NULL,
            content_type VARCHAR NOT NULL DEFAULT 'application/pdf',
            file_size INTEGER NOT NULL DEFAULT 0,
            storage_key VARCHAR NOT NULL,
            url VARCHAR NOT NULL,
            uploaded_at TIMESTAMP NOT NULL,
            notes VARCHAR,
            FOREIGN KEY (pet_id) REFERENCES pet (id)
        )
    """)
    create_index_if_missing(cursor, "ix_vaccinationdocument_pet_id", "vaccinationdocument", "pet_id")

    # ─────────────────────────────────────────────────────────
    print("\n[7/8] Creating 'tagscan' table...")
    # ─────────────────────────────────────────────────────────
    create_table_if_missing(cursor, "tagscan", """
        CREATE TABLE tagscan (
            id VARCHAR NOT NULL PRIMARY KEY,
            pet_id VARCHAR NOT NULL,
            tag_id VARCHAR,
            scanned_at TIMESTAMP NOT NULL,
            latitude REAL,
            longitude REAL,
            accuracy_meters REAL,
            city VARCHAR,
            country VARCHAR,
            scanner_user_id VARCHAR,
            scan_method VARCHAR NOT NULL DEFAULT 'QR',
            FOREIGN KEY (pet_id) REFERENCES pet (id),
            FOREIGN KEY (tag_id) REFERENCES pettag (id),
            FOREIGN KEY (scanner_user_id) REFERENCES user (id)
        )
    """)
    create_index_if_missing(cursor, "ix_tagscan_pet_id", "tagscan", "pet_id")

    # ─────────────────────────────────────────────────────────
    print("\n[8/8] Adding location columns to 'pet' table...")
    # ─────────────────────────────────────────────────────────
    add_column_if_missing(cursor, "pet", "last_scan_latitude", "REAL", "NULL")
    add_column_if_missing(cursor, "pet", "last_scan_longitude", "REAL", "NULL")
    add_column_if_missing(cursor, "pet", "last_scan_location", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "pet", "last_scan_at", "TIMESTAMP", "NULL")

    # ─────────────────────────────────────────────────────────
    print("\n[9/11] Adding nudge reply & GPS columns to 'nudgesession' table...")
    # ─────────────────────────────────────────────────────────
    add_column_if_missing(cursor, "nudgesession", "geo_latitude", "REAL", "NULL")
    add_column_if_missing(cursor, "nudgesession", "geo_longitude", "REAL", "NULL")
    add_column_if_missing(cursor, "nudgesession", "owner_response", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "nudgesession", "responded_at", "TIMESTAMP", "NULL")
    add_column_if_missing(cursor, "nudgesession", "deleted_by_finder", "BOOLEAN NOT NULL", "0")
    add_column_if_missing(cursor, "nudgesession", "deleted_by_owner", "BOOLEAN NOT NULL", "0")

    # ─────────────────────────────────────────────────────────
    print("\n[10/11] Adding access tracking columns to 'sharedaccess' table...")
    # ─────────────────────────────────────────────────────────
    add_column_if_missing(cursor, "sharedaccess", "last_accessed_at", "TIMESTAMP", "NULL")
    add_column_if_missing(cursor, "sharedaccess", "access_count", "INTEGER NOT NULL", "0")

    # ─────────────────────────────────────────────────────────
    print("\n[11/13] Adding care instruction columns to 'pet' table...")
    # ─────────────────────────────────────────────────────────
    add_column_if_missing(cursor, "pet", "medication_notes", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "pet", "emergency_vet_name", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "pet", "emergency_vet_phone", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "pet", "care_priority", "VARCHAR", "NULL")

    # ─────────────────────────────────────────────────────────
    print("\n[12/13] Adding emergency contact & pet clinic columns to 'pet' table...")
    # ─────────────────────────────────────────────────────────
    add_column_if_missing(cursor, "pet", "emergency_contact_name", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "pet", "emergency_contact_phone", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "pet", "clinic_name", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "pet", "clinic_address", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "pet", "clinic_phone", "VARCHAR", "NULL")

    # ─────────────────────────────────────────────────────────
    print("\n[13/16] Adding document metadata columns to 'vaccinationdocument' table...")
    # ─────────────────────────────────────────────────────────
    add_column_if_missing(cursor, "vaccinationdocument", "document_name", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "vaccinationdocument", "description", "VARCHAR", "NULL")

    # ─────────────────────────────────────────────────────────
    print("\n[14/16] Adding cancel_at_period_end to 'subscription' table...")
    # ─────────────────────────────────────────────────────────
    add_column_if_missing(cursor, "subscription", "cancel_at_period_end", "BOOLEAN NOT NULL", "0")

    # ─────────────────────────────────────────────────────────
    print("\n[15/16] Adding photo_url and identity_status to 'pet' table...")
    # ─────────────────────────────────────────────────────────
    add_column_if_missing(cursor, "pet", "photo_url", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "pet", "identity_status", "VARCHAR", "'UNVERIFIED'")

    # ─────────────────────────────────────────────────────────
    print("\n[16/16] Adding response_token to 'nudgesession' table...")
    # ─────────────────────────────────────────────────────────
    add_column_if_missing(cursor, "nudgesession", "response_token", "VARCHAR", "NULL")
    add_column_if_missing(cursor, "nudgesession", "is_resolved", "BOOLEAN NOT NULL", "0")
    add_column_if_missing(cursor, "nudgesession", "resolved_at", "TIMESTAMP", "NULL")
    add_column_if_missing(cursor, "nudgesession", "expires_at", "TIMESTAMP", "NULL")
    create_index_if_missing(cursor, "ix_nudgesession_response_token", "nudgesession", "response_token")

    # ─────────────────────────────────────────────────────────
    # Commit and close
    # ─────────────────────────────────────────────────────────
    conn.commit()
    conn.close()

    print(f"\n{'=' * 60}")
    print("Migration complete! Your database is up to date.")
    print(f"Backup saved at: {backup_path}")


if __name__ == "__main__":
    migrate(get_db_path())
