import json
import base64
from pathlib import Path

import httpx

from fridge_agent.models import (
    FridgeAnalysis,
    GeneratedMealPlan,
)


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

FRIDGE_ANALYSIS_INSTRUCTIONS = """
Analyze all provided images as photographs from the same refrigerator scan.

Identify food and drink products that are actually visible.

Rules:
- Treat all images as different views of the same refrigerator.
- Merge the same physical product when it appears in multiple images.
- Do not invent products that are hidden or not visible.
- Use generic French product names when possible.
- Estimate quantities only when reasonably visible.
- If quantity cannot be determined, return null.
- Do not invent package weights, brands, expiry dates, or contents.
- Confidence must represent how certain the visual identification is.
- Use warnings for important uncertainty or visibility problems.
"""

MEAL_PLAN_INSTRUCTIONS = """
You are the meal planner for a household.

Generate practical recipes based on the supplied household settings,
preferences and current refrigerator inventory.

Rules:
- Write recipe titles, ingredient names, instructions and notes in French.
- Generate exactly the requested dates and meal types.
- Respect avoided foods strictly.
- Favor liked foods and cuisines when practical.
- Prioritize ingredients already present in the inventory.
- Prefer using perishable refrigerator ingredients before buying alternatives.
- Every meal must be suitable for the requested number of people.
- Respect weekday and weekend cooking-time limits.
- Ingredients must represent the complete quantity required for the recipe.
- Use only the units allowed by the schema.
- Do not omit ingredients just because they are common pantry staples.
- Do not invent that an ingredient exists in the inventory.
- Keep recipes realistic and reasonably simple.
- Vary meals during the planning period.
- Always provide the notes field for every meal.
- Use an empty string when there is no specific note.
- Favorite recipes are strong preference signals.
- Reuse a favorite recipe when it fits the inventory and schedule.
- You may also create recipes inspired by favorite recipes.
- Do not overuse favorites or repeat the same recipe too frequently.
- Keep variety across the planning period.
"""

MEAL_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "meals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                    },
                    "meal_type": {
                        "type": "string",
                        "enum": [
                            "lunch",
                            "dinner",
                        ],
                    },
                    "title": {
                        "type": "string",
                    },
                    "servings": {
                        "type": "integer",
                    },
                    "preparation_minutes": {
                        "type": "integer",
                    },
                    "cooking_minutes": {
                        "type": "integer",
                    },
                    "ingredients": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                },
                                "quantity": {
                                    "type": "number",
                                },
                                "unit": {
                                    "type": "string",
                                    "enum": [
                                        "g",
                                        "kg",
                                        "ml",
                                        "l",
                                        "piece",
                                        "pack",
                                        "bottle",
                                        "jar",
                                        "can",
                                    ],
                                },
                            },
                            "required": [
                                "name",
                                "quantity",
                                "unit",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "notes": {
                        "type": "string",
                    },
                },
                "required": [
                    "date",
                    "meal_type",
                    "title",
                    "servings",
                    "preparation_minutes",
                    "cooking_minutes",
                    "ingredients",
                    "steps",
                    "notes",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "meals",
    ],
    "additionalProperties": False,
}


class OpenAIError(RuntimeError):
    pass


def _image_content(
    path: Path,
    content_type: str,
) -> dict:
    encoded = base64.b64encode(
        path.read_bytes()
    ).decode("ascii")

    return {
        "type": "input_image",
        "image_url": (
            f"data:{content_type};base64,{encoded}"
        ),
    }


def _extract_output_text(response: dict) -> str:
    for output in response.get("output", []):
        if output.get("type") != "message":
            continue

        for content in output.get("content", []):
            if content.get("type") == "output_text":
                return content["text"]

            if content.get("type") == "refusal":
                raise OpenAIError(
                    f"Model refused request: "
                    f"{content.get('refusal', 'unknown reason')}"
                )

    raise OpenAIError("OpenAI response contains no output text")


async def analyze_fridge(
    *,
    images: list[tuple[Path, str]],
    api_key: str,
    model: str,
) -> tuple[FridgeAnalysis, dict]:
    content = [
        {
            "type": "input_text",
            "text": "Analyze these refrigerator images.",
        }
    ]

    content.extend(
        _image_content(path, content_type)
        for path, content_type in images
    )

    payload = {
        "model": model,
        "store": False,
        "reasoning": {
            "effort": "low",
        },
        "instructions": FRIDGE_ANALYSIS_INSTRUCTIONS,
        "input": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "fridge_analysis",
                "strict": True,
                "schema": FridgeAnalysis.model_json_schema(),
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            OPENAI_RESPONSES_URL,
            headers=headers,
            json=payload,
        )

    if response.is_error:
        try:
            error = response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            error = response.text

        raise OpenAIError(
            f"OpenAI returned HTTP {response.status_code}: {error}"
        )

    response_data = response.json()

    output_text = _extract_output_text(response_data)

    try:
        analysis = FridgeAnalysis.model_validate_json(
            output_text
        )
    except ValueError as exception:
        raise OpenAIError(
            "Invalid structured response returned by OpenAI"
        ) from exception

    metadata = {
        "response_id": response_data.get("id"),
        "model": response_data.get("model"),
        "usage": response_data.get("usage", {}),
    }

    return analysis, metadata

async def generate_meal_plan(
    *,
    context: dict,
    api_key: str,
    model: str,
) -> tuple[GeneratedMealPlan, dict]:
    payload = {
        "model": model,
        "store": False,
        "reasoning": {
            "effort": "low",
        },
        "instructions": MEAL_PLAN_INSTRUCTIONS,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            context,
                            ensure_ascii=False,
                        ),
                    }
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "meal_plan",
                "strict": True,
                "schema": MEAL_PLAN_SCHEMA,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(
        timeout=120.0
    ) as client:
        response = await client.post(
            OPENAI_RESPONSES_URL,
            headers=headers,
            json=payload,
        )

    if response.is_error:
        try:
            error = response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            error = response.text

        raise OpenAIError(
            f"OpenAI returned HTTP "
            f"{response.status_code}: {error}"
        )

    response_data = response.json()

    output_text = _extract_output_text(
        response_data
    )

    try:
        plan = GeneratedMealPlan.model_validate_json(
            output_text
        )
    except ValueError as exception:
        raise OpenAIError(
            "Invalid meal plan returned by OpenAI"
        ) from exception

    metadata = {
        "response_id": response_data.get("id"),
        "model": response_data.get("model"),
        "usage": response_data.get("usage", {}),
    }

    return plan, metadata