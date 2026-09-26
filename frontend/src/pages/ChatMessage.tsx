import {
  Children,
  isValidElement,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import ChatMetrics from "./ChatMetrics";
import type { ChatMessage as ChatMessageType } from "./chatTypes";

export default function ChatMessage({
  message,
}: {
  message: ChatMessageType;
}) {
  return (
    <div
      className={`message-row ${message.role}`}
    >
      <div className="message-avatar">
        {message.role === "user" ? "U" : "E"}
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
              ol: ({ children }) => {
                const items =
                  Children.toArray(
                    children,
                  ).filter(isValidElement);

                return (
                  <div className="eris-steps">
                    {items.map(
                      (child, index) => (
                        <div
                          className="eris-step"
                          key={index}
                        >
                          <span className="eris-step-number">
                            {index + 1}.
                          </span>

                          <div className="eris-step-content">
                            {child}
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                );
              },

              li: ({ children }) => (
                <>{children}</>
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

        {message.role === "assistant" &&
          message.metadata && (
            <div className="message-metadata">
              {message.metadata.route && (
                <span>
                  Route:{" "}
                  {message.metadata.route}
                </span>
              )}

              {message.metadata.severity && (
                <span>
                  Severity:{" "}
                  {message.metadata.severity}
                </span>
              )}

              {typeof message.metadata
                .retrieval_confidence ===
                "number" && (
                <span>
                  Retrieval Confidence:{" "}
                  {Math.round(
                    message.metadata
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
                  {message.metadata
                    .sufficient_evidence
                    ? "Sufficient"
                    : "Insufficient"}
                </span>
              )}

              {message.metadata
                .evaluation_status ===
                "pending" && (
                <span>
                  Evaluation: pending
                </span>
              )}
            </div>
          )}

        {message.role === "assistant" &&
          message.metadata && (
            <ChatMetrics
              metadata={message.metadata}
            />
          )}

        {message.role === "assistant" &&
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

              {message.metadata
                .ticket_number && (
                <p>
                  Ticket:{" "}
                  {
                    message.metadata
                      .ticket_number
                  }
                </p>
              )}
            </div>
          )}
      </div>
    </div>
  );
}
