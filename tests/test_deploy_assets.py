from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_basic_auth_deploy_assets_exist():
    snippet = ROOT / "deploy" / "msk" / "nginx" / "snippets" / "adm.memlayer.basic-auth.conf.example"
    helper = ROOT / "scripts" / "prepare_msk_admin_basic_auth.sh"
    assert snippet.exists()
    assert helper.exists()


def test_basic_auth_helper_has_expected_targets():
    helper = (ROOT / "scripts" / "prepare_msk_admin_basic_auth.sh").read_text(encoding="utf-8")
    assert "openssl passwd -apr1" in helper
    assert "/etc/nginx/.htpasswd-memlayer-admin" in helper
    assert "/etc/nginx/snippets/memlayer_adm_basic_auth.conf" in helper
