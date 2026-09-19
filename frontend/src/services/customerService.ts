import { apiRequest } from "./api";

export interface UserProfile {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerAccount {
  id: string;
  customer_code: string;
  user_id: string;
  contact_name: string | null;
  company_name: string | null;
  region: string | null;
  industry: string | null;
  account_status: string | null;
  subscription_tier: string | null;
  sla_level: string | null;
  renewal_date: string | null;
}

export interface ProfileResponse {
  user: UserProfile;
  customer: CustomerAccount | null;
}

// Keep the profile in memory for the current frontend session.
let cachedProfile: ProfileResponse | null = null;
let cachedToken: string | null = null;

// Reuse an already-running request.
// This prevents duplicate requests caused by React StrictMode
// or multiple components requesting the profile at the same time.
let profileRequest: Promise<ProfileResponse> | null = null;

export async function getProfile(): Promise<ProfileResponse> {
  const token = localStorage.getItem("eris_access_token");

  if (!token) {
    throw new Error("No authentication token found.");
  }

  // Return cached profile when the same authenticated session is used.
  if (cachedProfile && cachedToken === token) {
    return cachedProfile;
  }

  // If another component is already requesting the same profile,
  // reuse that exact request instead of creating another HTTP request.
  if (profileRequest && cachedToken === token) {
    return profileRequest;
  }

  cachedToken = token;

  profileRequest = apiRequest<ProfileResponse>("/auth/profile", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
    .then((profile) => {
      cachedProfile = profile;
      return profile;
    })
    .finally(() => {
      profileRequest = null;
    });

  return profileRequest;
}

// Call this after logout or whenever the authenticated user changes.
export function clearProfileCache(): void {
  cachedProfile = null;
  cachedToken = null;
  profileRequest = null;
}