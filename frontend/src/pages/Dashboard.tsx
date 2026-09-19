import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getTickets,
  type Ticket,
} from "../services/ticketService";
import {
  getProfile,
  type ProfileResponse,
} from "../services/customerService";
import AppLayout from "../components/layout/AppLayout";
import "./Dashboard.css";

const ACCESS_TOKEN_KEY = "eris_access_token";
const USER_EMAIL_KEY = "eris_user_email";

function Dashboard() {
  const navigate = useNavigate();

  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [profile, setProfile] =
    useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      const token =
        localStorage.getItem(ACCESS_TOKEN_KEY);

      if (!token) {
        navigate("/login");
        return;
      }

      try {
        setLoading(true);

        const [ticketData, profileData] =
          await Promise.all([
            getTickets(),
            getProfile(),
          ]);

        if (!cancelled) {
          setTickets(ticketData);
          setProfile(profileData);
        }
      } catch (error) {
        if (!cancelled) {
          console.error(
            "Failed to load dashboard:",
            error
          );

          const message =
            error instanceof Error
              ? error.message.toLowerCase()
              : "";

          if (
            message.includes("401") ||
            message.includes("unauthorized") ||
            message.includes("authentication")
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

    loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const openTickets = tickets.filter(
    (ticket) =>
      ticket.status === "open" ||
      ticket.status === "in_progress"
  ).length;

  const resolvedTickets = tickets.filter(
    (ticket) =>
      ticket.status === "resolved" ||
      ticket.status === "closed"
  ).length;

  const escalations = tickets.filter(
    (ticket) => ticket.escalation_required
  ).length;

  const recentTickets = [...tickets]
    .sort((a, b) => {
      const dateA = a.created_at
        ? new Date(a.created_at).getTime()
        : 0;

      const dateB = b.created_at
        ? new Date(b.created_at).getTime()
        : 0;

      return dateB - dateA;
    })
    .slice(0, 5);

  const customer = profile?.customer;

  function handleLogout() {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(USER_EMAIL_KEY);

    window.location.href = "/login";
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

  function getStatusClass(status: string) {
    switch (status.toLowerCase()) {
      case "open":
        return "dashboard-status-open";

      case "in_progress":
      case "in progress":
        return "dashboard-status-progress";

      case "resolved":
        return "dashboard-status-resolved";

      case "closed":
        return "dashboard-status-closed";

      default:
        return "dashboard-status-default";
    }
  }

  function getSeverityClass(
    severity: string | null
  ) {
    switch (severity?.toLowerCase()) {
      case "critical":
        return "dashboard-severity-critical";

      case "high":
        return "dashboard-severity-high";

      case "medium":
        return "dashboard-severity-medium";

      case "low":
        return "dashboard-severity-low";

      default:
        return "dashboard-severity-default";
    }
  }

  return (
    <AppLayout onLogout={handleLogout}>
      <section className="customer-content">
        <div className="customer-welcome">
          <div>
            <h3>Welcome back 👋</h3>

            <p>
              Monitor your support requests, tickets,
              SLA, and account activity from one place.
            </p>
          </div>
        </div>

        {/* Statistics */}

        <div className="customer-stats">
          <div className="customer-stat-card">
            <div className="customer-stat-icon blue">
              □
            </div>

            <div className="customer-stat-info">
              <span>Open Tickets</span>

              <strong>
                {loading ? "—" : openTickets}
              </strong>
            </div>

            <small>
              Active support requests
            </small>
          </div>

          <div className="customer-stat-card">
            <div className="customer-stat-icon green">
              ✓
            </div>

            <div className="customer-stat-info">
              <span>Resolved Tickets</span>

              <strong>
                {loading ? "—" : resolvedTickets}
              </strong>
            </div>

            <small>
              Successfully resolved
            </small>
          </div>

          <div className="customer-stat-card">
            <div className="customer-stat-icon purple">
              ◷
            </div>

            <div className="customer-stat-info">
              <span>SLA Status</span>

              <strong>
                {loading
                  ? "—"
                  : customer?.sla_level || "—"}
              </strong>
            </div>

            <small>
              Current support agreement
            </small>
          </div>

          <div className="customer-stat-card">
            <div className="customer-stat-icon orange">
              !
            </div>

            <div className="customer-stat-info">
              <span>Escalations</span>

              <strong>
                {loading ? "—" : escalations}
              </strong>
            </div>

            <small>
              Requests requiring attention
            </small>
          </div>
        </div>

        {/* Recent Tickets */}

        <section className="customer-card recent-tickets-card">
          <div className="customer-card-header">
            <div>
              <h3>Recent Tickets</h3>

              <p>
                Your latest support requests
              </p>
            </div>

            <button
              className="customer-text-button"
              type="button"
              onClick={() => navigate("/tickets")}
            >
              View all
            </button>
          </div>

          {loading && (
            <div className="customer-empty-state">
              <div className="customer-empty-icon">
                ◷
              </div>

              <strong>
                Loading recent tickets...
              </strong>

              <p>
                Fetching your latest support requests.
              </p>
            </div>
          )}

          {!loading &&
            recentTickets.length === 0 && (
              <div className="customer-empty-state">
                <div className="customer-empty-icon">
                  □
                </div>

                <strong>
                  No recent tickets
                </strong>

                <p>
                  Your support tickets will appear
                  here.
                </p>

                <button
                  className="customer-secondary-button"
                  type="button"
                  onClick={() =>
                    navigate("/tickets")
                  }
                >
                  View Tickets
                </button>
              </div>
            )}

          {!loading &&
            recentTickets.length > 0 && (
              <div className="dashboard-recent-tickets">
                {recentTickets.map((ticket) => (
                  <button
                    key={ticket.id}
                    type="button"
                    className="dashboard-ticket-row"
                    onClick={() =>
                      navigate(
                        `/tickets/${ticket.id}`
                      )
                    }
                  >
                    <div className="dashboard-ticket-main">
                      <span className="dashboard-ticket-number">
                        #{ticket.ticket_number}
                      </span>

                      <strong>
                        {ticket.subject}
                      </strong>

                      <span className="dashboard-ticket-description">
                        {ticket.description.length >
                        80
                          ? `${ticket.description.slice(
                              0,
                              80
                            )}...`
                          : ticket.description}
                      </span>
                    </div>

                    <div className="dashboard-ticket-meta">
                      <span
                        className={`dashboard-ticket-badge ${getStatusClass(
                          ticket.status
                        )}`}
                      >
                        {ticket.status.replace(
                          "_",
                          " "
                        )}
                      </span>

                      <span
                        className={`dashboard-ticket-badge ${getSeverityClass(
                          ticket.severity
                        )}`}
                      >
                        {ticket.severity || "—"}
                      </span>

                      <span className="dashboard-ticket-date">
                        {formatDate(
                          ticket.created_at
                        )}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
        </section>

        {/* Account Overview */}

        <section className="customer-card account-summary-card">
          <div className="customer-card-header">
            <div>
              <h3>Account Overview</h3>

              <p>
                Your current support account
              </p>
            </div>

            <button
              className="customer-text-button"
              type="button"
              onClick={() =>
                navigate("/account")
              }
            >
              View account
            </button>
          </div>

          <div className="account-summary-grid">
            <div>
              <span>Account</span>

              <strong>
                {loading
                  ? "—"
                  : customer?.account_status ||
                    "—"}
              </strong>
            </div>

            <div>
              <span>Subscription</span>

              <strong>
                {loading
                  ? "—"
                  : customer?.subscription_tier ||
                    "—"}
              </strong>
            </div>

            <div>
              <span>SLA</span>

              <strong>
                {loading
                  ? "—"
                  : customer?.sla_level || "—"}
              </strong>
            </div>

            <div>
              <span>Region</span>

              <strong>
                {loading
                  ? "—"
                  : customer?.region || "—"}
              </strong>
            </div>
          </div>
        </section>
      </section>
    </AppLayout>
  );
}

export default Dashboard;