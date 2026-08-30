import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web


async def save_meal_as_favorite(
    request: web.Request,
) -> web.Response:
    meal_id = request.match_info["meal_id"]

    database_path: Path = request.app[
        "database_path"
    ]

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        meal = connection.execute(
            """
            SELECT
                id,
                title,
                servings,
                preparation_minutes,
                cooking_minutes,
                notes
            FROM meal_plan_meals
            WHERE id = ?
            """,
            (meal_id,),
        ).fetchone()

        if meal is None:
            raise web.HTTPNotFound(
                text="Unknown meal"
            )

        existing = connection.execute(
            """
            SELECT id
            FROM recipes
            WHERE source_meal_id = ?
            """,
            (meal_id,),
        ).fetchone()

        now = datetime.now(
            timezone.utc
        ).isoformat()

        if existing is not None:
            connection.execute(
                """
                UPDATE recipes
                SET
                    is_favorite = 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    existing["id"],
                ),
            )

            connection.commit()

            return web.json_response(
                {
                    "id": existing["id"],
                    "is_favorite": True,
                }
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

        steps = connection.execute(
            """
            SELECT
                step_index,
                instruction
            FROM meal_plan_steps
            WHERE meal_id = ?
            ORDER BY step_index
            """,
            (meal_id,),
        ).fetchall()

        recipe_id = str(uuid.uuid4())

        try:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute(
                """
                INSERT INTO recipes(
                    id,
                    title,
                    servings,
                    preparation_minutes,
                    cooking_minutes,
                    notes,
                    source,
                    source_meal_id,
                    is_favorite,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe_id,
                    meal["title"],
                    meal["servings"],
                    meal["preparation_minutes"],
                    meal["cooking_minutes"],
                    meal["notes"],
                    "meal_plan",
                    meal["id"],
                    1,
                    now,
                    now,
                ),
            )

            connection.executemany(
                """
                INSERT INTO recipe_ingredients(
                    recipe_id,
                    name,
                    quantity,
                    unit
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        recipe_id,
                        ingredient["name"],
                        ingredient["quantity"],
                        ingredient["unit"],
                    )
                    for ingredient in ingredients
                ],
            )

            connection.executemany(
                """
                INSERT INTO recipe_steps(
                    recipe_id,
                    step_index,
                    instruction
                )
                VALUES (?, ?, ?)
                """,
                [
                    (
                        recipe_id,
                        step["step_index"],
                        step["instruction"],
                    )
                    for step in steps
                ],
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    return web.json_response(
        {
            "id": recipe_id,
            "is_favorite": True,
        },
        status=201,
    )

async def get_recipes(
    request: web.Request,
) -> web.Response:
    database_path: Path = request.app[
        "database_path"
    ]

    favorites_only = (
        request.query.get("favorite")
        == "true"
    )

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        query = """
            SELECT
                id,
                title,
                servings,
                preparation_minutes,
                cooking_minutes,
                notes,
                source,
                is_favorite,
                cooked_count,
                last_cooked_at,
                created_at,
                updated_at
            FROM recipes
        """

        if favorites_only:
            query += """
                WHERE is_favorite = 1
            """

        query += """
            ORDER BY
                is_favorite DESC,
                title
        """

        recipes = connection.execute(
            query
        ).fetchall()

        result = []

        for recipe in recipes:
            ingredients = connection.execute(
                """
                SELECT
                    name,
                    quantity,
                    unit
                FROM recipe_ingredients
                WHERE recipe_id = ?
                ORDER BY id
                """,
                (recipe["id"],),
            ).fetchall()

            steps = connection.execute(
                """
                SELECT
                    step_index,
                    instruction
                FROM recipe_steps
                WHERE recipe_id = ?
                ORDER BY step_index
                """,
                (recipe["id"],),
            ).fetchall()

            value = dict(recipe)

            value["is_favorite"] = bool(
                value["is_favorite"]
            )

            value["ingredients"] = [
                dict(row)
                for row in ingredients
            ]

            value["steps"] = [
                row["instruction"]
                for row in steps
            ]

            result.append(value)

    return web.json_response(
        {
            "recipes": result,
        }
    )

async def set_recipe_favorite(
    request: web.Request,
) -> web.Response:
    recipe_id = request.match_info[
        "recipe_id"
    ]

    database_path: Path = request.app[
        "database_path"
    ]

    try:
        body = await request.json()
        favorite = body["favorite"]

        if not isinstance(favorite, bool):
            raise ValueError

    except (ValueError, KeyError):
        raise web.HTTPBadRequest(
            text="favorite must be a boolean"
        )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE recipes
            SET
                is_favorite = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                int(favorite),
                now,
                recipe_id,
            ),
        )

        if cursor.rowcount == 0:
            raise web.HTTPNotFound(
                text="Unknown recipe"
            )

        connection.commit()

    return web.json_response(
        {
            "id": recipe_id,
            "is_favorite": favorite,
        }
    )