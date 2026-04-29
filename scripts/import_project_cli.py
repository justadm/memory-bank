from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from memorybank_sdk import MemoryBankClient, build_project_import_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan a local project and import it into Memory Bank.")
    parser.add_argument("--project-root", default=".", help="Path to the project that should be scanned.")
    parser.add_argument("--memorybank-url", default=os.getenv("MEMORYBANK_URL", "http://127.0.0.1:18100"))
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--project-description", default=None)
    parser.add_argument("--existing-project-id", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Print the generated payload instead of sending it.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = build_project_import_payload(
        Path(args.project_root),
        project_name=args.project_name,
        project_description=args.project_description,
    )
    if args.existing_project_id:
        payload["project_id"] = args.existing_project_id
        payload.pop("project", None)

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    with MemoryBankClient(args.memorybank_url) as client:
        result = client.import_project_scan(**payload)

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
