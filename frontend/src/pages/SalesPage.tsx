import { zodResolver } from "@hookform/resolvers/zod";
import { FileText, LoaderCircle, Plus, ShoppingBag } from "lucide-react";
import { useState } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { formatNaira, formatQuantity } from "../lib/format";
import { hasPermission } from "../lib/permissions";
import type { Sale, User } from "../types";

const todayInBusinessTimezone = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Lagos" }).format(new Date());

const saleSchema = z.object({
  customer_id: z.string(),
  sale_type: z.enum(["retail", "wholesale"]),
  sale_date: z.string().min(1, "Choose the sale date."),
  lines: z.array(z.object({
    product_id: z.string().min(1, "Choose a product."),
    quantity: z.string().regex(/^\d{1,11}(?:\.\d{1,3})?$/, "Enter a positive quantity."),
  })).min(1),
  payment_amount: z.string().regex(/^\d{1,12}(?:\.\d{1,2})?$/, "Enter an amount with up to 2 decimals."),
  payment_method: z.string(),
  payment_reference: z.string().max(100),
  notes: z.string().max(1000),
}).superRefine((value, context) => {
  if (value.lines.some((line) => !/[1-9]/.test(line.quantity))) {
    context.addIssue({ code: "custom", path: ["lines"], message: "Every item needs a quantity greater than zero." });
  }
  if (/[1-9]/.test(value.payment_amount) && !value.payment_method) {
    context.addIssue({ code: "custom", path: ["payment_method"], message: "Choose a payment method for the amount received." });
  }
});

type SaleValues = z.infer<typeof saleSchema>;

interface SalesPageProps {
  user: User;
}

