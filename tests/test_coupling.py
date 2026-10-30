"""mra coupling on a synthetic git repository with known ownership and history."""

import subprocess
from pathlib import Path

import pytest
import yaml

from mra.coupling import analyse, facts_yaml, load_codeowners, load_module_map


def git(repo, *args, author=("A", "a@x.io")):
    env = {"GIT_AUTHOR_NAME": author[0], "GIT_AUTHOR_EMAIL": author[1], "GIT_COMMITTER_NAME": author[0],
           "GIT_COMMITTER_EMAIL": author[1], "PATH": "/usr/bin:/bin:/opt/homebrew/bin", "HOME": str(repo)}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def commit(repo, files, author):
    for f in files:
        p = repo / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(p.read_text() + "x\n" if p.exists() else "x\n")
        git(repo, "add", f, author=author)
    git(repo, "commit", "-m", "change", author=author)


ALICE, BOB, CAROL = ("Alice", "alice@x.io"), ("Bob", "bob@x.io"), ("Carol", "carol@x.io")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    # 10 changes: 6 inside one team's module, 4 spanning two teams (all touching checkout)
    for _ in range(3):
        commit(r, ["src/checkout/a.py"], ALICE)
        commit(r, ["src/catalogue/b.py"], BOB)
    for _ in range(4):
        commit(r, ["src/checkout/a.py", "src/search/c.py"], CAROL)
    (r / "modules.yaml").write_text(yaml.safe_dump({"modules": {
        "checkout": {"paths": ["src/checkout/**"], "owners": ["payments"]},
        "catalogue": {"paths": ["src/catalogue/**"], "owners": ["discovery"]},
        "search": {"paths": ["src/search/**"], "owners": ["discovery"]},
        "shared": {"paths": ["src/shared/**"], "owners": ["payments", "discovery"]},
    }}))
    (r / "CODEOWNERS").write_text("src/checkout/ @payments\nsrc/catalogue/ @discovery\nsrc/search/ @discovery\n")
    return r


def test_module_map(repo):
    result = analyse(repo, load_module_map(repo / "modules.yaml"))
    assert result.changes == 10 and result.cross_team_changes == 4
    assert result.facts["cross_team_change_pct"] == 40.0
    assert result.facts["teams_per_deployable"] == 2               # Carol inferred from the files she changed
    assert result.facts["module_single_owner_pct"] == 75.0           # "shared" has two owners
    # cross-team changes fall in checkout and search: top-3 share 1.0 over an even 3/4 → 1.33
    assert result.facts["friction_concentration_index"] == pytest.approx(1.33, abs=0.01)


def test_codeowners_and_authors_file(repo):
    result = analyse(repo, load_codeowners(repo / "CODEOWNERS"), authors={"carol@x.io": "platform"}, last_wins=True)
    assert result.facts["teams_per_deployable"] == 3                # Carol mapped explicitly to a third team
    assert result.facts["cross_team_change_pct"] == 40.0


def test_facts_snippet_is_marked_scripted(repo):
    snippet = yaml.safe_load(facts_yaml(analyse(repo, load_module_map(repo / "modules.yaml")), repo))
    assert snippet["cross_team_change_pct"]["scripted"] is True
    assert "mra coupling" in snippet["cross_team_change_pct"]["source"]
