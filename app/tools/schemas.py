
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal



class StrictArgs(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class ConceptArgs(StrictArgs):
    concept: str = Field(
        min_length=2,
        max_length=80,
    )


class HoursArgs(StrictArgs):
    hours_per_day: float = Field(
        gt=0,
        le=12,
    )

    days: int = Field(
        ge=1,
        le=31,
    )


class TaskArgs(StrictArgs):
    title: str = Field(
        min_length=3,
        max_length=120,
    )

    estimated_hours: float = Field(
        gt=0,
        le=40,
    )


class Effort(StrictArgs):

    title: str = Field(
        min_length=3,
        max_length=120,
    )

    topics_count: int = Field(
        gt=0,
        le=50,
    )

    difficulty: Literal[
        "facil",
        "media",
        "dificil",
    ]

    weekly_study_hours: float = Field(
        gt=0,
        le=168,
    )