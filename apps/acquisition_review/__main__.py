"""CLI: python -m apps.acquisition_review --evidence <file> [--model ...] [--out ...]"""

from __future__ import annotations

import argparse
import sys

from apps.acquisition_review.review import run_acquisition_review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an AEGIS acquisition review and print the decision dossier."
    )
    parser.add_argument("--evidence", required=True,
                        help="Path to the JSON evidence intake file.")
    parser.add_argument("--model", default=None,
                        help="Pydantic AI model string (default: $AEGIS_MODEL or 'test').")
    parser.add_argument("--no-rebuttal", action="store_true",
                        help="Skip the rebuttal round.")
    parser.add_argument("--no-reframing", action="store_true",
                        help="Skip reframing.")
    parser.add_argument("--out", default=None,
                        help="Write the dossier markdown to this path (default: stdout).")
    args = parser.parse_args(argv)

    result = run_acquisition_review(
        args.evidence,
        model_name=args.model,
        with_rebuttal=not args.no_rebuttal,
        with_reframing=not args.no_reframing,
    )
    if args.out:
        with open(args.out, "w") as f:
            f.write(result.dossier_markdown)
        print(f"dossier written to {args.out}")
    else:
        print(result.dossier_markdown)
    print(f"\ngate: {result.case.gate.state.value} | "
          f"readiness: {result.readiness.status.value} | "
          f"perspectives: {len(result.case.perspectives)} | "
          f"dissents: {len(result.minority_report.dissents)}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
