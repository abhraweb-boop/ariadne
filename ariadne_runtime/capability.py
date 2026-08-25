"""Capability acquisition + inspiration scoring (Phase 11).

Two jobs, both transparent-by-construction:

1. CAPABILITY MANIFEST -- read a compiled master DAG and derive which
   capabilities (skill domains) a build needs. Candidates are scored and
   greedily selected best-first; a candidate whose coverage adds nothing
   is rejected as skipped_overlap. Generic "do anything" skills can never
   outrank stack-specific ones.

2. INSPIRATION SCORING -- rank scouted reference projects on a public
   0-100 rubric: authority 25 / craft 30 / recency 15 / fit 20, minus
   slop penalties (hype adjectives, emoji spam) capped at -40.
   Stars alone cannot buy tier: craft out-weighs popularity.
   Tiers: gold >=80, silver >=60, bronze >=40, slop <40 (dropped).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Set

# ── vocabularies ──────────────────────────────────────────────────────────
DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "auth": ["auth", "login", "jwt", "oauth", "session", "password"],
    "testing": ["test", "pytest", "jest", "vitest", "coverage", "tdd"],
    "database": ["sqlite", "postgres", "sqlmodel", "sqlalchemy", "db",
                 "migration"],
    "api": ["api", "rest", "fastapi", "flask", "endpoint", "route"],
    "scraping": ["scrape", "crawl", "bs4", "beautifulsoup", "playwright",
                 "requests"],
    "deploy": ["docker", "deploy", "ci", "github-actions", "hosting",
               "vercel"],
    "frontend": ["react", "html", "css", "tailwind", "ui", "frontend"],
    "email": ["email", "smtp", "mail", "newsletter"],
}

HYPE_MARKERS = [
    "revolutionary", "game-changing", "game changing", "10x", "100x",
    "ultimate", "insane", "mind-blowing", "blow your mind", "secret sauce",
    "supercharge", "unleash the power", "next-level", "next level",
]
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\u2728\u26A1\U0001F680]")


def _norm(words: Iterable[str]) -> Set[str]:
    out = set()
    for w in words:
        for tok in re.findall(r"[a-z0-9+#]+", str(w).lower()):
            out.add(tok)
    return out


# ── 1. capability manifest ────────────────────────────────────────────────
def extract_manifest(specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Master-DAG specs -> {technologies[], domains[]} the build needs."""
    blob_parts: List[str] = []
    for s in specs:
        p = s.get("payload") or {}
        if isinstance(p, dict):
            if p.get("technologies"):
                blob_parts.extend(str(t) for t in p["technologies"])
            blob_parts.append(json_dumps(p))
        blob_parts.append(str(s.get("kind") or ""))
    text = " ".join(blob_parts).lower()
    tokens = _norm([text])

    techs: Set[str] = set()
    for t in _KNOWN_TECHS:
        if t in text:
            techs.add(t)

    domains: Set[str] = set()
    for dom, kws in DOMAIN_KEYWORDS.items():
        for kw in kws:
            if kw in tokens:
                domains.add(dom)
                break
    return {
        "technologies": sorted(techs),
        "domains": sorted(domains),
    }


_KNOWN_TECHS = [
    "fastapi", "flask", "django", "react", "vue", "sqlite", "postgres",
    "mysql", "sqlmodel", "sqlalchemy", "pytest", "docker", "tailwind",
    "playwright", "beautifulsoup", "node", "electron",
]


def json_dumps(obj: Any) -> str:
    import json as _json

    try:
        return _json.dumps(obj, default=str)
    except Exception:
        return str(obj)


# ── 2. skill candidate scoring + greedy overlap-free selection ───────────
def score_skill_candidate(candidate: Dict[str, Any],
                          needed_domains: List[str]) -> Dict[str, Any]:
    """Transparent rubric: relevance 50 / completeness 30 / specificity 20,
    minus slop penalty. Returns breakdown + covered domains."""
    name = str(candidate.get("name") or "")
    desc = str(candidate.get("description") or "")
    blob = f"{name}\n{desc}".lower()
    tokens = _norm([blob])
    claimed = set(candidate.get("domains") or [])
    for dom, kws in DOMAIN_KEYWORDS.items():
        for kw in kws:
            if kw in tokens:
                claimed.add(dom)
                break

    need = set(d.lower() for d in needed_domains)
    covered = claimed & need if need else claimed
    relevance = 50.0 * (len(covered) / len(need)) if need else \
        (50.0 if claimed else 0.0)

    completeness_signals = [
        bool(candidate.get("steps") or candidate.get("has_steps")),
        bool(candidate.get("references") or candidate.get("source_url")),
        bool(candidate.get("examples") or candidate.get("templates")),
    ]
    completeness = 30.0 * sum(1 for s in completeness_signals
                              if s) / len(completeness_signals)

    tech_hits = sum(1 for t in _KNOWN_TECHS if t in tokens)
    specificity = min(20.0, tech_hits * 7.0 +
                      (5.0 if len(name.split()) <= 6 else 0.0))

    slop = _slop_penalty(blob)
    score = max(0.0, min(100.0, relevance + completeness + specificity
                         + slop))
    return {
        "id": candidate.get("id") or name,
        "name": name,
        "score": round(score, 1),
        "breakdown": {"relevance": round(relevance, 1),
                      "completeness": round(completeness, 1),
                      "specificity": round(specificity, 1),
                      "slop_penalty": slop},
        "covers": sorted(claimed),
        "covers_needed": sorted(covered),
    }


