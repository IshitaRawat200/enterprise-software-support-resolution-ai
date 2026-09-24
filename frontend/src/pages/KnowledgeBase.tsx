import {
  useEffect,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  getKnowledgeDocuments,
  viewKnowledgeDocument,
  type KnowledgeDocument,
} from "../services/adminApi";
import AppLayout from "../components/layout/AppLayout";
import "./KnowledgeBase.css";

function getDocumentType(
  document: KnowledgeDocument
): string {
  if (document.document_type) {
    return document.document_type
      .toUpperCase()
      .replace(".", "");
  }

  const extension =
    document.document_name
      .split(".")
      .pop()
      ?.toUpperCase();

  return extension || "DOCUMENT";
}

function KnowledgeBase() {
  const navigate = useNavigate();

  const [documents, setDocuments] =
    useState<KnowledgeDocument[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadDocuments() {
      const token =
        localStorage.getItem(
          "eris_access_token"
        );

      if (!token) {
        navigate("/login");
        return;
      }

      try {
        setLoading(true);
        setError("");

        /*
         * Use the same API function as Admin.
         */
        const data =
          await getKnowledgeDocuments();

        if (cancelled) {
          return;
        }

        setDocuments(data);
      } catch (err) {
        if (cancelled) {
          return;
        }

        console.error(
          "Failed to load knowledge documents:",
          err
        );

        const message =
          err instanceof Error
            ? err.message
            : "Failed to load knowledge base.";

        setError(message);

        /*
         * If authentication has expired,
         * send the user back to login.
         */
        if (
          message.includes("401") ||
          message
            .toLowerCase()
            .includes("unauthorized") ||
          message
            .toLowerCase()
            .includes("authentication")
        ) {
          localStorage.removeItem(
            "eris_access_token"
          );

          localStorage.removeItem(
            "eris_user_email"
          );

          navigate("/login");
        }
      } finally {
        /*
         * IMPORTANT:
         *
         * Do not leave loading=true when the
         * request has completed.
         */
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadDocuments();

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  async function handleViewDocument(
    document: KnowledgeDocument
  ) {
    const token =
      localStorage.getItem(
        "eris_access_token"
      );

    if (!token) {
      navigate("/login");
      return;
    }

    /*
     * Open a blank tab immediately.
     * This prevents popup blockers from
     * blocking the document.
     */
    const viewerWindow =
      window.open("", "_blank");

    if (!viewerWindow) {
      setError(
        "The document could not be opened. Please allow pop-ups for this site."
      );

      return;
    }

    viewerWindow.document.title =
      "Opening document...";

    viewerWindow.document.body.innerHTML = `
      <div style="
        font-family: Arial, sans-serif;
        padding: 40px;
        text-align: center;
        color: #475569;
      ">
        Opening document...
      </div>
    `;

    try {
      setError("");

      /*
       * Use the same document-view API as Admin.
       */
      const objectUrl =
        await viewKnowledgeDocument(
          document.id
        );

      viewerWindow.location.href =
        objectUrl;

      /*
       * Release the Blob URL later.
       */
      window.setTimeout(() => {
        URL.revokeObjectURL(
          objectUrl
        );
      }, 60000);
    } catch (err) {
      viewerWindow.close();

      console.error(
        "Failed to open knowledge document:",
        err
      );

      setError(
        err instanceof Error
          ? err.message
          : "Failed to open document."
      );
    }
  }

  function handleLogout() {
    localStorage.removeItem(
      "eris_access_token"
    );

    localStorage.removeItem(
      "eris_user_email"
    );

    window.location.href =
      "/login";
  }

  return (
    <AppLayout onLogout={handleLogout}>
      <section className="knowledge-content">
        <div className="knowledge-intro">
          <h3>Documentation</h3>

          <p>
            Access the product documentation
            used by ERIS to provide support
            and troubleshooting guidance.
          </p>
        </div>

        {loading && (
          <div className="knowledge-state">
            <strong>
              Loading knowledge base...
            </strong>

            <p>
              Fetching available
              documentation.
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
                Customer documentation has
                not been published yet.
              </p>
            </div>
          )}

        {!loading &&
          !error &&
          documents.length > 0 && (
            <div className="knowledge-grid">
              {documents.map(
                (document) => {
                  const type =
                    getDocumentType(
                      document
                    );

                  return (
                    <article
                      className="knowledge-card"
                      key={document.id}
                    >
                      <div className="knowledge-card-icon">
                        {type}
                      </div>

                      <div className="knowledge-card-content">
                        <h3>
                          {
                            document.document_name
                          }
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
                            Version{" "}
                            {
                              document.version
                            }
                          </span>
                        )}
                      </div>

                      <button
                        className="knowledge-view-button"
                        type="button"
                        onClick={() =>
                          void handleViewDocument(
                            document
                          )
                        }
                      >
                        View {type}
                      </button>
                    </article>
                  );
                }
              )}
            </div>
          )}
      </section>
    </AppLayout>
  );
}

export default KnowledgeBase;