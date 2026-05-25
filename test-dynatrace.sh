#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Dynatrace connection smoke-tester.
#
# Exercises the same three endpoint families the Grafana plugin uses against a
# real Dynatrace tenant, so you can confirm credentials and network reachability
# before opening Grafana.
#
#   1. Metrics  (Classic API, Api-Token)        -> /api/v2/metrics
#   2. Problems (Classic API, Api-Token or Bearer) -> /api/v2/problems
#   3. Grail DQL (Platform Token Bearer)        -> /platform/storage/query/v1/{execute,poll}
#
# Usage:
#   export DT_CLASSIC_URL="https://<env-id>.live.dynatrace.com"
#   export DT_GRAIL_URL="https://<env-id>.apps.dynatrace.com"
#   export DT_API_TOKEN="dt0c01..."          # Classic Api-Token (logs.read, metrics.read, problems.read)
#   export DT_PLATFORM_TOKEN="dt0s16..."     # Platform Token   (storage:logs:read, ...)
#   ./test-dynatrace.sh                      # runs all checks
#   ./test-dynatrace.sh metrics              # runs only the metrics check
#   ./test-dynatrace.sh dql                  # runs only the Grail DQL check
#
# Optional:
#   export DT_DQL='fetch logs | filter status == "ERROR" | limit 5'
#   export DT_TIMEFRAME_FROM=2024-01-01T00:00:00.000Z
#   export DT_TIMEFRAME_TO=2024-01-02T00:00:00.000Z
#   export DT_PROXY="http://proxy.corp:3128"  # if behind a corporate egress
# -----------------------------------------------------------------------------
set -euo pipefail

# --- colors -------------------------------------------------------------------
if [[ -t 1 ]]; then
  C_OK=$'\033[1;32m'; C_WARN=$'\033[1;33m'; C_ERR=$'\033[1;31m'
  C_DIM=$'\033[2m';   C_BOLD=$'\033[1m';   C_RESET=$'\033[0m'
else
  C_OK=''; C_WARN=''; C_ERR=''; C_DIM=''; C_BOLD=''; C_RESET=''
fi

step()  { printf "\n${C_BOLD}== %s ==${C_RESET}\n" "$*"; }
ok()    { printf "${C_OK}✔${C_RESET}  %s\n" "$*"; }
warn()  { printf "${C_WARN}!${C_RESET}  %s\n" "$*"; }
fail()  { printf "${C_ERR}✘${C_RESET}  %s\n" "$*"; }
dim()   { printf "${C_DIM}%s${C_RESET}\n" "$*"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { fail "missing command: $1"; exit 2; }
}
# curl is required for any action; python3 is used for JSON pretty-print and
# field extraction (avoids a hard jq dependency).
require_cmd curl

# json_get '<dotted.path>'  (JSON on stdin)  -> prints value at path, or empty
json_get() {
  python3 -c '
import json, sys
path = sys.argv[1].split(".")
try:
    d = json.load(sys.stdin)
    for p in path:
        if p == "":
            continue
        d = d[int(p)] if isinstance(d, list) else d[p]
    if d is None:
        sys.exit(0)
    print(d if isinstance(d, str) else json.dumps(d))
except Exception:
    sys.exit(0)
' "$1" 2>/dev/null || true
}

# json_len '<dotted.path-to-array>'  (JSON on stdin)  -> array length, or empty
json_len() {
  python3 -c '
import json, sys
path = [p for p in sys.argv[1].split(".") if p]
try:
    d = json.load(sys.stdin)
    for p in path:
        d = d[p]
    if isinstance(d, list):
        print(len(d))
except Exception:
    sys.exit(0)
' "$1" 2>/dev/null || true
}

pretty_json() {
  python3 -m json.tool 2>/dev/null || cat
}

# --- config -------------------------------------------------------------------
DT_CLASSIC_URL="${DT_CLASSIC_URL:-${DT_API_URL:-}}"   # accept legacy DT_API_URL too
DT_GRAIL_URL="${DT_GRAIL_URL:-}"
DT_API_TOKEN="${DT_API_TOKEN:-}"
DT_PLATFORM_TOKEN="${DT_PLATFORM_TOKEN:-}"
DT_DQL="${DT_DQL:-fetch logs | filter status == \"ERROR\" | limit 5}"
DT_TIMEFRAME_FROM="${DT_TIMEFRAME_FROM:-$(date -u -d '2 hours ago' '+%Y-%m-%dT%H:%M:%S.000Z' 2>/dev/null || date -u -v-2H '+%Y-%m-%dT%H:%M:%S.000Z')}"
DT_TIMEFRAME_TO="${DT_TIMEFRAME_TO:-$(date -u '+%Y-%m-%dT%H:%M:%S.000Z')}"
DT_PROXY="${DT_PROXY:-}"

UA="grafana-dynatrace-plugin/2.0 (+test-dynatrace.sh)"

