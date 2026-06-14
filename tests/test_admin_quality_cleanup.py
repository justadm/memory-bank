from __future__ import annotations

from pathlib import Path

from scripts.admin_quality_cleanup import is_production_env


def test_is_production_env_from_app_env(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("APP_ENV=production\n", encoding="utf-8")

    assert is_production_env(env_path) is True


def test_is_production_env_from_environment_alias(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("ENVIRONMENT=prod\n", encoding="utf-8")

    assert is_production_env(env_path) is True


def test_is_production_env_false_for_development(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("APP_ENV=development\n", encoding="utf-8")

    assert is_production_env(env_path) is False
