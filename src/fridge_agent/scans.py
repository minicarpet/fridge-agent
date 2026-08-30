import sqlite3
import uuid
import logging
import os

from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web

from fridge_agent.openai_client import OpenAIError, analyze_fridge

LOGGER = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_IMAGE_SIZE = 10 * 1024 * 1024


async def create_scan(request: web.Request) -> web.Response:
    data_dir: Path = request.app["data_dir"]
    database_path: Path = request.app["database_path"]

    scan_id = str(uuid.uuid4())
    scan_dir = data_dir / "uploads" / scan_id
    scan_dir.mkdir(parents=True)

    reader = await request.multipart()

    images = []

    while True:
        field = await reader.next()

        if field is None:
            break

        if field.name != "images":
            continue

        if field.filename is None:
            continue

        if field.headers.get("Content-Type") not in ALLOWED_CONTENT_TYPES:
            raise web.HTTPBadRequest(
                text=f"Unsupported image type: {field.headers.get('Content-Type')}"
            )

        content = await field.read()

        if len(content) > MAX_IMAGE_SIZE:
            raise web.HTTPRequestEntityTooLarge(
                max_size=MAX_IMAGE_SIZE,
                actual_size=len(content),
            )

        extension = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }[field.headers["Content-Type"]]

        filename = f"image-{len(images) + 1:03d}{extension}"
        image_path = scan_dir / filename

        image_path.write_bytes(content)

        images.append(
            {
                "filename": filename,
                "content_type": field.headers["Content-Type"],
                "size_bytes": len(content),
            }
        )

    if not images:
        scan_dir.rmdir()
        raise web.HTTPBadRequest(text="No images provided")

    created_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO fridge_scans(id, created_at, status)
            VALUES (?, ?, ?)
            """,
            (
                scan_id,
                created_at,
                "uploaded",
            ),
        )

        connection.executemany(
            """
            INSERT INTO fridge_scan_images(
                scan_id,
                filename,
                content_type,
                size_bytes
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    image["filename"],
                    image["content_type"],
                    image["size_bytes"],
                )
                for image in images
            ],
        )

        connection.commit()

    return web.json_response(
        {
            "id": scan_id,
            "status": "uploaded",
            "images": images,
        },
        status=201,
    )

async def analyze_scan(request: web.Request) -> web.Response:
    scan_id = request.match_info["scan_id"]

    data_dir: Path = request.app["data_dir"]
    database_path: Path = request.app["database_path"]

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise web.HTTPServiceUnavailable(
            text="OPENAI_API_KEY is not configured"
        )

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6-luna",
    )

    with sqlite3.connect(database_path) as connection:
        scan = connection.execute(
            """
            SELECT id
            FROM fridge_scans
            WHERE id = ?
            """,
            (scan_id,),
        ).fetchone()

        if scan is None:
            raise web.HTTPNotFound(text="Unknown scan")

        image_rows = connection.execute(
            """
            SELECT filename, content_type
            FROM fridge_scan_images
            WHERE scan_id = ?
            ORDER BY id
            """,
            (scan_id,),
        ).fetchall()

        connection.execute(
            """
            UPDATE fridge_scans
            SET status = ?, error = NULL
            WHERE id = ?
            """,
            ("analyzing", scan_id),
        )

        connection.commit()

    scan_dir = data_dir / "uploads" / scan_id

    images = [
        (
            scan_dir / filename,
            content_type,
        )
        for filename, content_type in image_rows
    ]

    try:
        analysis, metadata = await analyze_fridge(
            images=images,
            api_key=api_key,
            model=model,
        )

    except OpenAIError as exception:
        LOGGER.exception(
            "Fridge analysis failed for scan %s",
            scan_id,
        )

        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                UPDATE fridge_scans
                SET status = ?, error = ?
                WHERE id = ?
                """,
                (
                    "analysis_failed",
                    str(exception),
                    scan_id,
                ),
            )

            connection.commit()

        raise web.HTTPBadGateway(
            text="AI analysis failed"
        ) from exception

    usage = metadata["usage"]

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            DELETE FROM fridge_scan_items
            WHERE scan_id = ?
            """,
            (scan_id,),
        )

        connection.executemany(
            """
            INSERT INTO fridge_scan_items(
                scan_id,
                name,
                category,
                quantity,
                unit,
                confidence,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    item.name,
                    item.category,
                    item.quantity,
                    item.unit,
                    item.confidence,
                    item.notes,
                )
                for item in analysis.items
            ],
        )

        connection.execute(
            """
            UPDATE fridge_scans
            SET
                status = ?,
                model = ?,
                response_id = ?,
                input_tokens = ?,
                output_tokens = ?,
                error = NULL
            WHERE id = ?
            """,
            (
                "analyzed",
                metadata["model"],
                metadata["response_id"],
                usage.get("input_tokens"),
                usage.get("output_tokens"),
                scan_id,
            ),
        )

        connection.commit()

    return web.json_response(
        {
            "id": scan_id,
            "status": "analyzed",
            "analysis": analysis.model_dump(),
            "model": metadata["model"],
            "usage": usage,
        }
    )