#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "Usage: $0 <username> [htpasswd_path] [snippet_path]" >&2
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required" >&2
  exit 1
fi

username="$1"
htpasswd_path="${2:-/etc/nginx/.htpasswd-memlayer-admin}"
snippet_path="${3:-/etc/nginx/snippets/memlayer_adm_basic_auth.conf}"

read -r -s -p "MemLayer admin password: " password
echo
read -r -s -p "Confirm password: " password_confirm
echo

if [[ "$password" != "$password_confirm" ]]; then
  echo "Passwords do not match" >&2
  exit 1
fi

mkdir -p "$(dirname "$htpasswd_path")" "$(dirname "$snippet_path")"

password_hash="$(openssl passwd -apr1 "$password")"
printf '%s:%s\n' "$username" "$password_hash" > "$htpasswd_path"
if getent group www-data >/dev/null 2>&1; then
  chgrp www-data "$htpasswd_path"
fi
chmod 640 "$htpasswd_path"

{
  echo 'auth_basic "MemLayer Admin";'
  echo "auth_basic_user_file $htpasswd_path;"
} > "$snippet_path"

echo "Wrote $htpasswd_path"
echo "Wrote $snippet_path"
echo "Next steps:"
echo "1. Uncomment 'include /etc/nginx/snippets/memlayer_adm_basic_auth.conf;' in adm.memlayer.ru.conf"
echo "2. sudo nginx -t && sudo nginx -s reload"
