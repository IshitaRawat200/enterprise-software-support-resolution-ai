from __future__ import annotations

from pathlib import Path
from typing import Any

from app.mcp.mcp_client import MCPClient
from app.observability.logging import logger


class MCPService:
    """
    Application service for the Enterprise Software Support MCP layer.

    Responsibilities:
        - Create/manage the MCP client
        - Discover available MCP tools
        - Keep an allow-list of supported tools
        - Execute bounded MCP operations
        - Expose application-friendly methods to LangGraph

    LangGraph should call this service instead of talking directly
    to the MCP SDK.
    """

    # ============================================================
    # APPROVED MCP TOOLS
    # ============================================================

    ALLOWED_TOOLS = {
        "mcp_validate_customer_account",
        "mcp_check_incident_status",
        "mcp_get_support_policy",
    }

    def __init__(
        self,
        server_script: str | Path = (
            "app/mcp/mcp_server.py"
        ),
    ) -> None:
        self.server_script = Path(
            server_script
        )

        self.client = MCPClient(
            server_script=self.server_script
        )

        self.available_tools: dict[
            str,
            Any,
        ] = {}

        self._initialized = False

    # ============================================================
    # INITIALIZE
    # ============================================================

    async def initialize(self) -> None:
        """
        Connect to the MCP server and discover its tools.

        MCP SDK v2 returns Tool objects.

        Therefore we use:

            tool.name

        rather than:

            tool["name"]
        """

        if self._initialized:
            logger.info(
                "MCP SERVICE: already initialized"
            )
            return

        logger.info(
            "MCP SERVICE: initializing MCP connection"
        )

        tools = await self.client.list_tools()

        # --------------------------------------------------------
        # MCP v2 Tool objects
        # --------------------------------------------------------

        self.available_tools = {
            tool.name: tool
            for tool in tools
        }

        logger.info(
            "MCP SERVICE: discovered %d tools: %s",
            len(self.available_tools),
            list(
                self.available_tools.keys()
            ),
        )

        # --------------------------------------------------------
        # Verify approved tools
        # --------------------------------------------------------

        discovered_names = set(
            self.available_tools.keys()
        )

        missing_tools = (
            self.ALLOWED_TOOLS
            - discovered_names
        )

        if missing_tools:
            logger.warning(
                "MCP SERVICE: approved tools not "
                "available: %s",
                sorted(missing_tools),
            )

        unexpected_tools = (
            discovered_names
            - self.ALLOWED_TOOLS
        )

        if unexpected_tools:
            logger.warning(
                "MCP SERVICE: server exposed tools "
                "outside the application allow-list: %s",
                sorted(unexpected_tools),
            )

        self._initialized = True

    # ============================================================
    # STATUS
    # ============================================================

    def is_initialized(self) -> bool:
        """Return whether the MCP service is initialized."""

        return self._initialized

    # ============================================================
    # TOOL DISCOVERY
    # ============================================================

    async def list_tools(
        self,
    ) -> list[Any]:
        """
        Return discovered MCP tools.
        """

        await self.initialize()

        return list(
            self.available_tools.values()
        )
    # ============================================================
    # GET TOOLS
    # ============================================================

    def get_tools(self) -> list[Any]:
        """
        Return currently discovered MCP tools.

        initialize() should be called before accessing this method.
        """

        return list(
            self.available_tools.values()
        )

    # ============================================================
    # TOOL AVAILABILITY
    # ============================================================

    def is_tool_allowed(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether a tool is allowed by the application
        allow-list.
        """

        return tool_name in self.ALLOWED_TOOLS

    def has_tool(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether a tool was actually exposed by the MCP server.
        """

        return (
            tool_name
            in self.available_tools
        )

    # ============================================================
    # LOW-LEVEL TOOL CALL
    # ============================================================

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute an approved MCP tool.

        This is the central tool permission boundary.
        """

        await self.initialize()

        # --------------------------------------------------------
        # Application allow-list
        # --------------------------------------------------------

        if not self.is_tool_allowed(
            tool_name
        ):
            logger.warning(
                "MCP SERVICE: blocked non-allow-listed tool: %s",
                tool_name,
            )

            return {
                "success": False,
                "error": (
                    f"MCP tool '{tool_name}' "
                    "is not allow-listed."
                ),
            }

        # --------------------------------------------------------
        # Server capability check
        # --------------------------------------------------------

        if not self.has_tool(
            tool_name
        ):
            logger.error(
                "MCP SERVICE: requested tool is "
                "not exposed by the server: %s",
                tool_name,
            )

            return {
                "success": False,
                "error": (
                    f"MCP tool '{tool_name}' "
                    "is not available on the MCP server."
                ),
            }

        logger.info(
            "MCP SERVICE: calling approved tool=%s",
            tool_name,
        )

        return await self.client.safe_call_tool(
            tool_name,
            arguments or {},
        )

    # ============================================================
    # ACCOUNT VALIDATION
    # ============================================================

    async def validate_customer_account(
        self,
        *,
        customer_id: str,
    ) -> dict[str, Any]:
        """
        Validate a customer account through MCP.
        """

        if not customer_id:
            return {
                "success": False,
                "account_exists": False,
                "customer_id": None,
                "error": (
                    "customer_id is required."
                ),
            }

        return await self.call_tool(
            "mcp_validate_customer_account",
            {
                "customer_id": customer_id,
            },
        )

    # ============================================================
    # INCIDENT STATUS
    # ============================================================

    async def check_incident_status(
        self,
        *,
        service_name: str,
        role: str = "support_agent",
    ) -> dict[str, Any]:
        """
        Check current production incident status through MCP.

        The role argument is retained at the service boundary so
        the application can enforce role-based access before the
        external operation.
        """

        if role not in {
            "support_agent",
            "admin",
        }:
            logger.warning(
                "MCP SERVICE: incident tool denied "
                "for role=%s",
                role,
            )

            return {
                "success": False,
                "incident_active": False,
                "service_name": service_name,
                "error": (
                    "Role is not permitted to "
                    "call the incident MCP tool."
                ),
            }

        if not service_name:
            return {
                "success": False,
                "incident_active": False,
                "service_name": None,
                "error": (
                    "service_name is required."
                ),
            }

        return await self.call_tool(
            "mcp_check_incident_status",
            {
                "service_name": service_name,
            },
        )

    # ============================================================
    # SUPPORT POLICY
    # ============================================================

    async def get_support_policy(
        self,
        *,
        policy_type: str,
        role: str = "support_agent",
    ) -> dict[str, Any]:
        """
        Retrieve an approved support policy through MCP.
        """

        if role not in {
            "support_agent",
            "admin",
        }:
            logger.warning(
                "MCP SERVICE: policy tool denied "
                "for role=%s",
                role,
            )

            return {
                "success": False,
                "policy_type": policy_type,
                "error": (
                    "Role is not permitted to "
                    "call the policy MCP tool."
                ),
            }

        if not policy_type:
            return {
                "success": False,
                "policy_type": None,
                "error": (
                    "policy_type is required."
                ),
            }

        return await self.call_tool(
            "mcp_get_support_policy",
            {
                "policy_type": policy_type,
            },
        )