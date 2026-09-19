import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import "./AppLayout.css";

interface AppLayoutProps {
  children: ReactNode;
  onLogout: () => void;
}

function AppLayout({
  children,
  onLogout,
}: AppLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const userEmail =
    localStorage.getItem("eris_user_email") || "Customer";

  function isActive(path: string): boolean {
    return (
      location.pathname === path ||
      location.pathname.startsWith(`${path}/`)
    );
  }

  function getPageTitle(): string {
    if (isActive("/dashboard")) {
      return "Dashboard";
    }

    if (isActive("/chat")) {
      return "AI Support";
    }

    if (isActive("/tickets")) {
      return "Tickets";
    }

    if (isActive("/knowledge-base")) {
      return "Knowledge Base";
    }

    if (isActive("/account")) {
      return "Account";
    }

    return "ERIS";
  }

  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        {/* ERIS Branding */}
        <div className="app-brand">
          <div className="app-brand-logo" aria-label="ERIS">
            <span className="eris-logo-e">E</span>
            <span className="eris-logo-sparkle">✦</span>
            <span className="eris-logo-orbit" />
          </div>

          <div className="app-brand-text">
            <h1>ERIS</h1>

            <p>
              Enterprise Software Support
              <br />
              &amp; Resolution Intelligence System
            </p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="app-nav">
          <button
            type="button"
            className={`app-nav-item ${
              isActive("/dashboard") ? "active" : ""
            }`}
            onClick={() => navigate("/dashboard")}
          >
            <span className="app-nav-icon">▦</span>
            <span className="app-nav-label">
              Dashboard
            </span>
          </button>

          <button
            type="button"
            className={`app-nav-item ${
              isActive("/chat") ? "active" : ""
            }`}
            onClick={() => navigate("/chat")}
          >
            <span className="app-nav-icon">✦</span>
            <span className="app-nav-label">
              AI Support
            </span>
          </button>

          <button
            type="button"
            className={`app-nav-item ${
              isActive("/tickets") ? "active" : ""
            }`}
            onClick={() => navigate("/tickets")}
          >
            <span className="app-nav-icon">□</span>
            <span className="app-nav-label">
              Tickets
            </span>
          </button>

          <button
            type="button"
            className={`app-nav-item ${
              isActive("/knowledge-base") ? "active" : ""
            }`}
            onClick={() => navigate("/knowledge-base")}
          >
            <span className="app-nav-icon">▤</span>
            <span className="app-nav-label">
              Knowledge Base
            </span>
          </button>

          <button
            type="button"
            className={`app-nav-item ${
              isActive("/account") ? "active" : ""
            }`}
            onClick={() => navigate("/account")}
          >
            <span className="app-nav-icon">○</span>
            <span className="app-nav-label">
              Account
            </span>
          </button>
        </nav>

        {/* Sign Out */}
        <div className="app-sidebar-bottom">
          <button
            type="button"
            className="app-nav-item"
            onClick={onLogout}
          >
            <span className="app-nav-icon">↪</span>
            <span className="app-nav-label">
              Sign out
            </span>
          </button>
        </div>
      </aside>

      {/* Main Application */}
      <div className="app-main">
        <header className="app-topbar">
          <div className="app-topbar-left">
            <h2>{getPageTitle()}</h2>
          </div>

          <div className="app-topbar-right">
            <div className="app-user">
              <div className="app-user-avatar">
                {userEmail.charAt(0).toUpperCase()}
              </div>

              <div className="app-user-info">
                <strong>{userEmail}</strong>
                <span>Customer</span>
              </div>
            </div>
          </div>
        </header>

        <main className="app-content">
          {children}
        </main>
      </div>
    </div>
  );
}

export default AppLayout;