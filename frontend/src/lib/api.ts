import type {
  Approval,
  AuditLog,
  Customer,
  CustomerDetail,
  DailySummary,
  OverdueQueueItem,
  OverviewResponse,
  PaymentLink,
  Product,
  ReportsResponse,
  ShopSettings,
  Supplier,
  SupplierBill,
  SupplierOrder,
  VoiceCommandResult,
  WhatsAppOrder,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  isOffline: boolean;

  constructor(message: string, status = 0, isOffline = false) {
    super(message);
    this.status = status;
    this.isOffline = isOffline;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    throw new ApiError("You appear to be offline. Reconnect to sync shop ledger.", 0, true);
  }
  const isFormData = init?.body instanceof FormData;
  const headers: Record<string, string> = isFormData
    ? {}
    : { "Content-Type": "application/json" };

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { ...headers, ...(init?.headers as Record<string, string>) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Cannot reach Kirana Khata backend (http://localhost:8000). Check that FastAPI is running.",
      0,
      true
    );
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const errBody = await res.json();
      if (errBody?.detail) detail = String(errBody.detail);
    } catch {
      // ignore json parse failure
    }
    throw new ApiError(detail, res.status, false);
  }
  return (await res.json()) as T;
}

export const api = {
  getOverview: () => request<OverviewResponse>("/api/dashboard/overview"),
  getReports: () => request<ReportsResponse>("/api/dashboard/reports"),
  generateDailySummary: () =>
    request<DailySummary>("/api/dashboard/daily-summary/generate", { method: "POST" }),
  getNotifications: () =>
    request<{
      total_count: number;
      pending_approvals: number;
      low_stock_alerts: number;
      overdue_customers: number;
      items: { id: number; code: string; title: string; risk_level: string; action_type: string }[];
    }>("/api/notifications"),
  search: (q: string) =>
    request<{
      customers: { id: number; name: string; name_kn: string; balance: number }[];
      products: { id: number; name: string; name_kn: string; stock_qty: number; unit: string }[];
      orders: { id: number; order_code: string; customer_name: string; raw_message: string }[];
    }>(`/api/search?q=${encodeURIComponent(q)}`),
  getAdaptersHealth: () =>
    request<{
      app_mode: string;
      database_backend: string;
      adapters: { adapter: string; mode: string; configured: boolean; note: string }[];
    }>("/api/adapters/health"),
  getMcpTools: () =>
    request<{
      server_name: string;
      tools: { name: string; access: string; description: string }[];
    }>("/api/mcp/tools"),

  // Orders
  listOrders: (status = "all") =>
    request<WhatsAppOrder[]>(`/api/orders?status=${encodeURIComponent(status)}`),
  simulateIncomingOrder: (payload: {
    customer_id: number;
    channel: "whatsapp_text" | "whatsapp_voice";
    raw_message: string;
    payment_intent?: "credit" | "cash" | "upi";
  }) =>
    request<WhatsAppOrder>("/api/orders/simulate-incoming", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  selectSubstitute: (
    orderId: number,
    payload: { original_product_id: number; substitute_product_id: number; draft_reply_kn?: string }
  ) =>
    request<{ order: WhatsAppOrder; approval: Approval }>(
      `/api/orders/${orderId}/select-substitute`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  decideOrder: (
    orderId: number,
    payload: {
      decision: "approve" | "ask_payment" | "cancel";
      edited_items?: Record<string, unknown>[];
      draft_reply_kn?: string;
      draft_reply_en?: string;
      note?: string;
      auto_send_reply?: boolean;
    }
  ) =>
    request<{ order: WhatsAppOrder; result: string; follow_up_approval: Approval | null }>(
      `/api/orders/${orderId}/decision`,
      { method: "POST", body: JSON.stringify(payload) }
    ),

  // Khata & Payments
  listCustomers: () => request<Customer[]>("/api/khata/customers"),
  getCustomerDetail: (customerId: number) =>
    request<CustomerDetail>(`/api/khata/customers/${customerId}`),
  getOverdueQueue: () => request<OverdueQueueItem[]>("/api/khata/overdue"),
  listPaymentLinks: () => request<PaymentLink[]>("/api/khata/payment-links"),
  draftReminder: (payload: {
    customer_id: number;
    custom_message_kn?: string;
    custom_message_en?: string;
  }) =>
    request<Approval>("/api/khata/reminders/draft", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  simulatePayment: (payload: {
    payment_link_id?: number;
    customer_id?: number;
    amount_paid: number;
  }) =>
    request<{
      payment_link: PaymentLink;
      customer: Customer;
      old_balance: number;
      new_balance: number;
      amount_paid: number;
      is_partial: boolean;
      thank_you_approval: Approval;
    }>("/api/khata/payments/simulate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Inventory & Bill OCR
  listInventory: (status = "all") =>
    request<Product[]>(`/api/inventory?status=${encodeURIComponent(status)}`),
  addInventoryStock: (payload: {
    product_id: number;
    quantity_added: number;
    note?: string;
    new_price?: number;
  }) =>
    request<Product>("/api/inventory/add-stock", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createInventoryProduct: (payload: {
    name: string;
    name_kn?: string;
    category: string;
    unit: string;
    price: number;
    stock_qty: number;
    reorder_level: number;
    supplier_id: number;
  }) =>
    request<Product>("/api/inventory/products", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listBills: () => request<SupplierBill[]>("/api/inventory/bills"),
  uploadBill: (formData: FormData) =>
    request<{ bill: SupplierBill; approval: Approval }>("/api/inventory/bills/upload", {
      method: "POST",
      body: formData,
    }),

  // Suppliers
  listSuppliers: () =>
    request<{ suppliers: Supplier[]; low_stock_products: Product[] }>("/api/suppliers"),
  listSupplierOrders: () => request<SupplierOrder[]>("/api/suppliers/orders"),
  createSupplierOrderDraft: (payload: {
    supplier_id?: number;
    product_ids?: number[];
    items?: { product_id: number; ordered_qty: number }[];
    whatsapp_draft_kn?: string;
  }) =>
    request<{ supplier_order: SupplierOrder; approval: Approval }>(
      "/api/suppliers/orders/draft",
      { method: "POST", body: JSON.stringify(payload) }
    ),

  // Approvals & Audit
  listApprovals: (status = "all") =>
    request<Approval[]>(`/api/approvals?status=${encodeURIComponent(status)}`),
  decideApproval: (
    approvalId: number,
    payload: {
      decision: "approve" | "reject";
      edited_payload?: Record<string, unknown>;
      decision_note?: string;
    }
  ) =>
    request<{ approval: Approval; follow_up_approval: Approval | null }>(
      `/api/approvals/${approvalId}/decision`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  listAuditLogs: (limit = 100) => request<AuditLog[]>(`/api/audit-logs?limit=${limit}`),

  // Owner Voice Commands
  runVoiceCommand: (command_text: string) =>
    request<VoiceCommandResult>("/api/voice/command", {
      method: "POST",
      body: JSON.stringify({ command_text, is_simulated_voice: true }),
    }),

  // Store Settings & Auth
  getSettings: () => request<ShopSettings>("/api/settings"),
  updateSettings: (payload: {
    shop_name: string;
    shop_name_kn?: string;
    owner_name: string;
    owner_phone?: string;
    upi_id?: string;
    default_credit_limit?: number;
    owner_pin?: string;
  }) =>
    request<ShopSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  login: (payload: { pin: string; owner_name?: string }) =>
    request<{ authenticated: boolean; owner_name: string; shop_name: string; settings: ShopSettings }>(
      "/api/auth/login",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  logout: () => request<{ authenticated: boolean }>("/api/auth/logout", { method: "POST" }),
};