# Build common curl flags (TLS + proxy + UA + accept)
CURL_FLAGS=(--silent --show-error --connect-timeout 10 --max-time 60 -H "User-Agent: $UA" -H "Accept: application/json")
[[ -n "$DT_PROXY" ]] && CURL_FLAGS+=(--proxy "$DT_PROXY")

# --- helpers ------------------------------------------------------------------

# call <method> <url> [body] [auth-header]
# Prints "HTTP <status>" then the response body (pretty if JSON).
call() {
  local method="$1" url="$2" body="${3:-}" auth="${4:-}"
  local args=("${CURL_FLAGS[@]}" -X "$method" -w "\n__HTTP__:%{http_code}\n" -H "$auth")
  [[ -n "$body" ]] && args+=(-H "Content-Type: application/json" --data-binary "$body")
  local raw
  raw="$(curl "${args[@]}" "$url" 2>&1)" || true
  local status="${raw##*__HTTP__:}"; status="${status//[^0-9]/}"
  local resp="${raw%__HTTP__:*}"
  printf "${C_DIM}%s %s${C_RESET}\n" "$method" "$url"
  printf "HTTP ${C_BOLD}%s${C_RESET}\n" "${status:-?}"
  if printf '%s' "$resp" | python3 -c 'import json,sys; json.load(sys.stdin)' >/dev/null 2>&1; then
    printf '%s\n' "$resp" | pretty_json
  else
    printf '%s\n' "$resp"
  fi
  # propagate status so callers can branch
  RESP_BODY="$resp"
  RESP_STATUS="$status"
}

guard() {
  local name="$1" value="$2"
  if [[ -z "$value" ]]; then
    fail "$name is not set."
    return 1
  fi
}

# --- checks -------------------------------------------------------------------

check_metrics() {
  step "Metrics  (Classic /api/v2/metrics)"
  guard "DT_CLASSIC_URL" "$DT_CLASSIC_URL" || return 1
  guard "DT_API_TOKEN"   "$DT_API_TOKEN"   || return 1

  call GET "${DT_CLASSIC_URL%/}/api/v2/metrics?pageSize=1" "" "Authorization: Api-Token $DT_API_TOKEN"
  case "$RESP_STATUS" in
    200) ok "Classic Api-Token accepted on metrics endpoint." ;;
    401|403) fail "Auth rejected. Verify the Api-Token and that it has 'Read metrics' scope." ;;
    *) warn "Unexpected status. If body is HTML, you are likely being filtered by a proxy/WAF (typical inside ARO egress)." ;;
  esac
}

check_problems() {
  step "Problems  (Classic /api/v2/problems)"
  guard "DT_CLASSIC_URL" "$DT_CLASSIC_URL" || return 1
  # Problems accepts either token type; prefer Platform Token on Grail tenants.
  local auth
  if [[ -n "$DT_PLATFORM_TOKEN" ]]; then
    auth="Authorization: Bearer $DT_PLATFORM_TOKEN"
    dim "(using Platform Token as Bearer)"
  else
    auth="Authorization: Api-Token $DT_API_TOKEN"
    dim "(using Api-Token)"
  fi
  call GET "${DT_CLASSIC_URL%/}/api/v2/problems?pageSize=1" "" "$auth"
  case "$RESP_STATUS" in
    200) ok "Problems endpoint reachable." ;;
    401|403) fail "Auth rejected. Verify token scope (logs/events/problems.read or storage:events:read on Grail)." ;;
    *) warn "Unexpected status — check the body above." ;;
  esac
}

inspect_platform_token() {
  local raw="${DT_PLATFORM_TOKEN-}"
  local stripped len prefix
  # strip leading/trailing whitespace + invisible chars
  stripped="$(printf '%s' "$raw" | tr -d '[:space:]')"
  len=${#stripped}
  prefix="${stripped:0:7}"

  dim "Platform token sanity check:"
  dim "  raw length: ${#raw}   stripped length: $len   prefix: '$prefix'"

  if [[ "$len" -ne "${#raw}" ]]; then
    warn "Token contains whitespace/newline. Run: export DT_PLATFORM_TOKEN=\"\$(echo \"\$DT_PLATFORM_TOKEN\" | tr -d '[:space:]')\""
  fi

  case "$stripped" in
    dt0s16.*)
      ok   "prefix dt0s16.* matches a Platform Token."
      ;;
    dt0c01.*)
      fail "This is an API ACCESS TOKEN (dt0c01.*), not a Platform Token."
      warn "Move it to DT_API_TOKEN (sent as 'Api-Token <value>') — Platform tokens are dt0s16.*."
      return 1
      ;;
    dt0s02.*)
      fail "This is an OAuth client_id/secret (dt0s02.*), not a Platform Token."
      warn "OAuth clients need the client_credentials grant to mint a Bearer — they are NOT Bearer themselves."
      warn "Create a Platform Token (dt0s16.*) under: Account Management → Access tokens → Platform tokens."
      return 1
      ;;
    "")
      fail "DT_PLATFORM_TOKEN is empty after stripping whitespace."
      return 1
      ;;
    *)
      warn "Unexpected prefix '$prefix'. Platform tokens start with 'dt0s16.'."
      warn "Double-check that you copied a Platform Token (not an Access Token / OAuth client)."
      ;;
  esac

  # Format-level sanity (real platform tokens look like dt0s16.AAA.BBB)
  local dots
  dots=$(printf '%s' "$stripped" | tr -cd '.' | wc -c)
  if [[ "$dots" -lt 2 ]]; then
    warn "Only $dots dot(s) in the token — Platform tokens normally have the shape dt0s16.<id>.<secret> (2 dots). Likely truncated."
  fi
  return 0
}

