import sqlite3

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web

from fridge_agent.food_quantities import (
    canonical_quantity,
    from_canonical_quantity,
    normalize_food_name,
)


_EPSILON = 1e-9


async def mark_meal_cooked(
    request: web.Request,
) -> web.Response:
    meal_id = request.match_info[
        "meal_id"
    ]

    database_path: Path = request.app[
        "database_path"
    ]

    cooked_at = datetime.now(
        timezone.utc
    ).isoformat()

    with sqlite3.connect(
        database_path
    ) as connection:
        connection.row_factory = (
            sqlite3.Row
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            meal = connection.execute(
                """
                SELECT
                    id,
                    cooked_at
                FROM meal_plan_meals
                WHERE id = ?
                """,
                (meal_id,),
            ).fetchone()

            if meal is None:
                raise web.HTTPNotFound(
                    text="Unknown meal"
                )

            if meal["cooked_at"] is not None:
                raise web.HTTPConflict(
                    text="Meal is already cooked"
                )

            ingredients = connection.execute(
                """
                SELECT
                    name,
                    quantity,
                    unit
                FROM meal_plan_ingredients
                WHERE meal_id = ?
                ORDER BY id
                """,
                (meal_id,),
            ).fetchall()

            stock = _load_stock(
                connection
            )

            updates = []
            unresolved = []

            for ingredient in ingredients:
                result = _consume_ingredient(
                    connection=connection,
                    ingredient=ingredient,
                    stock=stock,
                    updated_at=cooked_at,
                )

                updates.extend(
                    result["updates"]
                )

                if result["unresolved"]:
                    unresolved.append(
                        result["unresolved"]
                    )

            connection.execute(
                """
                UPDATE meal_plan_meals
                SET cooked_at = ?
                WHERE id = ?
                """,
                (
                    cooked_at,
                    meal_id,
                ),
            )

            connection.execute(
                """
                UPDATE recipes
                SET
                    cooked_count =
                        cooked_count + 1,
                    last_cooked_at = ?,
                    updated_at = ?
                WHERE source_meal_id = ?
                """,
                (
                    cooked_at,
                    cooked_at,
                    meal_id,
                ),
            )

            connection.commit()

        except web.HTTPException:
            connection.rollback()
            raise

        except Exception:
            connection.rollback()
            raise

    return web.json_response(
        {
            "id": int(meal_id),
            "cooked_at": cooked_at,
            "inventory_updates": updates,
            "unresolved": unresolved,
        }
    )


def _load_stock(
    connection: sqlite3.Connection,
) -> dict[str, list[dict]]:
    result = defaultdict(list)

    fridge_rows = connection.execute(
        """
        SELECT
            id,
            name,
            quantity,
            unit
        FROM inventory_items
        ORDER BY id
        """
    ).fetchall()

    pantry_rows = connection.execute(
        """
        SELECT
            id,
            name,
            quantity,
            unit
        FROM pantry_items
        ORDER BY id
        """
    ).fetchall()

    for row in fridge_rows:
        result[
            normalize_food_name(
                row["name"]
            )
        ].append(
            {
                **dict(row),
                "source": "fridge",
            }
        )

    for row in pantry_rows:
        result[
            normalize_food_name(
                row["name"]
            )
        ].append(
            {
                **dict(row),
                "source": "pantry",
            }
        )

    return result


def _consume_ingredient(
    *,
    connection: sqlite3.Connection,
    ingredient: sqlite3.Row,
    stock: dict[str, list[dict]],
    updated_at: str,
) -> dict:
    required_quantity, required_unit = (
        canonical_quantity(
            ingredient["quantity"],
            ingredient["unit"],
        )
    )

    normalized_name = (
        normalize_food_name(
            ingredient["name"]
        )
    )

    matches = stock.get(
        normalized_name,
        [],
    )

    if not matches:
        return _unresolved_result(
            ingredient,
            required_quantity,
            required_unit,
            "not_in_inventory",
        )

    compatible = []

    for item in matches:
        if item["quantity"] is None:
            return _unresolved_result(
                ingredient,
                required_quantity,
                required_unit,
                "unknown_quantity",
            )

        quantity, unit = (
            canonical_quantity(
                item["quantity"],
                item["unit"],
            )
        )

        if unit != required_unit:
            return _unresolved_result(
                ingredient,
                required_quantity,
                required_unit,
                "unit_mismatch",
            )

        compatible.append(
            (
                item,
                quantity,
            )
        )

    remaining = required_quantity
    updates = []

    for item, available in compatible:
        if remaining <= _EPSILON:
            break

        consumed = min(
            remaining,
            available,
        )

        remaining_after = (
            available - consumed
        )

        _update_stock_item(
            connection=connection,
            item=item,
            canonical_quantity_after=
                remaining_after,
            updated_at=updated_at,
        )

        updates.append(
            {
                "name": item["name"],
                "source": item["source"],
                "consumed_quantity":
                    consumed,
                "unit": required_unit,
            }
        )

        item["quantity"] = (
            from_canonical_quantity(
                remaining_after,
                item["unit"],
            )
        )

        remaining -= consumed

    unresolved = None

    if remaining > _EPSILON:
        unresolved = {
            "name": ingredient["name"],
            "quantity": remaining,
            "unit": required_unit,
            "reason":
                "insufficient_quantity",
        }

    return {
        "updates": updates,
        "unresolved": unresolved,
    }


def _update_stock_item(
    *,
    connection: sqlite3.Connection,
    item: dict,
    canonical_quantity_after: float,
    updated_at: str,
) -> None:
    if canonical_quantity_after <= _EPSILON:
        if item["source"] == "fridge":
            connection.execute(
                """
                DELETE FROM inventory_items
                WHERE id = ?
                """,
                (item["id"],),
            )
        else:
            connection.execute(
                """
                DELETE FROM pantry_items
                WHERE id = ?
                """,
                (item["id"],),
            )

        return

    quantity = from_canonical_quantity(
        canonical_quantity_after,
        item["unit"],
    )

    if item["source"] == "fridge":
        connection.execute(
            """
            UPDATE inventory_items
            SET
                quantity = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                quantity,
                updated_at,
                item["id"],
            ),
        )

    else:
        connection.execute(
            """
            UPDATE pantry_items
            SET
                quantity = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                quantity,
                updated_at,
                item["id"],
            ),
        )


def _unresolved_result(
    ingredient: sqlite3.Row,
    quantity: float,
    unit: str,
    reason: str,
) -> dict:
    return {
        "updates": [],
        "unresolved": {
            "name": ingredient["name"],
            "quantity": quantity,
            "unit": unit,
            "reason": reason,
        },
    }