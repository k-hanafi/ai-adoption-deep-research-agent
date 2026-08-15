"""Strict OpenAI JSON schema for the Stage 3 citation judge (D1 model fields).

`log_probs_conf` is intentionally absent: the package derives it from token
logprobs in confidence.py.
"""

from __future__ import annotations

from typing import Any

JUDGE_SCHEMA_NAME = "CitationVerificationResult"

# Model-emitted fields only (order matches product core, minus package conf).
JUDGE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verification": {
            "type": "integer",
            "enum": [0, 1],
            "description": (
                "1 = page supports the claim (verified); "
                "0 = page does not support the claim (hallucination)."
            ),
        },
        "confidence_1_5": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5,
            "description": "Verbalized confidence on a 1-5 scale.",
        },
        "verification_reasoning": {
            "type": "string",
            "description": "Short explanation of why verification is 0 or 1.",
        },
        "verification_critique": {
            "type": "string",
            "description": "Short self-check of the verdict and evidence limits.",
        },
    },
    "required": [
        "verification",
        "confidence_1_5",
        "verification_reasoning",
        "verification_critique",
    ],
}


def judge_text_format() -> dict[str, Any]:
    """Responses API `text.format` block (strict json_schema)."""
    return {
        "format": {
            "type": "json_schema",
            "name": JUDGE_SCHEMA_NAME,
            "strict": True,
            "schema": JUDGE_JSON_SCHEMA,
        }
    }
