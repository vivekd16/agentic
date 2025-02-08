import sqlite3
from pathlib import Path
from typing import Optional, overload, TypeVar

T = TypeVar("T")


class Settings:
    def __init__(self, db_path=".agentsdb", cache_dir="~/.agentic", key=None):
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        db_path = Path(cache_dir).expanduser() / db_path

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

        # Create tables for both secrets and settings
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT)"
        )
        self.conn.commit()

    def set(self, name, value):
        """Store an unencrypted setting"""
        self.cursor.execute(
            "INSERT OR REPLACE INTO settings (name, value) VALUES (?, ?)",
            (name, str(value)),
        )
        self.conn.commit()

    @overload
    def get(self, name) -> Optional[str]:
        return self.get(name, default=None)

    @overload
    def get(self, name: str, default: T) -> T:
        return self.get(name, default=default)

    def get(self, name, default: Optional[T] = None) -> Optional[T]:
        """Retrieve an unencrypted setting"""
        self.cursor.execute("SELECT value FROM settings WHERE name=?", (name,))
        result = self.cursor.fetchone()
        return result[0] if result else default

    def list_settings(self):
        """List all setting names"""
        self.cursor.execute("SELECT name FROM settings")
        return [row[0] for row in self.cursor.fetchall()]

    def delete_setting(self, name):
        """Delete a setting"""
        self.cursor.execute("DELETE FROM settings WHERE name=?", (name,))
        self.conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()


# Usage example:
settings = Settings()
