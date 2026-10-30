"""Scripted coupling facts from git history (`mra coupling`).

Computes, for one repository (= one deployable) over a time window:
    teams_per_deployable          teams whose members committed
    cross_team_change_pct         share of changes touching code owned by more than one team
    friction_concentration_index  share of cross-team changes falling in the three most affected modules,
                                  divided by the share expected if spread evenly (3 / modules)
    module_single_owner_pct       share of modules with exactly one owning team

Ownership comes from a module map (preferred; freeze it before extraction, decision_rules.yaml →
fact_discipline) or from a CODEOWNERS file. Authors map to teams through an optional authors file; otherwise an
author's team is the team owning most of the files they changed. Merge commits are skipped so that each change is
counted once.

module map (YAML):
    modules:
      checkout: {paths: ["src/checkout/**"], owners: [payments-team]}
      catalogue: {paths: ["src/catalogue/**", "src/search/**"], owners: [discovery-team]}
authors (YAML): {"jane@example.com": payments-team, "Joe Bloggs": discovery-team}
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Module:
    name: str
    patterns: list[str]
    owners: list[str]


@dataclass
class CouplingResult:
    facts: dict[str, float]
    changes: int
    cross_team_changes: int
    teams: list[str]
    modules: dict[str, dict] = field(default_factory=dict)
    unmapped_files: int = 0
    window_days: int = 90


# ---------------------------------------------------------------------------------------- ownership

def _match(path: str, pattern: str) -> bool:
    pattern = pattern.lstrip("/")
    if pattern.endswith("/"):
        pattern += "**"
    if "/" not in pattern.rstrip("*"):                       # CODEOWNERS: bare name matches anywhere
        return fnmatch.fnmatch(Path(path).name, pattern) or fnmatch.fnmatch(path, f"*/{pattern}") or \
            fnmatch.fnmatch(path, pattern) or path.startswith(pattern.rstrip("*"))
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.replace("/**", "/*")) or \
        (pattern.endswith("/**") and path.startswith(pattern[:-2]))


def load_module_map(path: Path) -> list[Module]:
    raw = yaml.safe_load(path.read_text()) or {}
    return [Module(name, spec.get("paths", []), spec.get("owners", [])) for name, spec in raw.get("modules", {}).items()]


def load_codeowners(path: Path) -> list[Module]:
    """Each CODEOWNERS rule becomes a module; as in GitHub, the last matching rule wins."""
    modules = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            modules.append(Module(parts[0], [parts[0]], [o.lstrip("@") for o in parts[1:]]))
    return modules


def owner_module(path: str, modules: list[Module], last_wins: bool) -> Module | None:
    hits = [m for m in modules if any(_match(path, p) for p in m.patterns)]
    if not hits:
        return None
    return hits[-1] if last_wins else hits[0]


# ---------------------------------------------------------------------------------------- history

def git_changes(repo: Path, since_days: int, branch: str | None = None) -> list[dict]:
    since = (dt.date.today() - dt.timedelta(days=since_days)).isoformat()
    cmd = ["git", "-C", str(repo), "log", f"--since={since}", "--no-merges", "--format=@@%H|%an|%ae", "--name-only"]
    if branch:
        cmd.insert(4, branch)
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    changes = []
    for block in out.split("@@")[1:]:
        lines = [l for l in block.strip().splitlines() if l.strip()]
        sha, name, email = lines[0].split("|", 2)
        changes.append({"sha": sha, "author": name, "email": email, "files": lines[1:]})
    return changes


def analyse(repo: Path, modules: list[Module], authors: dict[str, str] | None = None, since_days: int = 90,
            last_wins: bool = False, branch: str | None = None) -> CouplingResult:
    changes = git_changes(repo, since_days, branch)
    authors = authors or {}
    by_module_changes = Counter()
    cross_by_module = Counter()
    author_files = defaultdict(Counter)
    unmapped = 0
    cross = 0
    for c in changes:
        teams, mods = set(), set()
        for f in c["files"]:
            m = owner_module(f, modules, last_wins)
            if m is None:
                unmapped += 1
                continue
            mods.add(m.name)
            teams.update(m.owners)
            for o in m.owners:
                author_files[(c["author"], c["email"])][o] += 1
        c["modules"], c["teams"] = mods, teams
        for m in mods:
            by_module_changes[m] += 1
        if len(teams) > 1:
            cross += 1
            for m in mods:
                cross_by_module[m] += 1

    def team_of(name: str, email: str) -> str | None:
        if email in authors:
            return authors[email]
        if name in authors:
            return authors[name]
        counts = author_files.get((name, email))
        return counts.most_common(1)[0][0] if counts else None

    committing_teams = sorted({t for c in changes if (t := team_of(c["author"], c["email"]))})
    n_modules = len({m.name for m in modules})
    facts = {
        "teams_per_deployable": float(len(committing_teams)),
        "cross_team_change_pct": round(100 * cross / len(changes), 1) if changes else 0.0,
        "module_single_owner_pct": round(100 * sum(len(set(m.owners)) == 1 for m in modules) / n_modules, 1)
        if n_modules else 0.0,
    }
    if cross and n_modules >= 4:
        top3 = sum(v for _, v in cross_by_module.most_common(3)) / sum(cross_by_module.values())
        facts["friction_concentration_index"] = round(top3 / (3 / n_modules), 2)
    module_stats = {m: {"changes": by_module_changes[m], "cross_team_changes": cross_by_module[m]} for m in by_module_changes}
    return CouplingResult(facts, len(changes), cross, committing_teams, module_stats, unmapped, since_days)


def facts_yaml(result: CouplingResult, repo: Path) -> str:
    today = dt.date.today().isoformat()
    source = f"mra coupling on {repo.resolve().name}, last {result.window_days} days ({result.changes} changes)"
    body = {k: {"value": v, "source": source, "date": today, "scripted": True} for k, v in result.facts.items()}
    note = ("# friction_concentration_index here counts cross-team changes only; add incidents per module if available.\n"
            if "friction_concentration_index" in result.facts else
            "# friction_concentration_index not computed (needs at least 4 modules and some cross-team changes).\n")
    return note + yaml.safe_dump(body, sort_keys=False)
