from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.observability.logging import logger


class MCPClient:
    """
    MCP client for the local Enterprise Software Support MCP server.

    The server is launched as a Python subprocess and communication
    happens over MCP stdio transport.
    """

    def __init__(
        self,
        server_script: str | Path | None = None,
        server_module: str | None = None,
    ) -> None:
        """
        Initialize the MCP client.

        Preferred:
            server_script="app/mcp/mcp_server.py"

        Also supports:
            server_module="app.mcp.mcp_server"
        """

        if server_script is None and server_module is None:
            server_script = (
                "app/mcp/mcp_server.py"
            )

        self.server_script = (
            Path(server_script)
            if server_script is not None
            else None
        )

        self.server_module = server_module

        # backend/
        self.backend_dir = (
            Path(__file__)
            .resolve()
            .parents[2]
        )

    # ============================================================
    # SERVER PARAMETERS
    # ============================================================

    def _server_parameters(
        self,
    ) -> StdioServerParameters:
        """
        Build MCP stdio server parameters.
        """

        # --------------------------------------------------------
        # Module-based launch
        # --------------------------------------------------------

        if self.server_module:
            return StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    self.server_module,
                ],
                cwd=str(
                    self.backend_dir
                ),
            )

        # --------------------------------------------------------
        # Script-based launch
        # --------------------------------------------------------

        if self.server_script is None:
            raise RuntimeError(
                "MCP server script/module is not configured."
            )

        script_path = self.server_script

        if not script_path.is_absolute():
            script_path = (
                self.backend_dir
                / script_path
            )

        script_path = script_path.resolve()

        if not script_path.exists():
            raise FileNotFoundError(
                f"MCP server script not found: "
                f"{script_path}"
            )

        return StdioServerParameters(
            command=sys.executable,
            args=[
                str(script_path),
            ],
            cwd=str(
                self.backend_dir
            ),
        )

    # ============================================================
    # LIST TOOLS
    # ============================================================

    async def list_tools(self) -> list[Any]:
        """
        Discover tools exposed by the MCP server.
        """

        server = (
            self._server_parameters()
        )

        logger.info(
            "MCP CLIENT: starting server"
        )

        async with stdio_client(
            server
        ) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:

                await session.initialize()

                result = (
                    await session.list_tools()
                )

                tools = list(
                    result.tools
                )

                logger.info(
                    "MCP CLIENT: discovered %d tools: %s",
                    len(tools),
                    [
                        tool.name
                        for tool in tools
                    ],
                )

                return tools

    # ============================================================
    # CALL TOOL
    # ============================================================

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Call one MCP tool.
        """

        arguments = arguments or {}

        server = (
            self._server_parameters()
        )

        logger.info(
            "MCP CLIENT: calling %s",
            tool_name,
        )

        async with stdio_client(
            server
        ) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:

                await session.initialize()

                result = (
                    await session.call_tool(
                        tool_name,
                        arguments=arguments,
                    )
                )

                return self._normalize_result(
                    result
                )

    # ============================================================
    # NORMALIZE RESULT
    # ============================================================

    @staticmethod
    def _normalize_result(
        result: Any,
    ) -> dict[str, Any]:
        """
        Convert MCP tool output into a normal dictionary.
        """

        # --------------------------------------------------------
        # Structured content
        # --------------------------------------------------------

        structured = getattr(
            result,
            "structured_content",
            None,
        )

        if isinstance(
            structured,
            dict,
        ):
            return structured

        # --------------------------------------------------------
        # Text content
        # --------------------------------------------------------

        content = getattr(
            result,
            "content",
            None,
        )

        if content:
            text_parts: list[str] = []

            for item in content:
                text_value = getattr(
                    item,
                    "text",
                    None,
                )

                if text_value:
                    text_parts.append(
                        text_value
                    )

            combined = "\n".join(
                text_parts
            ).strip()

            if combined:
                try:
                    parsed = json.loads(
                        combined
                    )

                    if isinstance(
                        parsed,
                        dict,
                    ):
                        return parsed

                    return {
                        "result": parsed
                    }

                except json.JSONDecodeError:
                    return {
                        "result": combined
                    }

        # --------------------------------------------------------
        # Fallback
        # --------------------------------------------------------

        return {
            "result": str(result)
        }

    # ============================================================
    # TOOL CHECK
    # ============================================================

    async def has_tool(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether an MCP tool exists.
        """

        tools = (
            await self.list_tools()
        )

        return any(
            tool.name == tool_name
            for tool in tools
        )

    # ============================================================
    # SAFE TOOL CALL
    # ============================================================

    async def safe_call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Call a tool and return a normalized error instead of
        propagating transport errors.
        """

        try:
            available = (
                await self.has_tool(
                    tool_name
                )
            )

            if not available:
                return {
                    "success": False,
                    "error": (
                        f"MCP tool '{tool_name}' "
                        "is not available."
                    ),
                }

            return await self.call_tool(
                tool_name,
                arguments,
            )

        except Exception as exc:
            logger.exception(
                "MCP CLIENT: tool call failed: %s",
                tool_name,
            )

            return {
                "success": False,
                "error": (
                    f"MCP tool '{tool_name}' "
                    f"failed: {exc}"
                ),
            }