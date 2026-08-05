"""Eval instance archive under evals/instances/."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from evals.dashboard.landing import format_local_wall_time, rebuild_landing
from evals.dashboard.stubs import render_stub_dashboard
from evals.paths import EVAL_INSTANCES_DIR, KIND_LABELS, KINDS

DashboardRenderer = Callable[[str, dict[str, Any]], str]


def _catalog_path() -> Path:
    return EVAL_INSTANCES_DIR / "catalog.json"


def _empty_catalog() -> dict[str, Any]:
    return {
        "version": 1,
        "next_n": {kind: 1 for kind in KINDS},
        "instances": [],
    }


@contextmanager
def _catalog_lock() -> Iterator[None]:
    """Serialize allocate + catalog write across overlapping CLI processes."""
    EVAL_INSTANCES_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = EVAL_INSTANCES_DIR / ".catalog.lock"
    with lock_path.open("a+b") as lock_file:
        if sys.platform == "win32":
            import msvcrt

            lock_file.seek(0)
            if lock_file.read(1) == b"":
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if sys.platform == "win32":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def load_catalog(*, strict: bool = True) -> dict[str, Any]:
    path = _catalog_path()
    if not path.exists():
        return _empty_catalog()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        if strict:
            raise ValueError(
                f"Corrupt eval catalog at {path}: {exc}. "
                "Fix or remove catalog.json before archiving."
            ) from exc
        return _empty_catalog()
    if not isinstance(data, dict):
        if strict:
            raise ValueError(f"Corrupt eval catalog at {path}: expected a JSON object.")
        return _empty_catalog()
    data.setdefault("version", 1)
    data.setdefault("next_n", {kind: 1 for kind in KINDS})
    data.setdefault("instances", [])
    if not isinstance(data["instances"], list):
        if strict:
            raise ValueError(f"Corrupt eval catalog at {path}: instances must be a list.")
        data["instances"] = []
    for kind in KINDS:
        data["next_n"].setdefault(kind, 1)
    return data


def save_catalog(catalog: dict[str, Any]) -> None:
    """Atomically replace catalog.json (temp file + os.replace)."""
    EVAL_INSTANCES_DIR.mkdir(parents=True, exist_ok=True)
    path = _catalog_path()
    fd, tmp_name = tempfile.mkstemp(
        prefix=".catalog.",
        suffix=".tmp",
        dir=str(EVAL_INSTANCES_DIR),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(json.dumps(catalog, indent=2) + "\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _git_sha_short() -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            cwd=EVAL_INSTANCES_DIR.parents[1],
        )
    except OSError:
        return None
    if out.returncode != 0:
        return None
    sha = (out.stdout or "").strip()
    return sha or None


def _format_title(kind: str, n: int, when: datetime) -> str:
    label = KIND_LABELS[kind]
    # Local wall clock for professor-facing archive titles.
    stamp = format_local_wall_time(when, joiner=" at ")
    return f"{label} #{n} · {stamp}"


def create_instance(
    *,
    kind: str,
    cli: str,
    architecture: Optional[str] = None,
    full_name: Optional[str] = None,
    dry_run: bool = True,
    stub: bool = True,
    notes: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
    dashboard_renderer: Optional[DashboardRenderer] = None,
) -> Path:
    """Allocate per-kind #n, write dashboard, update catalog + landing."""
    if kind not in KINDS:
        raise ValueError(f"Unknown kind {kind!r}. Choose one of: {', '.join(KINDS)}")

    with _catalog_lock():
        catalog = load_catalog(strict=True)
        n = int(catalog["next_n"][kind])
        when = datetime.now().astimezone()
        folder_name = f"{n:03d}_{when.strftime('%Y-%m-%d_%H%M')}"
        instance_dir = EVAL_INSTANCES_DIR / kind / folder_name
        if instance_dir.exists():
            # Same-minute collision: append seconds.
            folder_name = f"{n:03d}_{when.strftime('%Y-%m-%d_%H%M%S')}"
            instance_dir = EVAL_INSTANCES_DIR / kind / folder_name
        instance_dir.mkdir(parents=True, exist_ok=False)

        title = _format_title(kind, n, when)
        git_sha = _git_sha_short()
        summary = {
            "kind": kind,
            "n": n,
            "title": title,
            "architecture": architecture,
            "full_name": full_name,
            "cli": cli,
            "dry_run": dry_run,
            "stub": stub,
            "created_at": when.isoformat(),
            "git_sha": git_sha,
            "notes": notes,
            **(extra or {}),
        }
        (instance_dir / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
        if dashboard_renderer is not None:
            dashboard_html = dashboard_renderer(title, summary)
        else:
            dashboard_html = render_stub_dashboard(
                kind=kind,
                title=title,
                summary=summary,
            )
        (instance_dir / "dashboard.html").write_text(dashboard_html, encoding="utf-8")

        rel_dashboard = f"{kind}/{folder_name}/dashboard.html"
        entry = {
            "kind": kind,
            "n": n,
            "instance_id": folder_name,
            "title": title,
            "created_at": when.isoformat(),
            "architecture": architecture,
            "full_name": full_name,
            "cli": cli,
            "dry_run": dry_run,
            "stub": stub,
            "git_sha": git_sha,
            "dashboard_relpath": rel_dashboard,
        }
        catalog["instances"].insert(0, entry)
        catalog["next_n"][kind] = n + 1
        save_catalog(catalog)
        rebuild_landing(catalog)
        return instance_dir


def create_stub_instance(
    *,
    kind: str,
    cli: str,
    architecture: Optional[str] = None,
    full_name: Optional[str] = None,
    dry_run: bool = True,
    notes: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> Path:
    """Allocate a stub dashboard instance (benchmark / verification / placeholder)."""
    return create_instance(
        kind=kind,
        cli=cli,
        architecture=architecture,
        full_name=full_name,
        dry_run=dry_run,
        stub=True,
        notes=notes,
        extra=extra,
    )
