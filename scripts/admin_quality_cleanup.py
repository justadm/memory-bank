#!/usr/bin/env python3
"""Admin-only quality review cleanup helpers.

Run on the MemLayer host where AUTH_API_KEYS is available in /opt/memlayer/.env.
The script never prints API keys or memory content.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:18120"
DEFAULT_ENV_PATH = "/opt/memlayer/.env"


def load_admin_key(env_path: Path) -> str:
    raw = None
    for line in env_path.read_text().splitlines():
        if line.startswith("AUTH_API_KEYS="):
            raw = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not raw:
        raise RuntimeError(f"AUTH_API_KEYS not found in {env_path}")

    for entry in raw.split(","):
        parts = entry.split(":")
        if len(parts) < 3:
            continue
        _name, key, scopes = parts[:3]
        if "admin" in scopes.split("|"):
            return key
    raise RuntimeError("No admin key found")


def request_json(base_url: str, api_key: str, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        method=method,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail[:500]}") from exc


def list_quality_review_entries(base_url: str, api_key: str, limit: int) -> list[dict[str, Any]]:
    summary = request_json(base_url, api_key, "GET", f"/admin/review-queues/summary?limit={limit}")
    review_items = summary.get("quality_review_required_items") or []
    entries: list[dict[str, Any]] = []
    for item in review_items:
        entry_id = item.get("entry_id")
        if not entry_id:
            continue
        entries.append(request_json(base_url, api_key, "GET", f"/memory/{entry_id}"))
    return entries


def is_safe_import_agent_missing_evidence(entry: dict[str, Any]) -> bool:
    metadata = entry.get("metadata") or {}
    quality = metadata.get("quality") or {}
    return (
        metadata.get("quality_review_required") is True
        and entry.get("source_agent") == "memorybank-import-agent"
        and quality.get("flags") == ["missing_evidence"]
        and not quality.get("reject")
        and not quality.get("duplicate_risk")
        and not quality.get("semantic_duplicate_risk")
    )


def cleanup_import_agent_missing_evidence(base_url: str, api_key: str, dry_run: bool, limit: int) -> dict[str, Any]:
    items = list_quality_review_entries(base_url, api_key, limit=limit)
    candidates = [entry for entry in items if is_safe_import_agent_missing_evidence(entry)]
    resolution = (
        "Automated cleanup 2026-06-14: memorybank-import-agent entry had only missing_evidence quality flag, "
        "no reject/duplicate/semantic-duplicate risk. Approved via admin resolve to close stale review queue; "
        "original quality metadata remains available."
    )
    resolved: list[str] = []
    failed: list[dict[str, str]] = []
    if not dry_run:
        for entry in candidates:
            try:
                request_json(
                    base_url,
                    api_key,
                    "POST",
                    "/admin/quality-review/resolve",
                    {
                        "entry_id": entry["id"],
                        "action": "approve",
                        "resolution": resolution,
                        "resolved_by": "codex-admin-cleanup",
                    },
                )
                resolved.append(entry["id"])
            except Exception as exc:  # pragma: no cover - operational safety output
                failed.append({"id": str(entry.get("id")), "error": str(exc)[:300]})

    return {
        "total_scanned": len(items),
        "candidate_count": len(candidates),
        "dry_run": dry_run,
        "resolved_count": len(resolved),
        "failed_count": len(failed),
        "sample_candidate_id": candidates[0]["id"] if candidates else None,
        "sample_resolved_id": resolved[0] if resolved else None,
        "failures": failed[:3],
    }


def collect_stats(base_url: str, api_key: str, limit: int) -> dict[str, Any]:
    metrics = request_json(base_url, api_key, "GET", "/metrics/overview")
    task_summary = request_json(base_url, api_key, "GET", "/task-logs/summary")
    observability = request_json(base_url, api_key, "GET", "/admin/observability/summary")
    review = request_json(base_url, api_key, "GET", f"/admin/review-queues/summary?limit={limit}")
    memory_items = request_json(base_url, api_key, "GET", "/memory").get("items") or []
    task_items = request_json(base_url, api_key, "GET", "/task-logs").get("items") or []

    memory_by_agent: collections.Counter[str] = collections.Counter()
    memory_by_type: collections.Counter[str] = collections.Counter()
    memory_by_project: collections.Counter[str] = collections.Counter()
    quality_by_agent: collections.Counter[str] = collections.Counter()
    read_receipts_by_agent: collections.Counter[str] = collections.Counter()
    for item in memory_items:
        agent = item.get("source_agent") or "(missing)"
        metadata = item.get("metadata") or {}
        memory_by_agent[agent] += 1
        memory_by_type[item.get("type") or "(missing)"] += 1
        memory_by_project[str(item.get("project_id") or "(no project)")] += 1
        if metadata.get("quality_review_required") is True:
            quality_by_agent[agent] += 1
        if metadata.get("receipt_type") == "memlayer_read" or metadata.get("read_receipt") is True:
            read_receipts_by_agent[agent] += 1

    task_by_agent: collections.Counter[str] = collections.Counter()
    task_used_memory_by_agent: collections.Counter[str] = collections.Counter()
    for item in task_items:
        agent = item.get("agent_id") or "(missing)"
        task_by_agent[agent] += 1
        if item.get("used_memory") is True:
            task_used_memory_by_agent[agent] += 1

    return {
        "metrics_overview": metrics,
        "task_logs_summary": task_summary,
        "top_agents": (observability.get("top_agents") or [])[:10],
        "top_experiments": (observability.get("top_experiments") or [])[:10],
        "recent_activity": observability.get("recent_activity"),
        "memory_usage": {
            "listed_entries_count": len(memory_items),
            "by_source_agent": memory_by_agent.most_common(20),
            "by_type": memory_by_type.most_common(20),
            "by_project": memory_by_project.most_common(20),
            "quality_review_required_by_source_agent": quality_by_agent.most_common(20),
            "read_receipts_by_source_agent": read_receipts_by_agent.most_common(20),
        },
        "task_usage": {
            "listed_tasks_count": len(task_items),
            "by_agent": task_by_agent.most_common(20),
            "used_memory_by_agent": task_used_memory_by_agent.most_common(20),
        },
        "review_queues": {
            "quality_review_required_count": review.get("quality_review_required_count"),
            "review_overdue_count": review.get("review_overdue_count"),
            "import_conflicts_count": review.get("import_conflicts_count"),
            "decision_conflicts_count": review.get("decision_conflicts_count"),
            "quality_review_required_sample": review.get("quality_review_required_items", [])[:10],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("MEMLAYER_ADMIN_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--env-path", default=os.environ.get("MEMLAYER_ENV_PATH", DEFAULT_ENV_PATH))
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    api_key = load_admin_key(Path(args.env_path))
    if args.stats:
        result = collect_stats(args.base_url, api_key, limit=args.limit)
    else:
        result = cleanup_import_agent_missing_evidence(args.base_url, api_key, dry_run=not args.apply, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
