import { useState } from "react";
import AppLayout from "../../components/layout/AppLayout";
import KnowledgeDocuments from "../../components/admin/KnowledgeDocuments";
import EvaluationDashboard from "../../components/admin/EvaluationDashboard";
import "./AdminDashboard.css";

type AdminSection = "knowledge" | "evaluation";

export default function AdminDashboard() {
  const [activeSection, setActiveSection] =
    useState<AdminSection>("knowledge");

  function handleLogout() {
    localStorage.removeItem("eris_access_token");
    localStorage.removeItem("eris_user_email");

    window.location.href = "/login";
  }

  return (
    <AppLayout onLogout={handleLogout}>
      <div className="admin-dashboard">
        <div className="admin-dashboard-header">
          <div>
            <h1>Admin Dashboard</h1>
            <p>
              Manage knowledge documents and evaluate ERIS
              performance.
            </p>
          </div>
        </div>

        <div className="admin-tabs">
          <button
            type="button"
            className={`admin-tab ${
              activeSection === "knowledge" ? "active" : ""
            }`}
            onClick={() => setActiveSection("knowledge")}
          >
            Knowledge Documents
          </button>

          <button
            type="button"
            className={`admin-tab ${
              activeSection === "evaluation" ? "active" : ""
            }`}
            onClick={() => setActiveSection("evaluation")}
          >
            Evaluation
          </button>
        </div>

        <div className="admin-dashboard-content">
          {activeSection === "knowledge" && (
            <KnowledgeDocuments />
          )}

          {activeSection === "evaluation" && (
            <EvaluationDashboard />
          )}
        </div>
      </div>
    </AppLayout>
  );
}