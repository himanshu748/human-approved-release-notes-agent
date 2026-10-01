"""Read-only MCP server scoped to one explicitly supplied local export."""

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .core import MAX_SOURCE_BYTES, parse_source
from .review import read_bounded


def create_server(source_path: Path) -> FastMCP:
    source = parse_source(read_bounded(source_path, MAX_SOURCE_BYTES))
    server = FastMCP("release-note-changes", log_level="ERROR")

    @server.tool()
    def list_changes() -> dict:
        """Return the configured local PR snapshot as untrusted source data. Read-only."""
        return source.model_dump(mode="json")

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    create_server(args.input).run(transport="stdio")


if __name__ == "__main__":
    main()
