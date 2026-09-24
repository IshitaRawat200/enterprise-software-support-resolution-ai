import {
  useEffect,
  useRef,
  useState,
} from "react";
import {
  deleteKnowledgeDocument,
  getKnowledgeDocuments,
  uploadKnowledgeDocument,
  viewKnowledgeDocument,
  type KnowledgeDocument,
} from "../../services/adminApi";
import "./KnowledgeDocuments.css";

const SUPPORTED_EXTENSIONS = [
  ".pdf",
  ".txt",
  ".md",
  ".html",
  ".htm",
];

const SUPPORTED_ACCEPT =
  SUPPORTED_EXTENSIONS.join(",");

function isSupportedDocument(
  file: File
): boolean {
  const fileName =
    file.name.toLowerCase();

  return SUPPORTED_EXTENSIONS.some(
    (extension) =>
      fileName.endsWith(extension)
  );
}

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

export default function KnowledgeDocuments() {
  const [documents, setDocuments] =
    useState<KnowledgeDocument[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [uploading, setUploading] =
    useState(false);

  const [
    openingDocumentId,
    setOpeningDocumentId,
  ] = useState<string | null>(null);

  const [error, setError] =
    useState("");

  const [success, setSuccess] =
    useState("");

  const fileInputRef =
    useRef<HTMLInputElement | null>(
      null
    );

  async function loadDocuments() {
    try {
      setLoading(true);
      setError("");

      const data =
        await getKnowledgeDocuments();

      setDocuments(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load knowledge documents."
      );
    } finally {
      setLoading(false);
    }
  }
  
  useEffect(() => {
    void loadDocuments();
  }, []);

  async function handleUpload(
    event: React.ChangeEvent<HTMLInputElement>
  ) {
    const file =
      event.target.files?.[0];

    if (!file) {
      return;
    }

    if (!isSupportedDocument(file)) {
      setError(
        "Unsupported document type. Please upload PDF, TXT, Markdown, or HTML files."
      );

      event.target.value = "";

      return;
    }

    try {
      setUploading(true);
      setError("");
      setSuccess("");

      await uploadKnowledgeDocument(
        file
      );

      setSuccess(
        "Knowledge document uploaded and processed successfully."
      );

      await loadDocuments();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to upload knowledge document."
      );
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function handleView(
    documentId: string
  ) {
    /*
     * Open the browser tab immediately
     * so popup blockers do not prevent it.
     */
    const viewerWindow =
      window.open("", "_blank");

    if (!viewerWindow) {
      setError(
        "The document could not be opened. Please allow pop-ups for this site."
      );

      return;
    }

    setOpeningDocumentId(
      documentId
    );

    setError("");

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
      const objectUrl =
        await viewKnowledgeDocument(
          documentId
        );

      viewerWindow.location.href =
        objectUrl;

      window.setTimeout(() => {
        URL.revokeObjectURL(
          objectUrl
        );
      }, 60000);
    } catch (err) {
      viewerWindow.close();

      setError(
        err instanceof Error
          ? err.message
          : "Failed to open knowledge document."
      );
    } finally {
      setOpeningDocumentId(null);
    }
  }

  async function handleDelete(
    documentId: string
  ) {
    const document =
      documents.find(
        (item) =>
          item.id === documentId
      );

    const confirmed =
      window.confirm(
        `Delete "${
          document?.document_name ||
          "this document"
        }"?\n\nThis will also remove its RAG chunks and embeddings.`
      );

    if (!confirmed) {
      return;
    }

    try {
      setError("");
      setSuccess("");

      await deleteKnowledgeDocument(
        documentId
      );

      setSuccess(
        "Knowledge document deleted successfully."
      );

      await loadDocuments();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to delete knowledge document."
      );
    }
  }

  return (
    <section className="knowledge-documents">
      <div className="knowledge-header">
        <div className="knowledge-header-content">
          <h2>
            Knowledge Documents
          </h2>

          <p>
            Upload documents used by the
            ERIS RAG knowledge base.
          </p>

          <span className="knowledge-supported-formats">
            Supported: PDF, TXT, Markdown,
            HTML
          </span>
        </div>

        <div className="knowledge-upload-area">
          <input
            ref={fileInputRef}
            type="file"
            accept={SUPPORTED_ACCEPT}
            onChange={handleUpload}
            className="knowledge-file-input"
          />

          <button
            type="button"
            className="knowledge-upload-button"
            disabled={uploading}
            onClick={() =>
              fileInputRef.current?.click()
            }
          >
            {uploading
              ? "Uploading..."
              : "Upload Document"}
          </button>
        </div>
      </div>

      {error && (
        <div className="knowledge-message error">
          {error}
        </div>
      )}

      {success && (
        <div className="knowledge-message success">
          {success}
        </div>
      )}

      <div className="knowledge-card">
        {loading ? (
          <div className="knowledge-empty">
            Loading documents...
          </div>
        ) : documents.length === 0 ? (
          <div className="knowledge-empty">
            No knowledge documents uploaded.
          </div>
        ) : (
          <div className="knowledge-table-wrapper">
            <table className="knowledge-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Product</th>
                  <th>Version</th>
                  <th>Uploaded</th>
                  <th>Action</th>
                </tr>
              </thead>

              <tbody>
                {documents.map(
                  (document) => (
                    <tr key={document.id}>
                      <td>
                        <div className="document-name">
                          {
                            document.document_name
                          }
                        </div>
                      </td>

                      <td>
                        <span className="knowledge-type-badge">
                          {getDocumentType(
                            document
                          )}
                        </span>
                      </td>

                      <td>
                        {document.product_name ||
                          "—"}
                      </td>

                      <td>
                        {document.version ||
                          document.product_version ||
                          "—"}
                      </td>

                      <td>
                        {new Date(
                          document.created_at
                        ).toLocaleDateString()}
                      </td>

                      <td>
                        <div className="knowledge-actions">
                          <button
                            type="button"
                            className="knowledge-view-button"
                            disabled={
                              openingDocumentId ===
                              document.id
                            }
                            onClick={() =>
                              void handleView(
                                document.id
                              )
                            }
                          >
                            {openingDocumentId ===
                            document.id
                              ? "Opening..."
                              : "View"}
                          </button>

                          <button
                            type="button"
                            className="knowledge-delete-button"
                            onClick={() =>
                              void handleDelete(
                                document.id
                              )
                            }
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}