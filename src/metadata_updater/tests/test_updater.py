import json

import pytest

from src.metadata_updater.app import parse_message_body


def test_parse_message_body_valid_payload():
    payload = {
        "originalKey": "cat.png",
        "processedKey": "resized_cat.png",
        "timestamp": "2026-03-20T00:00:00Z",
        "status": "SUCCESS",
        "processingDetails": {"durationMs": 10},
    }

    parsed = parse_message_body(json.dumps(payload))
    assert parsed["originalKey"] == "cat.png"


def test_parse_message_body_missing_required_field():
    payload = {
        "originalKey": "cat.png",
        "processedKey": "resized_cat.png",
        "timestamp": "2026-03-20T00:00:00Z",
        "status": "SUCCESS",
    }

    with pytest.raises(ValueError):
        parse_message_body(json.dumps(payload))
