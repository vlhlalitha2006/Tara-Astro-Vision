#!/usr/bin/env python3
"""
setup_admin.py — Secure Admin Account Setup Utility
Tara Astro Vision
══════════════════════════════════════════════════════════════
Only one authorized email address is allowed:
    info@taraastrovision.com

Usage:
    # Interactive prompt:
    python setup_admin.py

    # Non-interactive via argument:
    python setup_admin.py --password "YourStrongPassword123!"

    # Or set ADMIN_INITIAL_PASSWORD in .env
"""

import sys
import os
import argparse
import getpass
import sqlite3
import hashlib
import secrets
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

# Load .env if present
_env_path = ROOT_DIR / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass

_db_env = os.environ.get("DATABASE_URL") or os.getenv("DATABASE_URL", "")
if _db_env:
    if _db_env.startswith("sqlite:///") or _db_env.startswith("postgresql://") or os.path.isabs(_db_env):
        DATABASE_URL = _db_env
    else:
        DATABASE_URL = str((ROOT_DIR / _db_env).resolve())
else:
    DATABASE_URL = str((ROOT_DIR / "jyotisha.db").resolve())

AUTHORIZED_ADMIN_EMAIL = "info@taraastrovision.com"
PBKDF2_ITERATIONS = 600_000



def hash_admin_password(password: str, salt: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 600,000 iterations."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS
    ).hex()


def verify_admin_password(password: str, salt: str, password_hash: str) -> bool:
    """Constant-time verification of admin password."""
    computed = hash_admin_password(password, salt)
    return secrets.compare_digest(computed, password_hash)


def init_admin_tables(conn: sqlite3.Connection):
    """Ensure admin_users and admin_audit_logs tables exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            last_login_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_email TEXT NOT NULL,
            action TEXT NOT NULL,
            booking_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_audit_logs_booking ON admin_audit_logs(booking_id);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON admin_audit_logs(action);
    """)
    conn.commit()


def setup_admin_user(password: str, db_path: str = DATABASE_URL) -> bool:
    """Create or update the single authorized admin account."""
    if not password:
        raise ValueError("Password cannot be empty.")
    password = password.strip()
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    conn = sqlite3.connect(db_path)
    try:
        init_admin_tables(conn)
        salt = secrets.token_hex(16)
        pwd_hash = hash_admin_password(password, salt)

        existing = conn.execute(
            "SELECT id FROM admin_users WHERE email = ?",
            (AUTHORIZED_ADMIN_EMAIL,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE admin_users SET password_hash = ?, salt = ?, created_at = datetime('now') WHERE email = ?",
                (pwd_hash, salt, AUTHORIZED_ADMIN_EMAIL)
            )
            print(f"✓ Password updated for authorized admin: {AUTHORIZED_ADMIN_EMAIL}")
        else:
            conn.execute(
                "INSERT INTO admin_users (email, password_hash, salt) VALUES (?, ?, ?)",
                (AUTHORIZED_ADMIN_EMAIL, pwd_hash, salt)
            )
            print(f"✓ Admin account created successfully for: {AUTHORIZED_ADMIN_EMAIL}")

        conn.execute(
            "INSERT INTO admin_audit_logs (admin_email, action, details) VALUES (?, ?, ?)",
            (AUTHORIZED_ADMIN_EMAIL, "admin_password_setup", "Admin password configured or updated via setup utility")
        )
        conn.commit()
        return True
    finally:
        conn.close()


def auto_seed_admin_if_needed(db_path: str = DATABASE_URL):
    """Seed admin account from ADMIN_INITIAL_PASSWORD environment variable if table is empty."""
    initial_pwd = os.getenv("ADMIN_INITIAL_PASSWORD", "").strip()
    if not initial_pwd:
        return False

    conn = sqlite3.connect(db_path)
    try:
        init_admin_tables(conn)
        existing = conn.execute(
            "SELECT id FROM admin_users WHERE email = ?",
            (AUTHORIZED_ADMIN_EMAIL,)
        ).fetchone()
        if not existing:
            salt = secrets.token_hex(16)
            pwd_hash = hash_admin_password(initial_pwd, salt)
            conn.execute(
                "INSERT INTO admin_users (email, password_hash, salt) VALUES (?, ?, ?)",
                (AUTHORIZED_ADMIN_EMAIL, pwd_hash, salt)
            )
            conn.execute(
                "INSERT INTO admin_audit_logs (admin_email, action, details) VALUES (?, ?, ?)",
                (AUTHORIZED_ADMIN_EMAIL, "admin_auto_seed", "Admin account auto-seeded from ADMIN_INITIAL_PASSWORD")
            )
            conn.commit()
            return True
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configure admin password for Tara Astro Vision.")
    parser.add_argument("--password", "-p", help="Admin password (leave blank for secure prompt)")
    parser.add_argument("--db", help="Path to SQLite database", default=DATABASE_URL)
    args = parser.parse_args()

    pwd = args.password
    if not pwd:
        pwd = getpass.getpass(f"Enter password for {AUTHORIZED_ADMIN_EMAIL}: ")
        confirm = getpass.getpass("Confirm password: ")
        if pwd != confirm:
            print("❌ Passwords do not match.")
            sys.exit(1)

    try:
        setup_admin_user(pwd, args.db)
    except Exception as e:
        print(f"❌ Error setting up admin: {e}")
        sys.exit(1)
