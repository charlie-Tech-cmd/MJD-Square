export interface Permission {
  id: string;
  description: string;
}

export interface Role {
  id: string;
  name: string;
  permissions: Permission[];
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
}

export interface BusinessSettings {
  business_name: string;
  currency: string;
  timezone: string;
  payment_methods: string[];
}

export interface RolePermissionOption {
  id: string;
  description: string;
  granted: boolean;
}

export interface RolePermissions {
  role_id: string;
  role_name: string;
  permissions: RolePermissionOption[];
}

export interface OpeningBalance {
  amount: string;
  effective_date: string;
  source_notes: string;
}

export interface Customer {
  id: string;
  name: string;
  phone: string | null;
  whatsapp: string | null;
  whatsapp_receipt_opted_in: boolean;
  whatsapp_receipt_consent_at: string | null;
  email: string | null;
  address: string | null;
  customer_type: "retail" | "wholesale" | "both";
  notes: string;
  is_active: boolean;
  opening_balances: OpeningBalance[];
  opening_balance_total: string;
  created_at: string;
}

export interface CustomerCreateInput {
  name: string;
  phone: string | null;
  whatsapp: string | null;
  whatsapp_receipt_opted_in: boolean;
  email: string | null;
  address: string | null;
  customer_type: Customer["customer_type"];
  notes: string;
  opening_balance: string;
  opening_balance_date: string | null;
  opening_balance_notes: string | null;
}

export type CustomerUpdateInput = Partial<
  Pick<
    CustomerCreateInput,
    "name" | "phone" | "whatsapp" | "whatsapp_receipt_opted_in" | "email" | "address" | "customer_type" | "notes"
  >
> & { is_active?: boolean };

export interface Supplier {
  id: string;
  name: string;
  contact_person: string | null;
  phone: string | null;
  whatsapp: string | null;
  whatsapp_receipt_opted_in: boolean;
  whatsapp_receipt_consent_at: string | null;
  email: string | null;
  address: string | null;
  payment_terms_days: number | null;
  notes: string;
  is_active: boolean;
  opening_balances: OpeningBalance[];
  opening_balance_total: string;
  created_at: string;
}

export interface SupplierCreateInput {
  name: string;
  phone: string | null;
  whatsapp: string | null;
  whatsapp_receipt_opted_in: boolean;
  email: string | null;
  address: string | null;
  payment_terms_days: number | null;
  notes: string;
  opening_balance: string;
  opening_balance_date: string | null;
  opening_balance_notes: string | null;
}

export type SupplierUpdateInput = Partial<
  Pick<
    SupplierCreateInput,
    "name" | "phone" | "whatsapp" | "whatsapp_receipt_opted_in" | "email" | "address" | "payment_terms_days" | "notes"
  >
> & { is_active?: boolean };

export interface UnitOfMeasure {
  id: string;
  name: string;
  abbreviation: string;
  decimal_places: number;
}

export interface UnitConversion {
  id: string;
  from_unit_id: string;
  to_unit_id: string;
  factor: string;
}

export interface ProductCategory {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
}

export interface ProductPriceTier {
  price_type: "retail" | "wholesale";
  minimum_quantity: string;
  unit_price: string;
}

export interface Product {
  id: string;
  name: string;
  sku: string;
  barcode: string | null;
  category_id: string | null;
  category_name: string | null;
  description: string;
  unit_id: string;
  unit_name: string;
  unit_abbreviation: string;
  unit_decimal_places: number;
  supplier_id: string | null;
  supplier_name: string | null;
  purchase_cost: string;
  retail_price: string;
  wholesale_price: string;
  minimum_stock: string;
  stock_quantity: string;
  is_low_stock: boolean;
  is_active: boolean;
  price_tiers: ProductPriceTier[];
  created_at: string;
}

export interface ProductCreateInput {
  name: string;
  sku: string;
  barcode: string | null;
  category_id: string | null;
  description: string;
  unit_id: string;
  supplier_id: string | null;
  purchase_cost: string;
  retail_price: string;
  wholesale_price: string;
  minimum_stock: string;
  price_tiers: ProductPriceTier[];
  opening_stock: string;
  opening_stock_reason: string | null;
}

export type ProductUpdateInput = Partial<Omit<ProductCreateInput, "opening_stock" | "opening_stock_reason">> & {
  is_active?: boolean;
};

export interface StockMovementInput {
  movement_type: "adjustment" | "damage";
  quantity_delta: string;
  reason: string;
}

export interface StockMovement {
  id: string;
  product_id: string;
  movement_type: "opening" | "adjustment" | "damage" | "purchase" | "sale" | "customer_return" | "supplier_return";
  quantity_delta: string;
  reason: string;
  created_by: string | null;
  created_at: string;
}

