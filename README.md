# Dynatrace Plugin for Grafana

Grafana datasource plugin that talks to Dynatrace — **Metrics**, **Logs**, **Alerts (Problems)** and full **DQL on Grail**. Works on both Classic tenants (Api-Token) and Grail-migrated SaaS tenants (Platform Token / Bearer).

The repository ships two projects:

| Folder | What it is |
|--------|------------|
| [`plugin/opensource-dynatraceplugin-datasource/`](plugin/opensource-dynatraceplugin-datasource/) | The Grafana datasource plugin (Go backend + React/TypeScript frontend). |
| [`simulator_metric_dynatrace/`](simulator_metric_dynatrace/) | A Python/Flask simulator that mimics the Dynatrace SaaS endpoints (Classic + Grail + DQL parser) so you can develop without hitting a real tenant. |

A helper script [`test-dynatrace.sh`](test-dynatrace.sh) at the repo root runs the same calls the plugin makes against any tenant (simulator or production), with a sanity-checker for the Platform Token shape.

---

## Features (v2)

### Query types

The plugin exposes four query types in the Grafana query editor:

| Query Type | Endpoint | Auth | Returns |
|-----------|----------|------|---------|
| **Metrics** | `GET /api/v2/metrics/query` | Api-Token | time-series frames |
| **Logs / DQL (Grail)** | `POST /platform/storage/query/v1/query:execute` + polling | Platform Token (Bearer) | Loki-compatible logs frame |
| **Alerts (Problems)** | `GET /api/v2/problems` | Api-Token *or* Platform Token | table frame |
| **Logs Classic API (pre-Grail only)** | `GET /api/v2/logs/search` | Api-Token | Loki frame — *removed in Grail tenants; UI warns* |

Each type has its own editor form (selectors, time range, sort/limit, labels).

### Authentication

Two independent secrets, each used where it applies:

- **API Token (`dt0c01.…`)** — sent as `Authorization: Api-Token <…>`. Used by Metrics, Classic logs, and Problems by default.
- **Platform Token (`dt0s16.…`)** — sent as `Authorization: Bearer <…>`. Required for **Grail DQL**; used as a Bearer fallback by Problems when configured.
  Created in Dynatrace under *Account Management → Identity & access management → **Platform tokens***. Permissions: `storage:logs:read`, `storage:events:read`, `storage:bizevents:read`, `storage:metrics:read`, `storage:buckets:read` depending on what you query.

### Two URLs (Classic + Grail are separate hosts)

In Grail-migrated tenants, Dynatrace serves Classic and Platform on different hostnames:

| Field in the editor | Used for | Example |
|---------------------|----------|---------|
| **Classic API URL** | Metrics, Classic logs, Problems | `https://<tenant>.live.dynatrace.com` |
| **Platform API URL** | Grail DQL (`/platform/...`) | `https://<tenant>.apps.dynatrace.com` |

The Platform field is optional — leave blank for Classic-only tenants or the simulator, and the Classic URL is reused.

### Corporate / ARO-friendly

The HTTP client honors:

- `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` env vars on the Grafana pod (via `http.ProxyFromEnvironment`).
- A real `User-Agent` and `Accept: application/json` on every outbound request, so WAFs that block Go's default `Go-http-client/1.1` won't drop the calls.
- Optional custom TLS CA bundle (PEM) for tenants behind self-signed gateways.

### DQL parser (in the simulator)

The simulator implements a faithful subset of Dynatrace DQL — pipelines `fetch <source> | filter ... | sort ... | limit N`, operators `==/!=/<,<=,>,>=`, logical `and/or/not` with parentheses, and functions `contains() / matchesPhrase() / startsWith() / endsWith() / in()`. Lets you develop queries locally before pointing at production.

### URL-safe request tokens (Grail polling)

The `requestToken` returned by `query:execute` is base64-ish and frequently contains `+`, `/`, `=`. The plugin percent-encodes it before putting it into the `query:poll?request-token=…` URL — otherwise Dynatrace rejects the poll with `INVALID_REQUEST_TOKEN_PROVIDED` (a `+` decoded as space).

---

## Project Structure

