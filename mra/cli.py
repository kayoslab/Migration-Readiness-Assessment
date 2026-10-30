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

    chk = sub.add_parser("check-llm", help="verify the Vercel AI Gateway key and model with a one-line request")
    chk.add_argument("--config", default="assessment.yaml")

    args = parser.parse_args(argv)
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


if __name__ == "__main__":
    sys.exit(main())
