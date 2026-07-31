"""Prompt loading for UAS (lineage: prompts/stage_2_perplexity_prompt.txt).

Phase 1 keeps the March production habit of a single formatted prompt string.
A later split into lean `instructions` + company `input` is planned (§3.3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from contracts.types import CompanyInput

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "prompts"
DEFAULT_PROMPT_FILE = PROMPTS_DIR / "stage_2_perplexity_prompt.txt"
UAS_OVERRIDE_DIR = PROMPTS_DIR / "unified_adaptive_search"

# Cache keyed by resolved path so a later override file, or a one-off custom
# path, does not leave callers stuck on a stale default template.
_prompt_templates: dict[str, str] = {}


def resolve_prompt_path(prompt_path: Optional[Union[str, Path]] = None) -> Path:
    if prompt_path is not None:
        return Path(prompt_path)
    override = UAS_OVERRIDE_DIR / "research_prompt.txt"
    if override.exists():
        return override
    return DEFAULT_PROMPT_FILE


def get_prompt_template(prompt_path: Optional[Union[str, Path]] = None) -> str:
    path = resolve_prompt_path(prompt_path)
    key = str(path.resolve())
    cached = _prompt_templates.get(key)
    if cached is not None:
        return cached
    text = path.read_text(encoding="utf-8")
    _prompt_templates[key] = text
    return text


def build_company_prompt(
    company: CompanyInput,
    *,
    prompt_path: Optional[Union[str, Path]] = None,
) -> str:
    """Fill the Stage 2 prompt template with company identity fields."""
    template = get_prompt_template(prompt_path)
    return template.format(
        company_id=company.rcid,
        company_name=company.name,
        homepage_url=company.homepage_url or "N/A",
        short_description=company.short_description or "N/A",
    )


# Same structured schema spirit as production_agent_runner.RESPONSE_SCHEMA.
RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "genai_research_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "company_id": {"type": "integer"},
                "company_name": {"type": "string"},
                "genai_adoption_found": {"type": "boolean"},
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "finding_id": {"type": "integer"},
                            "AI_tool_used": {"type": "string"},
                            "use_case": {"type": "string"},
                            "business_function": {"type": "string"},
                            "evidence_description": {"type": "string"},
                            "source_url": {"type": "string"},
                            "source_type": {"type": "string"},
                        },
                        "required": [
                            "finding_id",
                            "AI_tool_used",
                            "use_case",
                            "business_function",
                            "evidence_description",
                            "source_url",
                            "source_type",
                        ],
                        "additionalProperties": False,
                    },
                },
                "no_finding_reason": {"type": ["string", "null"]},
                "no_finding_analysis": {"type": ["string", "null"]},
            },
            "required": [
                "company_id",
                "company_name",
                "genai_adoption_found",
                "findings",
                "no_finding_reason",
                "no_finding_analysis",
            ],
            "additionalProperties": False,
        },
    },
}
