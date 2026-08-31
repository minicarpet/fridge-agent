import os
import hashlib

from pathlib import Path

from aiohttp import web
from jinja2 import Environment, PackageLoader, select_autoescape

from fridge_agent.database import initialize_database
from fridge_agent.inventory import get_inventory
from fridge_agent.scans import analyze_scan, confirm_scan, create_scan
from fridge_agent.settings import (
    get_settings,
    update_settings,
)
from fridge_agent.meal_plans import (
    generate_plan,
    get_latest_plan,
    get_plan,
)
from fridge_agent.shopping import (
    get_shopping_list,
)
from fridge_agent.pantry import (
    get_pantry,
    update_pantry,
)
from fridge_agent.recipes import (
    get_recipes,
    save_meal_as_favorite,
    set_recipe_favorite,
)
from fridge_agent.cooking import (
    mark_meal_cooked,
)

def _get_asset_version(
    static_dir: Path,
) -> str:
    digest = hashlib.sha256()

    for path in sorted(
        item
        for item in static_dir.rglob("*")
        if item.is_file()
    ):
        digest.update(
            path.relative_to(
                static_dir
            ).as_posix().encode()
        )

        digest.update(
            path.read_bytes()
        )

    return digest.hexdigest()[:12]


def render_template(
    request: web.Request,
    template_name: str,
    *,
    active_page: str,
) -> web.Response:
    templates: Environment = request.app["templates"]

    template = templates.get_template(
        template_name
    )

    return web.Response(
        text=template.render(
            active_page=active_page,
            asset_version=request.app[
                "asset_version"
            ],
        ),
        content_type="text/html",
    )

async def dashboard(
    request: web.Request,
) -> web.Response:
    return render_template(
        request,
        "dashboard.html",
        active_page="dashboard",
    )


async def fridge_page(
    request: web.Request,
) -> web.Response:
    return render_template(
        request,
        "fridge.html",
        active_page="fridge",
    )


async def pantry_page(
    request: web.Request,
) -> web.Response:
    return render_template(
        request,
        "pantry.html",
        active_page="pantry",
    )


async def menu_page(
    request: web.Request,
) -> web.Response:
    return render_template(
        request,
        "menu.html",
        active_page="menu",
    )


async def recipes_page(
    request: web.Request,
) -> web.Response:
    return render_template(
        request,
        "recipes.html",
        active_page="recipes",
    )


async def shopping_page(
    request: web.Request,
) -> web.Response:
    return render_template(
        request,
        "shopping.html",
        active_page="shopping",
    )


async def settings_page(
    request: web.Request,
) -> web.Response:
    return render_template(
        request,
        "settings.html",
        active_page="settings",
    )


async def health(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": "ok",
        }
    )


def create_app(data_dir: Path) -> web.Application:
    static_dir = (
        Path(__file__).parent
        / "static"
    )

    app_asset_version = (
        _get_asset_version(
            static_dir
        )
    )

    app = web.Application(
        client_max_size=50 * 1024 * 1024,
    )

    app.router.add_static(
        "/static/",
        path=static_dir,
        name="static",
    )

    app["data_dir"] = data_dir
    app["asset_version"] = (
        app_asset_version
    )
    app["database_path"] = initialize_database(data_dir)

    app["templates"] = Environment(
        loader=PackageLoader("fridge_agent"),
        autoescape=select_autoescape(),
    )

    app.router.add_get("/", dashboard)

    app.router.add_get(
        "/fridge",
        fridge_page,
    )

    app.router.add_get(
        "/pantry",
        pantry_page,
    )

    app.router.add_get(
        "/menu",
        menu_page,
    )

    app.router.add_get(
        "/recipes",
        recipes_page,
    )

    app.router.add_get(
        "/shopping",
        shopping_page,
    )

    app.router.add_get(
        "/settings",
        settings_page,
    )
    app.router.add_get("/health", health)

    app.router.add_post(
        "/api/fridge/scans",
        create_scan,
    )

    app.router.add_post(
        "/api/fridge/scans/{scan_id}/analyze",
        analyze_scan,
    )

    app.router.add_post(
        "/api/fridge/scans/{scan_id}/confirm",
        confirm_scan,
    )

    app.router.add_get(
        "/api/inventory",
        get_inventory,
    )

    app.router.add_get(
        "/api/settings",
        get_settings,
    )

    app.router.add_put(
        "/api/settings",
        update_settings,
    )

    app.router.add_post(
        "/api/meal-plans/generate",
        generate_plan,
    )

    app.router.add_get(
        "/api/meal-plans/latest",
        get_latest_plan,
    )

    app.router.add_get(
        "/api/meal-plans/{meal_plan_id}/shopping-list",
        get_shopping_list,
    )

    app.router.add_get(
        "/api/meal-plans/{meal_plan_id}",
        get_plan,
    )

    app.router.add_get(
        "/api/pantry",
        get_pantry,
    )

    app.router.add_put(
        "/api/pantry",
        update_pantry,
    )

    app.router.add_get(
        "/api/recipes",
        get_recipes,
    )

    app.router.add_post(
        "/api/meals/{meal_id}/favorite",
        save_meal_as_favorite,
    )

    app.router.add_post(
        "/api/meals/{meal_id}/cooked",
        mark_meal_cooked,
    )

    app.router.add_put(
        "/api/recipes/{recipe_id}/favorite",
        set_recipe_favorite,
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