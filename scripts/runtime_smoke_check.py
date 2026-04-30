from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from memorybank_sdk import DEFAULT_MEMORYBANK_URL, MemoryBankClient, build_project_import_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MemLayer import -> search -> relevant smoke checks.")
    parser.add_argument("--memorybank-url", default=os.getenv("MEMORYBANK_URL", DEFAULT_MEMORYBANK_URL))
    parser.add_argument("--project-root", default=None, help="Optional project root to reimport before read checks.")
    parser.add_argument("--existing-project-id", default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--project-description", default=None)
    parser.add_argument("--query", default="architecture")
    parser.add_argument("--agent-id", default="runtime-smoke-agent")
    parser.add_argument("--limit", type=int, default=5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    api_key = os.getenv("MEMORYBANK_API_KEY")
    summary: dict[str, object] = {
        "base_url": args.memorybank_url,
        "project_root": args.project_root,
        "project_id": args.existing_project_id,
        "query": args.query,
    }

    try:
        with MemoryBankClient(args.memorybank_url, api_key=api_key) as client:
            summary["health"] = client.health()
            try:
                summary["auth"] = client.auth_status()
            except Exception as exc:
                summary["auth"] = {"status": "unavailable", "detail": str(exc)}

            if args.project_root:
                payload = build_project_import_payload(
                    Path(args.project_root),
                    project_name=args.project_name,
                    project_description=args.project_description,
                )
                if args.existing_project_id:
                    payload["project_id"] = args.existing_project_id
                    payload.pop("project", None)
                payload["existing_entry_mode"] = "update"
                import_result = client.import_project_scan(**payload)
                summary["import"] = {
                    "project_id": import_result["project"]["id"],
                    "entries_created": import_result["entries_created"],
                    "entries_updated": import_result.get("entries_updated", 0),
                    "conflicts_detected": import_result.get("conflicts_detected", 0),
                }
                summary["project_id"] = import_result["project"]["id"]

            summary["runtime_self_check"] = client.runtime_self_check(
                project_id=summary["project_id"],
                search_query=args.query,
                limit=args.limit,
            )
            summary["search"] = client.search_memory(
                args.query,
                project_id=summary["project_id"],
                limit=args.limit,
                mode="hybrid",
            )
            summary["relevant"] = client.get_relevant_memory(
                query=args.query,
                agent_id=args.agent_id,
                project_id=summary["project_id"],
                types=["decision", "constraint", "risk", "artifact", "task", "note"],
                limit=args.limit,
                search_mode="hybrid",
            )
    except Exception as exc:  # pragma: no cover - CLI failure path
        summary["status"] = "failed"
        summary["error"] = str(exc)
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
        sys.exit(1)

    summary["status"] = "ok"
    summary["search_results_count"] = len(summary["search"].get("items", []))
    summary["relevant_results_count"] = len(summary["relevant"].get("context", []))
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
