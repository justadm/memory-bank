from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from memorybank_sdk import DEFAULT_MEMORYBANK_URL, MemoryBankClient, build_directory_import_payloads, build_project_import_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan a local project and import it into Memory Bank.")
    parser.add_argument("--project-root", default=".", help="Path to the project that should be scanned.")
    parser.add_argument("--projects-directory", default=None, help="Import all detected child projects from this directory.")
    parser.add_argument("--memorybank-url", default=os.getenv("MEMORYBANK_URL", DEFAULT_MEMORYBANK_URL))
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--project-description", default=None)
    parser.add_argument("--existing-project-id", default=None)
    parser.add_argument("--names", default=None, help="Comma-separated child project names when using --projects-directory.")
    parser.add_argument("--limit", type=int, default=None, help="Max child projects to import when using --projects-directory.")
    parser.add_argument(
        "--existing-entry-mode",
        choices=["create", "skip", "update"],
        default="create",
        help="How to handle already imported entries in the same project.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the generated payload instead of sending it.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    api_key = os.getenv("MEMORYBANK_API_KEY")
    if args.projects_directory:
        names = [item.strip() for item in args.names.split(",") if item.strip()] if args.names else None
        payloads = build_directory_import_payloads(
            Path(args.projects_directory),
            names=names,
            limit=args.limit,
        )
        for payload in payloads:
            payload["existing_entry_mode"] = args.existing_entry_mode
        if args.dry_run:
            print(json.dumps(payloads, indent=2, ensure_ascii=False))
            return
        with MemoryBankClient(args.memorybank_url, api_key=api_key) as client:
            results = [client.import_project_scan(**payload) for payload in payloads]
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
        return

    payload = build_project_import_payload(
        Path(args.project_root),
        project_name=args.project_name,
        project_description=args.project_description,
    )
    if args.existing_project_id:
        payload["project_id"] = args.existing_project_id
        payload.pop("project", None)
    payload["existing_entry_mode"] = args.existing_entry_mode

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    with MemoryBankClient(args.memorybank_url, api_key=api_key) as client:
        result = client.import_project_scan(**payload)

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
