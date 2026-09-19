const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function logoutUser() {
  localStorage.removeItem("eris_access_token");
  localStorage.removeItem("eris_user_email");

  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
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

    throw new Error(
      errorText || `API request failed with status ${response.status}`
    );
  }

  return response.json();
}