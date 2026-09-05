from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agents.retrieval.retrieval_agent import RetrievalAgent
from app.database.connection import get_db_session
from app.hybrid.hybrid_retrieval_service import HybridRetrievalService
from app.mcp.mcp_runtime import mcp_service
from app.observability.logging import logger
from app.orchestrator.state import SupportState
from app.sql.sql_service import SQLService


async def act_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    ACT phase.

    Executes the route selected by the Intent Agent.

    Supported routes:
        rag
        sql
        hybrid
        incident

    Architecture:

        RAG
            → RetrievalAgent
            → FusionRetrievalService

        SQL
            → SQLService
            → SQLGenerator
            → SQLExecutor

        HYBRID
            → HybridRetrievalService
                ├── RetrievalAgent
                └── SQLService

        INCIDENT
            → MCPService
            → MCP Incident Tool
            → incident_logs
            → later severity/escalation

    Hybrid is an execution strategy, not a specialized agent.

    MCP is a controlled tool-access layer.
    It is used here for incident-status investigation.
    """

    route = (
        state.get("route")
        or state.get("suggested_route")
        or "rag"
    )

    message = (
        state.get("message") or ""
    ).strip()

    logger.info(
        "ACT: starting route=%s message_length=%d",
        route,
        len(message),
    )

    if not message:
        logger.warning(
            "ACT: empty customer message"
        )

        return {
            "current_node": "act",
            "errors": [
                (
                    "Cannot execute resolution without "
                    "a customer message."
                )
            ],
        }

    customer_id = state.get(
        "customer_id"
    )

    # ========================================================
    # RAG
    # ========================================================

    if route == "rag":
        rag_start = perf_counter()

        logger.info(
            "ACT/RAG: starting documentation retrieval"
        )

        try:
            # ------------------------------------------------
            # Retrieval agent creation
            # ------------------------------------------------

            retrieval_agent_start = perf_counter()

            retrieval_agent = RetrievalAgent(
                similarity_top_k=5,
            )

            logger.info(
                "ACT/RAG: RetrievalAgent created in %.3fs",
                perf_counter() - retrieval_agent_start,
            )

            # ------------------------------------------------
            # Database session
            # ------------------------------------------------

            db_session_start = perf_counter()

            async for db_session in get_db_session():
                logger.info(
                    "ACT/RAG: database session ready in %.3fs",
                    perf_counter() - db_session_start,
                )

                # --------------------------------------------
                # Retrieval
                # --------------------------------------------

                retrieval_start = perf_counter()

                result = await retrieval_agent.run(
                    query=message,
                    session=db_session,
                )

                retrieval_duration = (
                    perf_counter() - retrieval_start
                )

                logger.info(
                    "ACT/RAG: retrieval_agent.run "
                    "completed in %.3fs",
                    retrieval_duration,
                )

                total_duration = (
                    perf_counter() - rag_start
                )

                logger.info(
                    "ACT/RAG: total route time %.3fs",
                    total_duration,
                )

                retrieval_results = result.get(
                    "results",
                    [],
                )

                retrieval_confidence = float(
                    result.get(
                        "confidence",
                        0.0,
                    )
                    or 0.0
                )

                sufficient_evidence = bool(
                    result.get(
                        "sufficient_evidence",
                        False,
                    )
                )

                logger.info(
                    "ACT/RAG: results=%d confidence=%.4f "
                    "sufficient_evidence=%s",
                    len(retrieval_results),
                    retrieval_confidence,
                    sufficient_evidence,
                )

                return {
                    "selected_action": (
                        "documentation_retrieval"
                    ),

                    "retrieval_results": (
                        retrieval_results
                    ),

                    "retrieval_confidence": (
                        retrieval_confidence
                    ),

                    "sufficient_evidence": (
                        sufficient_evidence
                    ),

                    "retrieval_reason": (
                        result.get(
                            "reason"
                        )
                    ),

                    "current_node": "act",

                    "errors": result.get(
                        "errors",
                        [],
                    ),
                }

            # No database session yielded.
            total_duration = (
                perf_counter() - rag_start
            )

            logger.error(
                "ACT/RAG: no database session available "
                "after %.3fs",
                total_duration,
            )

            return {
                "current_node": "act",
                "errors": [
                    (
                        "Unable to obtain a database session "
                        "for documentation retrieval."
                    )
                ],
            }

        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
        ) as exc:
            total_duration = (
                perf_counter() - rag_start
            )

            logger.exception(
                "ACT/RAG: documentation retrieval failed "
                "after %.3fs",
                total_duration,
            )

            return {
                "current_node": "act",
                "errors": [
                    (
                        "Documentation retrieval failed: "
                        f"{exc}"
                    )
                ],
            }

    # ========================================================
    # SQL
    # ========================================================

    if route == "sql":
        sql_start = perf_counter()

        logger.info(
            "ACT/SQL: starting SQL investigation"
        )

        async for db_session in get_db_session():
            try:
                db_ready_time = (
                    perf_counter() - sql_start
                )

                logger.info(
                    "ACT/SQL: database session ready in %.3fs",
                    db_ready_time,
                )

                sql_service = SQLService(
                    db_session
                )

                query_start = perf_counter()

                result = await sql_service.query(
                    question=message,
                    customer_id=customer_id,
                )

                query_duration = (
                    perf_counter() - query_start
                )

                total_duration = (
                    perf_counter() - sql_start
                )

                logger.info(
                    "ACT/SQL: SQLService.query took %.3fs; "
                    "total route time %.3fs",
                    query_duration,
                    total_duration,
                )

                if not result.get(
                    "success",
                    False,
                ):
                    logger.warning(
                        "ACT/SQL: query unsuccessful: %s",
                        result.get("error"),
                    )

                    return {
                        "selected_action": "sql",

                        "sql_query": result.get(
                            "sql"
                        ),

                        "sql_rows": [],

                        "sql_row_count": 0,

                        "sql_confidence": float(
                            result.get(
                                "sql_confidence",
                                0.0,
                            )
                            or 0.0
                        ),

                        "sql_explanation": (
                            result.get(
                                "explanation"
                            )
                        ),

                        "sql_tables_used": (
                            result.get(
                                "tables_used",
                                [],
                            )
                        ),

                        "sql_success": False,

                        "sql_error": (
                            result.get(
                                "error"
                            )
                        ),

                        "current_node": "act",

                        "errors": [
                            (
                                "SQL execution failed: "
                                f"{result.get('error')}"
                            )
                        ],
                    }

                logger.info(
                    "ACT/SQL: query succeeded rows=%s confidence=%.4f",
                    result.get(
                        "row_count",
                        0,
                    ),
                    float(
                        result.get(
                            "sql_confidence",
                            0.0,
                        )
                        or 0.0
                    ),
                )

                return {
                    "selected_action": "sql",

                    "sql_query": result.get(
                        "sql"
                    ),

                    "sql_rows": result.get(
                        "rows",
                        [],
                    ),

                    "sql_row_count": result.get(
                        "row_count",
                        0,
                    ),

                    "sql_confidence": float(
                        result.get(
                            "sql_confidence",
                            0.0,
                        )
                        or 0.0
                    ),

                    "sql_explanation": (
                        result.get(
                            "explanation"
                        )
                    ),

                    "sql_tables_used": (
                        result.get(
                            "tables_used",
                            [],
                        )
                    ),

                    "sql_success": True,

                    "sql_error": None,

                    "current_node": "act",

                    "errors": [],
                }

            except (
                AttributeError,
                TypeError,
                ValueError,
                RuntimeError,
            ) as exc:
                logger.exception(
                    "ACT/SQL: SQL route failed"
                )

                return {
                    "selected_action": "sql",

                    "sql_success": False,

                    "sql_error": str(exc),

                    "current_node": "act",

                    "errors": [
                        f"SQL route failed: {exc}"
                    ],
                }

        logger.error(
            "ACT/SQL: no database session available"
        )

        return {
            "selected_action": "sql",

            "sql_success": False,

            "sql_error": (
                "Unable to obtain a database session."
            ),

            "current_node": "act",

            "errors": [
                (
                    "Unable to obtain a database session "
                    "for SQL execution."
                )
            ],
        }

    # ========================================================
    # HYBRID
    # ========================================================

    if route == "hybrid":
        hybrid_start = perf_counter()

        logger.info(
            "ACT/HYBRID: starting hybrid investigation"
        )

        async for db_session in get_db_session():
            try:
                logger.info(
                    "ACT/HYBRID: database session ready in %.3fs",
                    perf_counter() - hybrid_start,
                )

                retrieval_agent = RetrievalAgent(
                    similarity_top_k=5,
                )

                sql_service = SQLService(
                    db_session
                )

                hybrid_service = (
                    HybridRetrievalService(
                        rag_service=retrieval_agent,
                        sql_service=sql_service,
                    )
                )

                run_start = perf_counter()

                result = await hybrid_service.run(
                    query=message,
                    customer_id=customer_id,
                    session=db_session,
                )

                run_duration = (
                    perf_counter() - run_start
                )

                total_duration = (
                    perf_counter() - hybrid_start
                )

                logger.info(
                    "ACT/HYBRID: hybrid_service.run took %.3fs; "
                    "total route time %.3fs",
                    run_duration,
                    total_duration,
                )

                if hasattr(
                    result,
                    "model_dump",
                ):
                    data = result.model_dump()
                else:
                    data = result

                rag_results = data.get(
                    "rag_results",
                    [],
                )

                rag_confidence = float(
                    data.get(
                        "rag_confidence",
                        0.0,
                    )
                    or 0.0
                )

                sufficient_evidence = bool(
                    data.get(
                        "sufficient_evidence",
                        False,
                    )
                )

                sql_result = data.get(
                    "sql_result"
                )

                sql_query = None

                sql_rows: list[
                    dict[str, Any]
                ] = []

                sql_row_count = 0
                sql_confidence = 0.0
                sql_success = False
                sql_error = None
                sql_explanation = None

                sql_tables_used: list[str] = []

                if sql_result:
                    if hasattr(
                        sql_result,
                        "model_dump",
                    ):
                        sql_data = (
                            sql_result.model_dump()
                        )
                    else:
                        sql_data = sql_result

                    sql_query = (
                        sql_data.get(
                            "sql_query"
                        )
                        or sql_data.get(
                            "sql"
                        )
                        or sql_data.get(
                            "query"
                        )
                    )

                    sql_rows = sql_data.get(
                        "rows",
                        [],
                    )

                    sql_row_count = sql_data.get(
                        "row_count",
                        len(sql_rows),
                    )

                    sql_confidence = float(
                        sql_data.get(
                            "confidence",
                            sql_data.get(
                                "sql_confidence",
                                0.0,
                            ),
                        )
                        or 0.0
                    )

                    sql_success = bool(
                        sql_data.get(
                            "success",
                            False,
                        )
                    )

                    sql_error = (
                        sql_data.get(
                            "validation_message"
                        )
                        or sql_data.get(
                            "error"
                        )
                    )

                    sql_explanation = (
                        sql_data.get(
                            "explanation"
                        )
                    )

                    sql_tables_used = (
                        sql_data.get(
                            "tables_used",
                            [],
                        )
                    )

                hybrid_confidence = float(
                    data.get(
                        "hybrid_confidence",
                        min(
                            rag_confidence,
                            sql_confidence,
                        ),
                    )
                    or 0.0
                )

                hybrid_errors = data.get(
                    "errors",
                    [],
                )

                if not isinstance(
                    hybrid_errors,
                    list,
                ):
                    hybrid_errors = [
                        str(hybrid_errors)
                    ]

                existing_errors = list(
                    state.get(
                        "errors",
                        [],
                    )
                )

                errors = (
                    existing_errors
                    + hybrid_errors
                )

                logger.info(
                    "ACT/HYBRID: rag_confidence=%.4f "
                    "sql_confidence=%.4f "
                    "hybrid_confidence=%.4f "
                    "sql_success=%s",
                    rag_confidence,
                    sql_confidence,
                    hybrid_confidence,
                    sql_success,
                )

                return {
                    "selected_action": "hybrid",

                    "retrieval_results": (
                        rag_results
                    ),

                    "retrieval_confidence": (
                        rag_confidence
                    ),

                    "sufficient_evidence": (
                        sufficient_evidence
                    ),

                    "retrieval_reason": (
                        data.get(
                            "evidence_summary"
                        )
                    ),

                    "sql_query": sql_query,

                    "sql_rows": sql_rows,

                    "sql_row_count": (
                        sql_row_count
                    ),

                    "sql_confidence": (
                        sql_confidence
                    ),

                    "sql_explanation": (
                        sql_explanation
                    ),

                    "sql_tables_used": (
                        sql_tables_used
                    ),

                    "sql_success": (
                        sql_success
                    ),

                    "sql_error": sql_error,

                    "hybrid_results": (
                        rag_results
                    ),

                    "hybrid_confidence": (
                        hybrid_confidence
                    ),

                    "hybrid_success": (
                        sufficient_evidence
                        and sql_success
                        and not hybrid_errors
                    ),

                    "hybrid_reason": (
                        data.get(
                            "evidence_summary",
                            "",
                        )
                    ),

                    "hybrid_errors": (
                        hybrid_errors
                    ),

                    "current_node": "act",

                    "errors": errors,
                }

            except (
                AttributeError,
                TypeError,
                ValueError,
                RuntimeError,
            ) as exc:
                logger.exception(
                    "ACT/HYBRID: hybrid route failed"
                )

                return {
                    "selected_action": "hybrid",

                    "hybrid_results": [],

                    "hybrid_confidence": 0.0,

                    "hybrid_success": False,

                    "hybrid_reason": (
                        f"Hybrid execution failed: {exc}"
                    ),

                    "hybrid_errors": [
                        str(exc)
                    ],

                    "current_node": "act",

                    "errors": (
                        list(
                            state.get(
                                "errors",
                                [],
                            )
                        )
                        + [
                            (
                                "Hybrid route failed: "
                                f"{exc}"
                            )
                        ]
                    ),
                }

        logger.error(
            "ACT/HYBRID: no database session available"
        )

        return {
            "selected_action": "hybrid",

            "hybrid_results": [],

            "hybrid_confidence": 0.0,

            "hybrid_success": False,

            "hybrid_reason": (
                "Unable to obtain a database session "
                "for Hybrid retrieval."
            ),

            "hybrid_errors": [
                (
                    "Unable to obtain a database session "
                    "for Hybrid retrieval."
                )
            ],

            "current_node": "act",

            "errors": [
                (
                    "Unable to obtain a database session "
                    "for Hybrid retrieval."
                )
            ],
        }

    # ========================================================
    # INCIDENT → MCP
    # ========================================================

    if route == "incident":
        incident_start = perf_counter()

        logger.info(
            "ACT/INCIDENT: starting MCP incident investigation"
        )

        try:
            # ------------------------------------------------
            # Determine service
            # ------------------------------------------------

            service_name = (
                state.get("service_name")
                or state.get("incident_service")
                or "enterprise-api"
            )

            logger.info(
                "ACT/INCIDENT: checking service=%s",
                service_name,
            )

            # ------------------------------------------------
            # MCP call
            # ------------------------------------------------

            mcp_start = perf_counter()

            incident_result = (
                await mcp_service.check_incident_status(
                    service_name=service_name,
                    role="support_agent",
                )
            )

            mcp_duration = (
                perf_counter() - mcp_start
            )

            total_duration = (
                perf_counter() - incident_start
            )

            logger.info(
                "ACT/INCIDENT: MCP call took %.3fs; "
                "total route time %.3fs",
                mcp_duration,
                total_duration,
            )

            # ------------------------------------------------
            # Extract MCP result
            # ------------------------------------------------

            incident_success = bool(
                incident_result.get(
                    "success",
                    False,
                )
            )

            incident_active = bool(
                incident_result.get(
                    "incident_active",
                    False,
                )
            )

            incident_confidence = (
                0.95
                if incident_success
                else 0.0
            )

            logger.info(
                "ACT/INCIDENT: success=%s active=%s",
                incident_success,
                incident_active,
            )

            # ------------------------------------------------
            # Record MCP tool execution
            # ------------------------------------------------

            mcp_tool_call = {
                "tool": (
                    "mcp_check_incident_status"
                ),

                "arguments": {
                    "service_name": service_name,
                },

                "success": incident_success,
            }

            # ------------------------------------------------
            # Errors
            # ------------------------------------------------

            incident_errors: list[str] = []

            if not incident_success:
                incident_errors.append(
                    incident_result.get(
                        "error",
                        "MCP incident check failed.",
                    )
                )

                logger.warning(
                    "ACT/INCIDENT: MCP returned failure: %s",
                    incident_errors,
                )

            # ------------------------------------------------
            # Return state
            # ------------------------------------------------

            return {
                "selected_action": "incident",

                "current_node": "act",

                # MCP incident evidence
                "incident_results": [
                    incident_result
                ],

                "incident_active": (
                    incident_active
                ),

                "incident_confidence": (
                    incident_confidence
                ),

                "incident_status": (
                    incident_result.get(
                        "status"
                    )
                ),

                "incident_code": (
                    incident_result.get(
                        "incident_code"
                    )
                ),

                "incident_severity": (
                    incident_result.get(
                        "severity"
                    )
                ),

                "incident_affects_production": (
                    incident_result.get(
                        "affects_production",
                        False,
                    )
                ),

                "incident_unresolved_critical_alert": (
                    incident_result.get(
                        "unresolved_critical_alert",
                        False,
                    )
                ),

                "incident_security_related": (
                    incident_result.get(
                        "security_related",
                        False,
                    )
                ),

                "incident_data_loss_reported": (
                    incident_result.get(
                        "data_loss_reported",
                        False,
                    )
                ),

                # MCP operational/audit information
                "mcp_tool_calls": [
                    mcp_tool_call
                ],

                # RAG fields
                "retrieval_results": [],
                "retrieval_confidence": 0.0,

                "sufficient_evidence": (
                    incident_success
                ),

                "retrieval_reason": (
                    "Incident investigation "
                    "performed through MCP."
                ),

                # SQL fields
                "sql_query": None,
                "sql_rows": [],
                "sql_row_count": 0,
                "sql_confidence": 0.0,
                "sql_success": False,
                "sql_error": None,
                "sql_explanation": None,
                "sql_tables_used": [],

                # Hybrid fields
                "hybrid_results": [],
                "hybrid_confidence": 0.0,
                "hybrid_success": False,

                "hybrid_reason": (
                    "Incident route uses MCP "
                    "incident investigation."
                ),

                "hybrid_errors": [],

                # Errors
                "errors": incident_errors,
            }

        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
            PermissionError,
        ) as exc:
            logger.exception(
                "ACT/INCIDENT: MCP incident route failed "
                "after %.3fs",
                perf_counter() - incident_start,
            )

            return {
                "selected_action": "incident",

                "current_node": "act",

                # Incident failure state
                "incident_results": [],

                "incident_active": False,

                "incident_confidence": 0.0,

                "incident_status": None,

                "incident_code": None,

                "incident_severity": None,

                "incident_affects_production": (
                    False
                ),

                "incident_unresolved_critical_alert": (
                    False
                ),

                "incident_security_related": (
                    False
                ),

                "incident_data_loss_reported": (
                    False
                ),

                # MCP failure information
                "mcp_tool_calls": [
                    {
                        "tool": (
                            "mcp_check_incident_status"
                        ),
                        "success": False,
                        "error": str(exc),
                    }
                ],

                # RAG fields
                "retrieval_results": [],

                "retrieval_confidence": 0.0,

                "sufficient_evidence": False,

                "retrieval_reason": (
                    "MCP incident investigation "
                    "failed."
                ),

                # SQL fields
                "sql_query": None,

                "sql_rows": [],

                "sql_row_count": 0,

                "sql_confidence": 0.0,

                "sql_success": False,

                "sql_error": None,

                "sql_explanation": None,

                "sql_tables_used": [],

                # Hybrid fields
                "hybrid_results": [],

                "hybrid_confidence": 0.0,

                "hybrid_success": False,

                "hybrid_reason": (
                    "Incident route uses MCP."
                ),

                "hybrid_errors": [],

                # Error
                "errors": [
                    f"MCP incident route failed: {exc}"
                ],
            }

    # ========================================================
    # UNKNOWN ROUTE
    # ========================================================

    logger.error(
        "ACT: unsupported resolution route=%s",
        route,
    )

    return {
        "selected_action": route,

        "current_node": "act",

        "errors": [
            f"Unsupported resolution route: {route}"
        ],
    }