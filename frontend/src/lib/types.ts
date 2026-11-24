/** Typed API contracts matching FastAPI Pydantic schemas */

export type Language = "en" | "kn";

export interface Supplier {
  id: number;
  code: string;
  name: string;
  name_kn: string;
  contact_person: string;
  phone: string;
  whatsapp_number: string;
  category_focus: string;
  low_stock_product_count: number;
  pending_po_count: number;
}

export interface Product {
  id: number;
  sku: string;
  name: string;
  name_kn: string;
  category: string;
  unit: string;
  price: number;
  cost_price: number;
  stock_qty: number;
  reorder_level: number;
  default_reorder_qty: number;
  supplier_id: number;
  supplier_name: string;
  last_restocked_at: string;
  substitute_group: string | null;
  stock_status: "in_stock" | "low_stock" | "out_of_stock";
}

export interface Customer {
  id: number;
  code: string;
  name: string;
  name_kn: string;
  phone: string;
  whatsapp_number: string;
  address: string;
  credit_limit: number;
  current_balance: number;
  days_overdue: number;
  last_payment_date: string | null;
  reminder_stage: number;
  reminder_stage_label: string;
  preferred_language: string;
  over_limit: boolean;
  utilization_pct: number;
}

export interface KhataEntry {
  id: number;
  customer_id: number;
  entry_type: "credit_sale" | "payment_upi" | "payment_cash" | "adjustment";
  amount: number;
  balance_after: number;
  order_id: number | null;
  payment_link_id: number | null;
  description: string;
  description_kn: string;
  approved_by_id: number | null;
  created_at: string;
}

export interface PaymentLink {
  id: number;
  link_code: string;
  customer_id: number;
  customer_name: string;
  short_url: string;
  upi_intent_uri: string;
  amount_requested: number;
  amount_paid: number;
  remaining_amount: number;
  status: string;
  reminder_stage: number;
  created_at: string;
  paid_at: string | null;
}

export interface CustomerDetail {
  customer: Customer;
  entries: KhataEntry[];
  payment_links: PaymentLink[];
  recent_orders: {
    id: number;
    order_code: string;
    total_amount: number;
    status: string;
    payment_intent: string;
    created_at: string;
  }[];
}

export interface SubstituteOption {
  product_id: number;
  sku: string;
  name: string;
  name_kn: string;
  price: number;
  stock_qty: number;
  price_diff: number;
  comparison_label: string;
}

export interface ParsedOrderItem {
  product_id: number | null;
  requested_name: string;
  matched_product_name: string | null;
  matched_product_name_kn: string | null;
  qty: number;
  unit: string;
  unit_price: number;
  line_total: number;
  stock_qty: number;
  available: boolean;
  substitute_options: SubstituteOption[];
  selected_substitute_id: number | null;
}

