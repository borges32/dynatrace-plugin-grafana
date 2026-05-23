"""
Mock data generator for the Dynatrace Logs V2 API simulator.

Simulates the response format of:
- POST /api/v2/logs/search
- GET  /api/v2/logs/search

Reference (Dynatrace SaaS): records have a `timestamp` (ISO-8601),
`content` (log line), `status` (severity), and dimension fields
such as `host.name`, `log.source`, `dt.entity.host`, `k8s.namespace.name`,
`service.name`, `loglevel`, etc.
"""

import random
from datetime import datetime, timezone

from dql import compile_query, CompiledQuery


# Severities used by Dynatrace logs (status field)
SEVERITIES = ["INFO", "WARN", "ERROR", "DEBUG", "NONE"]

# Pre-defined log "templates" used to generate realistic looking lines
LOG_TEMPLATES = [
    ("INFO",  "Request {method} {path} completed in {ms}ms - status={status}"),
    ("INFO",  "User {user} logged in from {ip}"),
    ("WARN",  "Slow response detected on {path} ({ms}ms)"),
    ("ERROR", "Failed to connect to database {db}: connection timeout after {ms}ms"),
    ("ERROR", "Unhandled exception in {service}: NullPointerException at line {line}"),
    ("DEBUG", "Cache hit for key={key} (ttl={ms}ms)"),
    ("INFO",  "Garbage collection completed in {ms}ms, freed {mb}MB"),
    ("WARN",  "Memory usage above threshold: {pct}%"),
    ("INFO",  "Health check OK ({service})"),
    ("ERROR", "Authentication failure for user={user} from ip={ip}"),
]

HOSTS = ["host-prod-01", "host-prod-02", "host-stage-01", "host-dev-01"]
SERVICES = ["api-gateway", "auth-service", "billing-service", "order-service", "frontend"]
NAMESPACES = ["production", "staging", "default"]
LOG_SOURCES = ["/var/log/app.log", "/var/log/syslog", "stdout", "stderr"]
METHODS = ["GET", "POST", "PUT", "DELETE"]
PATHS = ["/api/users", "/api/orders", "/api/products", "/healthz", "/login"]


def _fmt_line(template: str) -> str:
    return template.format(
        method=random.choice(METHODS),
        path=random.choice(PATHS),
        ms=random.randint(1, 5000),
        status=random.choice([200, 201, 301, 400, 401, 404, 500, 502]),
        user=f"user{random.randint(1, 999)}",
        ip=f"10.0.{random.randint(0, 255)}.{random.randint(1, 254)}",
        db=random.choice(["postgres-primary", "mongo-cluster", "redis-cache"]),
        service=random.choice(SERVICES),
        line=random.randint(10, 800),
        key=f"cache:key:{random.randint(1, 9999)}",
        mb=random.randint(50, 800),
        pct=random.randint(70, 98),
    )


def _iso(ms: int) -> str:
    """Convert epoch milliseconds to ISO-8601 string (Dynatrace style)."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def generate_log_records(from_ms: int, to_ms: int, limit: int = 1000,
                         query: str = "", severity_filter: str = None):
    """
    Generate a pool of mock Dynatrace log records between from_ms and to_ms
    and return only the records that satisfy the DQL `query`.

    The `severity_filter` argument is kept for backward compatibility and is
    folded into the query as `status == "<sev>"` if provided.

    The query is parsed via `dql.compile_query`, which supports both real
    Dynatrace DQL (`fetch logs | filter ... | sort ... | limit ...`) and the
    legacy simplified inline syntax (`status=ERROR`, `host.name="x"`).
    """
    if to_ms <= from_ms:
        return []

    # Build the effective query: combine `severity_filter` with the user query.
    effective_query = (query or "").strip()
    if severity_filter:
        sev_clause = f'status == "{severity_filter.upper()}"'
        if effective_query:
            # If the user already wrote a pipeline, attach the severity to the
            # last filter clause; otherwise wrap it.
            if "|" in effective_query or effective_query.lower().startswith("fetch"):
                effective_query = f"{effective_query} | filter {sev_clause}"
            else:
                effective_query = f"{effective_query} {sev_clause}"
        else:
            effective_query = sev_clause

    try:
        compiled: CompiledQuery = compile_query(effective_query)
    except ValueError as exc:
        # Surface parser errors as an empty result; the caller logs them.
        print(f"[DQL] parse error: {exc} -- query={effective_query!r}")
        return []

    # Pool size: generate enough records to make filtering meaningful even
    # when the filter is restrictive. We cap at 5x the requested limit.
    span_seconds = max(1, (to_ms - from_ms) // 1000)
    pool_size = min(max(limit * 5, 50), max(50, span_seconds // 2))

    rng = random.Random(f"{from_ms}-{to_ms}")  # deterministic per range
    pool = []
    for i in range(pool_size):
        ts_ms = from_ms + int((to_ms - from_ms) * (i / max(1, pool_size)))
        ts_ms += rng.randint(0, 999)

        sev, template = rng.choice(LOG_TEMPLATES)
        host = rng.choice(HOSTS)
        service = rng.choice(SERVICES)
        namespace = rng.choice(NAMESPACES)
        source = rng.choice(LOG_SOURCES)

        record = {
            "timestamp": _iso(ts_ms),
            "content": _fmt_line(template),
            "status": sev,
            "loglevel": sev,
            "host.name": host,
            "dt.entity.host": f"HOST-{abs(hash(host)) % 10**12:012X}",
            "log.source": source,
            "service.name": service,
            "k8s.namespace.name": namespace,
            "dt.source_entity": f"PROCESS_GROUP_INSTANCE-{abs(hash(service)) % 10**12:012X}",
        }
        pool.append(record)

    # Apply DQL filter
    filtered = [r for r in pool if compiled.predicate(r)]

    # Apply DQL sort if present (otherwise the route does the default sort)
    if compiled.sort is not None:
        sort_field, descending = compiled.sort
        filtered.sort(key=lambda r: r.get(sort_field, ""), reverse=descending)

    # Apply effective limit: smaller of DQL limit and HTTP limit
    effective_limit = limit
    if compiled.limit is not None:
        effective_limit = min(effective_limit, compiled.limit)
    return filtered[:effective_limit]
