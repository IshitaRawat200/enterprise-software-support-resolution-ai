import {
  Children,
  isValidElement,
  useEffect,
  useState,
} from "react";
import type {
  FormEvent,
  KeyboardEvent,
} from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../services/api";
import {
  getConversations,
  type Conversation as ApiConversation,
} from "../services/chatService";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import AppLayout from "../components/layout/AppLayout";
import "./Chat.css";

// ============================================================
// TYPES
// ============================================================

interface ChatResponse {
  message: string;
  conversation_id?: string;
  request_id?: string;

  // ----------------------------------------------------------
  // Evaluation status
  // ----------------------------------------------------------

  evaluation_status?:
    | "pending"
    | "completed"
    | "partial"
    | "failed";

  // ----------------------------------------------------------
  // Intent / routing
  // ----------------------------------------------------------

  intent?: string;
  intent_confidence?: number;
  intent_reason?: string;
  route?: string;

  // ----------------------------------------------------------
  // Quality metrics
  // ----------------------------------------------------------

  accuracy?: number | null;
  faithfulness?: number | null;
  answer_relevance?: number | null;
  context_precision?: number | null;
  context_recall?: number | null;
  route_accuracy?: number | null;
  guardrail_effectiveness?: number | null;

  // ----------------------------------------------------------
  // Cost / latency
  // ----------------------------------------------------------

  cost_usd?: number | null;
  latency_ms?: number | null;

  // ----------------------------------------------------------
  // RAG
  // ----------------------------------------------------------

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

  // ----------------------------------------------------------
  // Severity / escalation
  // ----------------------------------------------------------

  severity?: string;
  severity_confidence?: number;
  escalation_required?: boolean;
  escalation_reason?: string;
  escalation_priority?: string;
  escalation_type?: string;
  escalation_reference_id?: string;
  ticket_id?: string;
  escalation_id?: string;
  ticket_number?: string;

  // ----------------------------------------------------------
  // Resolution
  // ----------------------------------------------------------

  recommended_action?: string;
  handoff_summary?: string;

  // ----------------------------------------------------------
  // SQL
  // ----------------------------------------------------------

  sql_query?: string;
  sql_rows?: Array<Record<string, unknown>>;
  sql_confidence?: number;
  sql_success?: boolean;

  // ----------------------------------------------------------
  // Hybrid / MCP
  // ----------------------------------------------------------

  hybrid_results?: Array<Record<string, unknown>>;
  hybrid_confidence?: number;
  mcp_tool_calls?: Array<Record<string, unknown>>;

  // ----------------------------------------------------------
  // Errors
  // ----------------------------------------------------------

  errors?: string[];
  ragas_errors?: string[];

  evaluation?: {
    status?:
      | "pending"
      | "completed"
      | "partial"
      | "failed";
    ragas_errors?: string[];
  };
}

interface EvaluationStatusResponse {
  request_id: string;
  evaluation_status?:
    | "pending"
    | "completed"
    | "partial"
    | "failed";
  accuracy?: number | null;
  faithfulness?: number | null;
  answer_relevance?: number | null;
  context_precision?: number | null;
  context_recall?: number | null;
  route_accuracy?: number | null;
  guardrail_effectiveness?: number | null;
  cost_usd?: number | null;
  latency_ms?: number | null;
  ragas_errors?: string[];
}

type ChatMetadata = Omit<
  ChatResponse,
  "message"
>;

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: ChatMetadata;
}

interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  messages: ChatMessage[];
}

// ============================================================
// CONSTANTS
// ============================================================

const ACCESS_TOKEN_KEY = "eris_access_token";
const USER_EMAIL_KEY = "eris_user_email";
const MAX_RECENT_CONVERSATIONS = 10;

const EVALUATION_POLL_INTERVAL_MS = 5000;
const MAX_EVALUATION_POLL_ATTEMPTS = 36;
const SHOW_EVALUATION_DEBUG =
  import.meta.env
    .VITE_SHOW_EVALUATION_DEBUG === "true";

// ============================================================
// HELPERS
// ============================================================

