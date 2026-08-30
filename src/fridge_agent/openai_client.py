import base64
from pathlib import Path

import httpx

from fridge_agent.models import FridgeAnalysis


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