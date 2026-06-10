from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memorybank_sdk import MemoryBankClient, build_project_import_payload
from scripts.import_project_cli import persist_project_id, resolve_memlayer_config_path
from scripts.install_memlayer_project_pack import LOCAL_API_URL, PRODUCTION_API_URL, install_for_project

ExistingEntryMode = Literal["create", "skip", "update"]
ClientFactory = Callable[..., Any]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]

EXCLUDED_PROJECT_ROOT_NAMES = {
    ".git",
    ".venv",
    ".venv313",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "vendor",
}


class OnboardError(ValueError):
    pass


@dataclass(frozen=True)
class OnboardOptions:
    apply: bool = False
    skip_pack: bool = False
    skip_import: bool = False
    skip_snapshot: bool = False
    smoke: bool = False
    memorybank_url: str = os.getenv("MEMORYBANK_URL", PRODUCTION_API_URL)
    existing_entry_mode: ExistingEntryMode = "update"
    preferred_url: str = PRODUCTION_API_URL
    local_url: str = LOCAL_API_URL
    human_url: str = PRODUCTION_API_URL
    snapshot_query: str | None = None
    smoke_query: str = "architecture"
    command_timeout_seconds: int = 120
    env_file: str | None = None


def parse_names(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    names = [item.strip() for item in raw.split(",") if item.strip()]
    return names or None


def validate_project_root(project_root: str | Path) -> Path:
    root = Path(project_root).expanduser().resolve()
    if not root.exists():
        raise OnboardError(f"Project root does not exist: {root}")
    if not root.is_dir():
        raise OnboardError(f"Project root is not a directory: {root}")
    if root.name in EXCLUDED_PROJECT_ROOT_NAMES:
        raise OnboardError(f"Refusing to onboard excluded project root: {root}")
    return root


def resolve_project_roots(
    *,
    project_root: str | Path | None = None,
    projects_root: str | Path | None = None,
    names: list[str] | None = None,
) -> list[Path]:
    if bool(project_root) == bool(projects_root):
        raise OnboardError("Pass exactly one of --project-root or --projects-root.")
    if project_root:
        return [validate_project_root(project_root)]

    root = Path(projects_root).expanduser().resolve()
    if not root.exists():
        raise OnboardError(f"Projects root does not exist: {root}")
    if not root.is_dir():
        raise OnboardError(f"Projects root is not a directory: {root}")

    wanted = set(names or [])
    project_roots: list[Path] = []
    for candidate in sorted(root.iterdir()):
        if not candidate.is_dir():
            continue
        if candidate.name.startswith(".") or candidate.name in EXCLUDED_PROJECT_ROOT_NAMES:
            continue
        if wanted and candidate.name not in wanted:
            continue
        project_roots.append(validate_project_root(candidate))
    return project_roots


def read_project_config(project_root: Path) -> tuple[Path | None, dict[str, Any], str | None]:
    config_path = resolve_memlayer_config_path(project_root)
    if config_path is None:
        return None, {}, None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return config_path, {}, f"Invalid JSON in {config_path}: {exc}"
    if not isinstance(payload, dict):
        return config_path, {}, f"Config is not a JSON object: {config_path}"
    return config_path, payload, None


def read_env_file_values(env_file: str | Path | None) -> dict[str, str]:
    if env_file is None:
        return {}
    path = Path(env_file).expanduser()
    if not path.exists() or not path.is_file():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def resolve_api_key(project_root: Path | None = None, env_file: str | Path | None = None) -> str | None:
    if os.getenv("MEMORYBANK_API_KEY") or os.getenv("MEMLAYER_WRITE_API_KEY"):
        return os.getenv("MEMORYBANK_API_KEY") or os.getenv("MEMLAYER_WRITE_API_KEY")

    for candidate in (
        env_file,
        project_root / ".memlayer" / ".env.memlayer" if project_root else None,
    ):
        values = read_env_file_values(candidate)
        api_key = values.get("MEMORYBANK_API_KEY") or values.get("MEMLAYER_WRITE_API_KEY")
        if api_key:
            return api_key
    return None


def default_command_runner(
    command: list[str],
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
        check=False,
    )


def _run_command(
    command_runner: CommandRunner,
    command: list[str],
    cwd: Path,
    timeout: int,
    *,
    api_key: str | None = None,
) -> subprocess.CompletedProcess[str]:
    if command_runner is default_command_runner:
        env = os.environ.copy()
        if api_key and not env.get("MEMORYBANK_API_KEY"):
            env["MEMORYBANK_API_KEY"] = api_key
        return command_runner(command, cwd, timeout, env=env)
    return command_runner(command, cwd, timeout)


def _build_import_payload(project_root: Path, project_id: str | None, existing_entry_mode: ExistingEntryMode) -> dict[str, Any]:
    payload = build_project_import_payload(project_root, project_name=project_root.name)
    if project_id:
        payload["project_id"] = project_id
        payload["project"] = None
    payload["existing_entry_mode"] = existing_entry_mode
    return payload


def _command_result_summary(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": "ok" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout_bytes": len(result.stdout or ""),
        "stderr_preview": (result.stderr or "").strip()[:1000],
    }
    if result.returncode != 0 and result.stdout:
        summary["stdout_preview"] = result.stdout.strip()[:1000]
    return summary


def _smoke_result_summary(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    summary = _command_result_summary(result)
    if result.returncode != 0 or not result.stdout:
        return summary
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return summary
    summary["runtime_status"] = payload.get("status")
    summary["project_id"] = payload.get("project_id")
    summary["search_results_count"] = payload.get("search_results_count")
    summary["relevant_results_count"] = payload.get("relevant_results_count")
    return summary


def _base_summary(project_root: Path, options: OnboardOptions) -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "apply" if options.apply else "dry_run",
        "project": project_root.name,
        "root": str(project_root),
        "project_id": None,
        "warnings": [],
        "pack": {"status": "not_started"},
        "import": {"status": "not_started"},
        "snapshot": {"status": "not_started"},
        "smoke": {"status": "not_requested" if not options.smoke else "not_started"},
    }


def onboard_project(
    project_root: str | Path,
    options: OnboardOptions,
    *,
    client_factory: ClientFactory = MemoryBankClient,
    command_runner: CommandRunner = default_command_runner,
) -> dict[str, Any]:
    root = validate_project_root(project_root)
    summary = _base_summary(root, options)
    api_key = resolve_api_key(root, options.env_file)

    if options.apply and not options.skip_import and not api_key:
        error = "Live import requires MEMORYBANK_API_KEY or MEMLAYER_WRITE_API_KEY."
        summary["status"] = "failed"
        summary["import"] = {"status": "failed", "error": error}
        summary["snapshot"] = {"status": "skipped", "reason": "import_failed"}
        if options.smoke:
            summary["smoke"] = {"status": "skipped", "reason": "import_failed"}
        return summary

    config_path, config, warning = read_project_config(root)
    if warning:
        summary["warnings"].append(warning)
    existing_project_id = str(config.get("project_id")) if config.get("project_id") else None
    summary["project_id"] = existing_project_id

    if options.skip_pack:
        summary["pack"] = {"status": "skipped"}
    else:
        pack_result = install_for_project(
            root,
            preferred_url=options.preferred_url,
            local_url=options.local_url,
            human_url=options.human_url,
            dry_run=not options.apply,
        )
        summary["pack"] = {
            "status": "applied" if options.apply else "planned",
            "agents": pack_result.get("agents"),
            "files": pack_result.get("files", []),
        }
        config_path, config, warning = read_project_config(root)
        if warning:
            summary["warnings"].append(warning)
        existing_project_id = str(config.get("project_id")) if config.get("project_id") else existing_project_id
        summary["project_id"] = existing_project_id

    if options.skip_import:
        summary["import"] = {"status": "skipped"}
    else:
        payload = _build_import_payload(root, existing_project_id, options.existing_entry_mode)
        if not options.apply:
            summary["import"] = {
                "status": "planned",
                "existing_entry_mode": options.existing_entry_mode,
                "uses_existing_project_id": bool(existing_project_id),
                "entries_count": len(payload.get("entries", [])),
                "links_count": len(payload.get("links", [])),
            }
        else:
            with client_factory(options.memorybank_url, api_key=api_key) as client:
                result = client.import_project_scan(**payload)
            project_id = result.get("project", {}).get("id")
            if project_id:
                persist_project_id(root, str(project_id))
                summary["project_id"] = str(project_id)
            elif not existing_project_id:
                summary["warnings"].append("Import result did not include project.id; project_id was not persisted.")
            summary["import"] = {
                "status": "applied",
                "existing_entry_mode": options.existing_entry_mode,
                "used_existing_project_id": bool(existing_project_id),
                "project_id": summary["project_id"],
                "entries_created": result.get("entries_created"),
                "entries_updated": result.get("entries_updated", 0),
                "conflicts_detected": result.get("conflicts_detected", 0),
                "quality_review_required_count": result.get("quality_review_required_count", 0),
            }
            config_path, config, warning = read_project_config(root)
            if warning:
                summary["warnings"].append(warning)
            if config_path is None:
                summary["warnings"].append("No memlayer.config.json found; project_id could not be persisted locally.")

    if options.skip_snapshot:
        summary["snapshot"] = {"status": "skipped"}
    elif not options.apply:
        command = [str(root / ".memlayer" / "memlayer_snapshot_pull.sh")]
        if options.snapshot_query:
            command.append(options.snapshot_query)
        summary["snapshot"] = {"status": "planned", "command": command}
    else:
        snapshot_script = root / ".memlayer" / "memlayer_snapshot_pull.sh"
        if not snapshot_script.exists():
            summary["snapshot"] = {"status": "failed", "error": f"Missing snapshot helper: {snapshot_script}"}
            summary["status"] = "failed"
        else:
            command = [str(snapshot_script)]
            if options.snapshot_query:
                command.append(options.snapshot_query)
            result = _run_command(command_runner, command, root, options.command_timeout_seconds, api_key=api_key)
            summary["snapshot"] = _command_result_summary(result)
            summary["snapshot"]["command"] = command
            if result.returncode != 0:
                summary["status"] = "failed"

    if options.smoke:
        smoke_command = [
            sys.executable,
            str(Path(__file__).resolve().parent / "runtime_smoke_check.py"),
            "--memorybank-url",
            options.memorybank_url,
            "--project-root",
            str(root),
            "--query",
            options.smoke_query,
        ]
        if summary.get("project_id"):
            smoke_command.extend(["--existing-project-id", str(summary["project_id"])])
        if not options.apply:
            summary["smoke"] = {"status": "planned", "command": smoke_command}
        else:
            result = _run_command(command_runner, smoke_command, root, options.command_timeout_seconds, api_key=api_key)
            summary["smoke"] = _smoke_result_summary(result)
            summary["smoke"]["command"] = smoke_command
            if result.returncode != 0:
                summary["status"] = "failed"

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Idempotently onboard local projects into MemLayer.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--project-root", default=None, help="Single project root to onboard.")
    target.add_argument("--projects-root", default=None, help="Directory containing top-level project roots.")
    parser.add_argument("--names", default=None, help="Comma-separated child project names when using --projects-root.")
    parser.add_argument("--apply", action="store_true", help="Write pack files and call live MemLayer APIs.")
    parser.add_argument("--skip-pack", action="store_true", help="Do not install or update the .memlayer root-pack.")
    parser.add_argument("--skip-import", action="store_true", help="Do not import or reimport the project scan.")
    parser.add_argument("--skip-snapshot", action="store_true", help="Do not refresh the local MemLayer snapshot.")
    parser.add_argument("--smoke", action="store_true", help="Run runtime smoke check after onboarding.")
    parser.add_argument("--memorybank-url", default=os.getenv("MEMORYBANK_URL", PRODUCTION_API_URL))
    parser.add_argument("--preferred-url", default=PRODUCTION_API_URL)
    parser.add_argument("--local-url", default=LOCAL_API_URL)
    parser.add_argument("--human-url", default=PRODUCTION_API_URL)
    parser.add_argument("--snapshot-query", default=None)
    parser.add_argument("--smoke-query", default="architecture")
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional env file with MEMORYBANK_API_KEY or MEMLAYER_WRITE_API_KEY. Defaults to project .memlayer/.env.memlayer when present.",
    )
    parser.add_argument(
        "--existing-entry-mode",
        choices=["create", "skip", "update"],
        default="update",
        help="How repeated imports should handle entries already present in the same project.",
    )
    parser.add_argument("--command-timeout-seconds", type=int, default=120)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    options = OnboardOptions(
        apply=args.apply,
        skip_pack=args.skip_pack,
        skip_import=args.skip_import,
        skip_snapshot=args.skip_snapshot,
        smoke=args.smoke,
        memorybank_url=args.memorybank_url,
        existing_entry_mode=args.existing_entry_mode,
        preferred_url=args.preferred_url,
        local_url=args.local_url,
        human_url=args.human_url,
        snapshot_query=args.snapshot_query,
        smoke_query=args.smoke_query,
        command_timeout_seconds=args.command_timeout_seconds,
        env_file=args.env_file,
    )

    try:
        roots = resolve_project_roots(
            project_root=args.project_root,
            projects_root=args.projects_root,
            names=parse_names(args.names),
        )
        projects = [onboard_project(root, options) for root in roots]
        status = "ok" if all(project.get("status") == "ok" for project in projects) else "failed"
        summary = {
            "status": status,
            "mode": "apply" if options.apply else "dry_run",
            "projects_count": len(projects),
            "projects": projects,
        }
    except OnboardError as exc:
        summary = {"status": "failed", "error": str(exc)}

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    if summary["status"] != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
