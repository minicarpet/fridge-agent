import sqlite3

from pathlib import Path

from aiohttp import web
from pydantic import ValidationError

from fridge_agent.models import HouseholdSettings


async def get_settings(
    request: web.Request,
) -> web.Response:
    database_path: Path = request.app["database_path"]

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        settings = connection.execute(
            """
            SELECT
                people,
                planning_days,
                plan_lunch,
                plan_dinner,
                weekday_max_cooking_minutes,
                weekend_max_cooking_minutes,
                use_leftovers,
                notes
            FROM household_settings
            WHERE id = 1
            """
        ).fetchone()

        preferences = connection.execute(
            """
            SELECT preference_type, name
            FROM food_preferences
            ORDER BY name
            """
        ).fetchall()

    liked_foods = [
        row["name"]
        for row in preferences
        if row["preference_type"] == "like"
    ]

    avoided_foods = [
        row["name"]
        for row in preferences
        if row["preference_type"] == "avoid"
    ]

    return web.json_response(
        {
            "people": settings["people"],
            "planning_days": settings["planning_days"],
            "plan_lunch": bool(settings["plan_lunch"]),
            "plan_dinner": bool(settings["plan_dinner"]),
            "weekday_max_cooking_minutes":
                settings["weekday_max_cooking_minutes"],
            "weekend_max_cooking_minutes":
                settings["weekend_max_cooking_minutes"],
            "use_leftovers": bool(
                settings["use_leftovers"]
            ),
            "liked_foods": liked_foods,
            "avoided_foods": avoided_foods,
            "notes": settings["notes"],
        }
    )


async def update_settings(
    request: web.Request,
) -> web.Response:
    database_path: Path = request.app["database_path"]

    try:
        body = await request.json()

        settings = HouseholdSettings.model_validate(
            body
        )

    except (ValueError, ValidationError) as exception:
        raise web.HTTPBadRequest(
            text="Invalid household settings"
        ) from exception

    liked_foods = _clean_food_list(
        settings.liked_foods
    )

    avoided_foods = _clean_food_list(
        settings.avoided_foods
    )

    with sqlite3.connect(database_path) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute(
                """
                UPDATE household_settings
                SET
                    people = ?,
                    planning_days = ?,
                    plan_lunch = ?,
                    plan_dinner = ?,
                    weekday_max_cooking_minutes = ?,
                    weekend_max_cooking_minutes = ?,
                    use_leftovers = ?,
                    notes = ?
                WHERE id = 1
                """,
                (
                    settings.people,
                    settings.planning_days,
                    int(settings.plan_lunch),
                    int(settings.plan_dinner),
                    settings.weekday_max_cooking_minutes,
                    settings.weekend_max_cooking_minutes,
                    int(settings.use_leftovers),
                    settings.notes.strip(),
                ),
            )

            connection.execute(
                """
                DELETE FROM food_preferences
                """
            )

            connection.executemany(
                """
                INSERT INTO food_preferences(
                    preference_type,
                    name
                )
                VALUES (?, ?)
                """,
                [
                    ("like", name)
                    for name in liked_foods
                ]
                +
                [
                    ("avoid", name)
                    for name in avoided_foods
                ],
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    return web.json_response(
        {
            "status": "updated",
        }
    )


def _clean_food_list(
    foods: list[str],
) -> list[str]:
    result = []

    for food in foods:
        food = food.strip()

        if not food:
            continue

        if food.casefold() not in {
            existing.casefold()
            for existing in result
        }:
            result.append(food)

    return result