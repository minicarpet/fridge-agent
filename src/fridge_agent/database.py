import sqlite3
from pathlib import Path

def initialize_database(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)

    database_path = data_dir / "fridge-agent.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fridge_scans (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                model TEXT,
                response_id TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                error TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fridge_scan_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                FOREIGN KEY(scan_id) REFERENCES fridge_scans(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fridge_scan_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity REAL,
                unit TEXT NOT NULL,
                confidence REAL NOT NULL,
                notes TEXT,
                FOREIGN KEY(scan_id) REFERENCES fridge_scans(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fridge_scan_confirmed_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity REAL,
                unit TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY(scan_id) REFERENCES fridge_scans(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity REAL,
                unit TEXT NOT NULL,
                notes TEXT,
                source_scan_id TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_scan_id) REFERENCES fridge_scans(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS household_settings (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                people INTEGER NOT NULL,
                planning_days INTEGER NOT NULL,
                plan_lunch INTEGER NOT NULL,
                plan_dinner INTEGER NOT NULL,
                weekday_max_cooking_minutes INTEGER NOT NULL,
                weekend_max_cooking_minutes INTEGER NOT NULL,
                use_leftovers INTEGER NOT NULL,
                notes TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS food_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                preference_type TEXT NOT NULL
                    CHECK(preference_type IN ('like', 'avoid')),
                name TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO household_settings(
                id,
                people,
                planning_days,
                plan_lunch,
                plan_dinner,
                weekday_max_cooking_minutes,
                weekend_max_cooking_minutes,
                use_leftovers,
                notes
            )
            VALUES (
                1,
                2,
                7,
                0,
                1,
                30,
                60,
                1,
                ''
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS meal_plans (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                start_date TEXT NOT NULL,
                planning_days INTEGER NOT NULL,
                status TEXT NOT NULL,
                model TEXT,
                response_id TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                error TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS meal_plan_meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meal_plan_id TEXT NOT NULL,
                meal_date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                title TEXT NOT NULL,
                servings INTEGER NOT NULL,
                preparation_minutes INTEGER NOT NULL,
                cooking_minutes INTEGER NOT NULL,
                notes TEXT NOT NULL,
                FOREIGN KEY(meal_plan_id) REFERENCES meal_plans(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS meal_plan_ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meal_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                FOREIGN KEY(meal_id) REFERENCES meal_plan_meals(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS meal_plan_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meal_id INTEGER NOT NULL,
                step_index INTEGER NOT NULL,
                instruction TEXT NOT NULL,
                FOREIGN KEY(meal_id) REFERENCES meal_plan_meals(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pantry_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                quantity REAL,
                unit TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recipes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                servings INTEGER NOT NULL,
                preparation_minutes INTEGER NOT NULL,
                cooking_minutes INTEGER NOT NULL,
                notes TEXT NOT NULL,
                source TEXT NOT NULL
                    CHECK(source IN ('meal_plan', 'manual')),
                source_meal_id INTEGER UNIQUE,
                is_favorite INTEGER NOT NULL DEFAULT 0,
                cooked_count INTEGER NOT NULL DEFAULT 0,
                last_cooked_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_meal_id)
                    REFERENCES meal_plan_meals(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recipe_ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id TEXT NOT NULL,
                name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                FOREIGN KEY(recipe_id)
                    REFERENCES recipes(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recipe_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                instruction TEXT NOT NULL,
                FOREIGN KEY(recipe_id)
                    REFERENCES recipes(id)
            )
            """
        )

        connection.commit()

    return database_path