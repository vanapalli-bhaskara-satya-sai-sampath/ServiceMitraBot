import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """Thin wrapper around an official MCP stdio client for ServiceMitra tools."""

    def __init__(self, server_path: Optional[str] = None):
        self.server_path = server_path or os.path.join(os.path.dirname(__file__), "mcp_server.py")

    async def list_tools(self) -> List[Dict[str, Any]]:
        params = StdioServerParameters(command=sys.executable, args=[self.server_path])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                result = await session.list_tools()
                return result.tools if hasattr(result, "tools") else []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        params = StdioServerParameters(command=sys.executable, args=[self.server_path])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                result = await session.call_tool(tool_name, arguments)
                if hasattr(result, "content"):
                    payload = result.content
                    if isinstance(payload, list):
                        item = payload[0]
                        if hasattr(item, "text"):
                            return json.loads(item.text)
                        return {"result": item}
                    return {"result": payload}
                return {"result": result}
