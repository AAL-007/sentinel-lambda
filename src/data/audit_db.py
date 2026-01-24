"""
SENTINEL-Λ: Persistent Audit Log
Feature: SQLite with WAL mode, JSON serialization, and Auto-Retention.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict

DB_PATH = "audit_logs.db"
logger = logging.getLogger("sentinel-audit")

class AuditDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        """
        Creates a fresh connection for every operation.
        check_same_thread=False is CRITICAL for FastAPI BackgroundTasks
        to avoid 'ProgrammingError' in async thread pools.
        """
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        """Initialize table, enable WAL, and run retention policy."""
        try:
            with self._get_conn() as conn:
                # 1. Enable Write-Ahead Logging (High Concurrency)
                conn.execute("PRAGMA journal_mode=WAL;")
                
                # 2. Performance Optimization (Safe with WAL)
                # Reduces fsync operations while maintaining durability
                conn.execute("PRAGMA synchronous=NORMAL;")
                
                # 3. Create Table with Full Audit Context
                conn.execute("""
                CREATE TABLE IF NOT EXISTS audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    domain TEXT,
                    query TEXT,
                    response TEXT,
                    normalized_query TEXT,    -- Adversarial Audit Trail
                    normalized_response TEXT, -- Adversarial Audit Trail
                    decision TEXT,
                    risk_score REAL,
                    detected_risks TEXT,      -- JSON Array
                    violations TEXT,          -- JSON Array
                    latency_ms REAL
                )
                """)
                
                # 4. Create Analytics Indices
                conn.execute("CREATE INDEX IF NOT EXISTS idx_decision ON audits (decision);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON audits (timestamp);")
                
                # 5. Retention Policy: Auto-delete records older than 30 days
                cleanup_threshold = (datetime.utcnow() - timedelta(days=30)).isoformat()
                conn.execute("DELETE FROM audits WHERE timestamp < ?", (cleanup_threshold,))
                
        except Exception as e:
            logger.error(f"Audit DB Init Failed: {e}")

    def log_decision(self, record: Dict):
        """
        Logs a decision using a scoped connection (Context Manager).
        Safe for use in BackgroundTasks.
        """
        try:
            with self._get_conn() as conn:
                conn.execute("""
                INSERT INTO audits (
                    request_id, timestamp, domain, query, response,
                    normalized_query, normalized_response,
                    decision, risk_score, detected_risks, violations, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.get("request_id"),
                    datetime.utcnow().isoformat(),
                    record.get("domain", "general"),
                    record.get("query", ""),
                    record.get("response", ""),
                    record.get("normalized_query", ""),
                    record.get("normalized_response", ""),
                    record.get("decision", "ERROR"),
                    record.get("risk_score", 0.0),
                    json.dumps(record.get("detected_risks", [])),
                    json.dumps(record.get("violations", [])),
                    record.get("latency_ms", 0.0)
                ))
        except Exception as e:
            logger.error(f"AUDIT LOG FAILURE: {e}")

# Singleton
audit_logger = AuditDB()