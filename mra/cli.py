"""Command line: `mra report [--config assessment.yaml] [--llm] [--output report.pdf]`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mra", description="Migration Readiness Assessment")
    sub = parser.add_subparsers(dest="command", required=True)

    rep = sub.add_parser("report", help="analyse responses and build the PDF report")
    rep.add_argument("--config", default="assessment.yaml")
    rep.add_argument("--output", help="PDF path (default: report.output in the config)")
    rep.add_argument("--llm", action="store_true", help="analyse free-text answers with the configured LLM")

    val = sub.add_parser("validate", help="cross-check the v3 instrument files")
    val.add_argument("--instrument", default="instrument")

    dec = sub.add_parser("decide", help="v3: recommended path per decision for an engagement")
    dec.add_argument("engagement", help="path to engagement.yaml")
    dec.add_argument("--draws", type=int, default=None)
    dec.add_argument("--json", action="store_true", help="print the full result as JSON")
    dec.add_argument("--llm", action="store_true", help="also code free-text answers via the Vercel AI Gateway")
    dec.add_argument("--pdf", help="write the v3 report to this PDF path")

    sim = sub.add_parser("simulate", help="v3: validity grid and threshold sweeps on synthetic engagements")
    sim.add_argument("--quick", action="store_true", help="reduced grid (as run in CI)")
    sim.add_argument("--out", default=None, help="output folder (default Output/sim)")

    cpl = sub.add_parser("coupling", help="v3: scripted coupling facts from a git repository")
    cpl.add_argument("repo", help="path to the repository of the deployable")
    own = cpl.add_mutually_exclusive_group(required=True)
    own.add_argument("--modules", help="module map YAML (preferred; freeze it before extraction)")
    own.add_argument("--codeowners", help="CODEOWNERS file")
    cpl.add_argument("--authors", help="YAML mapping author e-mail or name to team")
    cpl.add_argument("--days", type=int, default=90)
    cpl.add_argument("--branch", default=None, help="branch to analyse (default: current)")

    chk = sub.add_parser("check-llm", help="verify the Vercel AI Gateway key and model with a one-line request")
    chk.add_argument("--config", default="assessment.yaml")

    args = parser.parse_args(argv)

    if args.command == "validate":
        from .instrument import load_instrument, validate
        errors = validate(load_instrument(args.instrument))
        print("\n".join(errors) or "Instrument is consistent.")
        return 1 if errors else 0

    if args.command == "decide":
        return _decide(args)

    if args.command == "coupling":
        import yaml as _yaml

        from .coupling import analyse, facts_yaml, load_codeowners, load_module_map
        repo = Path(args.repo)
        modules = load_module_map(Path(args.modules)) if args.modules else load_codeowners(Path(args.codeowners))
        authors = _yaml.safe_load(Path(args.authors).read_text()) if args.authors else None
        result = analyse(repo, modules, authors, args.days, last_wins=bool(args.codeowners), branch=args.branch)
        if result.unmapped_files:
            print(f"# note: {result.unmapped_files} changed files are not covered by the ownership map")
        print(facts_yaml(result, repo))
        return 0

    if args.command == "simulate":
        from .sim import main as simulate, summary
        results = simulate(quick=args.quick, out=args.out)
        grid = results["grid"]
        print(summary(grid, ["group_size"]).round(3).to_string())
        wrong = (grid["result"] == "wrong").mean()
        print(f"\nWrong-outcome rate: {wrong:.1%} over {len(grid)} runs")
        return 1 if args.quick and wrong > 0.05 else 0

    config_path = Path(args.config).resolve()
    load_dotenv(config_path.parent / ".env")

    from .config import load_config
    cfg = load_config(config_path)

    if args.command == "check-llm":
        import pydantic

        from .llm import LLMClient, run_sync

        class Check(pydantic.BaseModel):
            ok: bool

        client = LLMClient.from_settings(cfg.llm)
        print(f"Vercel AI Gateway, model={client.model}")
        print("response:", run_sync(client.complete("Answer the request.", {"task": "Set ok to true."}, Check)))
        return 0

    from .report import build_report, run_analysis
    analysis = run_analysis(cfg, with_llm=args.llm or cfg.llm.enabled)
    v = analysis.verdict
    print(f"Verdict: {v.decision} (evidence: {v.evidence})")
    for reason in v.reasons:
        print(f"  - {reason}")
    path = build_report(cfg, analysis, Path(args.output) if args.output else None)
    print(f"Report written to {path}")
    return 0


def _decide(args) -> int:
    import json

    from .assess import assess
    if args.llm:
        load_dotenv(Path(args.engagement).resolve().parent / ".env")
        load_dotenv()
    result = assess(args.engagement, draws=args.draws, with_llm=args.llm)
    if args.json:
        print(json.dumps({d: r.as_dict() for d, r in result.results.items()}, indent=1, default=str))
        return 0
    if args.pdf:
        from .report_v3 import build_report as build_v3
        print(f"Report written to {build_v3(result, Path(args.pdf))}")
    outcomes = result.engagement.instrument.outcomes
    for problem in result.problems:
        print(f"! {problem}")
    for d, r in result.results.items():
        label = outcomes[d].get(r.verdict, outcomes["common"].get(r.verdict, {})).get("label", r.verdict)
        print(f"\n{d.title()} (current: {r.current_state})")
        print(f"  {label} — {r.status.replace('_', ' ')}, p = {r.probability:.2f}")
        if r.leaning:
            print(f"  leaning: {r.leaning}")
        for s in r.hard_stops:
            print(f"  blocked by: {s}")
        for c in r.unmet_capabilities:
            print(f"  capability to build: {c}")
        for g, info in r.gates.get("required", {}).items():
            if info["status"] != "pass":
                print(f"  gate {g}: {info['status']}")
        if r.interim:
            print(f"  interim step: {r.interim}")
        for w in r.what_would_change:
            ref = f" ({w['threshold_value']})" if w["threshold"] != w["threshold_value"] else ""
            print(f"  would become {w['outcome']} if {w['signal']} {w['op']} {w['threshold']}{ref} (now {w['current']})")
        for e in r.excluded:
            print(f"  excluded: {e}")
        for n in r.notes:
            print(f"  note: {n}")
        if r.economics:
            ratios = ", ".join(f"{o} {v:.2f}" for o, v in r.economics["ratio"].items())
            print(f"  cost vs current (5-year NPV): {ratios}")
            paid = {o: v for o, v in r.economics["payback_months"].items() if v is not None}
            if paid:
                print("  payback: " + ", ".join(f"{o} {v:.0f} months" for o, v in paid.items()))
            drivers = [t["input"] for t in r.economics["tornado"][1:4]]
            if drivers:
                print(f"  most sensitive inputs ({r.economics['tornado_option']}): {', '.join(drivers)}")
        if r.shadow and r.shadow["verdict"] != r.verdict:
            print(f"  shadow verdict under default rules: {r.shadow['verdict']}")
    st = result.stakes
    if st and (st.findings or st.suppressed):
        print("\nPreferences, stakes and alignment (group level; inputs for change management, never decisive)")
        for f in st.findings:
            print(f"  - {f}")
        for note in st.suppressed:
            print(f"  ({note})")
    if result.text is not None:
        print(f"\nFree text ({len(result.text.coded)} answers coded with {result.text.model})")
        for m in result.text.synthesis.get("key_messages", []):
            print(f"  - {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