```text
dynatrace-plugin-grafana/
├── plugin/
│   └── opensource-dynatraceplugin-datasource/   # Grafana datasource plugin
│       ├── src/                                  # Frontend (React/TypeScript)
│       │   ├── components/
│       │   │   ├── ConfigEditor.tsx              # Classic+Platform URL, Api-Token, Platform Token, TLS
│       │   │   └── QueryEditor.tsx               # Query type picker + per-type forms
│       │   ├── datasource.ts
│       │   ├── module.ts
│       │   └── types.ts
│       └── pkg/                                  # Backend (Go)
│           └── plugin/
│               ├── datasource.go                 # Wiring, applyAuth, HTTP client
│               ├── logs.go                       # /api/v2/logs/search → Loki frame
│               ├── alerts.go                     # /api/v2/problems → table frame
│               └── dqlgrail.go                   # Grail execute + poll → Loki frame
├── simulator_metric_dynatrace/                   # Local Dynatrace simulator (Python/Flask)
│   ├── app.py                                    # All endpoints (incl. /sso + /platform/…)
│   ├── dql.py                                    # DQL parser
│   ├── mock_data.py, mock_logs.py
│   ├── mock_alerts.py                            # Problem generator + problemSelector parser
│   ├── mock_dql_grail.py                         # Grail query:execute / query:poll backing
│   ├── QUERY_EXAMPLES.md                         # Metrics + Logs + Problems + DQL examples
│   └── Dockerfile
├── test-dynatrace.sh                             # Smoke-test script (curl + python3)
└── README.md
```

---

## Development Setup

### Prerequisites

- Node.js >= 18, npm >= 10
- Go >= 1.21
- Docker / Docker Compose
- `curl`, `python3` (for the test script)

### 1. Install plugin dependencies

```bash
cd plugin/opensource-dynatraceplugin-datasource
npm install
```

### 2. Start the simulator + Grafana

```bash
cd plugin/opensource-dynatraceplugin-datasource
docker compose up -d
```

- Grafana → <http://localhost:3000> (admin / admin)
- Simulator → <http://localhost:8080>

The simulator advertises every endpoint it serves at `GET /` and provides health on `/health`. See [QUERY_EXAMPLES.md](simulator_metric_dynatrace/QUERY_EXAMPLES.md) for full DQL + problemSelector examples.

### 3. Build the plugin

```bash
# dev: rebuilds backend once, watches frontend
npm run dev

# prod
npm run build
```

Then restart Grafana to pick up the new build:

```bash
docker compose restart grafana
```

---

## Configuring the datasource in Grafana

### Against the simulator

| Field | Value |
|-------|-------|
| Classic API URL | `http://dynatrace-api-simulator:8080` |
| Platform API URL | *(leave blank — fallback)* |
| API Token | `test-token` |
| Platform Token | *(optional)* `dt0s16.test-platform-token` |
| TLS Skip Verify | enabled (dev only) |

### Against production (Grail-migrated SaaS)

| Field | Value |
|-------|-------|
| Classic API URL | `https://<tenant>.live.dynatrace.com` |
| Platform API URL | `https://<tenant>.apps.dynatrace.com` |
| API Token | `dt0c01.…` with `Read metrics`, `Read problems`, optionally `Read logs` |
| Platform Token | `dt0s16.<id>.<secret>` with Grail scopes (`storage:logs:read`, `storage:events:read`, …) |
| TLS Skip Verify | **disabled** |

Hit **Save & test** — it validates that at least one token is configured. The actual reachability is tested on the first query.

---

## Example queries

### Metrics

```text
builtin:host.cpu.usage:filter(eq(dt.entity.host,HOST-123)):splitBy("dt.entity.host"):sort(value(auto,descending))
```

### Logs / DQL (Grail)

```text
fetch logs
| filter k8s.container.name == "fini-srv-cdcvei-formalizacao"
| filter contains(content, "buscarToken Fator gerador")
       or contains(content, "Cliente bloqueado por excesso de tentativas")
| summarize total_block = count(), by:{content}
| filter total_block >= 6
| sort total_block desc
```

### Alerts (Problems)

```text
status("OPEN"),severityLevel("ERROR","AVAILABILITY")
```

or DQL form:

```text
fetch dt.davis.problems | filter event.status == "OPEN" | sort startTime desc | limit 50
```

---

## Verifying connectivity outside Grafana — `test-dynatrace.sh`

The repo root has a script that performs the same calls the plugin does, with diagnostics for the common failure modes (token format, wrong URL, missing scope, proxy interception, polling-token encoding).

```bash
export DT_CLASSIC_URL="https://<tenant>.live.dynatrace.com"
export DT_GRAIL_URL="https://<tenant>.apps.dynatrace.com"
export DT_API_TOKEN="dt0c01..."
export DT_PLATFORM_TOKEN="dt0s16.<id>.<secret>"

./test-dynatrace.sh            # runs all targets
./test-dynatrace.sh metrics    # only /api/v2/metrics
./test-dynatrace.sh problems   # only /api/v2/problems
./test-dynatrace.sh dql        # only Grail DQL execute + poll loop
```

