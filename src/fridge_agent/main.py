import os

from pathlib import Path

from aiohttp import web
from jinja2 import Environment, PackageLoader, select_autoescape

from fridge_agent.database import initialize_database
from fridge_agent.scans import analyze_scan, create_scan


async def index(request: web.Request) -> web.Response:
    templates: Environment = request.app["templates"]

    template = templates.get_template("index.html")

    return web.Response(
        text=template.render(),
        content_type="text/html",
    )


async def health(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": "ok",
        }
    )


def create_app(data_dir: Path) -> web.Application:
    app = web.Application(
        client_max_size=50 * 1024 * 1024,
    )

    app["data_dir"] = data_dir
    app["database_path"] = initialize_database(data_dir)

    app["templates"] = Environment(
        loader=PackageLoader("fridge_agent"),
        autoescape=select_autoescape(),
    )

    app.router.add_get("/", index)
    app.router.add_get("/health", health)

    app.router.add_post(
        "/api/fridge/scans",
        create_scan,
    )

    app.router.add_post(
        "/api/fridge/scans/{scan_id}/analyze",
        analyze_scan,
    )

    return app


def main() -> None:
    bind_address = os.getenv(
        "FRIDGE_AGENT_BIND_ADDRESS",
        "0.0.0.0",
    )

    port = int(
        os.getenv(
            "FRIDGE_AGENT_PORT",
            "8080",
        )
    )

    data_dir = Path(
        os.getenv(
            "FRIDGE_AGENT_DATA_DIR",
            "/data/fridge-agent",
        )
    )

    web.run_app(
        create_app(data_dir),
        host=bind_address,
        port=port,
    )


if __name__ == "__main__":
    main()