"""Gold manifest coverage and scoreboard helpers."""

from __future__ import annotations

from citation_verification.gold import REQUIRED_FAMILIES, load_manifest, score_row


def test_manifest_covers_required_families() -> None:
    rows = load_manifest()
    families = {str(row.get("family") or "") for row in rows}
    missing = set(REQUIRED_FAMILIES) - families
    assert not missing, f"gold manifest missing families: {sorted(missing)}"
    ids = [row["case_id"] for row in rows]
    assert len(ids) == len(set(ids))
    assert "support_wiki_copilot" in ids
    assert "strict_name_not_on_page" in ids


def test_scoreboard_fp_fn_null() -> None:
    assert score_row(0, 1, unverifiable=False)["kind"] == "fp"
    assert score_row(1, 0, unverifiable=False)["kind"] == "fn"
    assert score_row(1, None, unverifiable=True)["kind"] == "false_na"
    assert score_row(None, None, unverifiable=True)["kind"] == "true_null"
    assert score_row("hero_or_null", 0, unverifiable=False)["ok"] is False
    assert score_row("hero_or_null", None, unverifiable=True)["ok"] is True
    assert score_row("name_rule", None, unverifiable=True)["ok"] is True
    assert score_row("name_rule", 1, unverifiable=False)["ok"] is False
