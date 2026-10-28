from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


BlockType = Literal["warmup", "strength", "skill", "metcon", "accessory"]
WodFormat = Literal[
    "for_time",
    "amrap",
    "emom",
    "rounds_for_time",
    "chipper",
    "intervals",
    "max_load",
    "max_reps",
    "calories",
    "distance",
    "tabata",
    "custom",
]
ScoreType = Literal[
    "time",
    "rounds_reps",
    "load",
    "reps",
    "calories",
    "distance",
    "intervals",
    "none",
]
ScalingLevel = Literal["rx", "scaled", "custom", "none"]


class TimeScore(BaseModel):
    type: Literal["time"]
    seconds: int = Field(gt=0)


class RoundsRepsScore(BaseModel):
    type: Literal["rounds_reps"]
    rounds: int = Field(ge=0)
    reps: int = Field(ge=0)


class LoadAttempt(BaseModel):
    load: float = Field(gt=0, allow_inf_nan=False)
    successful: bool


class LoadScore(BaseModel):
    type: Literal["load"]
    load: float = Field(gt=0, allow_inf_nan=False)
    unit: Literal["kg", "lb"]
    attempts: list[LoadAttempt] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_best_successful_attempt(self):
        if not self.attempts:
            return self
        successful = [attempt.load for attempt in self.attempts if attempt.successful]
        if not successful:
            raise ValueError("Load attempts require at least one successful lift.")
        if abs(self.load - max(successful)) > 0.000001:
            raise ValueError("Best load must match the highest successful attempt.")
        return self


class RepsScore(BaseModel):
    type: Literal["reps"]
    reps: int = Field(ge=0)


class CaloriesScore(BaseModel):
    type: Literal["calories"]
    calories: int = Field(ge=0)


class DistanceScore(BaseModel):
    type: Literal["distance"]
    distance: float = Field(gt=0, allow_inf_nan=False)
    unit: Literal["m", "km", "mi"]


class IntervalsScore(BaseModel):
    type: Literal["intervals"]
    values: list[float] = Field(min_length=1, max_length=100)


class NoScore(BaseModel):
    type: Literal["none"]


ScorePayload = Annotated[
    TimeScore
    | RoundsRepsScore
    | LoadScore
    | RepsScore
    | CaloriesScore
    | DistanceScore
    | IntervalsScore
    | NoScore,
    Field(discriminator="type"),
]


_ALLOWED_SCORES: dict[str, set[str]] = {
    "for_time": {"time"},
    "amrap": {"rounds_reps"},
    "emom": {"reps", "load", "intervals", "none"},
    "rounds_for_time": {"time"},
    "chipper": {"time"},
    "intervals": {"intervals", "reps", "calories", "distance"},
    "max_load": {"load"},
    "max_reps": {"reps"},
    "calories": {"calories"},
    "distance": {"distance", "time"},
    "tabata": {"reps", "intervals"},
    "custom": {
        "time",
        "rounds_reps",
        "load",
        "reps",
        "calories",
        "distance",
        "intervals",
        "none",
    },
}


class WodDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: WodFormat
    score_type: ScoreType
    duration_seconds: int | None = Field(default=None, gt=0)
    time_cap_seconds: int | None = Field(default=None, gt=0)
    rounds: int | None = Field(default=None, gt=0)
    scaling_options: list[ScalingLevel] = Field(default_factory=list, max_length=4)
    score_config: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_format_contract(self):
        if self.score_type not in _ALLOWED_SCORES[self.format]:
            raise ValueError(
                f"score_type={self.score_type!r} is not valid for format={self.format!r}."
            )
        if self.format == "amrap" and self.duration_seconds is None:
            raise ValueError("AMRAP requires duration_seconds.")
        if self.format == "emom":
            if self.duration_seconds is None:
                raise ValueError("EMOM requires duration_seconds.")
            targets = self.score_config.get("minute_targets")
            if targets is not None:
                if self.score_type != "intervals":
                    raise ValueError("EMOM minute targets require interval scores.")
                if self.duration_seconds % 60 != 0:
                    raise ValueError("EMOM minute targets require whole-minute duration.")
                if (
                    not isinstance(targets, list)
                    or len(targets) != self.duration_seconds // 60
                    or any(
                        not isinstance(target, str)
                        or not target.strip()
                        or len(target) > 160
                        for target in targets
                    )
                ):
                    raise ValueError(
                        "EMOM minute_targets must provide one nonempty label per minute."
                    )
        if self.format == "rounds_for_time" and self.rounds is None:
            raise ValueError("Rounds for Time requires rounds.")
        return self


class WodResultCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scaling: ScalingLevel
    score: ScorePayload
    dnf: bool = False
    rpe: float | None = Field(default=None, ge=1, le=10, allow_inf_nan=False)
    athlete_notes: str | None = Field(default=None, max_length=4000)

    def score_dict(self) -> dict:
        return self.score.model_dump()
