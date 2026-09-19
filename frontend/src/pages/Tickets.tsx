import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getTickets,
  type Ticket,
} from "../services/ticketService";
import AppLayout from "../components/layout/AppLayout";
import "./Tickets.css";

const ACCESS_TOKEN_KEY = "eris_access_token";
const USER_EMAIL_KEY = "eris_user_email";

function Tickets() {
  const navigate = useNavigate();

  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadTickets() {
      const token = localStorage.getItem(
        ACCESS_TOKEN_KEY
      );

      if (!token) {
        navigate("/login");
        return;
      }

      try {
        setLoading(true);
        setError("");

        const data = await getTickets();

        if (!cancelled) {
          setTickets(data);
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof Error
              ? err.message
              : "Unable to load tickets.";

          setError(message);

          if (
            message.includes("401") ||
            message.toLowerCase().includes("unauthorized") ||
            message.toLowerCase().includes("authentication")
          ) {
            localStorage.removeItem(
              ACCESS_TOKEN_KEY
            );
            localStorage.removeItem(
              USER_EMAIL_KEY
            );

            navigate("/login");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadTickets();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  function handleLogout() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(USER_EMAIL_KEY);

    window.location.href = "/login";
  }

  function getStatusClass(status: string) {
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

  function formatDate(date: string | null) {
    if (!date) {
      return "—";
    }

    return new Date(date).toLocaleDateString(
      undefined,
      {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }
    );
  }

  return (
    <AppLayout onLogout={handleLogout}>
      <main className="tickets-main">
        <div className="tickets-header">
          <div>
            <h1>Tickets</h1>

            <p>
              View and manage your support requests.
            </p>
          </div>
        </div>

        <div className="tickets-card">
          {loading && (
            <div className="tickets-state">
              <div className="tickets-spinner" />

              <p>
                Loading your tickets...
              </p>
            </div>
          )}

          {!loading && error && (
            <div className="tickets-state tickets-error">
              <h3>
                Unable to load tickets
              </h3>

              <p>{error}</p>

              <button
                type="button"
                onClick={() =>
                  window.location.reload()
                }
              >
                Try again
              </button>
            </div>
          )}

          {!loading &&
            !error &&
            tickets.length === 0 && (
              <div className="tickets-state">
                <div className="empty-ticket-icon">
                  □
                </div>

                <h3>No tickets yet</h3>

                <p>
                  Your support requests will appear
                  here.
                </p>

                <button
                  type="button"
                  onClick={() =>
                    navigate("/chat")
                  }
                >
                  Contact AI Support
                </button>
              </div>
            )}

          {!loading &&
            !error &&
            tickets.length > 0 && (
              <div className="tickets-table-wrapper">
                <table className="tickets-table">
                  <thead>
                    <tr>
                      <th>Ticket</th>
                      <th>Subject</th>
                      <th>Status</th>
                      <th>Severity</th>
                      <th>Created</th>
                      <th>Escalation</th>
                    </tr>
                  </thead>

                  <tbody>
                    {tickets.map((ticket) => (
                      <tr
                        key={ticket.id}
                        className="ticket-row"
                        onClick={() =>
                          navigate(
                            `/tickets/${ticket.id}`
                          )
                        }
                      >
                        <td>
                          <span className="ticket-number">
                            #{ticket.ticket_number}
                          </span>
                        </td>

                        <td>
                          <div className="ticket-subject">
                            {ticket.subject}
                          </div>

                          {ticket.description && (
                            <div className="ticket-description">
                              {ticket.description.length >
                              80
                                ? `${ticket.description.slice(
                                    0,
                                    80
                                  )}...`
                                : ticket.description}
                            </div>
                          )}
                        </td>

                        <td>
                          <span
                            className={`ticket-badge ${getStatusClass(
                              ticket.status
                            )}`}
                          >
                            {ticket.status.replace(
                              "_",
                              " "
                            )}
                          </span>
                        </td>

                        <td>
                          <span
                            className={`ticket-badge ${getSeverityClass(
                              ticket.severity
                            )}`}
                          >
                            {ticket.severity || "—"}
                          </span>
                        </td>

                        <td>
                          {formatDate(
                            ticket.created_at
                          )}
                        </td>

                        <td>
                          {ticket.escalation_required ? (
                            <span className="escalation-badge">
                              Required
                            </span>
                          ) : (
                            <span className="no-escalation">
                              —
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </div>
      </main>
    </AppLayout>
  );
}

export default Tickets;