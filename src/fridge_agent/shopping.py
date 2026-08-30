import sqlite3
import unicodedata

from collections import defaultdict
from pathlib import Path

from aiohttp import web


def _normalize_name(name: str) -> str:
    return " ".join(
        unicodedata.normalize(
            "NFKC",
            name,
        )
        .casefold()
        .split()
    )


def _canonical_quantity(
    quantity: float,
    unit: str,
) -> tuple[float, str]:
    if unit == "kg":
        return quantity * 1000.0, "g"

    if unit == "l":
        return quantity * 1000.0, "ml"

    return quantity, unit


def _display_quantity(
    quantity: float,
    unit: str,
) -> tuple[float, str]:
    if unit == "g" and quantity >= 1000:
        return quantity / 1000.0, "kg"

    if unit == "ml" and quantity >= 1000:
        return quantity / 1000.0, "l"

    return quantity, unit


async def get_shopping_list(
    request: web.Request,
) -> web.Response:
    meal_plan_id = request.match_info[
        "meal_plan_id"
    ]

    database_path: Path = request.app[
        "database_path"
    ]

    with sqlite3.connect(
        database_path
    ) as connection:
        connection.row_factory = sqlite3.Row

        plan = connection.execute(
            """
            SELECT id
            FROM meal_plans
            WHERE id = ?
            """,
            (meal_plan_id,),
        ).fetchone()

        if plan is None:
            raise web.HTTPNotFound(
                text="Unknown meal plan"
            )

        ingredient_rows = connection.execute(
            """
            SELECT
                ingredient.name,
                ingredient.quantity,
                ingredient.unit
            FROM meal_plan_ingredients AS ingredient
            JOIN meal_plan_meals AS meal
                ON meal.id = ingredient.meal_id
            WHERE meal.meal_plan_id = ?
            ORDER BY ingredient.id
            """,
            (meal_plan_id,),
        ).fetchall()

        inventory_rows = connection.execute(
            """
            SELECT
                name,
                quantity,
                unit,
                'fridge' AS source
            FROM inventory_items

            UNION ALL

            SELECT
                name,
                quantity,
                unit,
                'pantry' AS source
            FROM pantry_items

            ORDER BY name
            """
          ).fetchall()

    required = {}

    for row in ingredient_rows:
        quantity, unit = _canonical_quantity(
            row["quantity"],
            row["unit"],
        )

        normalized_name = _normalize_name(
            row["name"]
        )

        key = (
            normalized_name,
            unit,
        )

        if key not in required:
            required[key] = {
                "name": row["name"],
                "quantity": 0.0,
                "unit": unit,
            }

        required[key]["quantity"] += quantity

    inventory_by_name = defaultdict(list)

    for row in inventory_rows:
        inventory_by_name[
            _normalize_name(row["name"])
        ].append(row)

    shopping_items = []
    covered_items = []

    for (
        normalized_name,
        required_unit,
    ), item in required.items():
        required_quantity = item["quantity"]

        inventory_matches = inventory_by_name.get(
            normalized_name,
            [],
        )

        known_available = 0.0
        uncertain_inventory = []

        for inventory_item in inventory_matches:
            if inventory_item["quantity"] is None:
                uncertain_inventory.append(
                    {
                        "quantity": None,
                        "unit": inventory_item["unit"],
                        "source": inventory_item["source"],
                    }
                )
                continue

            available_quantity, available_unit = (
                _canonical_quantity(
                    inventory_item["quantity"],
                    inventory_item["unit"],
                )
            )

            if available_unit != required_unit:
                uncertain_inventory.append(
                    {
                        "quantity":
                            inventory_item["quantity"],
                        "unit":
                            inventory_item["unit"],
                        "source": 
                            inventory_item["source"],
                    }
                )
                continue

            known_available += available_quantity

        missing_quantity = max(
            0.0,
            required_quantity - known_available,
        )

        displayed_required, displayed_unit = (
            _display_quantity(
                required_quantity,
                required_unit,
            )
        )

        if missing_quantity <= 0:
            covered_items.append(
                {
                    "name": item["name"],
                    "required_quantity":
                        displayed_required,
                    "unit": displayed_unit,
                }
            )
            continue

        if uncertain_inventory:
            shopping_items.append(
                {
                    "name": item["name"],
                    "status": "check_inventory",
                    "required_quantity":
                        displayed_required,
                    "unit": displayed_unit,
                    "known_available_quantity":
                        known_available,
                    "inventory": uncertain_inventory,
                    "quantity_to_buy": None,
                }
            )
            continue

        displayed_missing, missing_unit = (
            _display_quantity(
                missing_quantity,
                required_unit,
            )
        )

        shopping_items.append(
            {
                "name": item["name"],
                "status": "buy",
                "required_quantity":
                    displayed_required,
                "unit": displayed_unit,
                "known_available_quantity":
                    known_available,
                "quantity_to_buy":
                    displayed_missing,
                "quantity_to_buy_unit":
                    missing_unit,
            }
        )

    shopping_items.sort(
        key=lambda item: item["name"].casefold()
    )

    covered_items.sort(
        key=lambda item: item["name"].casefold()
    )

    return web.json_response(
        {
            "meal_plan_id": meal_plan_id,
            "items": shopping_items,
            "covered_items": covered_items,
        }
    )