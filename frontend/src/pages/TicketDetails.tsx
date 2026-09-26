import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  getTicket,
  type Ticket,
} from "../services/ticketService";
import AppLayout from "../components/layout/AppLayout";
import "./TicketDetails.css";

const ACCESS_TOKEN_KEY = "eris_access_token";
const USER_EMAIL_KEY = "eris_user_email";

function TicketDetails() {
  const { ticketId } =
    useParams<{ ticketId: string }>();

  const navigate = useNavigate();

  const [ticket, setTicket] =
    useState<Ticket | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  // ======================================================
  // LOAD TICKET
  // ======================================================

  useEffect(() => {
    let cancelled = false;

    async function loadTicket() {
      const token = localStorage.getItem(
        ACCESS_TOKEN_KEY
      );

      if (!token) {
        navigate("/login");
        return;
      }

      if (!ticketId) {
        setError("Ticket ID is missing.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError("");

        console.log(
          "Loading ticket:",
          ticketId
        );

        const data =
          await getTicket(ticketId);

        console.log(
          "Ticket loaded:",
          data
        );

        if (!cancelled) {
          setTicket(data);
        }
      } catch (err) {
        console.error(
          "Failed to load ticket:",
          err
        );

        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load ticket."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadTicket();

    return () => {
      cancelled = true;
    };
  }, [ticketId, navigate]);

  // ======================================================
  // LOGOUT
  // ======================================================

  function handleLogout() {
    localStorage.removeItem(
      ACCESS_TOKEN_KEY
    );

    localStorage.removeItem(
      USER_EMAIL_KEY
    );

    navigate("/login");
  }

  // ======================================================
  // HELPERS
  // ======================================================

  function formatDate(
    value: string | null
  ) {
    if (!value) {
      return "—";
    }

    return new Date(value).toLocaleString(
      undefined,
      {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }
    );
  }

  function getStatusClass(
    status: string
  ) {
    switch (status.toLowerCase()) {
      case "open":
        return "status-open";

      case "in_progress":
      case "in progress":
        return "status-progress";

      case "resolved":
        return "status-resolved";

      case "closed":
        return "status-closed";

      default:
        return "status-default";
    }
  }

  function getSeverityClass(
    severity: string | null
  ) {
    switch (severity?.toLowerCase()) {
      case "critical":
        return "severity-critical";

      case "high":
        return "severity-high";

      case "medium":
        return "severity-medium";

      case "low":
        return "severity-low";

      default:
        return "severity-default";
    }
  }

  // ======================================================
  // PAGE CONTENT
  // ======================================================

  return (
    <AppLayout
      onLogout={handleLogout}
    >
      <main className="ticket-details-main">

        {/* ==================================================
            LOADING
        ================================================== */}

        {loading && (
          <div className="ticket-details-state">

            <div className="ticket-details-spinner" />

            <p>
              Loading ticket...
            </p>

          </div>
        )}

        {/* ==================================================
            ERROR
        ================================================== */}

        {!loading && error && (
          <div className="ticket-details-state ticket-details-error">

            <h2>
              Unable to load ticket
            </h2>

            <p>
              {error ||
                "Ticket not found."}
            </p>

            <button
              type="button"
              className="ticket-details-primary-button"
              onClick={() =>
                navigate("/tickets")
              }
            >
              View Tickets
            </button>

          </div>
        )}

        {/* ==================================================
            TICKET
        ================================================== */}

        {!loading &&
          !error &&
          ticket && (
            <>
              {/* ============================================
                  PAGE HEADER
              ============================================ */}

              <div className="ticket-details-page-header">

                <div>

                  <p className="ticket-details-breadcrumb">
                    Tickets /{" "}
                    {ticket.ticket_number}
                  </p>

                  <h1>
                    {ticket.subject}
                  </h1>

                  <p>
                    View details and support
                    information for this
                    ticket.
                  </p>

                </div>

                <button
                  type="button"
                  className="ticket-details-secondary-button"
                  onClick={() =>
                    navigate("/tickets")
                  }
                >
                  View All Tickets
                </button>

              </div>

              {/* ============================================
                  MAIN CARD
              ============================================ */}

              <div className="ticket-details-card">

                {/* ==========================================
                    TICKET HEADER
                ========================================== */}

                <div className="ticket-details-title-row">

                  <div>

                    <span className="ticket-details-number">
                      #{ticket.ticket_number}
                    </span>

                    <h2>
                      {ticket.subject}
                    </h2>

                    <p className="ticket-details-created">
                      Created{" "}
                      {formatDate(
                        ticket.created_at
                      )}
                    </p>

                  </div>

                  <div className="ticket-details-badges">

                    <span
                      className={`ticket-details-badge ${getStatusClass(
                        ticket.status
                      )}`}
                    >
                      {ticket.status.replace(
                        "_",
                        " "
                      )}
                    </span>

                    <span
                      className={`ticket-details-badge ${getSeverityClass(
                        ticket.severity
                      )}`}
                    >
                      {ticket.severity ||
                        "Unknown"}
                    </span>

                  </div>

                </div>

                {/* ==========================================
                    DESCRIPTION
                ========================================== */}

                <section className="ticket-details-section">

                  <h2>
                    Description
                  </h2>

                  <div className="ticket-details-description">
                    {ticket.description}
                  </div>

                </section>

                {/* ==========================================
                    TICKET INFORMATION
                ========================================== */}

                <section className="ticket-details-section">

                  <h2>
                    Ticket Information
                  </h2>

                  <div className="ticket-details-info-grid">

                    <div className="ticket-details-info-item">

                      <span>
                        Ticket Number
                      </span>

                      <strong>
                        #{ticket.ticket_number}
                      </strong>

                    </div>

                    <div className="ticket-details-info-item">

                      <span>
                        Status
                      </span>

                      <strong>
                        {ticket.status.replace(
                          "_",
                          " "
                        )}
                      </strong>

                    </div>

                    <div className="ticket-details-info-item">

                      <span>
                        Severity
                      </span>

                      <strong>
                        {ticket.severity ||
                          "Unknown"}
                      </strong>

                    </div>

                    <div className="ticket-details-info-item">

                      <span>
                        Created
                      </span>

                      <strong>
                        {formatDate(
                          ticket.created_at
                        )}
                      </strong>

                    </div>

                    <div className="ticket-details-info-item">

                      <span>
                        Last Updated
                      </span>

                      <strong>
                        {formatDate(
                          ticket.updated_at
                        )}
                      </strong>

                    </div>

                    <div className="ticket-details-info-item">

                      <span>
                        Resolved
                      </span>

                      <strong>
                        {formatDate(
                          ticket.resolved_at
                        )}
                      </strong>

                    </div>

                  </div>

                </section>

                {/* ==========================================
                    ESCALATION
                ========================================== */}

                {ticket.escalation_required && (
                  <section className="ticket-details-section">

                    <div className="ticket-details-section-heading">

                      <h2>
                        Escalation
                      </h2>

                      <span className="ticket-details-escalation-badge">
                        Required
                      </span>

                    </div>

                    <div className="ticket-details-escalation-box">

                      <div className="ticket-details-escalation-icon">
                        !
                      </div>

                      <div>

                        <strong>
                          Human support required
                        </strong>

                        <p>
                          This ticket has been
                          escalated for human
                          support.
                        </p>

                        {ticket.escalation_reason && (
                          <div className="ticket-details-escalation-reason">

                            <span>
                              Reason
                            </span>

                            <p>
                              {
                                ticket.escalation_reason
                              }
                            </p>

                          </div>
                        )}

                      </div>

                    </div>

                  </section>
                )}

                {/* ==========================================
                    AI INVESTIGATION
                ========================================== */}

                {ticket.ai_investigation_summary && (
                  <section className="ticket-details-section">

                    <h2>
                      AI Investigation Summary
                    </h2>

                    <div className="ticket-details-ai-summary">
                      {
                        ticket.ai_investigation_summary
                      }
                    </div>

                  </section>
                )}

                {/* ==========================================
                    AI PROCESSING
                ========================================== */}

                <section className="ticket-details-section">

                  <h2>
                    AI Processing
                  </h2>

                  <div className="ticket-details-info-grid">

                    <div className="ticket-details-info-item">

                      <span>
                        Intent
                      </span>

                      <strong>
                        {ticket.intent ||
                          "—"}
                      </strong>

                    </div>

                    <div className="ticket-details-info-item">

                      <span>
                        Route
                      </span>

                      <strong>
                        {ticket.route ||
                          "—"}
                      </strong>

                    </div>

                    <div className="ticket-details-info-item">

                      <span>
                        Confidence
                      </span>

                      <strong>
                        {ticket.confidence !==
                        null
                          ? `${Math.round(
                              ticket.confidence *
                                100
                            )}%`
                          : "—"}
                      </strong>

                    </div>

                  </div>

                </section>

              </div>
            </>
          )}

      </main>
    </AppLayout>
  );
}

export default TicketDetails;