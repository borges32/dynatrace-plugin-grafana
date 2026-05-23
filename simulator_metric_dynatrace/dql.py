"""
Minimal Dynatrace Query Language (DQL) parser for the logs simulator.

Goal: be faithful enough to the real DQL syntax that the documented log
queries in QUERY_EXAMPLES.md actually run against the simulator, without
trying to be a complete implementation of the language.

Supported grammar (EBNF-ish):

    pipeline   := source { "|" stage }
    source     := "fetch" identifier         (e.g. "fetch logs")  -- optional
    stage      := "filter" expression
                | "sort"   field [asc|desc]
                | "limit"  integer

    expression := orExpr
    orExpr     := andExpr { "or" andExpr }
    andExpr    := notExpr { "and" notExpr }
    notExpr    := ["not"] primary
    primary    := "(" expression ")"
                | functionCall
                | comparison
                | bareTerm                  -- a single word -> contains(content, "word")

    comparison := field op literal
    op         := "==" | "!=" | "<" | "<=" | ">" | ">="

    functionCall := name "(" [args] ")"
        contains(field, "x")          -> case-insensitive substring
        matchesPhrase(field, "x")     -> case-insensitive substring (alias)
        startsWith(field, "x")        -> prefix
        endsWith(field, "x")          -> suffix
        in(field, "a", "b", ...)      -> membership

    field      := identifier ("." identifier)*    (e.g. host.name)
    literal    := string | number

The parser also accepts legacy/simplified inputs used by previous versions:
    - bare word                  -> contains(content, "word")
    - "key=value" or 'key="value"' (unquoted RHS allowed) -> "key" == "value"

Returns a `CompiledQuery` object with:
    - predicate(record) -> bool          (filter)
    - sort: (field, descending) | None
    - limit: int | None
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple


# --------------------------------------------------------------------------- #
# Tokenizer                                                                   #
# --------------------------------------------------------------------------- #

_TOKEN_RE = re.compile(
    r"""
    \s+                                  |   # whitespace (skipped)
    (?P<STRING>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')   |
    (?P<NUMBER>\d+(?:\.\d+)?)            |
    (?P<OP>==|!=|<=|>=|<|>|=)            |
    (?P<PIPE>\|)                         |
    (?P<LPAREN>\()                       |
    (?P<RPAREN>\))                       |
    (?P<COMMA>,)                         |
    (?P<IDENT>[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*)
    """,
    re.VERBOSE,
)


@dataclass
class Token:
    kind: str
    value: str


def tokenize(src: str) -> List[Token]:
    tokens: List[Token] = []
    pos = 0
    while pos < len(src):
        m = _TOKEN_RE.match(src, pos)
        if not m:
            raise ValueError(f"DQL syntax error near {src[pos:pos+20]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind is None:  # whitespace
            continue
        value = m.group(kind)
        if kind == "STRING":
            # strip quotes and unescape simple sequences
            quote = value[0]
            inner = value[1:-1]
            inner = inner.replace("\\" + quote, quote).replace("\\\\", "\\")
            tokens.append(Token("STRING", inner))
        else:
            tokens.append(Token(kind, value))
    return tokens


# --------------------------------------------------------------------------- #
# AST → predicate                                                             #
# --------------------------------------------------------------------------- #

Predicate = Callable[[dict], bool]


def _get_field(rec: dict, field_name: str) -> Any:
    if field_name in rec:
        return rec[field_name]
    # also accept the "log." prefix used in some DQL examples
    if field_name.startswith("log."):
        return rec.get(field_name[4:])
    return None


def _coerce(value: Any) -> Any:
    if isinstance(value, str):
        # try numeric coercion for comparisons against numbers
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
    return value


def _make_cmp(field_name: str, op: str, literal: Any) -> Predicate:
    def pred(rec: dict) -> bool:
        lhs = _get_field(rec, field_name)
        if lhs is None:
            return False
        rhs = literal
        # for ordered comparisons attempt numeric coercion on both sides
        if op in ("<", "<=", ">", ">="):
            lhs_n, rhs_n = _coerce(lhs), _coerce(rhs)
            try:
                return {
                    "<":  lhs_n <  rhs_n,
                    "<=": lhs_n <= rhs_n,
                    ">":  lhs_n >  rhs_n,
                    ">=": lhs_n >= rhs_n,
                }[op]
            except TypeError:
                return False
        # equality / inequality: stringified comparison so types don't matter
        a, b = str(lhs), str(rhs)
        if op in ("==", "="):
            return a == b
        if op == "!=":
            return a != b
        return False
    return pred


def _make_func(name: str, args: List[Any]) -> Predicate:
    name = name.lower()
    if name in ("contains", "matchesphrase"):
        if len(args) != 2:
            raise ValueError(f"{name}() expects 2 arguments")
        field_name, needle = args
        needle = str(needle).lower()

        def pred(rec: dict) -> bool:
            v = _get_field(rec, field_name)
            return v is not None and needle in str(v).lower()
        return pred

    if name == "startswith":
        field_name, needle = args
        needle = str(needle).lower()

        def pred(rec: dict) -> bool:
            v = _get_field(rec, field_name)
            return v is not None and str(v).lower().startswith(needle)
        return pred

    if name == "endswith":
        field_name, needle = args
        needle = str(needle).lower()

        def pred(rec: dict) -> bool:
            v = _get_field(rec, field_name)
            return v is not None and str(v).lower().endswith(needle)
        return pred

    if name == "in":
        if len(args) < 2:
            raise ValueError("in() expects at least 2 arguments")
        field_name = args[0]
        choices = {str(a) for a in args[1:]}

        def pred(rec: dict) -> bool:
            v = _get_field(rec, field_name)
            return v is not None and str(v) in choices
        return pred

    raise ValueError(f"Unsupported DQL function: {name}()")


# --------------------------------------------------------------------------- #
# Parser                                                                      #
# --------------------------------------------------------------------------- #


@dataclass
class CompiledQuery:
    predicate: Predicate = field(default=lambda rec: True)
    sort: Optional[Tuple[str, bool]] = None   # (field, descending)
    limit: Optional[int] = None


class _Parser:
    def __init__(self, tokens: List[Token]):
        self.toks = tokens
        self.pos = 0

    # ---- token helpers ---------------------------------------------------- #

    def _peek(self, offset: int = 0) -> Optional[Token]:
        i = self.pos + offset
        return self.toks[i] if 0 <= i < len(self.toks) else None

    def _eat(self, kind: str, value: Optional[str] = None) -> Token:
        tok = self._peek()
        if tok is None or tok.kind != kind or (value is not None and tok.value.lower() != value.lower()):
            expected = f"{kind}={value!r}" if value else kind
            got = f"{tok.kind}={tok.value!r}" if tok else "EOF"
            raise ValueError(f"DQL parse error: expected {expected}, got {got}")
        self.pos += 1
        return tok

    def _accept_keyword(self, *words: str) -> Optional[Token]:
        tok = self._peek()
        if tok and tok.kind == "IDENT" and tok.value.lower() in {w.lower() for w in words}:
            self.pos += 1
            return tok
        return None

    # ---- top-level pipeline ---------------------------------------------- #

    def parse(self) -> CompiledQuery:
        q = CompiledQuery(predicate=lambda rec: True)

        # optional "fetch <identifier>"
        if self._accept_keyword("fetch"):
            # consume the source name (e.g. "logs", "events")
            if self._peek() and self._peek().kind == "IDENT":
                self.pos += 1

        # zero or more "| stage"
        while self._peek() is not None:
            self._eat("PIPE")
            kw = self._eat("IDENT").value.lower()
            if kw == "filter":
                pred = self._parse_expression()
                prev = q.predicate
                q.predicate = lambda rec, prev=prev, pred=pred: prev(rec) and pred(rec)
            elif kw == "sort":
                # sort <field> [asc|desc] [, ...] -- only the first key is used
                sort_field = self._read_field()
                desc = True
                tok = self._accept_keyword("asc", "desc")
                if tok:
                    desc = (tok.value.lower() == "desc")
                # consume any extra comma-separated keys (ignored)
                while self._peek() and self._peek().kind == "COMMA":
                    self.pos += 1
                    self._read_field()
                    self._accept_keyword("asc", "desc")
                q.sort = (sort_field, desc)
            elif kw == "limit":
                ntok = self._eat("NUMBER")
                q.limit = int(float(ntok.value))
            elif kw in ("fields", "fieldsadd", "fieldsremove", "summarize", "parse"):
                # Tolerate but ignore unsupported pipeline stages: consume
                # until the next pipe or EOF.
                while self._peek() and self._peek().kind != "PIPE":
                    self.pos += 1
            else:
                raise ValueError(f"Unsupported DQL stage: {kw}")

        return q

    # ---- expression grammar ---------------------------------------------- #

    def _parse_expression(self) -> Predicate:
        return self._parse_or()

    def _parse_or(self) -> Predicate:
        left = self._parse_and()
        while self._accept_keyword("or"):
            right = self._parse_and()
            left = (lambda l, r: (lambda rec: l(rec) or r(rec)))(left, right)
        return left

    def _parse_and(self) -> Predicate:
        left = self._parse_not()
        while self._accept_keyword("and"):
            right = self._parse_not()
            left = (lambda l, r: (lambda rec: l(rec) and r(rec)))(left, right)
        return left

    def _parse_not(self) -> Predicate:
        if self._accept_keyword("not"):
            inner = self._parse_primary()
            return lambda rec: not inner(rec)
        return self._parse_primary()

    def _parse_primary(self) -> Predicate:
        tok = self._peek()
        if tok is None:
            raise ValueError("DQL: unexpected end of input")

        # parenthesized
        if tok.kind == "LPAREN":
            self.pos += 1
            inner = self._parse_expression()
            self._eat("RPAREN")
            return inner

        # function call: IDENT followed by LPAREN
        if tok.kind == "IDENT" and self._peek(1) and self._peek(1).kind == "LPAREN":
            name = tok.value
            self.pos += 2  # consume name + (
            args: List[Any] = []
            if self._peek() and self._peek().kind != "RPAREN":
                args.append(self._read_arg())
                while self._peek() and self._peek().kind == "COMMA":
                    self.pos += 1
                    args.append(self._read_arg())
            self._eat("RPAREN")
            return _make_func(name, args)

        # comparison: field op literal
        if tok.kind == "IDENT":
            field_name = self._read_field()
            op_tok = self._peek()
            if op_tok and op_tok.kind == "OP":
                self.pos += 1
                lit = self._read_literal()
                return _make_cmp(field_name, op_tok.value, lit)
            # bare identifier with no operator -> contains(content, value)
            return _make_func("contains", ["content", field_name])

        if tok.kind == "STRING":
            self.pos += 1
            return _make_func("contains", ["content", tok.value])

        raise ValueError(f"DQL: unexpected token {tok.kind}={tok.value!r}")

    # ---- helpers --------------------------------------------------------- #

    def _read_field(self) -> str:
        tok = self._eat("IDENT")
        return tok.value

    def _read_literal(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise ValueError("DQL: expected literal")
        if tok.kind == "STRING":
            self.pos += 1
            return tok.value
        if tok.kind == "NUMBER":
            self.pos += 1
            v = tok.value
            return float(v) if "." in v else int(v)
        if tok.kind == "IDENT":
            # bareword RHS (e.g. status=ERROR) - treat as string
            self.pos += 1
            return tok.value
        raise ValueError(f"DQL: expected literal, got {tok.kind}={tok.value!r}")

    def _read_arg(self) -> Any:
        tok = self._peek()
        if tok and tok.kind == "STRING":
            self.pos += 1
            return tok.value
        if tok and tok.kind == "NUMBER":
            self.pos += 1
            return float(tok.value) if "." in tok.value else int(tok.value)
        if tok and tok.kind == "IDENT":
            # an identifier inside a function call is interpreted as a field name
            return self._read_field()
        raise ValueError(f"DQL: invalid argument token {tok}")


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #


def compile_query(query: str) -> CompiledQuery:
    """
    Compile a DQL (or simplified) query string into a CompiledQuery.

    An empty query matches everything.
    """
    if query is None:
        return CompiledQuery()
    src = query.strip()
    if not src:
        return CompiledQuery()

    # Heuristic: if the query doesn't look like a pipeline, wrap it as a
    # filter expression so legacy callers can still write `status=ERROR`
    # or `host.name="x" service.name="y"` directly.
    looks_like_pipeline = src.lower().startswith("fetch") or "|" in src
    if not looks_like_pipeline:
        # Translate "k1=v1 k2=v2 word" into "k1==v1 and k2==v2 and word"
        # by inserting "and" between top-level whitespace-separated clauses.
        src = _wrap_simple_query(src)

    tokens = tokenize(src)
    parser = _Parser(tokens)
    return parser.parse()


_SIMPLE_CLAUSE_RE = re.compile(
    r"""
    (?:
        [\w\.]+ \s* = \s* (?:"[^"]*"|'[^']*'|[^\s]+)   |
        "[^"]*"                                       |
        '[^']*'                                       |
        [^\s]+
    )
    """,
    re.VERBOSE,
)


def _wrap_simple_query(src: str) -> str:
    """Convert a simplified inline query into a pipeline.

    Examples:
        'status=ERROR'                       -> 'fetch logs | filter status == ERROR'
        'host.name="x" service.name="y" foo' -> 'fetch logs | filter host.name == "x" and service.name == "y" and foo'
        'timeout'                            -> 'fetch logs | filter timeout'

    Each `=` is upgraded to `==` so the regular parser handles it uniformly.
    """
    clauses = _SIMPLE_CLAUSE_RE.findall(src)
    # Upgrade single "=" to "==" only when used as comparison (not inside strings)
    upgraded = [re.sub(r"(?<![=!<>])=(?!=)", "==", c) for c in clauses]
    if not upgraded:
        return src
    return "fetch logs | filter " + " and ".join(upgraded)
