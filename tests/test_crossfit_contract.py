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

def test_max_load_attempts_preserve_failed_lifts_and_best_success():
    result = WodResultCreate.model_validate(
        {
            "scaling": "rx",
            "score": {
                "type": "load",
                "unit": "kg",
                "load": 85,
                "attempts": [
                    {"load": 80, "successful": True},
                    {"load": 90, "successful": False},
                    {"load": 85, "successful": True},
                ],
            },
        }
    )
    assert result.score_dict()["load"] == 85
    assert result.score_dict()["attempts"][1]["successful"] is False


@pytest.mark.parametrize(
    "score",
    [
        {
            "type": "load",
            "unit": "kg",
            "load": 90,
            "attempts": [
                {"load": 85, "successful": True},
                {"load": 90, "successful": False},
            ],
        },
        {
            "type": "load",
            "unit": "kg",
            "load": 80,
            "attempts": [{"load": 80, "successful": False}],
        },
        {
            "type": "load",
            "unit": "kg",
            "load": 80,
            "attempts": [{"load": -80, "successful": True}],
        },
    ],
)
def test_invalid_max_load_attempts(score):
    with pytest.raises(ValidationError):
        WodResultCreate.model_validate({"scaling": "rx", "score": score})

def test_emom_minute_targets_contract():
    definition = WodDefinition.model_validate(
        {
            "format": "emom",
            "score_type": "intervals",
            "duration_seconds": 180,
            "score_config": {
                "minute_targets": [
                    "10 Wall Balls",
                    "8 Box Jumps",
                    "6 Burpees",
                ]
            },
        }
    )
    assert len(definition.score_config["minute_targets"]) == 3


@pytest.mark.parametrize(
    "payload",
    [
        {
            "format": "emom",
            "score_type": "intervals",
            "duration_seconds": 180,
            "score_config": {"minute_targets": ["10 Wall Balls"]},
        },
        {
            "format": "emom",
            "score_type": "reps",
            "duration_seconds": 180,
            "score_config": {"minute_targets": ["A", "B", "C"]},
        },
        {
            "format": "emom",
            "score_type": "intervals",
            "duration_seconds": 170,
            "score_config": {"minute_targets": ["A", "B", "C"]},
        },
        {
            "format": "emom",
            "score_type": "intervals",
            "duration_seconds": 120,
            "score_config": {"minute_targets": ["A", ""]},
        },
    ],
)
def test_invalid_emom_minute_target_contract(payload):
    with pytest.raises(ValidationError):
        WodDefinition.model_validate(payload)
