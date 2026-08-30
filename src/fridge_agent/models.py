from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


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