const formatPercent = (
  value: number | null | undefined,
  pending = false,
  timedOut = false,
): string => {
  if (value == null) {
    return pending
      ? "Pending"
      : timedOut
        ? "Timed out"
        : "N/A";
  }

  const normalized =
    value <= 1 ? value * 100 : value;

  return `${normalized.toFixed(1)}%`;
};

const formatCost = (
  value: number | null | undefined,
): string => {
  if (value == null) {
    return "Not tracked";
  }

  return `$${value.toFixed(6)}`;
};

const formatLatency = (
  value: number | null | undefined,
): string => {
  if (value == null) {
    return "N/A";
  }

  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)}s`;
  }

  return `${value.toFixed(0)}ms`;
};

// ============================================================
// API CONVERSATION MAPPING
// ============================================================

const mapApiConversations = (
  savedConversations: ApiConversation[],
): Conversation[] =>
  [...savedConversations]
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
    .map(
      (
        conversation: ApiConversation,
      ) => ({
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

        messages:
          conversation.messages
            .filter(
              (message) =>
                message.role ===
                  "customer" ||
                message.role === "ai" ||
                message.role ===
                  "support_agent",
            )
            .map((message) => ({
              id: message.id,

              role:
                message.role === "customer"
                  ? "user"
                  : "assistant",

              content: message.content,

              metadata:
                message.role === "ai" &&
                message.metadata &&
                typeof message.metadata ===
                  "object"
                  ? (message.metadata as ChatMetadata)
                  : undefined,
            })),
      }),
    );

// ============================================================
// RESPONSE METRICS
// ============================================================

const MetricTag = ({
  label,
  value,
}: {
  label: string;
  value: string;
}) => {
  return (
    <span>
      {label}: {value}
    </span>
  );
};

const ChatMetrics = ({
  metadata,
}: {
  metadata?: ChatMetadata;
}) => {
  if (!metadata) {
    return null;
  }

  const ragasPending =
    metadata.route === "rag" &&
    (metadata.evaluation_status ==
      null ||
      metadata.evaluation_status ===
        "pending");

  const ragasTimedOut =
    metadata.route === "rag" &&
    (metadata.evaluation_status ===
      "partial" ||
      metadata.evaluation_status ===
        "failed");

  const evaluationStatus =
    metadata.evaluation_status ??
    metadata.evaluation?.status ??
    "unknown";

  const ragasErrors =
    metadata.ragas_errors ??
    metadata.evaluation?.ragas_errors ??
    [];

  return (
    <>
      <MetricTag
        label="Accuracy"
        value={formatPercent(
          metadata.accuracy,
          ragasPending,
          ragasTimedOut,
        )}
      />

      <MetricTag
        label="Faithfulness"
        value={formatPercent(
          metadata.faithfulness,
          ragasPending,
          ragasTimedOut,
        )}
      />

      <MetricTag
        label="Answer Relevancy"
        value={formatPercent(
          metadata.answer_relevance,
          ragasPending,
          ragasTimedOut,
        )}
      />

      <MetricTag
        label="Context Precision"
        value={formatPercent(
          metadata.context_precision,
          ragasPending,
          ragasTimedOut,
        )}
      />

      <MetricTag
        label="Context Recall"
        value={formatPercent(
          metadata.context_recall,
          ragasPending,
          ragasTimedOut,
        )}
      />

      <MetricTag
        label="Route Accuracy"
        value={formatPercent(
          metadata.route_accuracy,
        )}
      />

      <MetricTag
        label="Guardrail"
        value={formatPercent(
          metadata.guardrail_effectiveness,
        )}
      />

      <MetricTag
        label="Cost"
        value={formatCost(
          metadata.cost_usd,
        )}
      />

      <MetricTag
        label="Latency"
        value={formatLatency(
          metadata.latency_ms,
        )}
      />

      {SHOW_EVALUATION_DEBUG ? (
        <div
          style={{
            marginTop: "6px",
            fontSize: "11px",
            color: "#64748b",
            lineHeight: 1.4,
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
            padding: "8px 10px",
            wordBreak: "break-word",
            flexBasis: "100%",
          }}
        >
          <div>
            eval_status: {evaluationStatus} | route: {metadata.route ?? "n/a"} | request_id: {metadata.request_id ?? "n/a"}
          </div>
          <div>
            ragas_errors: {ragasErrors.length > 0 ? ragasErrors.join(" | ") : "none"}
          </div>
        </div>
      ) : null}
    </>
  );
};

// ============================================================
// CHAT PAGE
// ============================================================

function Chat() {
  const navigate = useNavigate();

  const [
    conversations,
    setConversations,
  ] = useState<Conversation[]>([]);

  const [
    activeConversationId,
    setActiveConversationId,
  ] = useState<string | null>(null);

  const [input, setInput] = useState("");
  const [loading, setLoading] =
    useState(false);

  const activeConversation =
    conversations.find(
      (conversation) =>
        conversation.id ===
        activeConversationId,
    ) ?? null;

  const messages =
    activeConversation?.messages ?? [];

  // ==========================================================
  // LOAD CONVERSATIONS
  // ==========================================================

  useEffect(() => {
    let cancelled = false;

    async function loadConversations() {
      const token =
        localStorage.getItem(
          ACCESS_TOKEN_KEY,
        );

      if (!token) {
        navigate("/login");
        return;
      }

      try {
        const savedConversations =
          await getConversations();

        if (cancelled) {
          return;
        }

        const mappedConversations =
          mapApiConversations(
            savedConversations,
          );

        setConversations(
          mappedConversations,
        );

        if (
          mappedConversations.length >
          0
        ) {
          setActiveConversationId(
            mappedConversations[0].id,
          );
        }
      } catch (error) {
        if (!cancelled) {
          console.error(
            "Failed to load conversations:",
            error,
          );
        }
      }
    }

    loadConversations();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  // ==========================================================
  // REFRESH ASYNCHRONOUS EVALUATION METRICS
  // ==========================================================

  async function refreshConversationMetrics(
    conversationId: string,
    requestId?: string,
  ): Promise<void> {
    if (!requestId) {
      return;
    }

    for (
      let attempt = 0;
      attempt < MAX_EVALUATION_POLL_ATTEMPTS;
      attempt += 1
    ) {
      try {
        const evaluation =
          await apiRequest<EvaluationStatusResponse>(
            `/chat/evaluations/${requestId}?refresh=${Date.now()}`,
            {
              method: "GET",
            },
          );

        setConversations((current) =>
          current.map((conversation) => {
            if (
              conversation.id !==
              conversationId
            ) {
              return conversation;
            }

            const messages =
              conversation.messages.map(
                (message) => {
                  if (
                    message.role !==
                    "assistant"
                  ) {
                    return message;
                  }

                  const messageRequestId =
                    message.metadata?.request_id;

                  if (
                    messageRequestId !==
                    requestId
                  ) {
                    return message;
                  }

                  return {
                    ...message,
                    metadata: {
                      ...message.metadata,
                      ...evaluation,
                      request_id: requestId,
                    },
                  };
                },
              );

            return {
              ...conversation,
              messages,
            };
          }),
        );

        const status =
          evaluation.evaluation_status;

        if (
          status ===
            "completed" ||
          status ===
            "partial" ||
          status ===
            "failed"
        ) {
          return;
        }
      } catch (error) {
        console.warn(
          "Failed to refresh asynchronous evaluation metrics:",
          error,
        );
      }

      await new Promise<void>(
        (resolve) =>
          window.setTimeout(
            resolve,
            EVALUATION_POLL_INTERVAL_MS,
          ),
      );
    }

    console.warn(
      "Evaluation polling timed out:",
      conversationId,
    );
  }
  // ==========================================================
  // NEW CONVERSATION
  // ==========================================================

  function createConversation() {
    if (loading) {
      return;
    }

    const existingEmptyConversation =
      conversations.find(
        (conversation) =>
          conversation.title ===
            "New conversation" &&
          conversation.messages.length ===
            0,
      );

    if (existingEmptyConversation) {
      setActiveConversationId(
        existingEmptyConversation.id,
      );
      setInput("");
      return;
    }

    const conversation: Conversation = {
      id: crypto.randomUUID(),
      title: "New conversation",
      createdAt:
        new Date().toISOString(),
      messages: [],
    };

    setConversations((current) => [
      conversation,
      ...current,
    ]);

    setActiveConversationId(
      conversation.id,
    );

    setInput("");
  }

  // ==========================================================
  // SELECT CONVERSATION
  // ==========================================================

  function selectConversation(
    id: string,
  ) {
    if (loading) {
      return;
    }

    setActiveConversationId(id);
    setInput("");
  }

  // ==========================================================
  // SEND MESSAGE
  // ==========================================================

  async function sendMessage(
    event?: FormEvent,
  ) {
    event?.preventDefault();

    const messageText =
      input.trim();

    if (!messageText || loading) {
      return;
    }

    const token =
      localStorage.getItem(
        ACCESS_TOKEN_KEY,
      );

    if (!token) {
      navigate("/login");
      return;
    }

    const conversationId =
      activeConversationId ??
      crypto.randomUUID();

    const isNewConversation =
      activeConversationId === null;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: messageText,
    };

    // --------------------------------------------------------
    // Optimistically add the user's question immediately.
    // --------------------------------------------------------

    setConversations((current) => {
      const existingConversation =
        current.find(
          (conversation) =>
            conversation.id ===
            conversationId,
        );

      if (existingConversation) {
        return current.map(
          (conversation) =>
            conversation.id ===
            conversationId
              ? {
                  ...conversation,
                  title:
                    conversation.title ===
                    "New conversation"
                      ? messageText.slice(
                          0,
                          45,
                        )
                      : conversation.title,
                  createdAt:
                    new Date().toISOString(),
                  messages: [
                    ...conversation.messages,
                    userMessage,
                  ],
                }
              : conversation,
        );
      }

      const newConversation: Conversation =
        {
          id: conversationId,
          title:
            messageText.slice(0, 45),
          createdAt:
            new Date().toISOString(),
          messages: [userMessage],
        };

      return [
        newConversation,
        ...current,
      ];
    });

    if (isNewConversation) {
      setActiveConversationId(
        conversationId,
      );
    }

    setInput("");
    setLoading(true);

    try {
      const response =
        await apiRequest<ChatResponse>(
          "/chat",
          {
            method: "POST",

            headers: {
              Authorization: `Bearer ${token}`,
            },

            body: JSON.stringify({
              message: messageText,
              conversation_id:
                conversationId,
            }),
          },
        );

      // ------------------------------------------------------
      // IMPORTANT:
      // /chat has now returned the AI answer.
      // Append the assistant message.
      // ------------------------------------------------------

      const assistantMessage: ChatMessage =
        {
          id: crypto.randomUUID(),
          role: "assistant",

          content:
            response.message ||
            "I’m sorry, but I could not generate a resolution.",

          metadata: response,
        };

      setConversations((current) =>
        current.map(
          (conversation) =>
            conversation.id ===
            conversationId
              ? {
                  ...conversation,
                  createdAt:
                    new Date().toISOString(),
                  messages: [
                    ...conversation.messages,
                    assistantMessage,
                  ],
                }
              : conversation,
        ),
      );

      // ------------------------------------------------------
      // RAGAS is intentionally asynchronous.
      // Start polling after the response is displayed.
      // ------------------------------------------------------

      void refreshConversationMetrics(
        conversationId,
        response.request_id,
      );
    } catch (error) {
      const errorMessage: ChatMessage =
        {
          id: crypto.randomUUID(),
          role: "assistant",

          content:
            error instanceof Error
              ? error.message
              : "Unable to reach ERIS. Please try again.",
        };

      setConversations((current) =>
        current.map(
          (conversation) =>
            conversation.id ===
            conversationId
              ? {
                  ...conversation,
                  messages: [
                    ...conversation.messages,
                    errorMessage,
                  ],
                }
              : conversation,
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  // ==========================================================
  // ENTER KEY
  // ==========================================================

  function handleInputKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      if (
        !loading &&
        input.trim()
      ) {
        sendMessage();
      }
    }
  }

  // ==========================================================
  // DATE
  // ==========================================================

  function formatConversationDate(
    date: string,
  ) {
    const conversationDate =
      new Date(date);

    const today = new Date();

    if (
      conversationDate.toDateString() ===
      today.toDateString()
    ) {
      return "Today";
    }

    return conversationDate.toLocaleDateString(
      undefined,
      {
        month: "short",
        day: "numeric",
      },
    );
  }

  // ==========================================================
  // LOGOUT
  // ==========================================================

  function handleLogout() {
    localStorage.removeItem(
      ACCESS_TOKEN_KEY,
    );

    localStorage.removeItem(
      USER_EMAIL_KEY,
    );

    window.location.href = "/login";
  }

  // ==========================================================
  // RENDER
  // ==========================================================

  return (
    <AppLayout
      onLogout={handleLogout}
    >
      <div className="chat-page">
        <main className="chat-main">
          <header className="chat-header">
            <div>
              <h2>Support Center</h2>

              <p>
                Intelligent enterprise
                support powered by ERIS
              </p>
            </div>

            <div className="eris-status">
              <span>●</span>
              ERIS Online
            </div>
          </header>

          <section className="chat-workspace">

            {/* =================================================
                CONVERSATION HISTORY
            ================================================= */}

            <aside className="chat-history-panel">
              <div className="chat-history-header">
                <div>
                  <strong>
                    Conversations
                  </strong>

                  <span>
                    Recent support chats
                  </span>
                </div>

                <button
                  type="button"
                  className="new-conversation-button"
                  onClick={
                    createConversation
                  }
                  disabled={loading}
                >
                  + New
                </button>
              </div>

              <div className="conversation-history">
                {conversations.length ===
                0 ? (
                  <div className="no-conversations">
                    No conversations yet.
                  </div>
                ) : (
                  conversations.map(
                    (conversation) => (
                      <button
                        key={
                          conversation.id
                        }
                        type="button"
                        className={`conversation-item ${
                          conversation.id ===
                          activeConversationId
                            ? "active"
                            : ""
                        }`}
                        onClick={() =>
                          selectConversation(
                            conversation.id,
                          )
                        }
                        disabled={loading}
                      >
                        <span className="conversation-icon">
                          ✦
                        </span>

                        <span className="conversation-details">
                          <strong>
                            {
                              conversation.title
                            }
                          </strong>

                          <small>
                            {formatConversationDate(
                              conversation.createdAt,
                            )}
                          </small>
                        </span>
                      </button>
                    ),
                  )
                )}
              </div>
            </aside>

            {/* =================================================
                CONVERSATION
            ================================================= */}

            <div className="chat-conversation">
              {messages.length === 0 ? (
                <div className="chat-empty">
                  <div className="chat-empty-logo">
                    ✦
                  </div>

                  <h3>
                    How can ERIS help you?
                  </h3>

                  <p>
                    Ask a question about
                    installation, APIs,
                    authentication, errors,
                    performance, security,
                    or other supported
                    issues.
                  </p>

                  <div className="suggested-questions">
                    <button
                      type="button"
                      onClick={() =>
                        setInput(
                          "How do I install ERIS?",
                        )
                      }
                    >
                      How do I install ERIS?
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        setInput(
                          "How do I troubleshoot HTTP 429 errors?",
                        )
                      }
                    >
                      How do I troubleshoot
                      HTTP 429 errors?
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        setInput(
                          "How do I authenticate with the ERIS API?",
                        )
                      }
                    >
                      How do I authenticate
                      with the ERIS API?
                    </button>
                  </div>
                </div>
              ) : (
                <div className="messages-list">
                  {messages.map(
                    (message) => (
                      <div
                        key={message.id}
                        className={`message-row ${message.role}`}
                      >
                        <div className="message-avatar">
                          {message.role ===
                          "user"
                            ? "U"
                            : "E"}
                        </div>

                        <div className="message-content">
                          <span className="message-author">
                            {message.role ===
                            "user"
                              ? "You"
                              : "ERIS"}
                          </span>

                          <div className="message-bubble markdown-content">
                            <ReactMarkdown
                              remarkPlugins={[
                                remarkGfm,
                              ]}
                              components={{
                                ol: ({
                                  children,
                                }) => {
                                  const items =
                                    Children.toArray(
                                      children,
                                    ).filter(
                                      isValidElement,
                                    );

                                  return (
                                    <div className="eris-steps">
                                      {items.map(
                                        (
                                          child,
                                          index,
                                        ) => (
                                          <div
                                            className="eris-step"
                                            key={
                                              index
                                            }
                                          >
                                            <span className="eris-step-number">
                                              {index +
                                                1}
                                              .
                                            </span>

                                            <div className="eris-step-content">
                                              {
                                                child
                                              }
                                            </div>
                                          </div>
                                        ),
                                      )}
                                    </div>
                                  );
                                },

                                li: ({
                                  children,
                                }) => (
                                  <>
                                    {
                                      children
                                    }
                                  </>
                                ),

                                p: ({
                                  children,
                                }) => (
                                  <p className="eris-paragraph">
                                    {
                                      children
                                    }
                                  </p>
                                ),

                                pre: ({
                                  children,
                                }) => (
                                  <pre className="eris-code-block">
                                    {
                                      children
                                    }
                                  </pre>
                                ),

                                code: ({
                                  children,
                                }) => (
                                  <code>
                                    {
                                      children
                                    }
                                  </code>
                                ),
                              }}
                            >
                              {
                                message.content
                              }
                            </ReactMarkdown>
                          </div>

                          {/* =================================================
                              ROUTE / RETRIEVAL METADATA
                          ================================================= */}

                          {message.role ===
                            "assistant" &&
                            message.metadata && (
                              <div className="message-metadata">
                                {message.metadata
                                  .route && (
                                  <span>
                                    Route:{" "}
                                    {
                                      message
                                        .metadata
                                        .route
                                    }
                                  </span>
                                )}

                                {message.metadata
                                  .severity && (
                                  <span>
                                    Severity:{" "}
                                    {
                                      message
                                        .metadata
                                        .severity
                                    }
                                  </span>
                                )}

                                {typeof message
                                  .metadata
                                  .retrieval_confidence ===
                                  "number" && (
                                  <span>
                                    Retrieval
                                    Confidence:{" "}
                                    {Math.round(
                                      message
                                        .metadata
                                        .retrieval_confidence *
                                        100,
                                    )}
                                    %
                                  </span>
                                )}

                                {message.metadata
                                  .sufficient_evidence !==
                                  undefined && (
                                  <span>
                                    Evidence:{" "}
                                    {message
                                      .metadata
                                      .sufficient_evidence
                                      ? "Sufficient"
                                      : "Insufficient"}
                                  </span>
                                )}

                                <ChatMetrics
                                  metadata={
                                    message.metadata
                                  }
                                />
                              </div>
                            )}

                          {/* =================================================
                              ESCALATION
                          ================================================= */}

                          {message.role ===
                            "assistant" &&
                            message.metadata
                              ?.escalation_required && (
                              <div className="escalation-notice">
                                <strong>
                                  Human support
                                  required
                                </strong>

                                <p>
                                  {message
                                    .metadata
                                    .escalation_reason ||
                                    "This request has been escalated for support review."}
                                </p>

                                {message
                                  .metadata
                                  .ticket_number && (
                                  <p>
                                    Ticket:{" "}
                                    {
                                      message
                                        .metadata
                                        .ticket_number
                                    }
                                  </p>
                                )}
                              </div>
                            )}
                        </div>
                      </div>
                    ),
                  )}

                  {/* =================================================
                      LOADING
                  ================================================= */}

                  {loading && (
                    <div className="message-row assistant">
                      <div className="message-avatar">
                        E
                      </div>

                      <div className="message-content">
                        <span className="message-author">
                          ERIS
                        </span>

                        <div className="message-bubble typing">
                          <span />
                          <span />
                          <span />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* =================================================
                INPUT
            ================================================= */}

            <div className="chat-input-area">
              <form
                className="chat-input-container"
                onSubmit={sendMessage}
              >
                <textarea
                  value={input}
                  onChange={(event) =>
                    setInput(
                      event.target.value,
                    )
                  }
                  onKeyDown={
                    handleInputKeyDown
                  }
                  placeholder="Describe your issue or ask ERIS a question..."
                  rows={1}
                  disabled={loading}
                />

                <button
                  type="submit"
                  disabled={
                    !input.trim() ||
                    loading
                  }
                  aria-label="Send message"
                >
                  ↑
                </button>
              </form>

              <p className="chat-disclaimer">
                ERIS uses enterprise
                knowledge, structured data,
                and intelligent support
                workflows to assist with your
                request.
              </p>
            </div>
          </section>
        </main>
      </div>
    </AppLayout>
  );
}

export default Chat;