from __future__ import annotations

import argparse
import json
from pathlib import Path

MANAGED_START = "<!-- MEMLAYER_ROOT_PACK:START -->"
MANAGED_END = "<!-- MEMLAYER_ROOT_PACK:END -->"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install MemLayer root-pack files into project roots.")
    parser.add_argument(
        "--projects-root",
        default="/Users/just/projects",
        help="Directory containing top-level projects that should receive the pack.",
    )
    parser.add_argument(
        "--preferred-url",
        default="http://127.0.0.1:18100",
        help="Primary MemLayer API URL that local sandboxed agents should prefer.",
    )
    parser.add_argument(
        "--local-url",
        default="https://memlayer.loc/api",
        help="Fallback MemLayer API URL when localhost is unavailable.",
    )
    parser.add_argument(
        "--human-url",
        default="https://memlayer.loc/api",
        help="Human-friendly MemLayer API URL for browsers and non-sandboxed tools.",
    )
    parser.add_argument(
        "--names",
        default=None,
        help="Optional comma-separated list of top-level project directory names.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without writing files.")
    return parser.parse_args()


def load_template(name: str) -> str:
    templates_dir = Path(__file__).resolve().parent.parent / "templates" / "project_root_pack"
    return (templates_dir / name).read_text(encoding="utf-8")


def render_template(name: str, **kwargs: str) -> str:
    raw = load_template(name)
    return raw.format(**kwargs)


def upsert_managed_section(existing_text: str, managed_section: str) -> str:
    block = f"{MANAGED_START}\n{managed_section.rstrip()}\n{MANAGED_END}"
    if MANAGED_START in existing_text and MANAGED_END in existing_text:
        start = existing_text.index(MANAGED_START)
        end = existing_text.index(MANAGED_END) + len(MANAGED_END)
        return f"{existing_text[:start].rstrip()}\n\n{block}\n"

    trimmed = existing_text.rstrip()
    if not trimmed:
        return f"{block}\n"
    return f"{trimmed}\n\n{block}\n"


def build_project_config(project_root: Path, preferred_url: str, local_url: str, human_url: str) -> dict[str, object]:
    project_name = project_root.name
    return {
        "schema_version": 1,
        "project_name": project_name,
        "project_root": str(project_root),
        "preferred_url": preferred_url,
        "local_fallback_url": local_url,
        "human_preferred_url": human_url,
        "existing_entry_mode": "update",
        "read_before_write": True,
        "recommended_search_mode": "hybrid",
        "recommended_memory_types": [
            "decision",
            "constraint",
            "risk",
            "artifact",
            "task",
            "note",
            "event",
        ],
    }


def merge_project_config(existing: dict[str, object], generated: dict[str, object]) -> dict[str, object]:
    merged = dict(existing)
    merged.update(generated)
    for key in ("project_id", "tenant_id"):
        if key in existing and existing.get(key):
            merged[key] = existing[key]
    return merged


def list_projects(projects_root: Path, names: list[str] | None) -> list[Path]:
    candidates = sorted(path for path in projects_root.iterdir() if path.is_dir())
    if names is None:
        return candidates
    wanted = set(names)
    return [path for path in candidates if path.name in wanted]


def write_text(path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, object], dry_run: bool) -> None:
    if dry_run:
        return
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def merge_env_text(existing_text: str, template_text: str) -> str:
    existing_lines = existing_text.splitlines()
    existing_keys = set()
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        existing_keys.add(stripped.split("=", 1)[0].strip())

    merged_lines = list(existing_lines)
    if merged_lines and merged_lines[-1].strip():
        merged_lines.append("")

    for line in template_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in existing_keys:
            continue
        merged_lines.append(line)
        existing_keys.add(key)

    return "\n".join(merged_lines).rstrip() + "\n"


