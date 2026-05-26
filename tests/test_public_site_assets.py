from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "deploy" / "msk" / "site"


def test_public_site_files_exist():
    assert (SITE_DIR / "index.html").exists()
    assert (SITE_DIR / "api" / "index.html").exists()
    assert (SITE_DIR / "styles.css").exists()
    assert (SITE_DIR / "site.js").exists()


def test_homepage_has_public_nav_and_no_admin_link():
    html = (SITE_DIR / "index.html").read_text(encoding="utf-8")
    assert "memlayer.ru/api" in html
    assert "github.com/justadm/memory-bank" in html
    assert "adm.memlayer.ru" not in html


def test_api_page_uses_placeholders_and_not_live_openapi():
    html = (SITE_DIR / "api" / "index.html").read_text(encoding="utf-8")
    assert "YOUR_API_KEY" in html
    assert "api.memlayer.ru/health" in html
    assert "openapi.json" not in html
    assert "ops-admin-key" not in html


def test_site_js_supports_copy_and_theme_switcher():
    js = (SITE_DIR / "site.js").read_text(encoding="utf-8")
    assert "navigator.clipboard.writeText" in js
    assert "theme-toggle" in js
    assert "prefers-color-scheme" in js
