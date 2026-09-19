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

export async function getKnowledgeDocuments(): Promise<
  KnowledgeDocument[]
> {
  const token = localStorage.getItem("eris_access_token");

  if (!token) {
    throw new Error("No authentication token found.");
  }

  return apiRequest<KnowledgeDocument[]>("/knowledge-base/documents", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}