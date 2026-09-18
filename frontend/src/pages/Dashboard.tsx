import { useNavigate } from "react-router-dom";
import "./Dashboard.css";

function Dashboard() {
  const navigate = useNavigate();
  const email = localStorage.getItem("eris_user_email") || "Customer";

  function handleLogout() {
    localStorage.removeItem("eris_access_token");
    localStorage.removeItem("eris_user_email");
    window.location.href = "/login";
  }

  return (
    <div className="customer-dashboard">
      <aside className="customer-sidebar">
        <div className="customer-brand">
          <div className="customer-brand-logo">E</div>

          <div>
            <h1>ERIS</h1>
            <span>Support Intelligence</span>
          </div>
        </div>

        <nav className="customer-nav">
          <button className="customer-nav-item active">
            <span>▦</span>
            Dashboard
          </button>

          <button
            className="customer-nav-item"
            onClick={() => navigate("/chat")}
          >
            <span>✦</span>
            AI Support
          </button>

          <button
            className="customer-nav-item"
            onClick={() => navigate("/tickets")}
          >
            <span>□</span>
            Tickets
          </button>

          <button
            className="customer-nav-item"
            onClick={() => navigate("/account")}
          >
            <span>○</span>
            Account
          </button>
        </nav>

        <div className="customer-sidebar-bottom">
          <button className="customer-nav-item">
            <span>⚙</span>
            Settings
          </button>

          <button
            className="customer-nav-item"
            onClick={handleLogout}
          >
            <span>↪</span>
            Sign out
          </button>
        </div>
      </aside>

      <main className="customer-main">
        <header className="customer-topbar">
          <div>
            <h2>Dashboard</h2>
            <p>Enterprise Support Workspace</p>
          </div>

          <div className="customer-user">
            <div className="customer-avatar">
              {email.charAt(0).toUpperCase()}
            </div>

            <div className="customer-user-details">
              <strong>{email}</strong>
              <span>Customer</span>
            </div>
          </div>
        </header>

        <section className="customer-content">
          <div className="customer-welcome">
            <div>
              <h3>Welcome back 👋</h3>
              <p>
                Monitor your support requests, tickets, SLA, and account
                activity from one place.
              </p>
            </div>
          </div>

          <div className="customer-stats">
            <div className="customer-stat-card">
              <div className="customer-stat-icon blue">□</div>

              <div className="customer-stat-info">
                <span>Open Tickets</span>
                <strong>—</strong>
              </div>

              <small>Active support requests</small>
            </div>

            <div className="customer-stat-card">
              <div className="customer-stat-icon green">✓</div>

              <div className="customer-stat-info">
                <span>Resolved Tickets</span>
                <strong>—</strong>
              </div>

              <small>Successfully resolved</small>
            </div>

            <div className="customer-stat-card">
              <div className="customer-stat-icon purple">◷</div>

              <div className="customer-stat-info">
                <span>SLA Status</span>
                <strong>Active</strong>
              </div>

              <small>Current support agreement</small>
            </div>

            <div className="customer-stat-card">
              <div className="customer-stat-icon orange">!</div>

              <div className="customer-stat-info">
                <span>Escalations</span>
                <strong>—</strong>
              </div>

              <small>Requests requiring attention</small>
            </div>
          </div>

          <section className="customer-card recent-tickets-card">
            <div className="customer-card-header">
              <div>
                <h3>Recent Tickets</h3>
                <p>Your latest support requests</p>
              </div>

              <button
                className="customer-text-button"
                onClick={() => navigate("/tickets")}
              >
                View all
              </button>
            </div>

            <div className="customer-empty-state">
              <div className="customer-empty-icon">□</div>

              <strong>No recent tickets</strong>

              <p>
                Your support tickets will appear here.
              </p>

              <button
                className="customer-secondary-button"
                onClick={() => navigate("/tickets")}
              >
                View Tickets
              </button>
            </div>
          </section>

          <section className="customer-card account-summary-card">
            <div className="customer-card-header">
              <div>
                <h3>Account Overview</h3>
                <p>Your current support account</p>
              </div>

              <button
                className="customer-text-button"
                onClick={() => navigate("/account")}
              >
                View account
              </button>
            </div>

            <div className="account-summary-grid">
              <div>
                <span>Account</span>
                <strong>Active</strong>
              </div>

              <div>
                <span>Subscription</span>
                <strong>—</strong>
              </div>

              <div>
                <span>SLA</span>
                <strong>Active</strong>
              </div>

              <div>
                <span>Region</span>
                <strong>—</strong>
              </div>
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}

export default Dashboard;