Requires `curl` and `python3` (no `jq`). Behind a corporate proxy:

```bash
export DT_PROXY="http://proxy.corp:3128"
./test-dynatrace.sh dql
```

The script color-codes common errors and points at the exact fix:

- `401 "Platform token has invalid format"` → wrong token type or truncated
- `403 "<html>...administrator rules"` → egress proxy/WAF (typical in Azure/ARO)
- `404` → Grail URL pointed at `.live.` instead of `.apps.`
- `400 INVALID_REQUEST_TOKEN_PROVIDED` → polling-token encoding bug *(fixed in the plugin)*

---

## Troubleshooting

### `401 OAuth token is missing` on the Logs endpoint

Your tenant is Grail-migrated and the legacy `/api/v2/logs/search` path requires Bearer. Switch the **Query Type** to **Logs / DQL (Grail)** in the editor and configure the **Platform Token** + **Platform API URL** in the datasource.

### `401 Platform token has invalid format`

You probably copied only the token ID from the Platform Tokens list (15-char `dt0s16.<id>`). The full token (`dt0s16.<id>.<secret>`, ~100 chars, two dots) is shown **only once** at creation time. Delete and recreate the token; copy the yellow banner.

### `403 <html>...administrator rules</body></html>`

Not Dynatrace — that's your network egress (proxy/WAF) blocking. From inside the Grafana pod:

```bash
oc rsh deploy/grafana
curl -v https://<tenant>.apps.dynatrace.com/platform/storage/query/v1/query:execute \
  -H "Authorization: Bearer $DT_PLATFORM_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"fetch logs | limit 1"}'
```

If the HTML 403 comes from the pod too, ask your infra team to allow `*.apps.dynatrace.com` (Grail) and `*.live.dynatrace.com` (Classic) on the Azure Firewall / egress proxy.

### `400 INVALID_REQUEST_TOKEN_PROVIDED` during DQL poll

Plugin bug — fixed in v2: the `requestToken` is now percent-encoded before being placed in the query string. Rebuild / re-pull the plugin.

### Backend changes not reflecting

```bash
npm run build:backend
docker compose restart grafana
```

---

## Build & Deployment

```bash
# build everything
npm run build

# (optional) sign for distribution outside the org
npm run sign

# package
cd plugin/opensource-dynatraceplugin-datasource
zip -r dynatrace-plugin.zip dist/
```

Install in a Grafana host:

```bash
cp -r dist /var/lib/grafana/plugins/dynatrace-plugin
systemctl restart grafana-server
```

`grafana.ini`:

```ini
[plugins]
allow_loading_unsigned_plugins = opensource-dynatraceplugin-datasource
```

---

## Scripts (in `plugin/opensource-dynatraceplugin-datasource/`)

- `npm run build` — frontend + backend (prod)
- `npm run build:backend` — Go backend only
- `npm run dev` — backend once, frontend watch
- `npm run test` / `npm run test:ci` — Jest
- `npm run lint` / `npm run lint:fix`
- `npm run typecheck`
- `npm run sign`

---

## Contributing

1. Fork
2. Branch off `v2`
3. Develop against the simulator (`docker compose up -d`)
4. Use `./test-dynatrace.sh` against your own tenant before opening the PR
5. Submit

---

## License

Apache-2.0

## Resources

- [Grafana Plugin Development](https://grafana.com/docs/grafana/latest/developers/plugins/)
- [Dynatrace Metrics V2 API](https://docs.dynatrace.com/docs/dynatrace-api/environment-api/metric-v2)
- [Dynatrace Log Monitoring V2](https://docs.dynatrace.com/docs/dynatrace-api/environment-api/log-monitoring-v2)
- [Dynatrace Problems V2](https://docs.dynatrace.com/docs/dynatrace-api/environment-api/problems-v2)
- [Dynatrace Grail Query API](https://developer.dynatrace.com/develop/platform-services/services/grail-service/)
- [Dynatrace Platform Tokens](https://docs.dynatrace.com/docs/manage/identity-access-management/access-tokens-and-oauth-clients/platform-tokens)
- [Field permissions in Grail](https://docs.dynatrace.com/docs/platform/grail/organize-data/assign-permissions-in-grail#field-permissions)
