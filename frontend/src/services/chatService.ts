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

let conversationsCache: Conversation[] | null = null;

let conversationsRequest: Promise<Conversation[]> | null = null;

export async function getConversations(
  forceRefresh = false
): Promise<Conversation[]> {
  const token = localStorage.getItem("eris_access_token");

  if (!token) {
    throw new Error("No authentication token found.");
  }

  // Return cached conversations when available.
  if (!forceRefresh && conversationsCache !== null) {
    return conversationsCache;
  }

  // Prevent duplicate requests when React Strict Mode
  // mounts the component more than once.
  if (!forceRefresh && conversationsRequest !== null) {
    return conversationsRequest;
  }

  conversationsRequest = apiRequest<Conversation[]>(
    "/chat/conversations",
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  try {
    const conversations = await conversationsRequest;

    conversationsCache = conversations;

    return conversations;
  } finally {
    conversationsRequest = null;
  }
}

export function clearConversationCache(): void {
  conversationsCache = null;
  conversationsRequest = null;
}

export function setConversationCache(
  conversations: Conversation[]
): void {
  conversationsCache = conversations;
}