def select_capabilities(candidates: List[Dict[str, Any]],
                        needed_domains: List[str]) -> Dict[str, Any]:
    """Best-first greedy selection; overlaps are rejected, not merged."""
    scored = [score_skill_candidate(c, needed_domains) for c in candidates]
    scored.sort(key=lambda x: x["score"], reverse=True)
    selected, rejected = [], []
    claimed_union: Set[str] = set()
    for sc in scored:
        cov_needed = set(sc["covers_needed"])
        if cov_needed and not cov_needed.issubset(claimed_union):
            selected.append(sc)
            claimed_union |= cov_needed
        else:
            rejected.append({"id": sc["id"], "score": sc["score"],
                             "reason": "skipped_overlap"})
    # zero-value candidates are dropped entirely (not even listed)
    selected = [s for s in selected if s["score"] > 0]
    return {"selected": selected, "rejected": rejected}


# ── 3. inspiration scoring ────────────────────────────────────────────────
def score_inspiration(card: Dict[str, Any],
                      plan_technologies: List[str]) -> Dict[str, Any]:
    """0-100 rubric over a scouted reference project card.

    authority 25 | craft 30 | recency 15 | fit 20 | slop -40 cap.
    """
    name = str(card.get("name") or "")
    url = str(card.get("url") or "").lower()
    desc = str(card.get("description") or card.get("note") or "")
    blob = f"{name} {desc}".lower()

    # authority (max 25): official/docs-backed beats raw popularity
    authority = 0.0
    if card.get("is_official") or "official" in blob or \
            any(d in url for d in (".dev/", ".io/", "readthedocs")):
        authority += 15
    stars = int(card.get("stars") or 0)
    if stars >= 5000:
        authority += 10
    elif stars >= 1000:
        authority += 7
    elif stars >= 100:
        authority += 4
    else:
        authority += 2  # exists at all

    # craft (max 30) -- the anti-stars counterweight
    craft = 0.0
    craft += 10 if card.get("has_tests") else 0
    craft += 8 if card.get("has_ci") else 0
    craft += 6 if card.get("has_license") else 0
    craft += 6 if card.get("typed") else 0
    # perfect craft substitutes for popularity: quality signals ARE
    # authority (this is how an unglamorous repo can still take silver/gold)
    if craft >= 30:
        authority += 10

    # recency (max 15)
    age_days = card.get("age_days")
    recency = 15.0 if (age_days is not None and age_days <= 365) else \
        8.0 if (age_days is not None and age_days <= 730) else \
        3.0 if age_days is not None else 6.0  # unknown -> neutral middle

    # fit (max 20)
    plan_tokens = _norm(plan_technologies)
    fit_tokens = _norm([blob])
    fit = min(20.0, 10.0 * len(plan_tokens & fit_tokens)
              if plan_tokens else 10.0)

    slop = _slop_penalty(f"{name} {desc}")
    score = max(0.0, min(100.0, authority + craft + recency + fit + slop))
    return {
        "name": name, "url": card.get("url"),
        "score": round(score, 1), "tier": tier_of(score),
        "breakdown": {"authority": round(authority, 1),
                      "craft": round(craft, 1),
                      "recency": round(recency, 1),
                      "fit": round(fit, 1),
                      "slop_penalty": slop},
    }


def tier_of(score: float) -> str:
    if score >= 80:
        return "gold"
    if score >= 60:
        return "silver"
    if score >= 40:
        return "bronze"
    return "slop"


def _slop_penalty(text: str) -> float:
    low = text.lower()
    hits = sum(1 for m in HYPE_MARKERS if m in low)
    emoji = len(EMOJI_RE.findall(text))
    if emoji >= 3:
        hits += 1
    return -min(40.0, hits * 10.0)


__all__ = [
    "extract_manifest", "score_skill_candidate", "select_capabilities",
    "score_inspiration", "tier_of",
]
