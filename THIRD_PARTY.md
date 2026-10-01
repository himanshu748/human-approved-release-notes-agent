# Dependencies and attribution

This repository contains original example code and fictional fixtures. It imports dependencies rather than vendoring upstream implementation files or tutorial prose.

- [mcp-agent](https://github.com/lastmile-ai/mcp-agent), version 0.2.6, by LastMile AI and contributors: [Apache License 2.0](https://github.com/lastmile-ai/mcp-agent/blob/main/LICENSE)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), version 1.30.0: [MIT license](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE)
- [Pydantic](https://github.com/pydantic/pydantic), version 2.13.5: MIT license
- Development tooling: pytest, pytest-asyncio, pytest-cov, Ruff, and Hatchling under their respective licenses

The complete transitive dependency graph and distribution hashes are in `uv.lock`. Installing dependencies includes their respective licenses. This project's MIT license covers its own code and documentation, not third-party packages. No affiliation or endorsement is implied.

References consulted: the official mcp-agent Agents documentation; upstream MCPApp, Agent, configuration, and human-input type definitions; and the installed, pinned 0.2.6 source. The review protocol, validation rules, fixtures, prose, and tests are original to this example.
