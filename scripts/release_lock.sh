#!/usr/bin/env bash

memlayer_release_lock_path() {
  if [[ "${MEMLAYER_RELEASE_TEST_MODE:-0}" == "1" ]]; then
    if [[ -z "${MEMLAYER_RELEASE_LOCK_DIR:-}" ]]; then
      echo "test mode requires MEMLAYER_RELEASE_LOCK_DIR" >&2
      return 2
    fi
    printf '%s\n' "${MEMLAYER_RELEASE_LOCK_DIR}"
    return
  fi

  printf '%s\n' "/run/memlayer-release/compose.lock"
}

memlayer_release_lock_validate_parent() {
  local lock_dir="$1"
  local parent_dir="${lock_dir%/*}"
  local metadata
  local owner_uid
  local mode
  local current_uid

  if [[ -z "${parent_dir}" || ! -d "${parent_dir}" || -L "${parent_dir}" ]]; then
    echo "release runtime directory must exist and must not be a symlink" >&2
    return 1
  fi

  case "$(uname -s)" in
    Darwin)
      metadata="$(stat -f '%u %Lp' "${parent_dir}")" || return 1
      ;;
    Linux)
      metadata="$(stat -c '%u %a' "${parent_dir}")" || return 1
      ;;
    *)
      echo "unsupported platform for release runtime validation" >&2
      return 1
      ;;
  esac
  read -r owner_uid mode <<<"${metadata}"
  current_uid="$(id -u)" || return 1

  if [[ "${owner_uid}" != "${current_uid}" ]]; then
    echo "release runtime directory must be owned by the deploy account" >&2
    return 1
  fi
  if [[ "${mode}" != "700" ]]; then
    echo "release runtime directory must have mode 0700" >&2
    return 1
  fi
}

memlayer_release_lock_acquire() {
  local lock_dir="$1"
  local token="$2"

  if ! memlayer_release_lock_validate_parent "${lock_dir}"; then
    return 1
  fi
  if ! mkdir -m 700 "${lock_dir}"; then
    return 1
  fi
  if ! (
    umask 077
    printf '%s\n' "${token}" >"${lock_dir}/owner"
  ); then
    rmdir "${lock_dir}" 2>/dev/null || true
    return 1
  fi
}

memlayer_release_lock_assert_owner() {
  local lock_dir="$1"
  local expected_token="$2"
  local actual_token

  if [[ -z "${expected_token}" || ! -f "${lock_dir}/owner" ]]; then
    return 1
  fi
  IFS= read -r actual_token <"${lock_dir}/owner" || return 1
  [[ "${actual_token}" == "${expected_token}" ]]
}

memlayer_release_lock_release() {
  local lock_dir="$1"
  local expected_token="$2"

  if ! memlayer_release_lock_assert_owner "${lock_dir}" "${expected_token}"; then
    return 1
  fi
  rm -f "${lock_dir}/owner"
  rmdir "${lock_dir}"
}
