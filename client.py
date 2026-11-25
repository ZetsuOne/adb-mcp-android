"""Stdio smoke-test client: list tools and call list_devices / adb_version."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> int:
    server = Path(__file__).resolve().parent / "server.py"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server)],
        env={**os.environ},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print(f"tools ({len(names)}): {', '.join(names)}")

            for tool_name in ("adb_version", "list_devices"):
                result = await session.call_tool(tool_name, arguments={})
                print(f"\n=== {tool_name} ===")
                for block in result.content:
                    text = getattr(block, "text", None)
                    if text is not None:
                        try:
                            print(json.dumps(json.loads(text), indent=2, ensure_ascii=False))
                        except json.JSONDecodeError:
                            print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
