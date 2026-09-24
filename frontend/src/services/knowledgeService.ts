import { apiRequest } from "./api";

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

let cachedDocuments: KnowledgeDocument[] | null = null;

let documentsRequest: Promise<KnowledgeDocument[]> | null = null;

export async function getKnowledgeDocuments(
  forceRefresh = false
): Promise<KnowledgeDocument[]> {
  if (!forceRefresh && cachedDocuments !== null) {
    return cachedDocuments;
  }

  if (!forceRefresh && documentsRequest !== null) {
    return documentsRequest;
  }

  documentsRequest = apiRequest<KnowledgeDocument[]>(
    "/knowledge-base/documents"
  )
    .then((documents) => {
      cachedDocuments = documents;
      return documents;
    })
    .finally(() => {
      documentsRequest = null;
    });

  return documentsRequest;
}

export function clearKnowledgeDocumentsCache(): void {
  cachedDocuments = null;
}

export function setKnowledgeDocumentsCache(
  documents: KnowledgeDocument[]
): void {
  cachedDocuments = documents;
}

export async function refreshKnowledgeDocuments(): Promise<
  KnowledgeDocument[]
> {
  clearKnowledgeDocumentsCache();

  return getKnowledgeDocuments(true);
}