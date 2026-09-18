import { useEffect, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../services/api";
import {
  getConversations,
  type Conversation as ApiConversation,
} from "../services/chatService";
import "./Chat.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatResponse {
  message: string;
  conversation_id?: string;
  intent?: string;
  route?: string;
  retrieval_confidence?: number;
  sufficient_evidence?: boolean;
  severity?: string;
  escalation_required?: boolean;
  escalation_reason?: string;
  handoff_summary?: string;
  retrieval_results?: Array<{
    document_name?: string;
    content?: string;
    score?: number;
  }>;
  errors?: string[];
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: ChatResponse;
}

interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  messages: ChatMessage[];
}

const ACCESS_TOKEN_KEY = "eris_access_token";
const USER_EMAIL_KEY = "eris_user_email";
const MAX_RECENT_CONVERSATIONS = 8;

function Chat() {
  const navigate = useNavigate();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] =
    useState<string | null>(null);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const activeConversation =
    conversations.find(
      (conversation) =>
        conversation.id === activeConversationId
    ) ?? null;

  const messages = activeConversation?.messages ?? [];

  // ------------------------------------------------------------
  // Load saved conversations
  // ------------------------------------------------------------

  useEffect(() => {
  let cancelled = false;

  async function loadConversations() {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);

    if (!token) {
      navigate("/login");
      return;
    }

    try {
      const savedConversations = await getConversations();

      if (cancelled) {
        return;
      }

      const mappedConversations: Conversation[] =
        savedConversations
          .slice(0, MAX_RECENT_CONVERSATIONS)
          .map(
            (conversation: ApiConversation) => ({
              id: conversation.conversation_id,

              title:
                conversation.messages.find(
                  (message) =>
                    message.role === "customer"
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
                    message.role === "support_agent"
                )
                .map((message) => ({
                  id: message.id,
                  role:
                    message.role === "customer"
                      ? "user"
                      : "assistant",
                  content: message.content,
                })),
            })
          );

      setConversations(mappedConversations);

      if (mappedConversations.length > 0) {
        setActiveConversationId(
          mappedConversations[0].id
        );
      }
    } catch (error) {
      if (!cancelled) {
        console.error(
          "Failed to load conversations:",
          error
        );
      }
    }
  }

  loadConversations();

  return () => {
    cancelled = true;
  };
}, [navigate]);
  // ------------------------------------------------------------
  // Conversation helpers
  // ------------------------------------------------------------

  function createConversation() {
    if (loading) {
      return;
    }

    const conversation: Conversation = {
      id: crypto.randomUUID(),
      title: "New conversation",
      createdAt: new Date().toISOString(),
      messages: [],
    };

    setConversations((current) => [
      conversation,
      ...current,
    ]);

    setActiveConversationId(conversation.id);
    setInput("");
  }

  function selectConversation(id: string) {
    if (loading) {
      return;
    }

    setActiveConversationId(id);
    setInput("");
  }

  // ------------------------------------------------------------
  // Send message
  // ------------------------------------------------------------

