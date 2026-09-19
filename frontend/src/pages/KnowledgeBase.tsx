import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getKnowledgeDocuments,
  type KnowledgeDocument,
} from "../services/knowledgeService";
import AppLayout from "../components/layout/AppLayout";
import "./KnowledgeBase.css";

function KnowledgeBase() {
  const navigate = useNavigate();

  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadDocuments() {
      const token = localStorage.getItem("eris_access_token");

      if (!token) {
        navigate("/login");
        return;
      }

      try {
        setLoading(true);
        setError("");

        const data = await getKnowledgeDocuments();

        if (!cancelled) {
          setDocuments(data);
        }
      } catch (err) {
        if (!cancelled) {
          console.error(
            "Failed to load knowledge documents:",
            err
          );

          const message =
            err instanceof Error
              ? err.message
              : "Failed to load knowledge base.";

          setError(message);

          if (
            message.includes("401") ||
            message.toLowerCase().includes("unauthorized") ||
            message.toLowerCase().includes("authentication")
          ) {
            localStorage.removeItem("eris_access_token");
            localStorage.removeItem("eris_user_email");

            navigate("/login");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadDocuments();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  function handleLogout() {
    localStorage.removeItem("eris_access_token");
    localStorage.removeItem("eris_user_email");

    window.location.href = "/login";
  }

  function handleViewDocument(document: KnowledgeDocument) {
    if (!document.source_url) {
      return;
    }

    window.open(
      document.source_url,
      "_blank",
      "noopener,noreferrer"
    );
  }

  return (
    <AppLayout onLogout={handleLogout}>
      <section className="knowledge-content">
        <div className="knowledge-intro">
          <h3>Documentation</h3>

          <p>
            Access the product documentation used by ERIS
            to provide support and troubleshooting guidance.
          </p>
        </div>

        {loading && (
          <div className="knowledge-state">
            <strong>Loading knowledge base...</strong>

            <p>
              Fetching available documentation.
            </p>
          </div>
        )}

        {!loading && error && (
          <div className="knowledge-state knowledge-error">
            <strong>
              Unable to load knowledge base
            </strong>

            <p>{error}</p>
          </div>
        )}

        {!loading &&
          !error &&
          documents.length === 0 && (
            <div className="knowledge-state">
              <div className="knowledge-empty-icon">
                ▤
              </div>

              <strong>
                No documents available
              </strong>

              <p>
                Customer documentation has not been
                published yet.
              </p>
            </div>
          )}

        {!loading &&
          !error &&
          documents.length > 0 && (
            <div className="knowledge-grid">
              {documents.map((document) => (
                <article
                  className="knowledge-card"
                  key={document.id}
                >
                  <div className="knowledge-card-icon">
                    PDF
                  </div>

                  <div className="knowledge-card-content">
                    <h3>
                      {document.document_name}
                    </h3>

                    <p>
                      {document.product_name ||
                        "ERIS Documentation"}

                      {document.product_version
                        ? ` • ${document.product_version}`
                        : ""}
                    </p>

                    {document.version && (
                      <span className="knowledge-version">
                        Version {document.version}
                      </span>
                    )}
                  </div>

                  <button
                    className="knowledge-view-button"
                    type="button"
                    disabled={!document.source_url}
                    onClick={() =>
                      handleViewDocument(document)
                    }
                  >
                    View PDF
                  </button>
                </article>
              ))}
            </div>
          )}
      </section>
    </AppLayout>
  );
}

export default KnowledgeBase;