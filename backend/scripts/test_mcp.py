from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)


class MCPService:
    """
    Application service for the Enterprise Software Support MCP layer.

    Responsibilities:
        - Create and manage the MCP client
        - Discover available MCP tools
        - Enforce the application-level tool allow-list
        - Execute approved MCP tools
        - Expose application-friendly methods to LangGraph
    """

    # ============================================================
    # APPROVED MCP TOOLS
    # ============================================================

    ALLOWED_TOOLS = {
        "mcp_validate_customer_account",
        "mcp_check_incident_status",
        "mcp_get_support_policy",
    }

    # ============================================================
    # INITIALIZATION
    # ============================================================

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
        Connect to the MCP server and discover tools.

        MCP SDK v2 returns Tool objects, so tool names are accessed
        using:

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
        # Store MCP Tool objects by name
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
        # Check approved tools
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
                "MCP SERVICE: approved tools missing "
                "from server: %s",
                sorted(missing_tools),
            )

        # --------------------------------------------------------
        # Detect tools exposed by the server but not approved
        # --------------------------------------------------------

        unexpected_tools = (
            discovered_names
            - self.ALLOWED_TOOLS
        )

        if unexpected_tools:
            logger.warning(
                "MCP SERVICE: server exposed tools outside "
                "application allow-list: %s",
                sorted(unexpected_tools),
            )

        self._initialized = True

    # ============================================================
    # STATUS
    # ============================================================

    def is_initialized(self) -> bool:
        """
        Return True when MCP tool discovery has completed.
        """

        return self._initialized

    # ============================================================
    # LIST TOOLS
    # ============================================================

    async def list_tools(self) -> list[Any]:
        """
        Initialize if necessary and return discovered MCP tools.
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

        This method is used by existing diagnostic/test code
        after initialize() has completed.
        """

        return list(
            self.available_tools.values()
        )

    # ============================================================
    # TOOL ALLOW-LIST
    # ============================================================

    def is_tool_allowed(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether a tool is explicitly approved by the
        application allow-list.
        """

        return (
            tool_name in self.ALLOWED_TOOLS
        )

    # ============================================================
    # SERVER TOOL AVAILABILITY
    # ============================================================

    def has_tool(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether the MCP server actually exposes a tool.
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

        Two checks are performed:

            1. Application allow-list
            2. Server tool availability
        """

        await self.initialize()

        # --------------------------------------------------------
        # Application allow-list
        # --------------------------------------------------------

        if not self.is_tool_allowed(
            tool_name
        ):
            logger.warning(
                "MCP SERVICE: blocked "
                "non-allow-listed tool=%s",
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
        # Server availability
        # --------------------------------------------------------

        if not self.has_tool(
            tool_name
        ):
            logger.error(
                "MCP SERVICE: tool=%s is not "
                "available on MCP server",
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
        Validate a customer account using the MCP account tool.
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
        Check production incident status.

        Only support-agent and admin roles are allowed to call
        this operational MCP capability.
        """

        # --------------------------------------------------------
        # Role check
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Parameter validation
        # --------------------------------------------------------

        if not service_name:
            return {
                "success": False,
                "incident_active": False,
                "service_name": None,
                "error": (
                    "service_name is required."
                ),
            }

        # --------------------------------------------------------
        # MCP call
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Role check
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Parameter validation
        # --------------------------------------------------------

        if not policy_type:
            return {
                "success": False,
                "policy_type": None,
                "error": (
                    "policy_type is required."
                ),
            }

        # --------------------------------------------------------
        # MCP call
        # --------------------------------------------------------

        return await self.call_tool(
            "mcp_get_support_policy",
            {
                "policy_type": policy_type,
            },
        )