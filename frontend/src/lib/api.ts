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

  patchJson: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "PATCH",
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

  /** File uploads. No Content-Type here on purpose — the browser has to
   * set it itself so the multipart boundary goes with it. */
  postMultipart: <T>(path: string, body: FormData) => request<T>(path, { method: "POST", body }),

  del: (path: string) => request<void>(path, { method: "DELETE" }),
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

export type Product = {
  id: number;
  code: string;
  name: string;
  category: string | null;
  uom: string;
  default_rate: string | null;
  notes: string | null;
  is_active: boolean;
};

export type DocStatus = "active" | "cancelled";

export type SaleLine = {
  line_no: number;
  product_id: number;
  description: string | null;
  quantity: string;
  rate: string;
  amount: string;
};

export type Sale = {
  id: number;
  invoice_no: string;
  invoice_date: string;
  party_id: number;
  gross_amount: string;
  discount: string;
  net_amount: string;
  narration: string | null;
  status: DocStatus;
  lines: SaleLine[];
};

export type PurchaseLine = {
  line_no: number;
  item_description: string;
  uom: string;
  quantity: string;
  rate: string;
  amount: string;
};

export type Purchase = {
  id: number;
  bill_no: string;
  bill_date: string;
  party_id: number;
  gross_amount: string;
  discount: string;
  net_amount: string;
  narration: string | null;
  status: DocStatus;
  lines: PurchaseLine[];
};

export type PaymentDirection = "in" | "out";

export type Payment = {
  id: number;
  voucher_no: string;
  payment_date: string;
  party_id: number;
  direction: PaymentDirection;
  amount: string;
  mode: string;
  reference_no: string | null;
  narration: string | null;
  status: DocStatus;
};

export type Attachment = {
  id: number;
  entity_type: string;
  entity_id: number;
  url: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
};

export type ActivityType = "sale" | "purchase" | "payment";

export type ActivityItem = {
  type: ActivityType;
  id: number;
  doc_no: string;
  party_id: number;
  party_name: string;
  amount: string;
  txn_date: string;
  status: DocStatus;
  created_at: string;
};

export type DashboardSummary = {
  as_on_date: string;
  receivable_total: string;
  payable_total: string;
  month_sales_total: string;
  recent_activity: ActivityItem[];
};

export const PAYMENT_MODES = ["Cash", "UPI", "Bank", "Cheque"] as const;

export const TXN_TYPE_LABELS: Record<LedgerTxnType, string> = {
  opening: "Opening balance",
  sale: "Sale",
  purchase: "Purchase",
  receipt: "Receipt",
  payment: "Payment",
};
