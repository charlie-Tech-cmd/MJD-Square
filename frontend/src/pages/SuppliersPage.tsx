import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, Filter, LoaderCircle, Plus, RotateCcw, Truck } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { formatNaira, formatQuantity } from "../lib/format";
import {
  calculatePurchaseLineTotal,
  filterPurchaseHistory,
  getPurchaseFilterError,
  hasPurchaseHistoryFilters,
  sumMoney,
  type PurchaseHistoryFilters,
} from "../lib/purchase";
import { hasPermission } from "../lib/permissions";
import type { Product, Supplier, User } from "../types";

const supplierSchema = z.object({
  name: z.string().trim().min(1, "Enter the supplier's name.").max(160),
  phone: z.string().max(40),
  whatsapp: z.string().max(40),
  whatsapp_receipt_opted_in: z.boolean(),
  email: z.union([z.email("Enter a valid email address."), z.literal("")]),
  address: z.string().max(500),
  payment_terms_days: z.union([z.literal(""), z.string().regex(/^\d{1,4}$/, "Enter days as a whole number.")]),
  notes: z.string().max(5000),
  opening_balance: z.string().regex(/^\d{1,12}(?:\.\d{1,2})?$/, "Enter an amount with up to 2 decimal places."),
  opening_balance_date: z.string(),
  opening_balance_notes: z.string().max(500),
}).superRefine((values, context) => {
  const hasOpeningBalance = /[1-9]/.test(values.opening_balance);
  if (hasOpeningBalance && !values.opening_balance_date) {
    context.addIssue({ code: "custom", path: ["opening_balance_date"], message: "Choose the date for this opening balance." });
  }
  if (hasOpeningBalance && !values.opening_balance_notes.trim()) {
    context.addIssue({ code: "custom", path: ["opening_balance_notes"], message: "Add the source of this opening balance." });
  }
  if (values.whatsapp_receipt_opted_in && !values.whatsapp.trim()) {
    context.addIssue({ code: "custom", path: ["whatsapp"], message: "Enter the supplier's WhatsApp number." });
  }
});

type SupplierValues = z.infer<typeof supplierSchema>;

const supplierGoodsSchema = z.object({
  product_id: z.string().min(1, "Choose a product."),
  quantity: z.string().regex(/^\d{1,11}(?:\.\d{1,3})?$/, "Enter a quantity with up to 3 decimal places."),
  unit_cost: z.string().regex(/^\d{1,12}(?:\.\d{1,2})?$/, "Enter a unit cost with up to 2 decimal places."),
}).superRefine((values, context) => {
  if (!/[1-9]/.test(values.quantity)) {
    context.addIssue({ code: "custom", path: ["quantity"], message: "Enter an amount supplied greater than zero." });
  }
});

type SupplierGoodsValues = z.infer<typeof supplierGoodsSchema>;

const todayInBusinessTimezone = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Lagos" }).format(new Date());

const EMPTY_PURCHASE_FILTERS: PurchaseHistoryFilters = {
  fromDate: "",
  toDate: "",
  product: "",
  minAmount: "",
  maxAmount: "",
  order: "",
  paymentStatus: "all",
};

interface SuppliersPageProps {
  user: User;
}

interface SupplierGoodsEntryProps {
  products: Product[];
  isSaving: boolean;
  onSave: (values: SupplierGoodsValues) => Promise<void>;
}

