from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


FoodCategory = Literal[
    "vegetable",
    "fruit",
    "meat",
    "fish",
    "dairy",
    "egg",
    "drink",
    "condiment",
    "prepared_food",
    "other",
]

FoodUnit = Literal[
    "piece",
    "g",
    "kg",
    "ml",
    "l",
    "pack",
    "bottle",
    "jar",
    "can",
    "unknown",
]


class DetectedFood(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: FoodCategory
    quantity: float | None
    unit: FoodUnit
    confidence: float
    notes: str | None

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

        return value


class FridgeAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DetectedFood]
    warnings: list[str]

class ConfirmedFood(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: FoodCategory
    quantity: float | None
    unit: FoodUnit
    notes: str | None = None


class ConfirmScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ConfirmedFood]

class HouseholdSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    people: int = Field(ge=1, le=20)
    planning_days: int = Field(ge=1, le=14)

    plan_lunch: bool
    plan_dinner: bool

    weekday_max_cooking_minutes: int = Field(
        ge=5,
        le=240,
    )

    weekend_max_cooking_minutes: int = Field(
        ge=5,
        le=360,
    )

    use_leftovers: bool

    liked_foods: list[str]
    avoided_foods: list[str]

    notes: str = ""