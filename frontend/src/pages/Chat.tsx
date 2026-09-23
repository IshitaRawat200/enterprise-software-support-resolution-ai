import { Children, isValidElement, useEffect, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
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

  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const activeConversation =
    conversations.find(
      (conversation) => conversation.id === activeConversationId,
    ) ?? null;

  const messages = activeConversation?.messages ?? [];

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

        const mappedConversations: Conversation[] = savedConversations
          .slice(0, MAX_RECENT_CONVERSATIONS)
          .map((conversation: ApiConversation) => ({
            id: conversation.conversation_id,

            title:
              conversation.messages
                .find((message) => message.role === "customer")
                ?.content.slice(0, 45) || "Conversation",

            createdAt: conversation.created_at || new Date().toISOString(),

            messages: conversation.messages
              .filter(
                (message) =>
                  message.role === "customer" ||
                  message.role === "ai" ||
                  message.role === "support_agent",
              )
              .map((message) => ({
                id: message.id,
                role: message.role === "customer" ? "user" : "assistant",
                content: message.content,
              })),
          }));

        setConversations(mappedConversations);

        if (mappedConversations.length > 0) {
          setActiveConversationId(mappedConversations[0].id);
        }
      } catch (error) {
        if (!cancelled) {
          console.error("Failed to load conversations:", error);
        }
      }
    }

    loadConversations();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  function createConversation() {
    if (loading) {
      return;
    }

    // Reuse an existing empty "New conversation"
    // instead of creating duplicates.
    const existingEmptyConversation = conversations.find(
      (conversation) =>
        conversation.title === "New conversation" &&
        conversation.messages.length === 0,
    );

    if (existingEmptyConversation) {
      setActiveConversationId(existingEmptyConversation.id);
      setInput("");
      return;
    }

    const conversation: Conversation = {
      id: crypto.randomUUID(),
      title: "New conversation",
      createdAt: new Date().toISOString(),
      messages: [],
    };

    setConversations((current) => [conversation, ...current]);

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

    const conversationId = activeConversationId ?? crypto.randomUUID();

    const isNewConversation = activeConversationId === null;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: messageText,
    };

    setConversations((current) => {
      const existingConversation = current.find(
        (conversation) => conversation.id === conversationId,
      );

      if (existingConversation) {
        return current.map((conversation) =>
          conversation.id === conversationId
            ? {
                ...conversation,
                messages: [...conversation.messages, userMessage],
              }
            : conversation,
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

    if (isNewConversation) {
      setActiveConversationId(conversationId);
    }

    setInput("");
    setLoading(true);

    try {
      const response = await apiRequest<ChatResponse>("/chat", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: messageText,
          conversation_id: conversationId,
        }),
      });

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
                messages: [...conversation.messages, assistantMessage],
              }
            : conversation,
        ),
      );
    } catch (error) {
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
                messages: [...conversation.messages, errorMessage],
              }
            : conversation,
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();

      if (!loading && input.trim()) {
        sendMessage();
      }
    }
  }

  function formatConversationDate(date: string) {
    const conversationDate = new Date(date);
    const today = new Date();

    if (conversationDate.toDateString() === today.toDateString()) {
      return "Today";
    }

    return conversationDate.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  }

  function handleLogout() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);

    localStorage.removeItem(USER_EMAIL_KEY);

    window.location.href = "/login";
  }

  return (
    <AppLayout onLogout={handleLogout}>
      <div className="chat-page">
        <main className="chat-main">
          <header className="chat-header">
            <div>
              <h2>Support Center</h2>

              <p>Intelligent enterprise support powered by ERIS</p>
            </div>

            <div className="eris-status">
              <span>●</span>
              ERIS Online
            </div>
          </header>

          <section className="chat-workspace">
            {/* Conversation history */}

            <aside className="chat-history-panel">
              <div className="chat-history-header">
                <div>
                  <strong>Conversations</strong>

                  <span>Recent support chats</span>
                </div>

                <button
                  type="button"
                  className="new-conversation-button"
                  onClick={createConversation}
                  disabled={loading}
                >
                  + New
                </button>
              </div>

              <div className="conversation-history">
                {conversations.length === 0 ? (
                  <div className="no-conversations">No conversations yet.</div>
                ) : (
                  conversations.map((conversation) => (
                    <button
                      key={conversation.id}
                      type="button"
                      className={`conversation-item ${
                        conversation.id === activeConversationId ? "active" : ""
                      }`}
                      onClick={() => selectConversation(conversation.id)}
                      disabled={loading}
                    >
                      <span className="conversation-icon">✦</span>

                      <span className="conversation-details">
                        <strong>{conversation.title}</strong>

                        <small>
                          {formatConversationDate(conversation.createdAt)}
                        </small>
                      </span>
                    </button>
                  ))
                )}
              </div>
            </aside>

            {/* Conversation area */}

            <div className="chat-conversation">
              {messages.length === 0 ? (
                <div className="chat-empty">
                  <div className="chat-empty-logo">✦</div>

                  <h3>How can ERIS help you?</h3>

                  <p>
                    Ask a question about installation, APIs, authentication,
                    errors, performance, security, or other supported issues.
                  </p>

                  <div className="suggested-questions">
                    <button
                      type="button"
                      onClick={() => setInput("How do I install ERIS?")}
                    >
                      How do I install ERIS?
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        setInput("How do I troubleshoot HTTP 429 errors?")
                      }
                    >
                      How do I troubleshoot HTTP 429 errors?
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        setInput("How do I authenticate with the ERIS API?")
                      }
                    >
                      How do I authenticate with the ERIS API?
                    </button>
                  </div>
                </div>
              ) : (
                <div className="messages-list">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`message-row ${message.role}`}
                    >
                      <div className="message-avatar">
                        {message.role === "user" ? "U" : "E"}
                      </div>

                      <div className="message-content">
                        <span className="message-author">
                          {message.role === "user" ? "You" : "ERIS"}
                        </span>

                        <div className="message-bubble markdown-content">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              ol: ({ children }) => {
                                const items =
                                  Children.toArray(children).filter(
                                    isValidElement,
                                  );

                                return (
                                  <div className="eris-steps">
                                    {items.map((child, index) => (
                                      <div className="eris-step" key={index}>
                                        <span className="eris-step-number">
                                          {index + 1}.
                                        </span>

                                        <div className="eris-step-content">
                                          {child}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                );
                              },

                              li: ({ children }) => <>{children}</>,

                              p: ({ children }) => (
                                <p className="eris-paragraph">{children}</p>
                              ),

                              pre: ({ children }) => (
                                <pre className="eris-code-block">
                                  {children}
                                </pre>
                              ),

                              code: ({ children }) => <code>{children}</code>,
                            }}
                          >
                            {message.content}
                          </ReactMarkdown>
                        </div>

                        {message.role === "assistant" && message.metadata && (
                          <div className="message-metadata">
                            {message.metadata.route && (
                              <span>Route: {message.metadata.route}</span>
                            )}

                            {message.metadata.severity && (
                              <span>Severity: {message.metadata.severity}</span>
                            )}

                            {typeof message.metadata.retrieval_confidence ===
                              "number" && (
                              <span>
                                Confidence:{" "}
                                {Math.round(
                                  message.metadata.retrieval_confidence * 100,
                                )}
                                %
                              </span>
                            )}
                          </div>
                        )}

                        {message.role === "assistant" &&
                          message.metadata?.escalation_required && (
                            <div className="escalation-notice">
                              <strong>Human support required</strong>

                              <p>
                                {message.metadata.escalation_reason ||
                                  "This request has been escalated for support review."}
                              </p>
                            </div>
                          )}
                      </div>
                    </div>
                  ))}

                  {loading && (
                    <div className="message-row assistant">
                      <div className="message-avatar">E</div>

                      <div className="message-content">
                        <span className="message-author">ERIS</span>

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

            {/* Input */}

            <div className="chat-input-area">
              <form className="chat-input-container" onSubmit={sendMessage}>
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={handleInputKeyDown}
                  placeholder="Describe your issue or ask ERIS a question..."
                  rows={1}
                  disabled={loading}
                />

                <button
                  type="submit"
                  disabled={!input.trim() || loading}
                  aria-label="Send message"
                >
                  ↑
                </button>
              </form>

              <p className="chat-disclaimer">
                ERIS uses enterprise knowledge, structured data, and intelligent
                support workflows to assist with your request.
              </p>
            </div>
          </section>
        </main>
      </div>
    </AppLayout>
  );
}

export default Chat;
