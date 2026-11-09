import type {
  ApiErrorPayload,
  BusinessSettings,
  Customer,
  CustomerCreateInput,
  CustomerUpdateInput,
  Expense,
  OutstandingReport,
  Product,
  ProductCategory,
  ProductCreateInput,
  ProductUpdateInput,
  Purchase,
  ReportSummary,
  Sale,
  StockMovement,
  StockMovementInput,
  Supplier,
  SupplierCreateInput,
  SupplierUpdateInput,
  UnitConversion,
  UnitOfMeasure,
  TransactionPayment,
  User,
} from "../types";

const API_ROOT = "/api/v1";

export class ApiError extends Error {
  readonly status: number;

  constructor(
    message: string,
    status: number,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function readCsrfToken(cookieString: string): string | null {
  const csrfCookie = cookieString
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith("mjd_csrf="));

  if (!csrfCookie) return null;
  return decodeURIComponent(csrfCookie.slice("mjd_csrf=".length));
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  const csrfExemptPaths = ["/auth/login", "/auth/forgot-password", "/auth/reset-password"];
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && !csrfExemptPaths.includes(path)) {
    const csrfToken = readCsrfToken(document.cookie);
    if (!csrfToken) throw new ApiError("Your session expired. Please sign in again.", 403);
    headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(`${API_ROOT}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    const body = await response.text();
    let payload: ApiErrorPayload = {};
    try {
      payload = JSON.parse(body) as ApiErrorPayload;
    } catch {
      // Reverse proxies can return plain-text errors when the API is unavailable.
    }
    const message = payload.detail
      ?? (response.status >= 500
        ? `The API server returned HTTP ${response.status}. Check that the backend and database are running.`
        : "Something went wrong. Please try again.");
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  async currentUser(): Promise<User | null> {
    try {
      return await request<User>("/auth/me");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return null;
      throw error;
    }
  },

  login(email: string, password: string): Promise<User> {
    return request<User>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  requestPasswordReset(email: string): Promise<{ message: string }> {
    return request<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  resetPassword(token: string, new_password: string): Promise<{ message: string }> {
    return request<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
    });
  },

  logout(): Promise<void> {
    return request<void>("/auth/logout", { method: "POST" });
  },

  changePassword(current_password: string, new_password: string): Promise<void> {
    return request<void>("/auth/password", {
      method: "PUT",
      body: JSON.stringify({ current_password, new_password }),
    });
  },

  getSettings(): Promise<BusinessSettings> {
    return request<BusinessSettings>("/settings");
  },

  updateSettings(settings: BusinessSettings): Promise<BusinessSettings> {
    return request<BusinessSettings>("/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    });
  },

  customers(): Promise<Customer[]> {
    return request<Customer[]>("/customers");
  },

  createCustomer(customer: CustomerCreateInput): Promise<Customer> {
    return request<Customer>("/customers", {
      method: "POST",
      body: JSON.stringify(customer),
    });
  },

  updateCustomer(id: string, changes: CustomerUpdateInput): Promise<Customer> {
    return request<Customer>(`/customers/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    });
  },

  suppliers(): Promise<Supplier[]> {
    return request<Supplier[]>("/suppliers");
  },

  createSupplier(supplier: SupplierCreateInput): Promise<Supplier> {
    return request<Supplier>("/suppliers", {
      method: "POST",
      body: JSON.stringify(supplier),
    });
  },

  updateSupplier(id: string, changes: SupplierUpdateInput): Promise<Supplier> {
    return request<Supplier>(`/suppliers/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    });
  },

  products(): Promise<Product[]> {
    return request<Product[]>("/products");
  },

  createProduct(product: ProductCreateInput): Promise<Product> {
    return request<Product>("/products", {
      method: "POST",
      body: JSON.stringify(product),
    });
  },

  updateProduct(id: string, changes: ProductUpdateInput): Promise<Product> {
    return request<Product>(`/products/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    });
  },

  productCategories(): Promise<ProductCategory[]> {
    return request<ProductCategory[]>("/product-categories");
  },

  createProductCategory(payload: { name: string; description: string }): Promise<ProductCategory> {
    return request<ProductCategory>("/product-categories", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  units(): Promise<UnitOfMeasure[]> {
    return request<UnitOfMeasure[]>("/units");
  },

  createUnit(unit: UnitOfMeasure): Promise<UnitOfMeasure> {
    return request<UnitOfMeasure>("/units", {
      method: "POST",
      body: JSON.stringify(unit),
    });
  },

  unitConversions(): Promise<UnitConversion[]> {
    return request<UnitConversion[]>("/unit-conversions");
  },

  createUnitConversion(conversion: Omit<UnitConversion, "id">): Promise<UnitConversion> {
    return request<UnitConversion>("/unit-conversions", {
      method: "POST",
      body: JSON.stringify(conversion),
    });
  },

  createStockMovement(productId: string, movement: StockMovementInput): Promise<StockMovement> {
    return request<StockMovement>(
      `/products/${encodeURIComponent(productId)}/stock-movements`,
      { method: "POST", body: JSON.stringify(movement) },
    );
  },

  stockMovements(productId: string): Promise<StockMovement[]> {
    return request<StockMovement[]>(
      `/products/${encodeURIComponent(productId)}/stock-movements`,
    );
  },

  sales(): Promise<Sale[]> {
    return request<Sale[]>("/sales");
  },

  createSale(sale: {
    customer_id: string | null;
    sale_type: "retail" | "wholesale";
    sale_date: string;
    lines: { product_id: string; quantity: string }[];
    payment_amount: string;
    payment_method: string | null;
    payment_reference: string | null;
    notes: string;
  }): Promise<Sale> {
    return request<Sale>("/sales", { method: "POST", body: JSON.stringify(sale) });
  },

  recordSalePayment(saleId: string, payment: {
    amount: string;
    method: string;
    reference: string | null;
    notes: string;
  }): Promise<void> {
    return request<void>(`/sales/${encodeURIComponent(saleId)}/payments`, {
      method: "POST",
      body: JSON.stringify(payment),
    });
  },

  purchases(): Promise<Purchase[]> {
    return request<Purchase[]>("/purchases");
  },

  createPurchase(purchase: {
    supplier_id: string | null;
    supplier_reference: string | null;
    purchase_date: string;
    lines: { product_id: string; quantity: string; unit_cost: string }[];
    payment_amount: string;
    payment_method: string | null;
    payment_reference: string | null;
    notes: string;
  }): Promise<Purchase> {
    return request<Purchase>("/purchases", { method: "POST", body: JSON.stringify(purchase) });
  },

  recordPurchasePayment(purchaseId: string, payment: {
    amount: string;
    method: string;
    reference: string | null;
    notes: string;
  }): Promise<void> {
    return request<void>(`/purchases/${encodeURIComponent(purchaseId)}/payments`, {
      method: "POST",
      body: JSON.stringify(payment),
    });
  },

  recordCustomerAccountPayment(customerId: string, payment: {
    amount: string;
    method: string;
    reference: string | null;
    notes: string;
  }): Promise<TransactionPayment> {
    return request<TransactionPayment>(`/customers/${encodeURIComponent(customerId)}/payments`, {
      method: "POST",
      body: JSON.stringify(payment),
    });
  },

  recordSupplierAccountPayment(supplierId: string, payment: {
    amount: string;
    method: string;
    reference: string | null;
    notes: string;
  }): Promise<TransactionPayment> {
    return request<TransactionPayment>(`/suppliers/${encodeURIComponent(supplierId)}/payments`, {
      method: "POST",
      body: JSON.stringify(payment),
    });
  },

  expenses(): Promise<Expense[]> {
    return request<Expense[]>("/expenses");
  },

  createExpense(expense: {
    category: string;
    description: string;
    amount: string;
    expense_date: string;
    method: string;
    reference: string | null;
    notes: string;
  }): Promise<Expense> {
    return request<Expense>("/expenses", { method: "POST", body: JSON.stringify(expense) });
  },

  reportSummary(from: string, to: string): Promise<ReportSummary> {
    return request<ReportSummary>(
      `/reports/summary?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    );
  },

  outstandingBalances(): Promise<OutstandingReport> {
    return request<OutstandingReport>("/reports/outstanding");
  },
};
