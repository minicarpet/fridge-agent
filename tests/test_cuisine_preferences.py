import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import TestClient, TestServer
import httpx

from fridge_agent.database import initialize_database
from fridge_agent.main import create_app
from fridge_agent.models import GeneratedMealPlan, PlannedMeal
from fridge_agent.openai_client import generate_meal_plan


class CuisinePreferencesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.directory.name)
        self.app = create_app(self.data_dir)
        self.client = TestClient(TestServer(self.app))
        await self.client.start_server()
        response = await self.client.get("/api/settings")
        self.settings = await response.json()
        self.settings.update(
            planning_days=1,
            liked_foods=["tomates"],
            avoided_foods=["arachides"],
            favorite_cuisines=["Thai", "Mexican"],
        )
        response = await self.client.put(
            "/api/settings", json=self.settings
        )
        self.assertEqual(response.status, 200)

    async def asyncTearDown(self):
        await self.client.close()
        self.directory.cleanup()

    async def get_settings(self):
        response = await self.client.get("/api/settings")
        self.assertEqual(response.status, 200)
        return await response.json()

    async def test_settings_round_trip_normalizes_cuisines(self):
        self.settings["favorite_cuisines"] = [
            " Thai ", "thai", "", "Mexican", "   ",
        ]
        response = await self.client.put(
            "/api/settings", json=self.settings
        )
        self.assertEqual(response.status, 200)
        settings = await self.get_settings()
        self.assertEqual(settings["favorite_cuisines"], ["Mexican", "Thai"])
        self.assertEqual(settings["liked_foods"], ["tomates"])
        self.assertEqual(settings["avoided_foods"], ["arachides"])
        self.assertEqual(settings["people"], self.settings["people"])

        initialize_database(self.data_dir)
        self.assertEqual(
            (await self.get_settings())["favorite_cuisines"],
            ["Mexican", "Thai"],
        )

    async def test_settings_can_clear_cuisines(self):
        self.settings["favorite_cuisines"] = []
        response = await self.client.put(
            "/api/settings", json=self.settings
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(
            (await self.get_settings())["favorite_cuisines"], []
        )

    async def test_older_settings_clients_preserve_cuisines(self):
        del self.settings["favorite_cuisines"]
        response = await self.client.put(
            "/api/settings", json=self.settings
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(
            (await self.get_settings())["favorite_cuisines"],
            ["Mexican", "Thai"],
        )

    async def test_existing_database_adds_cuisines_without_losing_settings(self):
        with sqlite3.connect(self.app["database_path"]) as connection:
            connection.execute("DROP TABLE favorite_cuisines")

        initialize_database(self.data_dir)
        settings = await self.get_settings()
        self.assertEqual(settings["favorite_cuisines"], [])
        self.assertEqual(settings["liked_foods"], ["tomates"])
        self.assertEqual(settings["avoided_foods"], ["arachides"])
        self.assertEqual(settings["planning_days"], 1)

    async def test_invalid_settings_do_not_replace_saved_cuisines(self):
        for invalid in ("Thai", [3], None):
            with self.subTest(invalid=invalid):
                response = await self.client.put(
                    "/api/settings",
                    json={**self.settings, "favorite_cuisines": invalid},
                )
                self.assertEqual(response.status, 400)
                self.assertEqual(
                    (await self.get_settings())["favorite_cuisines"],
                    ["Mexican", "Thai"],
                )

    async def test_generation_uses_defaults_overrides_and_explicit_empty_list(self):
        plan = GeneratedMealPlan(
            meals=[
                PlannedMeal(
                    date=date(2026, 10, 12),
                    meal_type="dinner",
                    title="Soupe",
                    servings=2,
                    preparation_minutes=10,
                    cooking_minutes=15,
                    ingredients=[],
                    steps=["Préparer la soupe."],
                    notes="",
                )
            ]
        )
        metadata = {
            "model": "test-model",
            "response_id": "test-response",
            "usage": {},
        }
        cases = [
            (None, ["Mexican", "Thai"]),
            ({}, ["Mexican", "Thai"]),
            ({"favorite_cuisines": None}, ["Mexican", "Thai"]),
            ({"favorite_cuisines": [" Asian ", "asian", ""]}, ["Asian"]),
            ({"favorite_cuisines": []}, []),
        ]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            for body, expected in cases:
                with self.subTest(body=body):
                    with patch(
                        "fridge_agent.meal_plans.generate_meal_plan",
                        new_callable=AsyncMock,
                        return_value=(plan, metadata),
                    ) as generate:
                        options = {} if body is None else {"json": body}
                        response = await self.client.post(
                            "/api/meal-plans/generate?start_date=2026-10-12",
                            **options,
                        )
                        self.assertEqual(response.status, 201, await response.text())
                        context = generate.await_args.kwargs["context"]
                        self.assertEqual(context["favorite_cuisines"], expected)
                        self.assertEqual(context["liked_foods"], ["tomates"])
                        self.assertEqual(context["avoided_foods"], ["arachides"])
                        self.assertEqual(context["household"]["people"], 2)
                        self.assertEqual(context["planning"]["dates"], ["2026-10-12"])
                        generated = await response.json()
                        persisted = await self.client.get(
                            f"/api/meal-plans/{generated['id']}"
                        )
                        self.assertEqual(persisted.status, 200)
                        self.assertEqual(
                            (await persisted.json())["meals"][0]["title"], "Soupe"
                        )
                    self.assertEqual(
                        (await self.get_settings())["favorite_cuisines"],
                        ["Mexican", "Thai"],
                    )

    async def test_invalid_generation_preferences_do_not_call_ai(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch(
                "fridge_agent.meal_plans.generate_meal_plan",
                new_callable=AsyncMock,
            ) as generate:
                for body in (
                    {"favorite_cuisines": "Thai"},
                    {"favorite_cuisines": [3]},
                    {"unexpected": True},
                    [],
                ):
                    with self.subTest(body=body):
                        response = await self.client.post(
                            "/api/meal-plans/generate", json=body
                        )
                        self.assertEqual(response.status, 400)
                response = await self.client.post(
                    "/api/meal-plans/generate",
                    data="{",
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(response.status, 400)
                generate.assert_not_awaited()

    async def test_pages_render_cuisine_controls(self):
        for path, control in (
            ("/settings", 'id="favorite-cuisines"'),
            ("/menu", 'id="menu-cuisines"'),
        ):
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status, 200)
                self.assertIn(control, await response.text())

    async def test_ai_request_includes_cuisines_and_preference_instructions(self):
        context = {"favorite_cuisines": ["thaïlandaise", "mexicaine"]}
        response = httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"meals": []}',
                            }
                        ],
                    }
                ]
            },
        )
        with patch("fridge_agent.openai_client.httpx.AsyncClient") as client:
            post = client.return_value.__aenter__.return_value.post
            post.return_value = response
            await generate_meal_plan(
                context=context,
                api_key="test-key",
                model="test-model",
            )
            payload = post.await_args.kwargs["json"]
            self.assertEqual(
                json.loads(payload["input"][0]["content"][0]["text"]), context
            )
            self.assertIn("favorite_cuisines", payload["instructions"])
            self.assertIn("Respect avoided foods strictly.", payload["instructions"])


if __name__ == "__main__":
    unittest.main()
