import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, PackagePlus, Plus } from "lucide-react";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { formatNaira, formatQuantity } from "../lib/format";
import { calculatePurchaseLineTotal, sumMoney } from "../lib/purchase";
import { hasPermission } from "../lib/permissions";
import { PaymentEvidenceFiles } from "../components/PaymentEvidenceFiles";
import type { Purchase, User } from "../types";

const todayInBusinessTimezone = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Lagos" }).format(new Date());

const purchaseSchema = z.object({
  supplier_id: z.string(),
  supplier_reference: z.string().max(100),
  purchase_date: z.string().min(1, "Choose the purchase date."),
  lines: z.array(z.object({
    product_id: z.string().min(1, "Choose a product."),
    quantity: z.string().regex(/^\d{1,11}(?:\.\d{1,3})?$/, "Enter a positive quantity."),
    unit_cost: z.string().regex(/^\d{1,12}(?:\.\d{1,2})?$/, "Enter a non-negative unit cost."),
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
    context.addIssue({ code: "custom", path: ["payment_method"], message: "Choose a payment method for the amount paid." });
  }
});

type PurchaseValues = z.infer<typeof purchaseSchema>;

interface PurchasesPageProps {
  user: User;
}

export function PurchasesPage({ user }: PurchasesPageProps) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const [paymentFor, setPaymentFor] = useState<Purchase | null>(null);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const purchasesQuery = useQuery({ queryKey: ["purchases"], queryFn: () => api.purchases() });
  const productsQuery = useQuery({ queryKey: ["products"], queryFn: api.products });
  const suppliersQuery = useQuery({
    queryKey: ["suppliers"],
    queryFn: api.suppliers,
    enabled: hasPermission(user, "suppliers:read"),
  });
  const settingsQuery = useQuery({ queryKey: ["business-settings"], queryFn: api.getSettings });
  const methods = settingsQuery.data?.payment_methods ?? [];
  const canCreate = hasPermission(user, "purchases:create");
  const canPay = hasPermission(user, "payments:create");
  const canReadPayments = hasPermission(user, "payments:read");
  const form = useForm<PurchaseValues>({
    resolver: zodResolver(purchaseSchema),
    defaultValues: {
      supplier_id: "",
      supplier_reference: "",
      purchase_date: todayInBusinessTimezone(),
      lines: [{ product_id: "", quantity: "1", unit_cost: "0.00" }],
      payment_amount: "0.00",
      payment_method: "",
      payment_reference: "",
      notes: "",
    },
  });
  const lines = useFieldArray({ control: form.control, name: "lines" });
  const watchedLines = form.watch("lines");
  const lineTotals = watchedLines.map((line) => (
    line.product_id ? calculatePurchaseLineTotal(line.quantity, line.unit_cost) : null
  ));
  const completeLineTotals = lineTotals.filter((lineTotal): lineTotal is string => lineTotal !== null);
  const goodsTotal = completeLineTotals.length === lineTotals.length ? sumMoney(completeLineTotals) : null;
  const createMutation = useMutation({
    mutationFn: api.createPurchase,
    onSuccess: async (purchase) => {
      setActionError(`Purchase ${purchase.purchase_number} recorded for ${formatNaira(purchase.total_amount)}.`);
      form.reset({
        supplier_id: "",
        supplier_reference: "",
        purchase_date: todayInBusinessTimezone(),
        lines: [{ product_id: "", quantity: "1", unit_cost: "0.00" }],
        payment_amount: "0.00",
        payment_method: "",
        payment_reference: "",
        notes: "",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["purchases"] }),
        queryClient.invalidateQueries({ queryKey: ["products"] }),
        queryClient.invalidateQueries({ queryKey: ["reports"] }),
      ]);
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to record purchase."),
  });
  const paymentMutation = useMutation({
    mutationFn: ({ purchaseId, amount, method, reference }: {
      purchaseId: string; amount: string; method: string; reference: string | null;
    }) => api.recordPurchasePayment(purchaseId, { amount, method, reference, notes: "" }),
    onSuccess: async () => {
      setActionError("Supplier payment recorded.");
      setPaymentFor(null);
      setPaymentAmount("");
      setPaymentReference("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["purchases"] }),
        queryClient.invalidateQueries({ queryKey: ["reports"] }),
      ]);
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to record payment."),
  });

  const submit = form.handleSubmit((values) => {
    setActionError("");
    createMutation.mutate({
      supplier_id: values.supplier_id || null,
      supplier_reference: values.supplier_reference.trim() || null,
      purchase_date: values.purchase_date,
      lines: values.lines.map((line) => ({
        product_id: line.product_id,
        quantity: line.quantity,
        unit_cost: line.unit_cost,
      })),
      payment_amount: values.payment_amount || "0.00",
      payment_method: /[1-9]/.test(values.payment_amount) ? values.payment_method : null,
      payment_reference: values.payment_reference.trim() || null,
      notes: values.notes.trim(),
    });
  });

  if (purchasesQuery.isPending || productsQuery.isPending || settingsQuery.isPending) {
    return <div className="loading-panel"><LoaderCircle className="spin" size={20} /> Loading purchase workspace…</div>;
  }
  if (purchasesQuery.isError || productsQuery.isError || settingsQuery.isError) {
    const error = purchasesQuery.error ?? productsQuery.error ?? settingsQuery.error;
    return <p className="form-alert" role="alert">{error instanceof ApiError ? error.message : "Unable to load purchase data."}</p>;
  }

  return (
    <div className="settings-page records-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">DAILY OPERATIONS</span>
          <h1>Purchases</h1>
          <p>Record supplier invoices and received stock, with any supplier payment against the purchase.</p>
        </div>
      </div>
      {actionError && (
        <p
          className={actionError.startsWith("Purchase ") || actionError.startsWith("Supplier ") ? "success-alert" : "form-alert"}
          role={actionError.startsWith("Purchase ") || actionError.startsWith("Supplier ") ? "status" : "alert"}
        >
          {actionError}
        </p>
      )}
      {suppliersQuery.isError && (
        <p className="form-alert" role="alert">
          {suppliersQuery.error instanceof ApiError ? suppliersQuery.error.message : "Unable to load suppliers."}
        </p>
      )}
      {canCreate && (
        <form className="settings-card transaction-form" onSubmit={submit}>
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><PackagePlus size={18} /></span>
            <div><h2>Record a purchase</h2><p>Line totals are calculated from quantity and unit cost; stock and invoice records are saved together.</p></div>
          </div>
          <div className="settings-fields">
            <div className="settings-field-row">
              <label className="field"><span>Purchase date</span><input type="date" {...form.register("purchase_date")} /></label>
              <label className="field"><span>Supplier (optional)</span>
                <select {...form.register("supplier_id")}>
                  <option value="">Cash purchase / no supplier</option>
                  {(suppliersQuery.data ?? []).filter((supplier) => supplier.is_active).map((supplier) =>
                    <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
                </select>
              </label>
            </div>
            <label className="field"><span>Supplier invoice / reference (optional)</span><input {...form.register("supplier_reference")} /></label>
            <div className="record-subsection">
              <div className="record-subsection-heading">
                <strong>Items received</strong>
                <button className="button button-secondary" onClick={() => lines.append({ product_id: "", quantity: "1", unit_cost: "0.00" })} type="button">
                  <Plus size={14} /> Add item
                </button>
              </div>
              {lines.fields.map((field, index) => (
                <div className="settings-field-row transaction-line" key={field.id}>
                  <label className="field"><span>Product</span>
                    <select {...form.register(`lines.${index}.product_id`)} onChange={(event) => {
                      form.setValue(`lines.${index}.product_id`, event.target.value);
                      const product = productsQuery.data.find((item) => item.id === event.target.value);
                      if (product) form.setValue(`lines.${index}.unit_cost`, product.purchase_cost);
                    }}>
                      <option value="">Choose product</option>
                      {productsQuery.data.filter((product) => product.is_active).map((product) =>
                        <option key={product.id} value={product.id}>{product.name} · stock {formatQuantity(product.stock_quantity, product.unit_decimal_places)}</option>)}
                    </select>
                  </label>
                  <label className="field"><span>Quantity received</span><input inputMode="decimal" {...form.register(`lines.${index}.quantity`)} /></label>
                  <label className="field"><span>Unit cost (NGN)</span><input inputMode="decimal" {...form.register(`lines.${index}.unit_cost`)} /></label>
                  {lines.fields.length > 1 && <button className="button button-secondary" onClick={() => lines.remove(index)} type="button">Remove</button>}
                  <div className="purchase-line-total">
                    <span>Line total</span>
                    <strong>{lineTotals[index] ? formatNaira(lineTotals[index]) : "—"}</strong>
                  </div>
                </div>
              ))}
              {form.formState.errors.lines && <small className="field-error">{form.formState.errors.lines.message}</small>}
              <div aria-live="polite" className="purchase-goods-total">
                <span>Total goods</span>
                <strong>{goodsTotal === null ? "Complete each product, quantity, and unit cost" : formatNaira(goodsTotal)}</strong>
              </div>
            </div>
            {canPay && (
              <div className="settings-field-row">
                <label className="field"><span>Amount paid now (NGN)</span><input inputMode="decimal" {...form.register("payment_amount")} /></label>
                <label className="field"><span>Payment method</span>
                  <select {...form.register("payment_method")}><option value="">No payment now</option>{methods.map((method) => <option key={method}>{method}</option>)}</select>
                  {form.formState.errors.payment_method && <small className="field-error">{form.formState.errors.payment_method.message}</small>}
                </label>
              </div>
            )}
            {canPay && <label className="field"><span>Payment reference (optional)</span><input {...form.register("payment_reference")} /></label>}
            <label className="field"><span>Notes (optional)</span><input {...form.register("notes")} /></label>
          </div>
          <div className="settings-card-footer">
            <span className="settings-hint">Purchase quantities are added to inventory and movements are audited.</span>
            <button className="button button-primary" disabled={createMutation.isPending} type="submit">
              {createMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />} Record purchase
            </button>
          </div>
        </form>
      )}

      <section className="settings-card record-list-card transaction-history-card">
        <div className="settings-card-heading">
          <span className="settings-heading-icon"><PackagePlus size={18} /></span>
          <div><h2>Recent purchases</h2><p>Supplier balances are derived from opening entries, purchases, and payment records.</p></div>
        </div>
        {purchasesQuery.data.length === 0 ? <p className="empty-staff">No purchases recorded yet.</p> : (
          <div className="record-list">
            {purchasesQuery.data.map((purchase) => (
              <article className="transaction-row" key={purchase.id}>
                <div className="transaction-row-main">
                  <div className="record-details">
                    <strong>{purchase.purchase_number} · {purchase.supplier_name ?? "Cash purchase"}</strong>
                    <small>{purchase.purchase_date}{purchase.supplier_reference ? ` · Ref ${purchase.supplier_reference}` : ""} · {purchase.lines.map((line) =>
                      `${line.product_name} × ${formatQuantity(line.quantity, 3)}`).join(", ")}</small>
                  </div>
                  <div className="transaction-amounts">
                    <strong>{formatNaira(purchase.total_amount)}</strong>
                    <small>{purchase.balance_due === "0.00" ? "Paid" : `${formatNaira(purchase.balance_due)} due`}</small>
                  </div>
                  {canPay && purchase.balance_due !== "0.00" && (
                    <button className="button button-secondary record-action" onClick={() => {
                      setPaymentFor(paymentFor?.id === purchase.id ? null : purchase);
                      setPaymentAmount(purchase.balance_due);
                      setPaymentMethod(methods[0] ?? "");
                    }} type="button">Record payment</button>
                  )}
                </div>
                {purchase.payments.map((payment) => (
                  <div className="purchase-payment-evidence" key={payment.id}>
                    <small className="transaction-payment">
                      {formatNaira(payment.amount)} paid · {payment.method}{payment.reference ? ` · ${payment.reference}` : ""}
                    </small>
                    {payment.whatsapp_receipt_status && (
                      <small className="transaction-payment">
                        WhatsApp payment confirmation: {payment.whatsapp_receipt_status}
                      </small>
                    )}
                    <PaymentEvidenceFiles
                      canDownload={canReadPayments}
                      canUpload={canPay}
                      canDelete={user.role.name === "Owner"}
                      onUploaded={() => void queryClient.invalidateQueries({ queryKey: ["purchases"] })}
                      onDeleted={() => void queryClient.invalidateQueries({ queryKey: ["purchases"] })}
                      paymentId={payment.id}
                      receipts={payment.receipts}
                    />
                  </div>
                ))}
                {paymentFor?.id === purchase.id && (
                  <form className="payment-inline-form" onSubmit={(event) => {
                    event.preventDefault();
                    paymentMutation.mutate({
                      purchaseId: purchase.id,
                      amount: paymentAmount,
                      method: paymentMethod,
                      reference: paymentReference.trim() || null,
                    });
                  }}>
                    <label className="field"><span>Amount</span><input type="number" min="0.01" max={purchase.balance_due} step="0.01" required value={paymentAmount} onChange={(event) => setPaymentAmount(event.target.value)} /></label>
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
    </div>
  );
}