export interface Approval {
  id: number;
  approval_code: string;
  action_type:
    | "order_fulfill"
    | "credit_override"
    | "send_whatsapp"
    | "payment_reminder"
    | "payment_thank_you"
    | "supplier_reorder"
    | "bill_stock_intake"
    | "voice_khata_entry";
  title: string;
  title_kn: string;
  entity_type: string;
  entity_id: number;
  customer_id: number | null;
  customer_name: string | null;
  supplier_id: number | null;
  supplier_name: string | null;
  mcp_tool_name: string;
  payload: Record<string, unknown>;
  reason: string;
  source_data: Record<string, unknown>;
  amount_impact: number | null;
  risk_level: "normal" | "attention" | "high";
  status: "pending" | "approved" | "rejected";
  decision_note: string | null;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface WhatsAppOrder {
  id: number;
  order_code: string;
  customer_id: number;
  customer_name: string;
  customer_name_kn: string;
  customer_phone: string;
  customer_balance: number;
  customer_credit_limit: number;
  projected_balance: number;
  credit_exceeded: boolean;
  exceeds_by: number;
  channel: "whatsapp_text" | "whatsapp_voice" | "telegram_text" | "telegram_voice";
  raw_message: string;
  english_translation: string;
  audio_duration_sec: number | null;
  audio_transcript_kn: string | null;
  transcript_confidence: number | null;
  intent: string;
  payment_intent: "credit" | "cash" | "upi";
  status: string;
  workflow_stage: string;
  parsed_items: ParsedOrderItem[];
  total_amount: number;
  credit_check_status: string;
  suggested_action: string;
  reason_text: string;
  source_data: Record<string, unknown>;
  draft_reply_kn: string;
  draft_reply_en: string;
  is_repeat_order: boolean;
  reference_order_id: number | null;
  related_approvals: {
    id: number;
    approval_code: string;
    action_type: string;
    title: string;
    status: string;
    payload: Record<string, unknown>;
  }[];
  created_at: string;
}

export interface OverdueQueueItem {
  customer: Customer;
  recommended_stage: number;
  recommended_stage_label: string;
  payment_link: PaymentLink | null;
  preview_kn: string;
  preview_en: string;
  risk_level: string;
}

export interface SupplierOrder {
  id: number;
  po_code: string;
  supplier_id: number;
  supplier_name: string;
  supplier_name_kn: string;
  supplier_phone: string;
  items: {
    product_id: number;
    sku: string;
    product_name: string;
    product_name_kn: string;
    current_stock: number;
    reorder_level: number;
    suggested_qty: number;
    ordered_qty: number;
    unit: string;
    unit_cost: number;
    line_cost: number;
  }[];
  total_estimated_cost: number;
  whatsapp_draft_kn: string;
  whatsapp_draft_en: string;
  status: string;
  created_at: string;
  sent_at: string | null;
}

export interface SupplierBill {
  id: number;
  bill_code: string;
  supplier_id: number | null;
  supplier_name_extracted: string;
  invoice_number: string;
  bill_date: string;
  image_filename: string;
  extracted_items: {
    item_name: string;
    matched_product_id: number | null;
    matched_product_name: string;
    quantity: number;
    unit: string;
    unit_price: number;
    line_total: number;
  }[];
  total_amount: number;
  ocr_confidence: number;
  status: string;
  approval_id: number | null;
  created_at: string;
}

export interface AuditLog {
  id: number;
  event_type: string;
  actor: string;
  mcp_tool: string | null;
  approval_id: number | null;
  entity_type: string;
  entity_id: number | null;
  summary: string;
  summary_kn: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  created_at: string;
}

export interface DailySummary {
  id: number;
  summary_date: string;
  total_sales: number;
  credit_sales: number;
  cash_upi_sales: number;
  payments_collected: number;
  low_stock_count: number;
  pending_approvals_count: number;
  top_overdue: {
    id: number;
    name: string;
    name_kn: string;
    balance: number;
    days_overdue: number;
    reminder_stage: number;
  }[];
  low_stock_items: {
    id: number;
    name: string;
    name_kn: string;
    stock_qty: number;
    reorder_level: number;
    unit: string;
  }[];
  text_en: string;
  text_kn: string;
  voice_script_kn: string;
  created_at: string;
}

export interface OverviewResponse {
  shop_name: string;
  shop_name_kn: string;
  owner_name: string;
  kpis: {
    today_sales: number;
    credit_given_today: number;
    payments_collected_today: number;
    low_stock_alerts: number;
    overdue_customers: number;
    pending_approvals: number;
  };
  needs_approval: Approval[];
  today_timeline: WhatsAppOrder[];
  daily_summary: {
    summary_date: string;
    text_en: string;
    text_kn: string;
    top_overdue: DailySummary["top_overdue"];
    low_stock_items: DailySummary["low_stock_items"];
  };
}

export interface ReportsResponse {
  daily_summary: DailySummary;
  seven_day_series: {
    day: string;
    total_sales: number;
    credit_sales: number;
    payments_collected: number;
  }[];
  khata_aging: {
    bucket: string;
    amount: number;
    customers: number;
  }[];
}

export interface VoiceCommandResult {
  transcript: string;
  english_meaning: string;
  intent: string;
  summary_en: string;
  summary_kn: string;
  result_data: Record<string, unknown>;
  created_approval: Approval | null;
  mcp_tool_used: string;
  source_data: Record<string, unknown>;
}

export interface ShopSettings {
  shop_name: string;
  shop_name_kn: string;
  owner_name: string;
  owner_phone: string;
  upi_id: string;
  default_credit_limit: number;
  telegram_connected: boolean;
}
