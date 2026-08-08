"""Compose frozen PCS channel prompts (shared preamble + channel contract)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from contracts.types import CompanyInput
from parallel_channel_search.channels import CHANNEL_IDS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "parallel_channel_search"
SHARED_PREAMBLE_FILE = PROMPTS_DIR / "shared_preamble.txt"

_CHANNEL_FILES = {
    "jobs": PROMPTS_DIR / "channel_jobs.txt",
    "owned": PROMPTS_DIR / "channel_owned.txt",
    "third_party": PROMPTS_DIR / "channel_third_party.txt",
}

# Cache keyed by resolved path so callers are not stuck on a stale template.
_prompt_templates: dict[str, str] = {}

# Same structured schema spirit as UAS / production_agent_runner.RESPONSE_SCHEMA.
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


def _read_template(path: Path) -> str:
    key = str(path.resolve())
    cached = _prompt_templates.get(key)
    if cached is not None:
        return cached
    text = path.read_text(encoding="utf-8")
    _prompt_templates[key] = text
    return text


def resolve_channel_prompt_path(
    channel_id: str,
    *,
    prompt_path: Optional[Union[str, Path]] = None,
) -> Path:
    if prompt_path is not None:
        return Path(prompt_path)
    cid = (channel_id or "").strip().lower()
    if cid not in _CHANNEL_FILES:
        known = ", ".join(CHANNEL_IDS)
        raise ValueError(f"Unknown PCS channel {channel_id!r}. Choose: {known}")
    return _CHANNEL_FILES[cid]


def compose_channel_template(
    channel_id: str,
    *,
    prompt_path: Optional[Union[str, Path]] = None,
    shared_preamble_path: Optional[Union[str, Path]] = None,
) -> str:
    """Expand `{shared_preamble}` into the channel file (company fields still open)."""
    channel_path = resolve_channel_prompt_path(channel_id, prompt_path=prompt_path)
    shared_path = (
        Path(shared_preamble_path)
        if shared_preamble_path is not None
        else SHARED_PREAMBLE_FILE
    )
    channel_tmpl = _read_template(channel_path)
    shared = _read_template(shared_path)
    if "{shared_preamble}" not in channel_tmpl:
        raise ValueError(
            f"PCS channel template {channel_path} is missing {{shared_preamble}} placeholder"
        )
    return channel_tmpl.replace("{shared_preamble}", shared)


def build_channel_prompt(
    company: CompanyInput,
    channel_id: str,
    *,
    prompt_path: Optional[Union[str, Path]] = None,
    shared_preamble_path: Optional[Union[str, Path]] = None,
) -> str:
    """Compose one channel agent prompt for a company."""
    template = compose_channel_template(
        channel_id,
        prompt_path=prompt_path,
        shared_preamble_path=shared_preamble_path,
    )
    return template.format(
        company_id=company.rcid,
        company_name=company.name,
        homepage_url=company.homepage_url or "N/A",
        short_description=company.short_description or "N/A",
    )
