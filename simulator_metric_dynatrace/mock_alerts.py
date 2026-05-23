"""
Mock data generator for the Dynatrace Problems / Alerts V2 API simulator.

Simulates the response format of:
    GET /api/v2/problems
    GET /api/v2/problems/{problemId}

Each record mirrors the fields Dynatrace SaaS returns for the
`problems` endpoint (a subset relevant to typical dashboards):

    problemId, displayId, title, status, severityLevel, impactLevel,
    startTime, endTime, affectedEntities, impactedEntities,
    rootCauseEntity, managementZones, entityTags, problemFilters,
    recentComments

Filtering supports both Dynatrace's `problemSelector` mini-DSL and the
DQL pipeline form (`fetch dt.davis.problems | filter ... | sort ... |
limit N`), reusing the parser from `dql.py`.
"""

from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Catalogue                                                                   #
# --------------------------------------------------------------------------- #

SEVERITIES = [
    "AVAILABILITY",
    "ERROR",
    "PERFORMANCE",
    "RESOURCE_CONTENTION",
    "CUSTOM_ALERT",
    "MONITORING_UNAVAILABLE",
    "INFO",
]

IMPACT_LEVELS = ["INFRASTRUCTURE", "SERVICES", "APPLICATION", "ENVIRONMENT"]
STATUSES = ["OPEN", "CLOSED"]

TITLES = [
    ("AVAILABILITY",          "Service unavailable - {service}"),
    ("ERROR",                 "Failure rate increase on {service}"),
    ("PERFORMANCE",           "Response time degradation on {service}"),
    ("RESOURCE_CONTENTION",   "High CPU usage on {host}"),
    ("RESOURCE_CONTENTION",   "Memory exhausted on {host}"),
    ("CUSTOM_ALERT",          "Custom threshold exceeded for {metric}"),
    ("MONITORING_UNAVAILABLE","OneAgent connection lost on {host}"),
    ("INFO",                  "Maintenance window started on {host}"),
]

HOSTS = ["host-prod-01", "host-prod-02", "host-stage-01", "host-dev-01"]
SERVICES = ["api-gateway", "auth-service", "billing-service", "order-service", "frontend"]
METRICS = ["builtin:host.cpu.usage", "builtin:service.errors.total", "custom:queue.depth"]
MANAGEMENT_ZONES = ["Production", "Staging", "Development", "PCI"]
TAGS_POOL = [
    {"key": "env",     "value": "prod"},
    {"key": "env",     "value": "stage"},
    {"key": "env",     "value": "dev"},
    {"key": "team",    "value": "payments"},
    {"key": "team",    "value": "platform"},
    {"key": "tier",    "value": "frontend"},
    {"key": "tier",    "value": "backend"},
]


# --------------------------------------------------------------------------- #
# Generation                                                                  #
# --------------------------------------------------------------------------- #

def _entity_ref(entity_type: str, name: str) -> Dict[str, Any]:
    return {
        "entityId": {
            "id": f"{entity_type}-{abs(hash(name)) % 10**12:012X}",
            "type": entity_type,
        },
        "name": name,
    }


def generate_problems(from_ms: int, to_ms: int, seed_count: int = 200) -> List[Dict[str, Any]]:
    """
    Build a deterministic pool of problem records whose `startTime` falls
    inside [from_ms, to_ms]. ~30% are OPEN (endTime == -1), the rest closed.
    """
    if to_ms <= from_ms:
        return []

    rng = random.Random(f"problems-{from_ms}-{to_ms}")
    pool: List[Dict[str, Any]] = []

    for i in range(seed_count):
        sev, title_tmpl = rng.choice(TITLES)
        host = rng.choice(HOSTS)
        service = rng.choice(SERVICES)
        metric = rng.choice(METRICS)
        title = title_tmpl.format(host=host, service=service, metric=metric)

        start = from_ms + int((to_ms - from_ms) * rng.random())
        is_open = rng.random() < 0.3
        duration = rng.randint(60_000, 3_600_000)
        end = -1 if is_open else min(to_ms, start + duration)
        status = "OPEN" if is_open else "CLOSED"

        impact = rng.choice(IMPACT_LEVELS)
        mz = rng.sample(MANAGEMENT_ZONES, k=rng.randint(1, 2))
        tags = rng.sample(TAGS_POOL, k=rng.randint(1, 3))

        host_ref = _entity_ref("HOST", host)
        svc_ref = _entity_ref("SERVICE", service)

        affected = [host_ref] if "host" in title_tmpl else [svc_ref]
        impacted = [svc_ref, host_ref] if rng.random() < 0.5 else [svc_ref]
        root = host_ref if "host" in title_tmpl else svc_ref

        problem_id = f"{start * 1000 + i:020d}_v2"
        display_id = f"P-{(23000 + i):05d}"

        pool.append({
            "problemId":        problem_id,
            "displayId":        display_id,
            "title":            title,
            "status":           status,
            "severityLevel":    sev,
            "impactLevel":      impact,
            "startTime":        start,
            "endTime":          end,
            "affectedEntities": affected,
            "impactedEntities": impacted,
            "rootCauseEntity":  root,
            "managementZones":  [{"id": str(abs(hash(z)) % 10**10), "name": z} for z in mz],
            "entityTags":       [
                {"context": "CONTEXTLESS", "key": t["key"], "value": t["value"],
                 "stringRepresentation": f"{t['key']}:{t['value']}"}
                for t in tags
            ],
            "problemFilters":   [{"id": "default", "name": "default"}],
            "recentComments":   {"totalCount": 0, "comments": [], "nextPageKey": None},
            # convenience flat fields used by DQL filtering (event-style names)
            "event.status":     status,
            "event.kind":       "DAVIS_PROBLEM",
            "event.severity":   sev,
            "host.name":        host,
            "service.name":     service,
            "tags":             [f"{t['key']}:{t['value']}" for t in tags],
        })

    pool.sort(key=lambda p: p["startTime"])
    return pool