async function sendMessage(event?: FormEvent) {
  event?.preventDefault();

  const messageText = input.trim();

  if (!messageText || loading) {
    return;
  }

  const token = localStorage.getItem(ACCESS_TOKEN_KEY);

  if (!token) {
    navigate("/login");
    return;
  }

  // Always create/use one conversation ID
  const conversationId =
    activeConversationId ?? crypto.randomUUID();

  const isNewConversation =
    activeConversationId === null;

  const userMessage: ChatMessage = {
    id: crypto.randomUUID(),
    role: "user",
    content: messageText,
  };

  // ------------------------------------------------------------
  // Immediately put the conversation + user message into state
  // ------------------------------------------------------------

  setConversations((current) => {
    const existingConversation = current.find(
      (conversation) =>
        conversation.id === conversationId
    );

    if (existingConversation) {
      return current.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              messages: [
                ...conversation.messages,
                userMessage,
              ],
            }
          : conversation
      );
    }

    const newConversation: Conversation = {
      id: conversationId,
      title: messageText.slice(0, 45),
      createdAt: new Date().toISOString(),
      messages: [userMessage],
    };

    return [newConversation, ...current];
  });

  // Make this conversation active immediately
  if (isNewConversation) {
    setActiveConversationId(conversationId);
  }

  setInput("");
  setLoading(true);

  try {
    const response = await apiRequest<ChatResponse>(
      "/chat",
      {
        method: "POST",

        headers: {
          Authorization: `Bearer ${token}`,
        },

        body: JSON.stringify({
          message: messageText,
          conversation_id: conversationId,
        }),
      }
    );

    // ----------------------------------------------------------
    // Add ERIS response
    // ----------------------------------------------------------

    const assistantMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content:
        response.message ||
        "I’m sorry, but I could not generate a resolution.",
      metadata: response,
    };

    setConversations((current) =>
      current.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              messages: [
                ...conversation.messages,
                assistantMessage,
              ],
            }
          : conversation
      )
    );

  } catch (error) {
    // ----------------------------------------------------------
    // Show error inside chat
    // ----------------------------------------------------------

    const errorMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content:
        error instanceof Error
          ? error.message
          : "Unable to reach ERIS. Please try again.",
    };

    setConversations((current) =>
      current.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              messages: [
                ...conversation.messages,
                errorMessage,
              ],
            }
          : conversation
      )
    );
  } finally {
    setLoading(false);
  }
}
  // ------------------------------------------------------------
  // Keyboard handling
  // ------------------------------------------------------------

  function handleInputKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      if (!loading && input.trim()) {
        sendMessage();
      }
    }
  }

  // ------------------------------------------------------------
  // Date formatting
  // ------------------------------------------------------------

  function formatConversationDate(
    date: string
  ) {
    const conversationDate = new Date(date);
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
      }
    );
  }

  // ------------------------------------------------------------
  // Logout
  // ------------------------------------------------------------

  function handleLogout() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(USER_EMAIL_KEY);

    window.location.href = "/login";
  }

  // ------------------------------------------------------------
  // Render
  // ------------------------------------------------------------

  return (
    <div className="chat-page">

      {/* ======================================================
          SIDEBAR
          ====================================================== */}

      <aside className="chat-sidebar">

        <div className="chat-brand">
          <div className="chat-brand-logo">
            E
          </div>

          <div>
            <h1>ERIS</h1>
            <span>AI Support</span>
          </div>
        </div>

        <button
          className="new-conversation-button"
          onClick={createConversation}
          disabled={loading}
        >
          + New conversation
        </button>

        {/* Recent conversations */}

        <div className="conversation-history">
          <div className="conversation-history-title">
            Recent
          </div>

          {conversations.length === 0 ? (
            <div className="no-conversations">
              No previous conversations
            </div>
          ) : (
            conversations
              .slice(
                0,
                MAX_RECENT_CONVERSATIONS
              )
              .map((conversation) => (
                <button
                  key={conversation.id}
                  className={`conversation-item ${
                    conversation.id ===
                    activeConversationId
                      ? "active"
                      : ""
                  }`}
                  onClick={() =>
                    selectConversation(
                      conversation.id
                    )
                  }
                  disabled={loading}
                >
                  <span className="conversation-icon">
                    •
                  </span>

                  <span className="conversation-details">
                    <strong>
                      {conversation.title}
                    </strong>

                    <small>
                      {formatConversationDate(
                        conversation.createdAt
                      )}
                    </small>
                  </span>
                </button>
              ))
          )}
        </div>

        {/* Main navigation */}

        <nav className="chat-navigation">

          <button
            className="chat-nav-item"
            onClick={() =>
              navigate("/dashboard")
            }
          >
            <span>▦</span>
            Dashboard
          </button>

          <button className="chat-nav-item active">
            <span>✦</span>
            AI Support
          </button>

          <button
            className="chat-nav-item"
            onClick={() =>
              navigate("/tickets")
            }
          >
            <span>□</span>
            Tickets
          </button>

          <button
            className="chat-nav-item"
            onClick={() =>
              navigate("/account")
            }
          >
            <span>○</span>
            Account
          </button>

        </nav>

        {/* Bottom navigation */}

        <div className="chat-sidebar-bottom">

          <button className="chat-nav-item">
            <span>⚙</span>
            Settings
          </button>

          <button
            className="chat-nav-item"
            onClick={handleLogout}
          >
            <span>↪</span>
            Sign out
          </button>

        </div>

      </aside>

      {/* ======================================================
          MAIN CHAT
          ====================================================== */}

      <main className="chat-main">

        <header className="chat-header">

          <div>
            <h2>AI Support</h2>

            <p>
              Intelligent enterprise support
              powered by ERIS
            </p>
          </div>

          <div className="eris-status">
            <span>●</span>
            ERIS Online
          </div>

        </header>

        <section className="chat-workspace">

          <div className="chat-conversation">

            {/* Empty state */}

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
                  or other supported issues.
                </p>

                <div className="suggested-questions">

                  <button
                    onClick={() =>
                      setInput(
                        "How do I install ERIS?"
                      )
                    }
                  >
                    How do I install ERIS?
                  </button>

                  <button
                    onClick={() =>
                      setInput(
                        "How do I troubleshoot HTTP 429 errors?"
                      )
                    }
                  >
                    How do I troubleshoot
                    HTTP 429 errors?
                  </button>

                  <button
                    onClick={() =>
                      setInput(
                        "How do I authenticate with the ERIS API?"
                      )
                    }
                  >
                    How do I authenticate
                    with the ERIS API?
                  </button>

                </div>

              </div>

            ) : (

              /* Messages */

              <div className="messages-list">

                {messages.map((message) => (

                  <div
                    key={message.id}
                    className={`message-row ${message.role}`}
                  >

                    <div className="message-avatar">
                      {message.role === "user"
                        ? "U"
                        : "E"}
                    </div>

                    <div className="message-content">

                      <span className="message-author">
                        {message.role === "user"
                          ? "You"
                          : "ERIS"}
                      </span>

                      <div className="message-bubble markdown-content">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            ol: ({ children }) => (
                              <ol className="eris-steps">
                                {children}
                              </ol>
                            ),

                            li: ({ children }) => (
                              <li className="eris-step">
                                {children}
                              </li>
                            ),

                            p: ({ children }) => (
                              <p className="eris-paragraph">
                                {children}
                              </p>
                            ),

                            pre: ({ children }) => (
                              <pre className="eris-code-block">
                                {children}
                              </pre>
                            ),

                            code: ({ children }) => (
                              <code>{children}</code>
                            ),
                          }}
                        >
                          {message.content}
                        </ReactMarkdown>
                      </div>

                      {/* AI metadata */}

                      {message.role ===
                        "assistant" &&
                        message.metadata && (

                          <div className="message-metadata">

                            {message.metadata.route && (
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
                                Confidence:{" "}
                                {Math.round(
                                  message
                                    .metadata
                                    .retrieval_confidence *
                                    100
                                )}
                                %
                              </span>
                            )}

                          </div>
                        )}

                      {/* Escalation */}

                      {message.role ===
                        "assistant" &&
                        message.metadata
                          ?.escalation_required && (

                          <div className="escalation-notice">

                            <strong>
                              Human support required
                            </strong>

                            <p>
                              {message.metadata
                                .escalation_reason ||
                                "This request has been escalated for support review."}
                            </p>

                          </div>
                        )}

                    </div>

                  </div>

                ))}

                {/* Loading indicator */}

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

          {/* ==================================================
              INPUT
              ================================================== */}

          <div className="chat-input-area">

            <form
              className="chat-input-container"
              onSubmit={sendMessage}
            >

              <textarea
                value={input}
                onChange={(event) =>
                  setInput(event.target.value)
                }
                onKeyDown={handleInputKeyDown}
                placeholder="Describe your issue or ask ERIS a question..."
                rows={1}
                disabled={loading}
              />

              <button
                type="submit"
                disabled={
                  !input.trim() || loading
                }
                aria-label="Send message"
              >
                ↑
              </button>

            </form>

            <p className="chat-disclaimer">
              ERIS uses enterprise knowledge,
              structured data, and intelligent
              support workflows to assist with
              your request.
            </p>

          </div>

        </section>

      </main>

    </div>
  );
}

export default Chat;