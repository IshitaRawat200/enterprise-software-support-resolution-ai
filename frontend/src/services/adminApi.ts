export interface KnowledgeDocument {
  id: string;
  document_name: string;
  document_type: string | null;
  product_name: string | null;
  product_version: string | null;
  version: string | null;
  source_url: string | null;
  created_at: string;
}

export interface SLOMetric {
  name: string;
  value: number;
  target: number;
  unit: string;
  passed: boolean;
}

export interface EvaluationSLOMetric {
  name: string;
  value: number;
  target: number;
  unit: string;
  passed: boolean;
}

export interface EvaluationCase {
  case_id?: string;
  test_id?: string;
  id?: string;
  query?: string;
  question?: string;
  expected_route?: string;
  actual_route?: string;
  passed?: boolean;
  success?: boolean;
  evaluation_passed?: boolean;
  [key: string]: unknown;
}

export interface EvaluationReport {
  run_id: string;
  created_at: string;
  status: string;
  total_cases: number;
  overall_passed?: boolean;
  overall_slo_passed?: boolean;
  slo_metrics?: EvaluationSLOMetric[];
  cases?: EvaluationCase[];
  report?: Record<string, unknown>;
}
let knowledgeDocumentsCache:
  | KnowledgeDocument[]
  | null = null;

let knowledgeDocumentsRequest:
  | Promise<KnowledgeDocument[]>
  | null = null;

/* ============================================================
   API CONFIGURATION
   ============================================================ */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL;

/* ============================================================
   CLEAR KNOWLEDGE DOCUMENT CACHE
   ============================================================ */

export function clearKnowledgeDocumentsCache(): void {
  knowledgeDocumentsCache = null;
  knowledgeDocumentsRequest = null;
}
/* ============================================================
   GET KNOWLEDGE DOCUMENTS
   ============================================================ */
export async function getKnowledgeDocuments(
  forceRefresh = false
): Promise<KnowledgeDocument[]> {
  /*
   * If we already have documents cached and
   * the caller does not explicitly request
   * a refresh, return them immediately.
   */
  if (
    !forceRefresh &&
    knowledgeDocumentsCache !== null
  ) {
    return knowledgeDocumentsCache;
  }

  /*
   * If another request is already running,
   * reuse that exact request.
   *
   * This is important for React StrictMode,
   * which can execute effects twice in development.
   */
  if (
    !forceRefresh &&
    knowledgeDocumentsRequest !== null
  ) {
    return knowledgeDocumentsRequest;
  }

  const token =
    localStorage.getItem(
      "eris_access_token"
    );

  if (!token) {
    throw new Error(
      "No authentication token found."
    );
  }

  const request = fetch(
    `${import.meta.env.VITE_API_BASE_URL}/knowledge-base/documents`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    }
  )
    .then(async (response) => {
      if (!response.ok) {
        const errorText =
          await response.text();

        throw new Error(
          errorText ||
            `Failed to load knowledge documents (${response.status})`
        );
      }

      const data =
        (await response.json()) as KnowledgeDocument[];

      if (!Array.isArray(data)) {
        throw new Error(
          "Invalid response received from knowledge-base API."
        );
      }

      /*
       * Store the successful response.
       */
      knowledgeDocumentsCache = data;

      return data;
    })
    .finally(() => {
      /*
       * The request is no longer in-flight.
       *
       * The actual data remains in
       * knowledgeDocumentsCache.
       */
      knowledgeDocumentsRequest = null;
    });

  /*
   * Store the in-flight request immediately.
   * A second component/effect can reuse it.
   */
  if (!forceRefresh) {
    knowledgeDocumentsRequest = request;
  }

  return request;
}
/* ============================================================
   UPLOAD KNOWLEDGE DOCUMENT
   ============================================================ */

export async function uploadKnowledgeDocument(
  file: File
): Promise<KnowledgeDocument> {
  const token = localStorage.getItem(
    "eris_access_token"
  );

  if (!token) {
    throw new Error(
      "No authentication token found."
    );
  }

  const formData = new FormData();

  formData.append("file", file);

  const response = await fetch(
    `${API_BASE_URL}/knowledge-base/documents`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    }
  );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      errorText ||
        `Upload failed with status ${response.status}`
    );
  }

  const payload = await response.json();

  /*
   * Backend response:
   *
   * {
   *   message: "...",
   *   document: {...},
   *   duplicate: false
   * }
   *
   * Support both wrapped and direct responses.
   */
  const document =
    payload.document ?? payload;

  if (!document?.id) {
    throw new Error(
      "Upload succeeded, but the server returned an invalid document response."
    );
  }

  clearKnowledgeDocumentsCache();

  return document as KnowledgeDocument;
}

/* ============================================================
   DELETE KNOWLEDGE DOCUMENT
   ============================================================ */

export async function deleteKnowledgeDocument(
  documentId: string
): Promise<{
  message: string;
  document_id: string;
}> {
  const token = localStorage.getItem(
    "eris_access_token"
  );

  if (!token) {
    throw new Error(
      "No authentication token found."
    );
  }

  const response = await fetch(
    `${API_BASE_URL}/knowledge-base/documents/${documentId}`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      errorText ||
        `Delete failed with status ${response.status}`
    );
  }

  const result =
    (await response.json()) as {
      message: string;
      document_id: string;
    };

  clearKnowledgeDocumentsCache();

  return result;
}

/* ============================================================
   VIEW ORIGINAL KNOWLEDGE DOCUMENT
   ============================================================ */

export async function viewKnowledgeDocument(
  documentId: string
): Promise<string> {
  const token = localStorage.getItem(
    "eris_access_token"
  );

  if (!token) {
    throw new Error(
      "No authentication token found."
    );
  }

  const response = await fetch(
    `${API_BASE_URL}/knowledge-base/documents/${documentId}/file`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      errorText ||
        `Failed to open document. Status: ${response.status}`
    );
  }

  const blob = await response.blob();

  return URL.createObjectURL(blob);
}

/* ============================================================
   GET EVALUATION REPORT
   ============================================================ */

export async function getEvaluationReport(): Promise<EvaluationReport> {
  const token = localStorage.getItem(
    "eris_access_token"
  );

  if (!token) {
    throw new Error(
      "No authentication token found."
    );
  }

  const response = await fetch(
    `${API_BASE_URL}/admin/evaluation/report`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    }
  );

  if (!response.ok) {
    const errorText =
      await response.text();

    throw new Error(
      errorText ||
        `Failed to load evaluation report (${response.status})`
    );
  }

  return (await response.json()) as EvaluationReport;
}