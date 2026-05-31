"""Tests for LLM response parsing and prompt loading."""

import json
import pytest

from seniority_detector.llm_analyzer import _parse_response, SYSTEM_PROMPT


def test_parse_clean_json() -> None:
    payload = {"nivel": "senior", "puntaje": 85, "señales_junior": [], "señales_senior": ["type hints"]}
    result = _parse_response(json.dumps(payload))
    assert result["nivel"] == "senior"
    assert result["puntaje"] == 85


def test_parse_json_wrapped_in_markdown() -> None:
    raw = '```json\n{"nivel": "junior", "puntaje": 30}\n```'
    result = _parse_response(raw)
    assert result["nivel"] == "junior"


def test_parse_json_with_surrounding_text() -> None:
    raw = 'Aquí está el análisis:\n{"nivel": "junior+", "puntaje": 55}\nEso es todo.'
    result = _parse_response(raw)
    assert result["nivel"] == "junior+"


def test_parse_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="JSON"):
        _parse_response("esto no es json")


def test_system_prompt_loaded() -> None:
    assert len(SYSTEM_PROMPT) > 100
    assert "JSON" in SYSTEM_PROMPT
    assert "senior" in SYSTEM_PROMPT
