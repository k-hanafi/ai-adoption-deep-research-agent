"""Compose SGS scout and dig prompts (shared preamble + channel overlay)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from contracts.types import CompanyInput
from parallel_channel_search.prompting import RESPONSE_SCHEMA
from signal_gated_search.channels import CHANNEL_IDS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "signal_gated_search"
SCOUT_SHARED_FILE = PROMPTS_DIR / "scout_shared_preamble.txt"
DIG_SHARED_FILE = PROMPTS_DIR / "dig_shared_preamble.txt"

_SCOUT_FILES = {
    "jobs": PROMPTS_DIR / "scout_jobs.txt",
    "owned": PROMPTS_DIR / "scout_owned.txt",
    "third_party": PROMPTS_DIR / "scout_third_party.txt",
}
_DIG_FILES = {
    "jobs": PROMPTS_DIR / "dig_jobs.txt",
    "owned": PROMPTS_DIR / "dig_owned.txt",
    "third_party": PROMPTS_DIR / "dig_third_party.txt",
}

_prompt_templates: dict[str, str] = {}

# Digs reuse the PCS findings schema so bake-off rows stay comparable.
DIG_RESPONSE_SCHEMA = RESPONSE_SCHEMA

SCOUT_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "sgs_scout_presence",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string"},
                "evidence_bin": {
                    "type": "string",
                    "enum": ["none", "weak", "moderate", "strong"],
                },
                "urls": {"type": "array", "items": {"type": "string"}},
                "snippets": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"},
            },
            "required": [
                "channel",
                "evidence_bin",
                "urls",
                "snippets",
                "rationale",
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


def _require_channel(channel_id: str) -> str:
    cid = (channel_id or "").strip().lower()
    if cid not in CHANNEL_IDS:
        known = ", ".join(CHANNEL_IDS)
        raise ValueError(f"Unknown SGS channel {channel_id!r}. Choose: {known}")
    return cid


def compose_role_template(
    channel_id: str,
    *,
    role: str,
    prompt_path: Optional[Union[str, Path]] = None,
    shared_preamble_path: Optional[Union[str, Path]] = None,
) -> str:
    """Expand `{shared_preamble}` into a scout or dig channel file."""
    cid = _require_channel(channel_id)
    if role == "scout":
        default_channel = _SCOUT_FILES[cid]
        default_shared = SCOUT_SHARED_FILE
    elif role == "dig":
        default_channel = _DIG_FILES[cid]
        default_shared = DIG_SHARED_FILE
    else:
        raise ValueError(f"role must be 'scout' or 'dig', got {role!r}")

    channel_path = Path(prompt_path) if prompt_path is not None else default_channel
    shared_path = (
        Path(shared_preamble_path)
        if shared_preamble_path is not None
        else default_shared
    )
    channel_tmpl = _read_template(channel_path)
    shared = _read_template(shared_path)
    if "{shared_preamble}" not in channel_tmpl:
        raise ValueError(
            f"SGS {role} template {channel_path} is missing {{shared_preamble}} placeholder"
        )
    return channel_tmpl.replace("{shared_preamble}", shared)


def build_scout_prompt(
    company: CompanyInput,
    channel_id: str,
    *,
    prompt_path: Optional[Union[str, Path]] = None,
    shared_preamble_path: Optional[Union[str, Path]] = None,
) -> str:
    template = compose_role_template(
        channel_id,
        role="scout",
        prompt_path=prompt_path,
        shared_preamble_path=shared_preamble_path,
    )
    return template.format(
        company_id=company.rcid,
        company_name=company.name,
        homepage_url=company.homepage_url or "N/A",
        short_description=company.short_description or "N/A",
    )


def build_dig_prompt(
    company: CompanyInput,
    channel_id: str,
    *,
    prompt_path: Optional[Union[str, Path]] = None,
    shared_preamble_path: Optional[Union[str, Path]] = None,
) -> str:
    template = compose_role_template(
        channel_id,
        role="dig",
        prompt_path=prompt_path,
        shared_preamble_path=shared_preamble_path,
    )
    return template.format(
        company_id=company.rcid,
        company_name=company.name,
        homepage_url=company.homepage_url or "N/A",
        short_description=company.short_description or "N/A",
    )