check_dql() {
  step "Grail DQL  (Platform /platform/storage/query/v1/query:{execute,poll})"
  guard "DT_GRAIL_URL"      "$DT_GRAIL_URL"      || return 1
  guard "DT_PLATFORM_TOKEN" "$DT_PLATFORM_TOKEN" || return 1

  inspect_platform_token || return 1

  # 1) execute
  local body
  body=$(DT_DQL="$DT_DQL" DT_TIMEFRAME_FROM="$DT_TIMEFRAME_FROM" DT_TIMEFRAME_TO="$DT_TIMEFRAME_TO" \
         python3 -c '
import json, os
print(json.dumps({
    "query":                 os.environ["DT_DQL"],
    "defaultTimeframeStart": os.environ["DT_TIMEFRAME_FROM"],
    "defaultTimeframeEnd":   os.environ["DT_TIMEFRAME_TO"],
    "maxResultRecords":      1000,
}))')
  call POST "${DT_GRAIL_URL%/}/platform/storage/query/v1/query:execute" \
            "$body" "Authorization: Bearer $DT_PLATFORM_TOKEN"

  if [[ "$RESP_STATUS" != "200" && "$RESP_STATUS" != "202" ]]; then
    fail "query:execute failed."
    local msg=""
    msg=$(printf '%s' "$RESP_BODY" | json_get "error.message")
    case "$RESP_STATUS" in
      401)
        if [[ "$msg" == *"invalid format"* ]]; then
          warn "Dynatrace rejected the *shape* of the token, not the permissions."
          warn "The value sent isn't recognized as a Platform Token. Almost always one of:"
          warn "  - wrong token type (Access Token dt0c01.* or OAuth client dt0s02.* instead of Platform Token dt0s16.*)"
          warn "  - whitespace/newline pasted along with the secret"
          warn "  - token truncated (full Platform Token has two dots: dt0s16.<id>.<secret>)"
        else
          warn "Platform Token rejected (auth failure). Recreate it under Account Management → Access tokens → Platform tokens."
        fi
        ;;
      403) warn "Token format OK but lacking permissions (e.g. storage:logs:read) or field permissions in Grail." ;;
      404) warn "Wrong URL. Grail lives on https://<env>.apps.dynatrace.com (NOT .live.dynatrace.com)." ;;
    esac
    return 1
  fi

  local req_token
  req_token=$(printf '%s' "$RESP_BODY" | json_get "requestToken")
  [[ -n "$req_token" ]] || { fail "no requestToken in execute response"; return 1; }
  ok "query accepted, requestToken=${req_token:0:24}..."

  # The requestToken is base64-ish (frequently has '+', '/', '=') so it must
  # be percent-encoded before going into a query string — otherwise '+' is
  # decoded as a literal space and Dynatrace returns INVALID_REQUEST_TOKEN_PROVIDED.
  local req_token_enc
  req_token_enc=$(printf '%s' "$req_token" | python3 -c \
    'import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read(), safe=""))')

  # 2) poll until SUCCEEDED / FAILED / timeout
  local poll_url="${DT_GRAIL_URL%/}/platform/storage/query/v1/query:poll?request-token=$req_token_enc"
  local tries=0 state="RUNNING"
  while (( tries < 30 )) && [[ "$state" == "RUNNING" || "$state" == "NOT_STARTED" ]]; do
    sleep 1
    tries=$((tries + 1))
    call GET "$poll_url" "" "Authorization: Bearer $DT_PLATFORM_TOKEN"
    state=$(printf '%s' "$RESP_BODY" | json_get "state")
    [[ "$state" != "RUNNING" && "$state" != "NOT_STARTED" ]] && break
    dim "  ... still $state (try $tries)"
  done

  case "$state" in
    SUCCEEDED)
      local n
      n=$(printf '%s' "$RESP_BODY" | json_len "result.records")
      ok "DQL query succeeded — ${n:-0} record(s) returned."
      ;;
    FAILED|CANCELLED) fail "DQL state=$state" ;;
    *)                fail "Timed out waiting for DQL result (last state=$state)" ;;
  esac
}

# --- main ---------------------------------------------------------------------

usage() {
  sed -n '/^# Usage:/,/^# ---/p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
}

target="${1:-all}"
case "$target" in
  -h|--help|help) usage ;;
esac
require_cmd python3
case "$target" in
  all)      check_metrics; check_problems; check_dql ;;
  metrics)  check_metrics ;;
  problems) check_problems ;;
  dql|logs) check_dql ;;
  *) fail "unknown target: $target"; usage ;;
esac
