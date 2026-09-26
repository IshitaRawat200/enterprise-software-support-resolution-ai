import type { Conversation as ApiConversation } from "../services/chatService";
import type {
  ChatMetadata,
  Conversation,
} from "./chatTypes";

export const ACCESS_TOKEN_KEY = "eris_access_token";
export const USER_EMAIL_KEY = "eris_user_email";
export const MAX_RECENT_CONVERSATIONS = 10;

export function formatPercent(
  value: number | null | undefined,
): string {
  if (value == null) {
    return "N/A";
  }

  const normalized = value <= 1 ? value * 100 : value;
  return `${normalized.toFixed(1)}%`;
}

export function formatCost(
  value: number | null | undefined,
): string {
  if (value == null) {
    return "N/A";
  }

  return `$${value.toFixed(6)}`;
}

export function formatLatency(
  value: number | null | undefined,
): string {
  if (value == null) {
    return "N/A";
  }

  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)}s`;
  }

  return `${value.toFixed(0)}ms`;
}

/**
 * The backend returns JSONB metadata as an object.
 * Keep only values that are safe for the Chat UI.
 */
function normalizeMetadata(
  value: unknown,
): ChatMetadata | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }

  const raw = value as Record<string, unknown>;

  const metadata: ChatMetadata = {
    conversation_id:
      typeof raw.conversation_id === "string"
        ? raw.conversation_id
        : undefined,

    intent:
      typeof raw.intent === "string"
        ? raw.intent
        : undefined,

    intent_confidence:
      typeof raw.intent_confidence === "number"
        ? raw.intent_confidence
        : undefined,

    intent_reason:
      typeof raw.intent_reason === "string"
        ? raw.intent_reason
        : undefined,

    route:
      typeof raw.route === "string"
        ? raw.route
        : undefined,

    accuracy:
      typeof raw.accuracy === "number"
        ? raw.accuracy
        : null,

    faithfulness:
      typeof raw.faithfulness === "number"
        ? raw.faithfulness
        : null,

    answer_relevance:
      typeof raw.answer_relevance === "number"
        ? raw.answer_relevance
        : null,

    context_precision:
      typeof raw.context_precision === "number"
        ? raw.context_precision
        : null,

    context_recall:
      typeof raw.context_recall === "number"
        ? raw.context_recall
        : null,

    route_accuracy:
      typeof raw.route_accuracy === "number"
        ? raw.route_accuracy
        : null,

    guardrail_effectiveness:
      typeof raw.guardrail_effectiveness === "number"
        ? raw.guardrail_effectiveness
        : null,

    cost_usd:
      typeof raw.cost_usd === "number"
        ? raw.cost_usd
        : null,

    latency_ms:
      typeof raw.latency_ms === "number"
        ? raw.latency_ms
        : null,

    retrieval_confidence:
      typeof raw.retrieval_confidence === "number"
        ? raw.retrieval_confidence
        : undefined,

    sufficient_evidence:
      typeof raw.sufficient_evidence === "boolean"
        ? raw.sufficient_evidence
        : undefined,

    severity:
      typeof raw.severity === "string"
        ? raw.severity
        : undefined,

    severity_confidence:
      typeof raw.severity_confidence === "number"
        ? raw.severity_confidence
        : undefined,

    severity_reason:
      typeof raw.severity_reason === "string"
        ? raw.severity_reason
        : undefined,

    escalation_required:
      typeof raw.escalation_required === "boolean"
        ? raw.escalation_required
        : undefined,

    escalation_reason:
      typeof raw.escalation_reason === "string"
        ? raw.escalation_reason
        : undefined,

    escalation_priority:
      typeof raw.escalation_priority === "string"
        ? raw.escalation_priority
        : undefined,

    escalation_type:
      typeof raw.escalation_type === "string"
        ? raw.escalation_type
        : undefined,

    escalation_reference_id:
      typeof raw.escalation_reference_id === "string"
        ? raw.escalation_reference_id
        : undefined,

    ticket_id:
      typeof raw.ticket_id === "string"
        ? raw.ticket_id
        : undefined,

    escalation_id:
      typeof raw.escalation_id === "string"
        ? raw.escalation_id
        : undefined,

    ticket_number:
      typeof raw.ticket_number === "string"
        ? raw.ticket_number
        : undefined,

    recommended_action:
      typeof raw.recommended_action === "string"
        ? raw.recommended_action
        : undefined,

    handoff_summary:
      typeof raw.handoff_summary === "string"
        ? raw.handoff_summary
        : undefined,

    sql_query:
      typeof raw.sql_query === "string"
        ? raw.sql_query
        : undefined,

    sql_rows:
      Array.isArray(raw.sql_rows)
        ? raw.sql_rows.filter(
            (item): item is Record<string, unknown> =>
              !!item &&
              typeof item === "object",
          )
        : undefined,

    sql_confidence:
      typeof raw.sql_confidence === "number"
        ? raw.sql_confidence
        : undefined,

    sql_success:
      typeof raw.sql_success === "boolean"
        ? raw.sql_success
        : undefined,

    hybrid_results:
      Array.isArray(raw.hybrid_results)
        ? raw.hybrid_results.filter(
            (item): item is Record<string, unknown> =>
              !!item &&
              typeof item === "object",
          )
        : undefined,

    hybrid_confidence:
      typeof raw.hybrid_confidence === "number"
        ? raw.hybrid_confidence
        : undefined,

    mcp_tool_calls:
      Array.isArray(raw.mcp_tool_calls)
        ? raw.mcp_tool_calls.filter(
            (item): item is Record<string, unknown> =>
              !!item &&
              typeof item === "object",
          )
        : undefined,

    errors:
      Array.isArray(raw.errors)
        ? raw.errors.map(String)
        : undefined,

    evaluation_status:
      typeof raw.evaluation_status === "string"
        ? raw.evaluation_status
        : undefined,

    ragas_evaluated:
      typeof raw.ragas_evaluated === "boolean"
        ? raw.ragas_evaluated
        : undefined,

    ragas_errors:
      Array.isArray(raw.ragas_errors)
        ? raw.ragas_errors.map(String)
        : undefined,
  };

  return metadata;
}

export function mapApiConversations(
  savedConversations: ApiConversation[],
): Conversation[] {
  return [...savedConversations]
    .sort(
      (a, b) =>
        new Date(
          b.created_at || 0,
        ).getTime() -
        new Date(
          a.created_at || 0,
        ).getTime(),
    )
    .slice(0, MAX_RECENT_CONVERSATIONS)
    .map((conversation) => ({
      id: conversation.conversation_id,

      title:
        conversation.messages.find(
          (message) =>
            message.role === "customer",
        )?.content.slice(0, 45) ||
        "Conversation",

      createdAt:
        conversation.created_at ||
        new Date().toISOString(),

      messages: conversation.messages
        .filter(
          (message) =>
            message.role === "customer" ||
            message.role === "ai" ||
            message.role === "support_agent",
        )
        .map((message) => ({
          id: message.id,

          role:
            message.role === "customer"
              ? "user"
              : "assistant",

          content: message.content,

          metadata:
            message.role === "ai"
              ? normalizeMetadata(
                  (
                    message as typeof message & {
                      metadata?: unknown;
                    }
                  ).metadata,
                )
              : undefined,
        })),
    }));
}
