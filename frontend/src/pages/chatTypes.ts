export interface ChatResponse {
  message: string;
  conversation_id?: string;

  intent?: string;
  intent_confidence?: number;
  intent_reason?: string;
  route?: string;

  accuracy?: number | null;
  faithfulness?: number | null;
  answer_relevance?: number | null;
  context_precision?: number | null;
  context_recall?: number | null;
  route_accuracy?: number | null;
  guardrail_effectiveness?: number | null;

  cost_usd?: number | null;
  latency_ms?: number | null;

  retrieval_confidence?: number;
  sufficient_evidence?: boolean;

  retrieval_results?: Array<{
    document_name?: string;
    content?: string;
    score?: number;
    vector_score?: number;
    rrf_score?: number;
    source?: string;
  }>;

  severity?: string;
  severity_confidence?: number;
  severity_reason?: string;

  escalation_required?: boolean;
  escalation_reason?: string;
  escalation_priority?: string;
  escalation_type?: string;
  escalation_reference_id?: string;
  ticket_id?: string;
  escalation_id?: string;
  ticket_number?: string;

  recommended_action?: string;
  handoff_summary?: string;

  sql_query?: string;
  sql_rows?: Array<Record<string, unknown>>;
  sql_confidence?: number;
  sql_success?: boolean;

  hybrid_results?: Array<Record<string, unknown>>;
  hybrid_confidence?: number;
  mcp_tool_calls?: Array<Record<string, unknown>>;

  errors?: string[];

  // Asynchronous production evaluation state.
  evaluation_status?: "pending" | "partial" | "completed" | string;
  ragas_evaluated?: boolean;
  ragas_errors?: string[];
}

export type ChatMetadata = Omit<ChatResponse, "message">;

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: ChatMetadata;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  messages: ChatMessage[];
}
