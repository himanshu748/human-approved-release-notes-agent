"""Local-only command line: draft, inspect, and explicitly review an export."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .core import MAX_DRAFT_BYTES, load_draft
from .review import ReviewBlocked, read_bounded, validate_path_display


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Human-approved release drafts. No model API calls.")
    commands = root.add_subparsers(dest="command", required=True)
    draft = commands.add_parser("draft", help="Read a local JSON export through a real MCP server")
    draft.add_argument("--input", required=True, type=Path)
    draft.add_argument("--output", required=True, type=Path)
    inspect = commands.add_parser("inspect", help="Verify and display a deterministic draft")
    inspect.add_argument("draft", type=Path)
    inspect.add_argument(
        "--sources", action="store_true", help="Also print the normalized source JSON"
    )
    review = commands.add_parser(
        "review", help="Require an interactive approval before local export"
    )
    review.add_argument("draft", type=Path)
    review.add_argument("--output", required=True, type=Path)
    review.add_argument(
        "--reviewer", required=True, help="Self-declared name/handle, not authentication"
    )
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "draft":
            validate_path_display(args.input)
            validate_path_display(args.output)
            if args.output.exists() or args.output.is_symlink():
                raise FileExistsError(f"Refusing to overwrite: {args.output}")
            from .workflow import draft_from_mcp

            result = asyncio.run(draft_from_mcp(args.input))
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(result.draft.model_dump_json(indent=2) + "\n")
            print(f"Draft: {args.output}\nSHA-256: {result.draft.digest}")
            print(f"MCP tools: {', '.join(result.tools)}\nModel calls: {result.model_calls}")
        elif args.command == "inspect":
            draft = load_draft(read_bounded(args.draft, MAX_DRAFT_BYTES))
            print(draft.markdown)
            print("Review warnings:\n" + "\n".join(f"- {w}" for w in draft.warnings))
            print(f"Draft SHA-256: {draft.digest}")
            if args.sources:
                print("\nUNTRUSTED SOURCE DATA (JSON):")
                print(draft.source.model_dump_json(indent=2))
        else:
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                raise ReviewBlocked("Approval requires an interactive terminal")
            from .workflow import review_with_mcp

            receipt = asyncio.run(review_with_mcp(args.draft, args.output, args.reviewer))
            print("Exported locally. No GitHub release was published.")
            print(json.dumps(receipt, indent=2))
        return 0
    except (OSError, ValueError, TimeoutError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Review cancelled; no new approval granted.", file=sys.stderr)
        return 130
