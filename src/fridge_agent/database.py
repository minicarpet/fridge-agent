import sqlite3
from pathlib import Path


def initialize_database(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)

    database_path = data_dir / "fridge-agent.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fridge_scans (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fridge_scan_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                FOREIGN KEY(scan_id) REFERENCES fridge_scans(id)
            )
            """
        )

        connection.commit()

    return database_path