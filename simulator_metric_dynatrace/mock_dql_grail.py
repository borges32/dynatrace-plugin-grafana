"""
Simulator for the Dynatrace Grail DQL endpoints:

    POST /platform/storage/query/v1/query:execute
    GET  /platform/storage/query/v1/query:poll?request-token=...

The real Dynatrace platform runs DQL asynchronously: `query:execute` returns
a `requestToken`, and the client polls `query:poll` until `state` is
`SUCCEEDED`. This simulator follows the same flow but completes the query
in-memory in microseconds, so a single poll is enough.

DQL sources understood by this simulator:

    fetch logs                 -> uses the same generator as /api/v2/logs/search
    fetch events               -> alias for "dt.davis.problems"
    fetch dt.davis.problems    -> uses the alerts generator

The DQL pipeline (`| filter`, `| sort`, `| limit`, `| fields`) is parsed by
`dql.compile_query` (the same parser used by the legacy log search endpoint).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Tuple

from dql import compile_query, CompiledQuery
from mock_logs import generate_log_records
from mock_alerts import generate_problems


# In-memory store of pending/completed queries.
# Keyed by requestToken. Each value: {"state": "...", "records": [...], "src": "logs|problems"}
_QUERY_STORE: Dict[str, Dict[str, Any]] = {}


def _detect_source(query: str) -> str:
    """Return 'logs' or 'problems' based on the `fetch <source>` clause."""
    q = (query or '').strip().lower()
    if not q.startswith('fetch'):
        return 'logs'
    after = q[len('fetch'):].strip().split('|', 1)[0].strip()
    # take first whitespace token as source name
    src = after.split()[0] if after else 'logs'
    if src in ('logs',):
        return 'logs'
    if src in ('events', 'dt.davis.problems', 'dt.davis.events'):
        return 'problems'
    # default to logs for unknown sources
    return 'logs'


def _strip_fetch(query: str) -> str:
    """Drop the leading `fetch <source>` so dql.compile_query can build a predicate."""
    q = (query or '').strip()
    if q.lower().startswith('fetch'):
        # find first pipe
        idx = q.find('|')
        if idx == -1:
            return 'fetch logs'  # nothing to filter on, parser handles it
        return 'fetch logs ' + q[idx:]  # rewrite source uniformly
    return q


def _execute_dql(query: str, from_ms: int, to_ms: int, limit: int = 1000) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Run a DQL query and return (records, types) where types is a list of
    column descriptors like `[{"name": "timestamp", "type": "timestamp"}, ...]`,
    matching the shape of the real Grail response.
    """
    src = _detect_source(query)
    normalized = _strip_fetch(query)

    if src == 'logs':
        # The logs generator already understands the same DQL parser, so just
        # delegate to it (it will apply filter/sort/limit from the pipeline).
        records = generate_log_records(from_ms, to_ms, limit=limit, query=normalized)
        types = [
            {"name": "timestamp",          "type": "timestamp"},
            {"name": "content",            "type": "string"},
            {"name": "status",             "type": "string"},
            {"name": "loglevel",           "type": "string"},
            {"name": "host.name",          "type": "string"},
            {"name": "service.name",       "type": "string"},
            {"name": "k8s.namespace.name", "type": "string"},
            {"name": "log.source",         "type": "string"},
            {"name": "dt.entity.host",     "type": "string"},
        ]
        return records, types

    # Problems source
    pool = generate_problems(from_ms, to_ms)
    compiled: CompiledQuery = compile_query(normalized)
    rows = [p for p in pool if compiled.predicate(p)]

    sort_field, descending = ("startTime", True)
    if compiled.sort is not None:
        sort_field, descending = compiled.sort
    rows.sort(key=lambda p: p.get(sort_field, 0), reverse=descending)

    effective_limit = limit
    if compiled.limit is not None:
        effective_limit = min(effective_limit, compiled.limit)
    rows = rows[:effective_limit]

    # Project the flat columns most consumers will want
    projected = []
    for p in rows:
        projected.append({
            "timestamp":       p["startTime"],
            "displayId":       p["displayId"],
            "problemId":       p["problemId"],
            "title":           p["title"],
            "status":          p["status"],
            "severityLevel":   p["severityLevel"],
            "impactLevel":     p["impactLevel"],
            "host.name":       p.get("host.name"),
            "service.name":    p.get("service.name"),
            "event.kind":      "DAVIS_PROBLEM",
        })
    types = [
        {"name": "timestamp",     "type": "timestamp"},
        {"name": "displayId",     "type": "string"},
        {"name": "problemId",     "type": "string"},
        {"name": "title",         "type": "string"},
        {"name": "status",        "type": "string"},
        {"name": "severityLevel", "type": "string"},
        {"name": "impactLevel",   "type": "string"},
        {"name": "host.name",     "type": "string"},
        {"name": "service.name",  "type": "string"},
        {"name": "event.kind",    "type": "string"},
    ]
    return projected, types


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #

def start_query(query: str, from_ms: int, to_ms: int, limit: int = 1000) -> str:
    """
    Execute the query in-memory and return a requestToken. The result is
    stashed under the token so `poll_query` can retrieve it.
    """
    try:
        records, types = _execute_dql(query, from_ms, to_ms, limit=limit)
        token = f"dt-{uuid.uuid4().hex[:24]}"
        _QUERY_STORE[token] = {
            "state": "SUCCEEDED",
            "records": records,
            "types": types,
            "createdAt": int(time.time() * 1000),
        }
        return token
    except ValueError as exc:
        token = f"dt-{uuid.uuid4().hex[:24]}"
        _QUERY_STORE[token] = {
            "state": "FAILED",
            "error": {"code": 400, "message": f"DQL parse error: {exc}"},
            "createdAt": int(time.time() * 1000),
        }
        return token


def poll_query(token: str) -> Dict[str, Any]:
    """
    Return the polling envelope for the given token. Unknown tokens yield
    a NOT_STARTED state. Once a record is returned with state==SUCCEEDED it
    stays available; in real Dynatrace results expire after some minutes.
    """
    entry = _QUERY_STORE.get(token)
    if entry is None:
        return {"state": "NOT_STARTED"}

    if entry["state"] == "FAILED":
        return {"state": "FAILED", "error": entry["error"]}

    return {
        "state": "SUCCEEDED",
        "result": {
            "records": entry["records"],
            "types":   entry["types"],
            "metadata": {
                "grail": {
                    "scannedRecords":   len(entry["records"]),
                    "scannedBytes":     sum(len(str(r)) for r in entry["records"]),
                    "executionTimeMilliseconds": 1,
                }
            },
        },
    }
