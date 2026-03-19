#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

# shellcheck source=../scripts/docker/common.sh
source "./scripts/docker/common.sh"

assert_eq() {
  local got="${1}"
  local want="${2}"
  if [ "${got}" != "${want}" ]; then
    echo "assertion failed: got '${got}', want '${want}'" >&2
    exit 1
  fi
}

echo "=== Testing ss parser ==="
SS_OUTPUT='LISTEN 0 4096 127.0.0.1:7890 0.0.0.0:* users:(("mihomo",pid=1,fd=3))'
assert_eq "$(_find_proxy_endpoint_from_ss_output "${SS_OUTPUT}")" "http:7890"

echo "=== Testing lsof parser ==="
LSOF_OUTPUT=$'COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\nclash-verge 123 user 12u IPv4 0t0 TCP 127.0.0.1:7891 (LISTEN)'
assert_eq "$(_find_proxy_endpoint_from_lsof_output "${LSOF_OUTPUT}")" "socks5:7891"

echo "=== Testing netstat parser ==="
NETSTAT_OUTPUT=$'tcp4       0      0  127.0.0.1.7897         *.*                    LISTEN'
assert_eq "$(_find_proxy_endpoint_from_netstat_output "${NETSTAT_OUTPUT}")" "http:7897"

echo "=== Testing HTTP proxy export ==="
configure_proxy_env "http:7890"
assert_eq "${HTTP_PROXY}" "http://127.0.0.1:7890"
assert_eq "${HTTPS_PROXY}" "http://127.0.0.1:7890"
if [ -n "${ALL_PROXY:-}" ]; then
  echo "assertion failed: ALL_PROXY should be unset for HTTP proxy" >&2
  exit 1
fi
if [ -n "${all_proxy:-}" ]; then
  echo "assertion failed: all_proxy should be unset for HTTP proxy" >&2
  exit 1
fi

echo "=== Testing SOCKS proxy export ==="
configure_proxy_env "socks5:7891"
assert_eq "${ALL_PROXY}" "socks5://127.0.0.1:7891"
assert_eq "${all_proxy}" "socks5://127.0.0.1:7891"

echo "=== Proxy common tests passed ==="
