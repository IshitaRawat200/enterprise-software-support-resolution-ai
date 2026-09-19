import { apiRequest } from "./api";
export interface Ticket {
  id: string;
  ticket_number: string;
  customer_id: string;

  subject: string;
  description: string;

  status: string;
  intent: string | null;
  route: string | null;
  severity: string | null;
  confidence: number | null;

  escalation_required: boolean;
  escalation_reason: string | null;
  ai_investigation_summary: string | null;

  created_at: string | null;
  updated_at: string | null;
  resolved_at: string | null;
}

export interface TicketMessage {
  id: string;
  ticket_id: string;
  sender_type: string;
  sender_user_id: string | null;
  message: string;
  created_at: string | null;
}

export interface CreateTicketRequest {
  subject: string;
  description: string;
  severity?: string;
}

export interface AddTicketMessageRequest {
  message: string;
}

/* ---------------------------------------------------------
   Ticket list cache
--------------------------------------------------------- */

let ticketsCache: Ticket[] | null = null;

let ticketsRequest: Promise<Ticket[]> | null = null;

/* ---------------------------------------------------------
   Get all tickets
--------------------------------------------------------- */

export async function getTickets(
  forceRefresh = false
): Promise<Ticket[]> {
  const token = localStorage.getItem("eris_access_token");

  if (!token) {
    throw new Error("No authentication token found.");
  }

  // Return cached tickets immediately.
  if (!forceRefresh && ticketsCache !== null) {
    return ticketsCache;
  }

  // Prevent duplicate requests.
  if (!forceRefresh && ticketsRequest !== null) {
    return ticketsRequest;
  }

  ticketsRequest = apiRequest<Ticket[]>("/tickets", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  try {
    const tickets = await ticketsRequest;

    ticketsCache = tickets;

    return tickets;
  } finally {
    ticketsRequest = null;
  }
}

/* ---------------------------------------------------------
   Get single ticket
--------------------------------------------------------- */

export async function getTicket(
  ticketId: string
): Promise<Ticket> {
  const token = localStorage.getItem("eris_access_token");

  if (!token) {
    throw new Error("No authentication token found.");
  }

  return apiRequest<Ticket>(`/tickets/${ticketId}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

/* ---------------------------------------------------------
   Create ticket
--------------------------------------------------------- */

export async function createTicket(
  data: CreateTicketRequest
): Promise<Ticket> {
  const token = localStorage.getItem("eris_access_token");

  if (!token) {
    throw new Error("No authentication token found.");
  }

  const ticket = await apiRequest<Ticket>("/tickets", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  // Keep list cache consistent.
  if (ticketsCache !== null) {
    ticketsCache = [ticket, ...ticketsCache];
  }

  return ticket;
}

/* ---------------------------------------------------------
   Add message to ticket
--------------------------------------------------------- */

export async function addTicketMessage(
  ticketId: string,
  data: AddTicketMessageRequest
): Promise<TicketMessage> {
  const token = localStorage.getItem("eris_access_token");

  if (!token) {
    throw new Error("No authentication token found.");
  }

  return apiRequest<TicketMessage>(
    `/tickets/${ticketId}/messages`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    }
  );
}

/* ---------------------------------------------------------
   Cache controls
--------------------------------------------------------- */

export function clearTicketCache(): void {
  ticketsCache = null;
  ticketsRequest = null;
}

export function setTicketCache(
  tickets: Ticket[]
): void {
  ticketsCache = tickets;
}