export interface TransactionPayment {
  id: string;
  amount: string;
  method: string;
  reference: string | null;
  notes: string;
  received_at: string;
  receipts: PaymentEvidence[];
  whatsapp_receipt_status: string | null;
}

export interface ManualPaymentReceipt {
  id: string;
  receipt_number: string;
  business_name: string;
  currency: string;
  payer_name: string;
  payer_phone: string | null;
  purpose: string;
  amount: string;
  payment_method: string;
  paid_on: string;
  created_at: string;
}

export interface ManualPaymentReceiptList {
  receipts: ManualPaymentReceipt[];
  business_name: string;
  currency: string;
  payment_methods: string[];
}

export interface PaymentEvidence {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  uploaded_at: string;
}

export interface AccountPaymentHistory extends TransactionPayment {
  account_type: "customer" | "supplier";
  account_name: string;
}

export type ReminderStatus =
  | "prepared"
  | "sent_manually"
  | "follow_up_required"
  | "promised_payment"
  | "disputed"
  | "resolved";

export interface ReminderActivity {
  id: string;
  status: ReminderStatus;
  channel: "whatsapp" | "phone" | "in_person" | "other" | null;
  notes: string;
  actor_name: string | null;
  created_at: string;
}

export interface PaymentReminder {
  sale_id: string;
  invoice_number: string;
  customer_id: string;
  customer_name: string;
  customer_phone: string | null;
  customer_whatsapp: string | null;
  sale_date: string;
  due_date: string;
  total_amount: string;
  amount_paid: string;
  balance_due: string;
  days_overdue: number;
  latest_status: ReminderStatus | null;
  last_contacted_at: string | null;
  activities: ReminderActivity[];
}

export interface TransactionHistoryEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown>;
  actor_name: string | null;
  created_at: string;
}

export interface SaleLine {
  product_id: string;
  product_name: string;
  sku: string;
  unit_name: string;
  quantity: string;
  unit_price: string;
  line_total: string;
}

export interface Sale {
  id: string;
  invoice_number: string;
  customer_id: string | null;
  customer_name: string | null;
  sale_type: "retail" | "wholesale";
  sale_date: string;
  due_date: string;
  lines: SaleLine[];
  total_amount: string;
  amount_paid: string;
  balance_due: string;
  payments: TransactionPayment[];
  notes: string;
  created_at: string;
}

export interface PurchaseLine {
  product_id: string;
  product_name: string;
  sku: string;
  unit_name: string;
  quantity: string;
  unit_cost: string;
  line_total: string;
}

export interface Purchase {
  id: string;
  purchase_number: string;
  supplier_id: string | null;
  supplier_name: string | null;
  supplier_reference: string | null;
  purchase_date: string;
  lines: PurchaseLine[];
  total_amount: string;
  amount_paid: string;
  balance_due: string;
  payments: TransactionPayment[];
  notes: string;
  created_at: string;
}

export interface Expense {
  id: string;
  category: string;
  description: string;
  amount: string;
  expense_date: string;
  method: string;
  reference: string | null;
  notes: string;
  created_at: string;
}

export interface ReportSummary {
  from_date: string;
  to_date: string;
  sales_total: string;
  payments_received: string;
  purchases_total: string;
  payments_made: string;
  expenses_total: string;
  low_stock_count: number;
}

export interface DashboardSummary {
  from_date: string;
  to_date: string;
  sales_total: string;
  payments_received: string;
  purchases_total: string;
  payments_made: string;
  expenses_total: string;
  customer_receivables: string;
  supplier_payables: string;
  overdue_invoice_buckets: {
    "1_30_days": string;
    "31_60_days": string;
    "61_90_days": string;
    over_90_days: string;
  };
  inventory_value_at_recorded_cost: string;
  low_stock_count: number;
  sales_trend: { date: string; sales_total: string }[];
  top_products: {
    product_id: string;
    product_name: string;
    quantity_sold: string;
    sales_total: string;
  }[];
  recent_activity: {
    id: number;
    action: string;
    entity_type: string;
    entity_id: string | null;
    details: Record<string, unknown>;
    actor_name: string | null;
    created_at: string;
  }[];
  aging_note: string;
  inventory_value_note: string;
}

export interface OutstandingBalance {
  id: string;
  name: string;
  balance_due: string;
}

export interface OutstandingReport {
  customer_balances: OutstandingBalance[];
  supplier_balances: OutstandingBalance[];
}

export interface ApiErrorPayload {
  detail?: string;
}