function SupplierGoodsEntry({ products, isSaving, onSave }: SupplierGoodsEntryProps) {
  const form = useForm<SupplierGoodsValues>({
    resolver: zodResolver(supplierGoodsSchema),
    defaultValues: { product_id: "", quantity: "1", unit_cost: "0.00" },
  });
  const watchedValues = form.watch();
  const selectedProduct = products.find((product) => product.id === watchedValues.product_id);
  const lineTotal = watchedValues.product_id
    ? calculatePurchaseLineTotal(watchedValues.quantity, watchedValues.unit_cost)
    : null;

  const submit = form.handleSubmit(async (values) => {
    await onSave(values);
    form.reset({ product_id: "", quantity: "1", unit_cost: "0.00" });
  });

  return (
    <form className="supplier-goods-form" onSubmit={submit}>
      <label className="field">
        <span>Product name</span>
        <select
          {...form.register("product_id", {
            onChange: (event) => {
              const product = products.find((item) => item.id === event.target.value);
              if (product) form.setValue("unit_cost", product.purchase_cost);
            },
          })}
          aria-invalid={Boolean(form.formState.errors.product_id)}
        >
          <option value="">Choose product</option>
          {products.filter((product) => product.is_active).map((product) => (
            <option key={product.id} value={product.id}>
              {product.name} · {product.unit_name}
            </option>
          ))}
        </select>
        {form.formState.errors.product_id && <small className="field-error">{form.formState.errors.product_id.message}</small>}
      </label>
      <label className="field">
        <span>Amount supplied ({selectedProduct?.unit_name ?? "quantity"})</span>
        <input inputMode="decimal" {...form.register("quantity")} aria-invalid={Boolean(form.formState.errors.quantity)} />
        {form.formState.errors.quantity && <small className="field-error">{form.formState.errors.quantity.message}</small>}
      </label>
      <label className="field">
        <span>Unit cost (NGN)</span>
        <input inputMode="decimal" {...form.register("unit_cost")} aria-invalid={Boolean(form.formState.errors.unit_cost)} />
        {form.formState.errors.unit_cost && <small className="field-error">{form.formState.errors.unit_cost.message}</small>}
      </label>
      <div aria-live="polite" className="supplier-goods-total">
        <span>Calculated goods amount</span>
        <strong>{lineTotal === null ? "Enter a valid quantity and unit cost" : formatNaira(lineTotal)}</strong>
      </div>
      <button className="button button-primary" disabled={isSaving || products.every((product) => !product.is_active)} type="submit">
        {isSaving ? <LoaderCircle className="spin" size={15} /> : <Plus size={15} />}
        Record goods supplied
      </button>
    </form>
  );
}