# --------------------------------------------------------------------------- #
# problemSelector parser                                                      #
# --------------------------------------------------------------------------- #

# Dynatrace's `problemSelector` is a comma-separated list of clauses such as:
#   status("OPEN")
#   severityLevel("ERROR","AVAILABILITY")
#   text("response time")
#   impactLevel("SERVICES")
#   entityTags("env:prod","team:payments")
#   managementZones("Production")
#
# Clauses are combined with AND.

_CLAUSE_RE = re.compile(r"""
    ([A-Za-z_][A-Za-z_0-9]*)
    \(
        ([^)]*)
    \)
""", re.VERBOSE)

_ARG_RE = re.compile(r'"([^"]*)"|\'([^\']*)\'|([^,\s]+)')


def _parse_args(raw: str) -> List[str]:
    args = []
    for m in _ARG_RE.finditer(raw):
        args.append(m.group(1) or m.group(2) or m.group(3))
    return [a for a in args if a]


def compile_problem_selector(selector: str):
    """
    Compile a Dynatrace problemSelector string into a predicate function.
    Returns a predicate that defaults to True for an empty selector.
    """
    if not selector or not selector.strip():
        return lambda p: True

    predicates = []
    for m in _CLAUSE_RE.finditer(selector):
        name = m.group(1).lower()
        args = _parse_args(m.group(2))
        if not args:
            continue

        if name == "status":
            wanted = {a.upper() for a in args}
            predicates.append(lambda p, w=wanted: p["status"] in w)
        elif name == "severitylevel":
            wanted = {a.upper() for a in args}
            predicates.append(lambda p, w=wanted: p["severityLevel"] in w)
        elif name == "impactlevel":
            wanted = {a.upper() for a in args}
            predicates.append(lambda p, w=wanted: p["impactLevel"] in w)
        elif name == "text":
            needle = args[0].lower()
            predicates.append(lambda p, n=needle: n in p["title"].lower())
        elif name == "entitytags":
            wanted = set(args)
            predicates.append(lambda p, w=wanted: bool(w & set(p["tags"])))
        elif name == "managementzones":
            wanted = {a.lower() for a in args}
            predicates.append(
                lambda p, w=wanted: any(mz["name"].lower() in w for mz in p["managementZones"])
            )
        elif name == "displayids":
            wanted = set(args)
            predicates.append(lambda p, w=wanted: p["displayId"] in w)
        elif name == "problemid":
            wanted = set(args)
            predicates.append(lambda p, w=wanted: p["problemId"] in w)
        # Unknown clauses are silently ignored (forward-compatibility).

    if not predicates:
        return lambda p: True
    return lambda p: all(fn(p) for fn in predicates)


def is_dql_query(selector: str) -> bool:
    """True if the selector looks like a DQL pipeline rather than a problemSelector."""
    if not selector:
        return False
    s = selector.strip().lower()
    return s.startswith("fetch") or "|" in s


def filter_problems(pool: List[Dict[str, Any]], *,
                    problem_selector: str = "",
                    dql_query: str = "",
                    from_ms: Optional[int] = None,
                    to_ms: Optional[int] = None,
                    sort_field: str = "startTime",
                    sort_desc: bool = True,
                    limit: int = 50) -> List[Dict[str, Any]]:
    """
    Apply `problemSelector` (Dynatrace mini-DSL) and/or DQL filter, time
    window, sort and limit to `pool`.
    """
    results = list(pool)

    # Time-window filter: a problem matches when its open interval overlaps the
    # requested window. An OPEN problem (endTime == -1) extends to "now".
    if from_ms is not None and to_ms is not None:
        def in_window(p):
            start = p["startTime"]
            end = p["endTime"] if p["endTime"] != -1 else to_ms
            return start <= to_ms and end >= from_ms
        results = [p for p in results if in_window(p)]

    if problem_selector:
        pred = compile_problem_selector(problem_selector)
        results = [p for p in results if pred(p)]

    if dql_query:
        from dql import compile_query
        compiled = compile_query(dql_query)
        results = [p for p in results if compiled.predicate(p)]
        if compiled.sort is not None:
            sort_field, sort_desc = compiled.sort[0], compiled.sort[1]
        if compiled.limit is not None:
            limit = min(limit, compiled.limit)

    results.sort(key=lambda p: p.get(sort_field, 0), reverse=sort_desc)
    return results[:limit]
