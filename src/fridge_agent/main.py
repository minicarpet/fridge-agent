import os

from aiohttp import web


async def index(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "service": "fridge-agent",
            "status": "running",
        }
    )


async def health(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": "ok",
        }
    )


def create_app() -> web.Application:
    app = web.Application()

    app.router.add_get("/", index)
    app.router.add_get("/health", health)

    return app


def main() -> None:
    bind_address = os.getenv("FRIDGE_AGENT_BIND_ADDRESS", "0.0.0.0")
    port = int(os.getenv("FRIDGE_AGENT_PORT", "8080"))

    web.run_app(
        create_app(),
        host=bind_address,
        port=port,
    )


if __name__ == "__main__":
    main()