export function SuppliersPage({ user }: SuppliersPageProps) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [recordingFor, setRecordingFor] = useState<string | null>(null);
  const [goodsSuccess, setGoodsSuccess] = useState("");
  const [purchaseFilters, setPurchaseFilters] = useState<PurchaseHistoryFilters>(EMPTY_PURCHASE_FILTERS);
  const canRecordOpeningBalance = hasPermission(user, "suppliers:opening_balance");
  const canReadPurchases = hasPermission(user, "purchases:read");
  const canCreatePurchase = hasPermission(user, "purchases:create");
  const canReadProducts = hasPermission(user, "inventory:read");
  const canRecordSupplierGoods = canCreatePurchase && canReadProducts;
  const suppliersQuery = useQuery({ queryKey: ["suppliers"], queryFn: api.suppliers });
  const purchasesQuery = useQuery({
    queryKey: ["purchases", { limit: 500 }],
    queryFn: () => api.purchases(500),
    enabled: canReadPurchases,
  });
  const productsQuery = useQuery({
    queryKey: ["products"],
    queryFn: api.products,
    enabled: canRecordSupplierGoods,
  });
  const filterError = getPurchaseFilterError(purchaseFilters);
  const supplierPurchaseHistory = purchasesQuery.data?.filter((purchase) => purchase.supplier_id !== null) ?? [];
  const matchingPurchases = filterError || !purchasesQuery.data
    ? []
    : filterPurchaseHistory(supplierPurchaseHistory, purchaseFilters);
  const hasActivePurchaseFilters = hasPurchaseHistoryFilters(purchaseFilters);
  const matchingPurchaseCount = matchingPurchases.length;
  const matchingPurchaseTotal = sumMoney(matchingPurchases.map((purchase) => purchase.total_amount));
  const form = useForm<SupplierValues>({
    resolver: zodResolver(supplierSchema),
    defaultValues: {
      name: "",
      phone: "",
      whatsapp: "",
      whatsapp_receipt_opted_in: false,
      email: "",
      address: "",
      payment_terms_days: "",
      notes: "",
      opening_balance: "0.00",
      opening_balance_date: "",
      opening_balance_notes: "",
    },
  });
  const createMutation = useMutation({
    mutationFn: api.createSupplier,
    onSuccess: async () => {
      setActionError("");
      form.reset();
      await queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "Unable to create supplier.");
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: Parameters<typeof api.updateSupplier>[1] }) =>
      api.updateSupplier(id, changes),
    onSuccess: async () => {
      setActionError("");
      setEditingSupplier(null);
      form.reset();
      await queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "Unable to update supplier.");
    },
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.updateSupplier(id, { is_active }),
    onSuccess: async () => {
      setActionError("");
      await queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "Unable to update supplier.");
    },
  });
  const supplierGoodsMutation = useMutation({
    mutationFn: ({ supplierId, values }: { supplierId: string; values: SupplierGoodsValues }) =>
      api.createPurchase({
        supplier_id: supplierId,
        supplier_reference: null,
        purchase_date: todayInBusinessTimezone(),
        lines: [{
          product_id: values.product_id,
          quantity: values.quantity,
          unit_cost: values.unit_cost,
        }],
        payment_amount: "0.00",
        payment_method: null,
        payment_reference: null,
        notes: "",
      }),
    onSuccess: async (purchase) => {
      setGoodsSuccess(`Recorded ${purchase.purchase_number} for ${formatNaira(purchase.total_amount)}.`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["purchases"] }),
        queryClient.invalidateQueries({ queryKey: ["products"] }),
        queryClient.invalidateQueries({ queryKey: ["reports"] }),
        queryClient.invalidateQueries({ queryKey: ["suppliers"] }),
      ]);
    },
    onError: (error) => {
      setGoodsSuccess(error instanceof ApiError ? error.message : "Unable to record supplied goods.");
    },
  });

  const submit = form.handleSubmit((values) => {
    const fields = {
      name: values.name,
      phone: values.phone.trim() || null,
      whatsapp: values.whatsapp.trim() || null,
      whatsapp_receipt_opted_in: values.whatsapp_receipt_opted_in,
      email: values.email || null,
      address: values.address.trim() || null,
      payment_terms_days: values.payment_terms_days ? Number.parseInt(values.payment_terms_days, 10) : null,
      notes: values.notes.trim(),
    };
    if (editingSupplier) {
      updateMutation.mutate({ id: editingSupplier.id, changes: fields });
    } else {
      createMutation.mutate({
        ...fields,
        opening_balance: canRecordOpeningBalance ? values.opening_balance : "0.00",
        opening_balance_date: canRecordOpeningBalance ? values.opening_balance_date || null : null,
        opening_balance_notes: canRecordOpeningBalance ? values.opening_balance_notes.trim() || null : null,
      });
    }
  });

  const editSupplier = (supplier: Supplier) => {
    setActionError("");
    setEditingSupplier(supplier);
    form.reset({
      name: supplier.name,
      phone: supplier.phone ?? "",
      whatsapp: supplier.whatsapp ?? "",
      whatsapp_receipt_opted_in: supplier.whatsapp_receipt_opted_in,
      email: supplier.email ?? "",
      address: supplier.address ?? "",
      payment_terms_days: supplier.payment_terms_days?.toString() ?? "",
      notes: supplier.notes,
      opening_balance: "0.00",
      opening_balance_date: "",
      opening_balance_notes: "",
    });
  };

  return (
    <div className="settings-page records-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">BUSINESS RECORDS</span>
          <h1>Suppliers</h1>
          <p>Track supplier details and documented opening amounts payable.</p>
        </div>
      </div>
      <div className="records-layout">
        <form className="settings-card record-form-card" onSubmit={submit}>
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><Building2 size={18} /></span>
            <div><h2>{editingSupplier ? "Edit supplier" : "Add supplier"}</h2><p>Supplier balances start with documented opening entries.</p></div>
          </div>
          <div className="settings-fields">
            <label className="field">
              <span>Supplier name</span>
              <input {...form.register("name")} aria-invalid={Boolean(form.formState.errors.name)} />
              {form.formState.errors.name && <small className="field-error">{form.formState.errors.name.message}</small>}
            </label>
            <div className="settings-field-row">
              <label className="field"><span>Phone number</span><input {...form.register("phone")} /></label>
              <label className="field">
                <span>Payment terms (days)</span>
                <input inputMode="numeric" {...form.register("payment_terms_days")} aria-invalid={Boolean(form.formState.errors.payment_terms_days)} />
                {form.formState.errors.payment_terms_days && <small className="field-error">{form.formState.errors.payment_terms_days.message}</small>}
              </label>
            </div>
            <label className="field">
              <span>WhatsApp number</span>
              <input {...form.register("whatsapp", {
                onChange: (event) => {
                  if (editingSupplier && event.target.value.trim() !== (editingSupplier.whatsapp ?? "")) {
                    form.setValue("whatsapp_receipt_opted_in", false);
                  }
                },
              })} />
              {form.formState.errors.whatsapp && <small className="field-error">{form.formState.errors.whatsapp.message}</small>}
            </label>
            <label className="field whatsapp-consent-field">
              <span>
                <input type="checkbox" {...form.register("whatsapp_receipt_opted_in")} />
                Supplier agreed to receive payment confirmations on WhatsApp
              </span>
              <small>Only send after explicit supplier consent. Changing the WhatsApp number clears this consent.</small>
            </label>
            <div className="settings-field-row">
              <label className="field">
                <span>Email (optional)</span>
                <input type="email" {...form.register("email")} aria-invalid={Boolean(form.formState.errors.email)} />
                {form.formState.errors.email && <small className="field-error">{form.formState.errors.email.message}</small>}
              </label>
              <label className="field"><span>Address</span><input {...form.register("address")} /></label>
            </div>
            {canRecordOpeningBalance && !editingSupplier && (
              <>
                <div className="settings-field-row">
                  <label className="field">
                    <span>Opening amount MJD Square owes (NGN)</span>
                    <input inputMode="decimal" {...form.register("opening_balance")} />
                    {form.formState.errors.opening_balance && <small className="field-error">{form.formState.errors.opening_balance.message}</small>}
                  </label>
                  <label className="field">
                    <span>Effective date</span>
                    <input type="date" {...form.register("opening_balance_date")} />
                    {form.formState.errors.opening_balance_date && <small className="field-error">{form.formState.errors.opening_balance_date.message}</small>}
                  </label>
                </div>
                <label className="field">
                  <span>Opening balance source notes</span>
                  <input placeholder="For example, statement brought forward" {...form.register("opening_balance_notes")} />
                  {form.formState.errors.opening_balance_notes && <small className="field-error">{form.formState.errors.opening_balance_notes.message}</small>}
                </label>
              </>
            )}
            <label className="field"><span>Notes</span><input {...form.register("notes")} /></label>
          </div>
          {actionError && <p className="form-alert" role="alert">{actionError}</p>}
          <div className="settings-card-footer">
            <span className="settings-hint">Supplier records are retained; deactivate instead of deleting.</span>
            <div className="record-form-actions">
              {editingSupplier && <button className="button button-secondary" onClick={() => { setEditingSupplier(null); form.reset(); }} type="button">Cancel</button>}
              <button className="button button-primary" disabled={createMutation.isPending || updateMutation.isPending} type="submit">
                {createMutation.isPending || updateMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}
                {editingSupplier ? "Save supplier" : "Add supplier"}
              </button>
            </div>
          </div>
        </form>

        <section className="settings-card record-list-card">
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><Truck size={18} /></span>
            <div><h2>Supplier directory</h2><p>Filter up to the latest 500 supplier invoices by date, goods, amount, order reference, or payment status.</p></div>
          </div>
          {canReadPurchases && purchasesQuery.isError && (
            <p className="form-alert" role="alert">
              {purchasesQuery.error instanceof ApiError ? purchasesQuery.error.message : "Unable to load supplier purchase history."}
            </p>
          )}
          {canRecordSupplierGoods && productsQuery.isError && (
            <p className="form-alert" role="alert">
              {productsQuery.error instanceof ApiError ? productsQuery.error.message : "Unable to load products for supplier goods entry."}
            </p>
          )}
          {canReadPurchases && (
            <div className="supplier-purchase-filters">
              <div className="supplier-purchase-filters-heading">
                <span className="settings-heading-icon"><Filter size={16} /></span>
                <div><strong>Filter receipts</strong><small>Find supplier invoices and supplied goods</small></div>
              </div>
              <div className="supplier-purchase-filter-grid">
                <label className="field">
                  <span>From day</span>
                  <input
                    type="date"
                    max={purchaseFilters.toDate || undefined}
                    value={purchaseFilters.fromDate}
                    onChange={(event) => setPurchaseFilters((filters) => ({ ...filters, fromDate: event.target.value }))}
                  />
                </label>
                <label className="field">
                  <span>To day</span>
                  <input
                    type="date"
                    min={purchaseFilters.fromDate || undefined}
                    value={purchaseFilters.toDate}
                    onChange={(event) => setPurchaseFilters((filters) => ({ ...filters, toDate: event.target.value }))}
                  />
                </label>
                <label className="field">
                  <span>Goods / product</span>
                  <input
                    placeholder="Product name or SKU"
                    type="search"
                    value={purchaseFilters.product}
                    onChange={(event) => setPurchaseFilters((filters) => ({ ...filters, product: event.target.value }))}
                  />
                </label>
                <label className="field">
                  <span>Minimum amount (NGN)</span>
                  <input
                    inputMode="decimal"
                    min="0"
                    placeholder="Any"
                    step="0.01"
                    type="number"
                    value={purchaseFilters.minAmount}
                    onChange={(event) => setPurchaseFilters((filters) => ({ ...filters, minAmount: event.target.value }))}
                  />
                </label>
                <label className="field">
                  <span>Maximum amount (NGN)</span>
                  <input
                    inputMode="decimal"
                    min="0"
                    placeholder="Any"
                    step="0.01"
                    type="number"
                    value={purchaseFilters.maxAmount}
                    onChange={(event) => setPurchaseFilters((filters) => ({ ...filters, maxAmount: event.target.value }))}
                  />
                </label>
                <label className="field">
                  <span>Invoice / order / supplier</span>
                  <input
                    placeholder="Invoice number or reference"
                    type="search"
                    value={purchaseFilters.order}
                    onChange={(event) => setPurchaseFilters((filters) => ({ ...filters, order: event.target.value }))}
                  />
                </label>
                <label className="field">
                  <span>Payment status</span>
                  <select
                    value={purchaseFilters.paymentStatus}
                    onChange={(event) => setPurchaseFilters((filters) => ({
                      ...filters,
                      paymentStatus: event.target.value === "paid" || event.target.value === "outstanding"
                        ? event.target.value
                        : "all",
                    }))}
                  >
                    <option value="all">All invoices</option>
                    <option value="outstanding">Outstanding balance</option>
                    <option value="paid">Fully paid</option>
                  </select>
                </label>
              </div>
              {filterError && <p className="field-error" role="alert">{filterError}</p>}
              <div aria-live="polite" className="supplier-purchase-filter-summary">
                <span>
                  {purchasesQuery.isPending
                    ? "Loading receipts…"
                    : `${matchingPurchaseCount} matching ${matchingPurchaseCount === 1 ? "receipt" : "receipts"}`}
                </span>
                <strong>{purchasesQuery.data && !filterError ? `Total: ${formatNaira(matchingPurchaseTotal)}` : ""}</strong>
                {hasActivePurchaseFilters && (
                  <button
                    className="button button-secondary"
                    onClick={() => setPurchaseFilters(EMPTY_PURCHASE_FILTERS)}
                    type="button"
                  >
                    <RotateCcw size={13} /> Clear filters
                  </button>
                )}
              </div>
            </div>
          )}
          {suppliersQuery.isPending ? (
            <div className="loading-panel"><LoaderCircle className="spin" size={19} /> Loading suppliers…</div>
          ) : suppliersQuery.isError ? (
            <p className="form-alert" role="alert">
              {suppliersQuery.error instanceof ApiError ? suppliersQuery.error.message : "Unable to load suppliers."}
            </p>
          ) : suppliersQuery.data.length === 0 ? (
            <p className="empty-staff">No supplier records yet.</p>
          ) : hasActivePurchaseFilters && !filterError && purchasesQuery.data && matchingPurchases.length === 0 ? (
            <p className="empty-staff">No supplier receipts match these filters.</p>
          ) : (
            <div className="record-list">
              {suppliersQuery.data.map((supplier) => {
                const supplierPurchases = matchingPurchases.filter(
                  (purchase) => purchase.supplier_id === supplier.id,
                );
                if (hasActivePurchaseFilters && !filterError && purchasesQuery.data && supplierPurchases.length === 0) return null;
                return (
                  <article className="record-row supplier-record-row" key={supplier.id}>
                    <span className="profile-avatar">{supplier.name.slice(0, 1).toUpperCase()}</span>
                    <div className="record-details">
                      <strong>{supplier.name}</strong>
                      <small>{supplier.phone || supplier.whatsapp || supplier.email || "No contact details"}{supplier.payment_terms_days !== null ? ` · ${supplier.payment_terms_days} day terms` : ""}</small>
                      {supplier.opening_balances.map((balance) => (
                        <small className="record-note" key={`${balance.effective_date}-${balance.source_notes}`}>
                          Opening payable {formatNaira(balance.amount)} from {balance.effective_date}
                        </small>
                      ))}
                    </div>
                    <strong className="record-amount">{formatNaira(supplier.opening_balance_total)}</strong>
                    <span className={`staff-status${supplier.is_active ? " staff-status-active" : ""}`}>
                      {supplier.is_active ? "Active" : "Inactive"}
                    </span>
                    <button
                      className="button button-secondary record-action"
                      onClick={() => editSupplier(supplier)}
                      type="button"
                    >
                      Edit
                    </button>
                    <button
                      className="button button-secondary record-action"
                      disabled={statusMutation.isPending}
                      onClick={() => statusMutation.mutate({ id: supplier.id, is_active: !supplier.is_active })}
                      type="button"
                    >
                      {supplier.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                    {canRecordSupplierGoods && (
                      <button
                        className="button button-secondary record-action"
                        disabled={productsQuery.isPending || productsQuery.isError}
                        onClick={() => {
                          setGoodsSuccess("");
                          setRecordingFor(recordingFor === supplier.id ? null : supplier.id);
                        }}
                        type="button"
                      >
                        {recordingFor === supplier.id ? "Cancel entry" : "Record supplied goods"}
                      </button>
                    )}
                    {canReadPurchases && (
                      <div className="supplier-purchase-history">
                        <div className="supplier-purchase-heading">
                          <strong>Recent supplied goods</strong>
                          {purchasesQuery.data && (
                            <span>
                              Recent total (up to 500 invoices): {formatNaira(sumMoney(supplierPurchases.map((purchase) => purchase.total_amount)))}
                            </span>
                          )}
                        </div>
                        {purchasesQuery.isPending ? (
                          <small>Loading purchase history…</small>
                        ) : purchasesQuery.isError ? (
                          <small>Purchase history is unavailable.</small>
                        ) : supplierPurchases.length === 0 ? (
                          <small>No supplied goods recorded.</small>
                        ) : (
                          <ul className="supplier-purchase-list">
                            {supplierPurchases.map((purchase) => (
                              <li key={purchase.id}>
                                <div className="supplier-purchase-invoice">
                                  <strong>{purchase.purchase_number} · {purchase.purchase_date}</strong>
                                  <strong>{formatNaira(purchase.total_amount)}</strong>
                                </div>
                                {purchase.lines.map((line, index) => (
                                  <div className="supplier-purchase-line" key={`${purchase.id}-${line.product_id}-${index}`}>
                                    <span>{line.product_name}</span>
                                    <span>
                                      {formatQuantity(line.quantity, 3)} {line.unit_name} × {formatNaira(line.unit_cost)}
                                    </span>
                                    <strong>{formatNaira(line.line_total)}</strong>
                                  </div>
                                ))}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                    {recordingFor === supplier.id && canRecordSupplierGoods && productsQuery.data && (
                      <div className="supplier-goods-entry">
                        <strong>Record goods supplied by {supplier.name}</strong>
                        <p>This creates a supplier purchase and adds the quantity to inventory.</p>
                        {goodsSuccess && (
                          <p className={supplierGoodsMutation.isError ? "form-alert" : "success-alert"} role={supplierGoodsMutation.isError ? "alert" : "status"}>
                            {goodsSuccess}
                          </p>
                        )}
                        {productsQuery.data.filter((product) => product.is_active).length === 0 ? (
                          <p className="empty-staff">Add an active product before recording supplied goods.</p>
                        ) : (
                          <SupplierGoodsEntry
                            isSaving={supplierGoodsMutation.isPending}
                            onSave={(values) => supplierGoodsMutation.mutateAsync({ supplierId: supplier.id, values }).then(() => undefined)}
                            products={productsQuery.data}
                          />
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
