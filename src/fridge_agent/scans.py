import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web


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