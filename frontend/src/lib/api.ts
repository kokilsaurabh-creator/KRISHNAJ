const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "kj_token";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token === null) localStorage.removeItem(TOKEN_KEY);
    else localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* private browsing — the session just won't survive a reload */
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(`${BASE_URL}${path}`, { ...init, headers });

  if (resp.status === 401) {
    setToken(null);
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }

  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body; keep the generic message */
    }
    throw new ApiError(resp.status, detail);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),

  postJson: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  /** /auth/login takes OAuth2 form encoding, not JSON. */
  postForm: <T>(path: string, fields: Record<string, string>) =>
    request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(fields).toString(),
    }),
};

// ---- response types, mirroring the backend schemas ----

export type Role = "admin" | "owner" | "staff";

export type User = {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
};

export type Party = {
  id: number;
  party_type: "customer" | "supplier" | "both";
  name: string;
  phone: string | null;
  email: string | null;
  address_line: string | null;
  city: string | null;
  state: string | null;
  pincode: string | null;
  notes: string | null;
  is_active: boolean;
};

export type LedgerTxnType = "opening" | "sale" | "purchase" | "receipt" | "payment";

export type LedgerRow = {
  date: string;
  type: LedgerTxnType;
  doc_no: string | null;
  narration: string | null;
  /** Decimal strings — display only, never used for arithmetic here. */
  debit: string;
  credit: string;
  balance: string;
};

export type Ledger = {
  party: {
    id: number;
    name: string;
    phone: string | null;
    address_line: string | null;
    city: string | null;
    state: string | null;
    pincode: string | null;
  };
  from_date: string;
  to_date: string;
  opening: string;
  rows: LedgerRow[];
  total_debit: string;
  total_credit: string;
  closing: string;
};

export const TXN_TYPE_LABELS: Record<LedgerTxnType, string> = {
  opening: "Opening balance",
  sale: "Sale",
  purchase: "Purchase",
  receipt: "Receipt",
  payment: "Payment",
};
