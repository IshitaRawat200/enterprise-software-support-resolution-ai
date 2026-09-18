import { apiRequest } from "./api";

export interface ConversationMessage {
  id: string;
  role: "customer" | "ai" | "support_agent" | "system";
  content: string;
  created_at?: string | null;
  ticket_id?: string | null;
}

export interface Conversation {
  conversation_id: string;
  created_at?: string | null;
  messages: ConversationMessage[];
}

export async function getConversations(): Promise<Conversation[]> {
  const token = localStorage.getItem("eris_access_token");

  if (!token) {
    throw new Error("No authentication token found.");
  }

  return apiRequest<Conversation[]>("/chat/conversations", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}