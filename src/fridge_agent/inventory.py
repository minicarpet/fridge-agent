import sqlite3

from pathlib import Path

from aiohttp import web


async def get_inventory(request: web.Request) -> web.Response:
    database_path: Path = request.app["database_path"]

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                id,
                name,
                category,
                quantity,
                unit,
                notes,
                source_scan_id,
                updated_at
            FROM inventory_items
            ORDER BY category, name
            """
        ).fetchall()

    return web.json_response(
        {
            "items": [
                dict(row)
                for row in rows
            ]
        }
    )