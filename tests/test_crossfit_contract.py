import pytest
from pydantic import ValidationError

from app.schemas.crossfit import WodDefinition, WodResultCreate


@pytest.mark.parametrize(
    "payload",
    [
        {"format": "for_time", "score_type": "time", "time_cap_seconds": 720},
        {"format": "amrap", "score_type": "rounds_reps", "duration_seconds": 720},
        {"format": "emom", "score_type": "reps", "duration_seconds": 600},
        {"format": "max_load", "score_type": "load"},
        {"format": "max_reps", "score_type": "reps"},
        {"format": "calories", "score_type": "calories"},
        {"format": "distance", "score_type": "distance"},
        {"format": "rounds_for_time", "score_type": "time", "rounds": 5},
        {"format": "custom", "score_type": "none"},
    ],
)
def test_valid_wod_definitions(payload):
    assert WodDefinition.model_validate(payload).score_type == payload["score_type"]


@pytest.mark.parametrize(
    "payload",
    [
        {"format": "amrap", "score_type": "time", "duration_seconds": 720},
        {"format": "amrap", "score_type": "rounds_reps"},
        {"format": "emom", "score_type": "reps"},
        {"format": "max_load", "score_type": "rounds_reps"},
        {"format": "rounds_for_time", "score_type": "time"},
    ],
)
def test_invalid_wod_definitions(payload):
    with pytest.raises(ValidationError):
        WodDefinition.model_validate(payload)


@pytest.mark.parametrize(
    "score",
    [
        {"type": "time", "seconds": 342},
        {"type": "rounds_reps", "rounds": 7, "reps": 14},
        {"type": "load", "load": 92.5, "unit": "kg"},
        {"type": "reps", "reps": 42},
        {"type": "calories", "calories": 86},
        {"type": "distance", "distance": 5000, "unit": "m"},
        {"type": "intervals", "values": [12, 11, 10]},
        {"type": "none"},
    ],
)
def test_score_payload_shapes(score):
    result = WodResultCreate.model_validate(
        {"scaling": "rx", "score": score, "rpe": 8}
    )
    assert result.score_dict()["type"] == score["type"]


@pytest.mark.parametrize(
    "payload",
    [
        {"scaling": "invalid", "score": {"type": "time", "seconds": 342}},
        {"scaling": "rx", "score": {"type": "time", "seconds": 0}},
        {"scaling": "rx", "score": {"type": "load", "load": -1, "unit": "kg"}},
        {"scaling": "rx", "score": {"type": "distance", "distance": 500, "unit": "yards"}},
        {"scaling": "rx", "score": {"type": "intervals", "values": []}},
        {"scaling": "rx", "score": {"type": "reps", "reps": 10}, "rpe": 11},
    ],
)
def test_invalid_score_payloads(payload):
    with pytest.raises(ValidationError):
        WodResultCreate.model_validate(payload)