def chmod_executable(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.chmod(0o755)


def ensure_directory(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def relocate_legacy_file(project_root: Path, relative_name: str, target_path: Path, dry_run: bool) -> None:
    legacy_path = project_root / relative_name
    if legacy_path == target_path or not legacy_path.exists():
        return
    if dry_run:
        return
    if not target_path.exists():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.replace(target_path)
    elif legacy_path.is_file():
        legacy_path.unlink()


def ensure_gitignore_has_memlayer(project_root: Path, dry_run: bool) -> None:
    gitignore_path = project_root / ".gitignore"
    ignore_line = ".memlayer/"
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        if ignore_line in {line.strip() for line in content.splitlines()}:
            return
        new_content = content.rstrip() + ("\n\n" if content.rstrip() else "") + ignore_line + "\n"
        write_text(gitignore_path, new_content, dry_run=dry_run)
        return
    write_text(gitignore_path, ignore_line + "\n", dry_run=dry_run)


def install_for_project(project_root: Path, preferred_url: str, local_url: str, human_url: str, dry_run: bool) -> dict[str, object]:
    project_name = project_root.name
    managed_section = render_template("AGENTS_SECTION.md.tmpl")
    memlayer_dir = project_root / ".memlayer"
    agents_path = project_root / "AGENTS.md"
    memlayer_path = memlayer_dir / "MEMLAYER.md"
    env_path = memlayer_dir / ".env.memlayer.example"
    local_env_path = memlayer_dir / ".env.memlayer"
    config_path = memlayer_dir / "memlayer.config.json"
    helper_path = memlayer_dir / "memlayer_api.sh"
    watchdog_path = memlayer_dir / "memlayer_watchdog.sh"
    recover_path = memlayer_dir / "memlayer_recover.sh"
    launchd_install_path = memlayer_dir / "memlayer_launchd_install.sh"
    context_path = memlayer_dir / "memlayer_context.sh"
    write_path = memlayer_dir / "memlayer_write.sh"
    sync_path = memlayer_dir / "memlayer_sync.sh"
    snapshot_pull_path = memlayer_dir / "memlayer_snapshot_pull.sh"
    snapshot_json_path = memlayer_dir / "memlayer.snapshot.json"
    snapshot_md_path = memlayer_dir / "memlayer.snapshot.md"
    offline_log_path = memlayer_dir / "memlayer.offline.log.md"
    offline_queue_path = memlayer_dir / "memlayer.offline.queue.jsonl"

    ensure_directory(memlayer_dir, dry_run=dry_run)
    ensure_gitignore_has_memlayer(project_root, dry_run=dry_run)

    for relative_name, target_path in (
        ("MEMLAYER.md", memlayer_path),
        (".env.memlayer.example", env_path),
        (".env.memlayer", local_env_path),
        ("memlayer.config.json", config_path),
        ("memlayer_api.sh", helper_path),
        ("memlayer_watchdog.sh", watchdog_path),
        ("memlayer_recover.sh", recover_path),
        ("memlayer_launchd_install.sh", launchd_install_path),
        ("memlayer_context.sh", context_path),
        ("memlayer_write.sh", write_path),
        ("memlayer_sync.sh", sync_path),
        ("memlayer_snapshot_pull.sh", snapshot_pull_path),
        ("memlayer.snapshot.json", snapshot_json_path),
        ("memlayer.snapshot.md", snapshot_md_path),
        ("memlayer.offline.log.md", offline_log_path),
        ("memlayer.offline.queue.jsonl", offline_queue_path),
    ):
        relocate_legacy_file(project_root, relative_name, target_path, dry_run=dry_run)

    if agents_path.exists():
        agents_text = agents_path.read_text(encoding="utf-8")
        new_agents_text = upsert_managed_section(agents_text, managed_section)
        agents_mode = "updated"
    else:
        new_agents_text = render_template(
            "AGENTS_NEW.md.tmpl",
            project_name=project_name,
            managed_section=managed_section,
        )
        agents_mode = "created"

    memlayer_text = render_template(
        "MEMLAYER.md.tmpl",
        project_name=project_name,
        project_root=str(project_root),
        preferred_url=preferred_url,
        local_url=local_url,
        human_url=human_url,
    )
    env_text = render_template(
        "env.memlayer.example.tmpl",
        project_name=project_name,
        project_root=str(project_root),
        preferred_url=preferred_url,
        local_url=local_url,
        human_url=human_url,
    )
    local_env_text = load_template("env.memlayer.tmpl")
    helper_text = load_template("memlayer_api.sh.tmpl")
    watchdog_text = load_template("memlayer_watchdog.sh.tmpl")
    recover_text = load_template("memlayer_recover.sh.tmpl")
    launchd_install_text = load_template("memlayer_launchd_install.sh.tmpl")
    context_text = load_template("memlayer_context.sh.tmpl")
    write_text_template = load_template("memlayer_write.sh.tmpl")
    sync_text_template = load_template("memlayer_sync.sh.tmpl")
    snapshot_pull_text = load_template("memlayer_snapshot_pull.sh.tmpl")
    snapshot_json_text = load_template("memlayer.snapshot.json.tmpl")
    snapshot_md_text = load_template("memlayer.snapshot.md.tmpl")
    offline_log_text = load_template("memlayer.offline.log.md.tmpl")
    offline_queue_text = load_template("memlayer.offline.queue.jsonl.tmpl")
    config_payload = build_project_config(
        project_root,
        preferred_url=preferred_url,
        local_url=local_url,
        human_url=human_url,
    )
    if config_path.exists():
        try:
            existing_config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_config = {}
        if isinstance(existing_config, dict):
            config_payload = merge_project_config(existing_config, config_payload)

    write_text(agents_path, new_agents_text, dry_run=dry_run)
    write_text(memlayer_path, memlayer_text, dry_run=dry_run)
    write_text(env_path, env_text, dry_run=dry_run)
    if not local_env_path.exists():
        write_text(local_env_path, local_env_text, dry_run=dry_run)
    else:
        merged_local_env = merge_env_text(local_env_path.read_text(encoding="utf-8"), local_env_text)
        write_text(local_env_path, merged_local_env, dry_run=dry_run)
    write_json(config_path, config_payload, dry_run=dry_run)
    write_text(helper_path, helper_text, dry_run=dry_run)
    write_text(watchdog_path, watchdog_text, dry_run=dry_run)
    write_text(recover_path, recover_text, dry_run=dry_run)
    write_text(launchd_install_path, launchd_install_text, dry_run=dry_run)
    write_text(context_path, context_text, dry_run=dry_run)
    write_text(write_path, write_text_template, dry_run=dry_run)
    write_text(sync_path, sync_text_template, dry_run=dry_run)
    write_text(snapshot_pull_path, snapshot_pull_text, dry_run=dry_run)
    if not snapshot_json_path.exists():
        write_text(snapshot_json_path, snapshot_json_text, dry_run=dry_run)
    if not snapshot_md_path.exists():
        write_text(snapshot_md_path, snapshot_md_text, dry_run=dry_run)
    if not offline_log_path.exists():
        write_text(offline_log_path, offline_log_text, dry_run=dry_run)
    if not offline_queue_path.exists():
        write_text(offline_queue_path, offline_queue_text, dry_run=dry_run)
    chmod_executable(helper_path, dry_run=dry_run)
    chmod_executable(watchdog_path, dry_run=dry_run)
    chmod_executable(recover_path, dry_run=dry_run)
    chmod_executable(launchd_install_path, dry_run=dry_run)
    chmod_executable(context_path, dry_run=dry_run)
    chmod_executable(write_path, dry_run=dry_run)
    chmod_executable(sync_path, dry_run=dry_run)
    chmod_executable(snapshot_pull_path, dry_run=dry_run)

    return {
        "project": project_name,
        "root": str(project_root),
        "agents": agents_mode,
        "files": [
            str(agents_path),
            str(memlayer_path),
            str(env_path),
            str(local_env_path),
            str(config_path),
            str(helper_path),
            str(watchdog_path),
            str(recover_path),
            str(launchd_install_path),
            str(context_path),
            str(write_path),
            str(sync_path),
            str(snapshot_pull_path),
            str(snapshot_json_path),
            str(snapshot_md_path),
            str(offline_log_path),
            str(offline_queue_path),
        ],
    }


def main() -> None:
    args = parse_args()
    projects_root = Path(args.projects_root).expanduser().resolve()
    names = [item.strip() for item in args.names.split(",") if item.strip()] if args.names else None
    results = [
        install_for_project(
            project_root,
            args.preferred_url,
            args.local_url,
            args.human_url,
            dry_run=args.dry_run,
        )
        for project_root in list_projects(projects_root, names)
    ]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
