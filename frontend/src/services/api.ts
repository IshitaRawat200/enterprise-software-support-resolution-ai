const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function logoutUser() {
  localStorage.removeItem("eris_access_token");
  localStorage.removeItem("eris_user_email");

  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

function formatApiError(rawError: unknown): string {
  if (typeof rawError === "string") {
    const trimmed = rawError.trim();

    if (!trimmed) {
      return "Something went wrong. Please try again.";
    }

    try {
      const parsed = JSON.parse(trimmed) as unknown;
      return formatApiError(parsed);
    } catch {
      return trimmed;
    }
  }

  if (!rawError || typeof rawError !== "object") {
    return "Something went wrong. Please try again.";
  }

  const detail = (rawError as { detail?: unknown }).detail;
  const payload = detail && typeof detail === "object" ? detail : rawError;
  const typedPayload = payload as {
    message?: string;
    error?: string;
    reason?: string;
    guardrail?: string;
    code?: string;
    detail?: unknown;
  };

  if (
    typedPayload.guardrail === "input_guardrail" ||
    typedPayload.guardrail === "security_guardrail" ||
    typedPayload.code === "PROMPT_INJECTION"
  ) {
    return "Your request was blocked by the security guardrails. Please rephrase the question and avoid unauthorized access or restricted-data requests.";
  }

  const candidate =
    typedPayload.message ||
    typedPayload.error ||
    typedPayload.reason ||
    (typeof typedPayload.detail === "string" ? typedPayload.detail : "");

  if (candidate && typeof candidate === "string" && candidate.trim()) {
    return candidate.trim();
  }

  return "Something went wrong. Please try again.";
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem("eris_access_token");

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token
        ? {
            Authorization: `Bearer ${token}`,
          }
        : {}),
      ...(options.headers || {}),
    },
  });

  if (response.status === 401) {
    logoutUser();
    throw new Error("Your session has expired. Please sign in again.");
  }

  if (!response.ok) {
    const errorText = await response.text();

    try {
      const parsed = JSON.parse(errorText) as unknown;
      throw new Error(formatApiError(parsed));
    } catch {
      throw new Error(formatApiError(errorText));
    }
  }

  return response.json();
}