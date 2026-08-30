import sqlite3

from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web
from pydantic import ValidationError

from fridge_agent.models import PantryUpdateRequest


async def get_pantry(
    request: web.Request,
) -> web.Response:
    database_path: Path = request.app["database_path"]

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                id,
                name,
                quantity,
                unit,
                updated_at
            FROM pantry_items
            ORDER BY name
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


async def update_pantry(
    request: web.Request,
) -> web.Response:
    database_path: Path = request.app["database_path"]

    try:
        body = await request.json()

        pantry = PantryUpdateRequest.model_validate(
            body
        )

    except (ValueError, ValidationError) as exception:
        raise web.HTTPBadRequest(
            text="Invalid pantry inventory"
        ) from exception

    updated_at = datetime.now(
        timezone.utc
    ).isoformat()

    with sqlite3.connect(database_path) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute(
                """
                DELETE FROM pantry_items
                """
            )

            connection.executemany(
                """
                INSERT INTO pantry_items(
                    name,
                    quantity,
                    unit,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        item.name.strip(),
                        item.quantity,
                        item.unit,
                        updated_at,
                    )
                    for item in pantry.items
                    if item.name.strip()
                ],
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    return web.json_response(
        {
            "status": "updated",
            "count": len(pantry.items),
        }
    )