export function SalesPage({ user }: SalesPageProps) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const [paymentFor, setPaymentFor] = useState<Sale | null>(null);
  const [printingSale, setPrintingSale] = useState<Sale | null>(null);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const salesQuery = useQuery({ queryKey: ["sales"], queryFn: api.sales });
  const productsQuery = useQuery({ queryKey: ["products"], queryFn: api.products });
  const customersQuery = useQuery({
    queryKey: ["customers"],
    queryFn: api.customers,
    enabled: hasPermission(user, "customers:read"),
  });
  const settingsQuery = useQuery({ queryKey: ["business-settings"], queryFn: api.getSettings });
  const methods = settingsQuery.data?.payment_methods ?? [];
  const canCreate = hasPermission(user, "sales:create");
  const canTakePayment = hasPermission(user, "payments:create");
  const form = useForm<SaleValues>({
    resolver: zodResolver(saleSchema),
    defaultValues: {
      customer_id: "",
      sale_type: "retail",
      sale_date: todayInBusinessTimezone(),
      lines: [{ product_id: "", quantity: "1" }],
      payment_amount: "0.00",
      payment_method: "",
      payment_reference: "",
      notes: "",
    },
  });
  const lines = useFieldArray({ control: form.control, name: "lines" });
  const createMutation = useMutation({
    mutationFn: api.createSale,
    onSuccess: async (sale) => {
      setActionError("");
      form.reset({
        customer_id: "",
        sale_type: "retail",
        sale_date: todayInBusinessTimezone(),
        lines: [{ product_id: "", quantity: "1" }],
        payment_amount: "0.00",
        payment_method: "",
        payment_reference: "",
        notes: "",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sales"] }),
        queryClient.invalidateQueries({ queryKey: ["products"] }),
        queryClient.invalidateQueries({ queryKey: ["reports"] }),
      ]);
      setActionError(`Invoice ${sale.invoice_number} recorded for ${formatNaira(sale.total_amount)}.`);
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to record sale."),
  });
  const paymentMutation = useMutation({
    mutationFn: ({ saleId, amount, method, reference }: {
      saleId: string; amount: string; method: string; reference: string | null;
    }) => api.recordSalePayment(saleId, { amount, method, reference, notes: "" }),
    onSuccess: async () => {
      setActionError("Payment recorded.");
      setPaymentFor(null);
      setPaymentAmount("");
      setPaymentReference("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sales"] }),
        queryClient.invalidateQueries({ queryKey: ["reports"] }),
      ]);
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to record payment."),
  });

  const submit = form.handleSubmit((values) => {
    setActionError("");
    createMutation.mutate({
      customer_id: values.customer_id || null,
      sale_type: values.sale_type,
      sale_date: values.sale_date,
      lines: values.lines.map((line) => ({ product_id: line.product_id, quantity: line.quantity })),
      payment_amount: values.payment_amount || "0.00",
      payment_method: values.payment_amount && /[1-9]/.test(values.payment_amount) ? values.payment_method : null,
      payment_reference: values.payment_reference.trim() || null,
      notes: values.notes.trim(),
    });
  });

  if (salesQuery.isPending || productsQuery.isPending || settingsQuery.isPending) {
    return <div className="loading-panel"><LoaderCircle className="spin" size={20} /> Loading sales workspace…</div>;
  }
  if (salesQuery.isError || productsQuery.isError || settingsQuery.isError) {
    const error = salesQuery.error ?? productsQuery.error ?? settingsQuery.error;
    return <p className="form-alert" role="alert">{error instanceof ApiError ? error.message : "Unable to load sales data."}</p>;
  }

  return (
    <div className="settings-page records-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">DAILY OPERATIONS</span>
          <h1>Sales & invoices</h1>
          <p>Record completed sales, update stock, and track payments against each invoice.</p>
        </div>
      </div>
      {actionError && (
        <p
          className={actionError.startsWith("Invoice ") || actionError === "Payment recorded." ? "success-alert" : "form-alert"}
          role={actionError.startsWith("Invoice ") || actionError === "Payment recorded." ? "status" : "alert"}
        >
          {actionError}
        </p>
      )}
      {customersQuery.isError && (
        <p className="form-alert" role="alert">
          {customersQuery.error instanceof ApiError ? customersQuery.error.message : "Unable to load customers."}
        </p>
      )}
      {canCreate && (
        <form className="settings-card transaction-form" onSubmit={submit}>
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><ShoppingBag size={18} /></span>
            <div><h2>Record a sale</h2><p>Prices use the product retail/wholesale price and applicable quantity tier.</p></div>
          </div>
          <div className="settings-fields">
            <div className="settings-field-row">
              <label className="field"><span>Sale date</span><input type="date" {...form.register("sale_date")} /></label>
              <label className="field"><span>Sale type</span>
                <select {...form.register("sale_type")}><option value="retail">Retail</option><option value="wholesale">Wholesale</option></select>
              </label>
            </div>
            <label className="field"><span>Customer (optional)</span>
              <select {...form.register("customer_id")}>
                <option value="">Walk-in customer</option>
                {(customersQuery.data ?? []).filter((customer) => customer.is_active).map((customer) =>
                  <option key={customer.id} value={customer.id}>{customer.name}</option>)}
              </select>
            </label>
            <div className="record-subsection">
              <div className="record-subsection-heading">
                <strong>Items</strong>
                <button className="button button-secondary" onClick={() => lines.append({ product_id: "", quantity: "1" })} type="button">
                  <Plus size={14} /> Add item
                </button>
              </div>
              {lines.fields.map((field, index) => (
                <div className="settings-field-row transaction-line" key={field.id}>
                  <label className="field"><span>Product</span>
                    <select {...form.register(`lines.${index}.product_id`)}>
                      <option value="">Choose product</option>
                      {productsQuery.data.filter((product) => product.is_active).map((product) =>
                        <option key={product.id} value={product.id}>
                          {product.name} · stock {formatQuantity(product.stock_quantity, product.unit_decimal_places)}
                        </option>)}
                    </select>
                  </label>
                  <label className="field"><span>Quantity</span><input inputMode="decimal" {...form.register(`lines.${index}.quantity`)} /></label>
                  {lines.fields.length > 1 && <button className="button button-secondary" onClick={() => lines.remove(index)} type="button">Remove</button>}
                </div>
              ))}
              {form.formState.errors.lines && <small className="field-error">{form.formState.errors.lines.message}</small>}
            </div>
            {canTakePayment && (
              <div className="settings-field-row">
                <label className="field"><span>Amount received now (NGN)</span><input inputMode="decimal" {...form.register("payment_amount")} /></label>
                <label className="field"><span>Payment method</span>
                  <select {...form.register("payment_method")}><option value="">No payment now</option>{methods.map((method) => <option key={method}>{method}</option>)}</select>
                  {form.formState.errors.payment_method && <small className="field-error">{form.formState.errors.payment_method.message}</small>}
                </label>
              </div>
            )}
            {canTakePayment && <label className="field"><span>Payment reference (optional)</span><input {...form.register("payment_reference")} /></label>}
            <label className="field"><span>Notes (optional)</span><input {...form.register("notes")} /></label>
          </div>
          <div className="settings-card-footer">
            <span className="settings-hint">A sale is finalized when recorded; stock cannot go below zero.</span>
            <button className="button button-primary" disabled={createMutation.isPending || settingsQuery.isError} type="submit">
              {createMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />} Record sale
            </button>
          </div>
        </form>
      )}

      <section className="settings-card record-list-card transaction-history-card">
        <div className="settings-card-heading">
          <span className="settings-heading-icon"><FileText size={18} /></span>
          <div><h2>Recent invoices</h2><p>Invoices and payment entries are retained as an audit trail.</p></div>
        </div>
        {salesQuery.data.length === 0 ? <p className="empty-staff">No sales recorded yet.</p> : (
          <div className="record-list">
            {salesQuery.data.map((sale) => (
              <article className="transaction-row" key={sale.id}>
                <div className="transaction-row-main">
                  <div className="record-details">
                    <strong>{sale.invoice_number} · {sale.customer_name ?? "Walk-in customer"}</strong>
                    <small>{sale.sale_date} · {sale.sale_type} · {sale.lines.map((line) =>
                      `${line.product_name} × ${formatQuantity(line.quantity, 3)}`).join(", ")}</small>
                  </div>
                  <div className="transaction-amounts">
                    <strong>{formatNaira(sale.total_amount)}</strong>
                    <small>{sale.balance_due === "0.00" ? "Paid" : `${formatNaira(sale.balance_due)} due`}</small>
                  </div>
                  {canTakePayment && sale.balance_due !== "0.00" && (
                    <button className="button button-secondary record-action" onClick={() => {
                      setPaymentFor(paymentFor?.id === sale.id ? null : sale);
                      setPaymentAmount(sale.balance_due);
                      setPaymentMethod(methods[0] ?? "");
                    }} type="button">Record payment</button>
                  )}
                  <button className="button button-secondary record-action" onClick={() => {
                    setPrintingSale(sale);
                    window.addEventListener("afterprint", () => setPrintingSale(null), { once: true });
                    window.setTimeout(() => window.print(), 0);
                  }} type="button">Print invoice</button>
                </div>
                {sale.payments.map((payment) => (
                  <small className="transaction-payment" key={payment.id}>
                    {formatNaira(payment.amount)} received · {payment.method}{payment.reference ? ` · ${payment.reference}` : ""}
                  </small>
                ))}
                {paymentFor?.id === sale.id && (
                  <form className="payment-inline-form" onSubmit={(event) => {
                    event.preventDefault();
                    paymentMutation.mutate({
                      saleId: sale.id,
                      amount: paymentAmount,
                      method: paymentMethod,
                      reference: paymentReference.trim() || null,
                    });
                  }}>
                    <label className="field"><span>Amount</span><input type="number" min="0.01" max={sale.balance_due} step="0.01" required value={paymentAmount} onChange={(event) => setPaymentAmount(event.target.value)} /></label>
                    <label className="field"><span>Method</span><select required value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)}>{methods.map((method) => <option key={method}>{method}</option>)}</select></label>
                    <label className="field"><span>Reference</span><input value={paymentReference} onChange={(event) => setPaymentReference(event.target.value)} /></label>
                    <button className="button button-primary" disabled={paymentMutation.isPending || !methods.length} type="submit">{paymentMutation.isPending ? "Saving…" : "Save payment"}</button>
                  </form>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
      {printingSale && (
        <article className="print-invoice" aria-label="Printable invoice">
          <header className="print-invoice-header">
            <div>
              <span className="eyebrow">MJD SQUARE</span>
              <h1>{settingsQuery.data.business_name}</h1>
              <p>Sales invoice · {printingSale.sale_type}</p>
            </div>
            <div className="print-invoice-number">
              <strong>{printingSale.invoice_number}</strong>
              <span>{printingSale.sale_date}</span>
            </div>
          </header>
          <p><strong>Customer:</strong> {printingSale.customer_name ?? "Walk-in customer"}</p>
          <table>
            <thead><tr><th>Item</th><th>Qty</th><th>Unit price</th><th>Total</th></tr></thead>
            <tbody>{printingSale.lines.map((line) => (
              <tr key={line.product_id}>
                <td>{line.product_name}<small>{line.sku}</small></td>
                <td>{formatQuantity(line.quantity, 3)} {line.unit_name}</td>
                <td>{formatNaira(line.unit_price)}</td>
                <td>{formatNaira(line.line_total)}</td>
              </tr>
            ))}</tbody>
          </table>
          <div className="print-invoice-totals">
            <p><span>Total</span><strong>{formatNaira(printingSale.total_amount)}</strong></p>
            <p><span>Paid</span><strong>{formatNaira(printingSale.amount_paid)}</strong></p>
            <p><span>Balance due</span><strong>{formatNaira(printingSale.balance_due)}</strong></p>
          </div>
          <p className="print-invoice-note">Thank you for your business. Payments shown are manually recorded and are not independently bank-verified.</p>
        </article>
      )}
    </div>
  );
}
