import logging
import os
import sqlite3
import uuid

from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

from aiohttp import web

from fridge_agent.openai_client import (
    OpenAIError,
    generate_meal_plan,
)


LOGGER = logging.getLogger(__name__)


async def generate_plan(
    request: web.Request,
) -> web.Response:
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

    start_date = _get_start_date(request)

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

        inventory = connection.execute(
            """
            SELECT
                name,
                category,
                quantity,
                unit,
                notes
            FROM inventory_items
            ORDER BY category, name
            """
        ).fetchall()

    if settings is None:
        raise web.HTTPConflict(
            text="Household settings are not configured"
        )

    meal_types = []

    if settings["plan_lunch"]:
        meal_types.append("lunch")

    if settings["plan_dinner"]:
        meal_types.append("dinner")

    if not meal_types:
        raise web.HTTPConflict(
            text="At least one meal type must be enabled"
        )

    planning_days = settings["planning_days"]

    dates = [
        start_date + timedelta(days=index)
        for index in range(planning_days)
    ]

    context = {
        "planning": {
            "start_date": start_date.isoformat(),
            "dates": [
                value.isoformat()
                for value in dates
            ],
            "meal_types": meal_types,
        },
        "household": {
            "people": settings["people"],
            "weekday_max_cooking_minutes":
                settings[
                    "weekday_max_cooking_minutes"
                ],
            "weekend_max_cooking_minutes":
                settings[
                    "weekend_max_cooking_minutes"
                ],
            "use_leftovers": bool(
                settings["use_leftovers"]
            ),
            "notes": settings["notes"],
        },
        "liked_foods": [
            row["name"]
            for row in preferences
            if row["preference_type"] == "like"
        ],
        "avoided_foods": [
            row["name"]
            for row in preferences
            if row["preference_type"] == "avoid"
        ],
        "inventory": [
            dict(row)
            for row in inventory
        ],
    }

    try:
        plan, metadata = await generate_meal_plan(
            context=context,
            api_key=api_key,
            model=model,
        )

        _validate_generated_plan(
            plan=plan,
            dates=dates,
            meal_types=meal_types,
            people=settings["people"],
        )

    except OpenAIError as exception:
        LOGGER.exception(
            "Meal plan generation failed"
        )

        raise web.HTTPBadGateway(
            text="AI meal plan generation failed"
        ) from exception

    plan_id = str(uuid.uuid4())

    created_at = (
        datetime.now(timezone.utc).isoformat()
    )

    usage = metadata["usage"]

    with sqlite3.connect(database_path) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute(
                """
                INSERT INTO meal_plans(
                    id,
                    created_at,
                    start_date,
                    planning_days,
                    status,
                    model,
                    response_id,
                    input_tokens,
                    output_tokens
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    created_at,
                    start_date.isoformat(),
                    planning_days,
                    "generated",
                    metadata["model"],
                    metadata["response_id"],
                    usage.get("input_tokens"),
                    usage.get("output_tokens"),
                ),
            )

            for meal in plan.meals:
                cursor = connection.execute(
                    """
                    INSERT INTO meal_plan_meals(
                        meal_plan_id,
                        meal_date,
                        meal_type,
                        title,
                        servings,
                        preparation_minutes,
                        cooking_minutes,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        meal.date.isoformat(),
                        meal.meal_type,
                        meal.title,
                        meal.servings,
                        meal.preparation_minutes,
                        meal.cooking_minutes,
                        meal.notes,
                    ),
                )

                meal_id = cursor.lastrowid

                connection.executemany(
                    """
                    INSERT INTO meal_plan_ingredients(
                        meal_id,
                        name,
                        quantity,
                        unit
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            meal_id,
                            ingredient.name,
                            ingredient.quantity,
                            ingredient.unit,
                        )
                        for ingredient
                        in meal.ingredients
                    ],
                )

                connection.executemany(
                    """
                    INSERT INTO meal_plan_steps(
                        meal_id,
                        step_index,
                        instruction
                    )
                    VALUES (?, ?, ?)
                    """,
                    [
                        (
                            meal_id,
                            index,
                            instruction,
                        )
                        for index, instruction
                        in enumerate(
                            meal.steps,
                            start=1,
                        )
                    ],
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    return web.json_response(
        {
            "id": plan_id,
            "status": "generated",
            "start_date": start_date.isoformat(),
            "plan": plan.model_dump(
                mode="json"
            ),
            "model": metadata["model"],
            "usage": usage,
        },
        status=201,
    )


def _get_start_date(
    request: web.Request,
) -> date:
    value = request.query.get("start_date")

    if value is None:
        return datetime.now().astimezone().date()

    try:
        return date.fromisoformat(value)
    except ValueError as exception:
        raise web.HTTPBadRequest(
            text="start_date must use YYYY-MM-DD"
        ) from exception


def _validate_generated_plan(
    *,
    plan,
    dates: list[date],
    meal_types: list[str],
    people: int,
) -> None:
    expected = {
        (meal_date, meal_type)
        for meal_date in dates
        for meal_type in meal_types
    }

    actual = {
        (meal.date, meal.meal_type)
        for meal in plan.meals
    }

    if len(plan.meals) != len(expected):
        raise OpenAIError(
            "AI returned an incorrect number of meals"
        )

    if actual != expected:
        raise OpenAIError(
            "AI returned incorrect dates or meal types"
        )

    if any(
        meal.servings != people
        for meal in plan.meals
    ):
        raise OpenAIError(
            "AI returned an incorrect serving count"
        )