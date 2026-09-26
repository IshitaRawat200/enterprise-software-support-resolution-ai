import { apiRequest } from "./api";

interface ConversationMessage {
  id: string;
  role: "customer" | "ai" | "support_agent" | "system";
  content: string;
  created_at?: string;
  metadata?: Record<string, unknown> | null;
}

export interface Conversation {
  conversation_id: string;
  created_at?: string;
  updated_at?: string;
  messages: ConversationMessage[];
}

let conversationsCache: Conversation[] | null = null;

let conversationsRequest: Promise<Conversation[]> | null = null;

/**
 * Load conversation history.
 *
 * Normal calls:
 *   - use the in-memory cache when available
 *
 * Forced refresh:
 *   - always performs a fresh HTTP request
 *   - adds a cache-busting query parameter
 *
 * This is important for asynchronous RAGAS evaluation because
 * the backend updates the AI message metadata after /chat returns.
 */
export async function getConversations(
  forceRefresh = false,
): Promise<Conversation[]> {
  const token = localStorage.getItem(
    "eris_access_token",
  );

  if (!token) {
    throw new Error(
      "No authentication token found.",
    );
  }

  // ------------------------------------------------------------
  // NORMAL REQUEST
  // ------------------------------------------------------------

  if (
    !forceRefresh &&
    conversationsCache !== null
  ) {
    return conversationsCache;
  }

  // ------------------------------------------------------------
  // REQUEST DEDUPLICATION
  // ------------------------------------------------------------

  /*
   * If another request is already running, reuse it.
   *
   * This protects against React Strict Mode and multiple
   * simultaneous refresh calls.
   */
  if (conversationsRequest !== null) {
    return conversationsRequest;
  }

  // ------------------------------------------------------------
  // CACHE-BUSTING URL
  // ------------------------------------------------------------

  const endpoint = forceRefresh
    ? `/chat/conversations?refresh=${Date.now()}`
    : "/chat/conversations";

  conversationsRequest =
    apiRequest<Conversation[]>(
      endpoint,
      {
        method: "GET",

        headers: {
          Authorization: `Bearer ${token}`,
          "Cache-Control": "no-cache",
          Pragma: "no-cache",
        },
      },
    );

  try {
    const conversations =
      await conversationsRequest;

    conversationsCache = conversations;

    return conversations;
  } finally {
    conversationsRequest = null;
  }
}

/**
 * Clear the local conversation cache.
 *
 * Call this after creating/updating conversation data
 * when a subsequent normal getConversations() should
 * perform a fresh request.
 */
export function clearConversationCache(): void {
  conversationsCache = null;
  conversationsRequest = null;
}

/**
 * Explicitly replace the local conversation cache.
 */
export function setConversationCache(
  conversations: Conversation[],
): void {
  conversationsCache = conversations;
}