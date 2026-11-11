import { zodResolver } from "@hookform/resolvers/zod";
import { BarChart3, Download, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { formatNaira } from "../lib/format";
import { PaymentEvidenceFiles } from "../components/PaymentEvidenceFiles";
import type { User } from "../types";

const todayInBusinessTimezone = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Lagos" }).format(new Date());
const dateRangeSchema = z.object({
  from: z.string().min(1, "Choose a start date."),
  to: z.string().min(1, "Choose an end date."),
}).refine((value) => value.from <= value.to, {
  path: ["to"],
  message: "End date must be on or after the start date.",
});

type DateRange = z.infer<typeof dateRangeSchema>;

function csvCell(value: string): string {
  const safeValue = /^[=+\-@]/.test(value) ? `'${value}` : value;
  return `"${safeValue.replaceAll('"', '""')}"`;
}

function downloadCsv(filename: string, rows: string[][]) {
  const content = rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
  const objectUrl = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

export function ReportsPage({ user }: { user: User }) {
  const queryClient = useQueryClient();
  const [range, setRange] = useState<DateRange>({
    from: todayInBusinessTimezone(),
    to: todayInBusinessTimezone(),
  });
  const form = useForm<DateRange>({
    resolver: zodResolver(dateRangeSchema),
    defaultValues: range,
  });
  const summaryQuery = useQuery({
    queryKey: ["reports", "summary", range.from, range.to],
    queryFn: () => api.reportSummary(range.from, range.to),
  });
  const outstandingQuery = useQuery({
    queryKey: ["reports", "outstanding"],
    queryFn: api.outstandingBalances,
  });
  const accountPaymentsQuery = useQuery({
    queryKey: ["account-payments"],
    queryFn: api.accountPayments,
  });
  const settingsQuery = useQuery({ queryKey: ["business-settings"], queryFn: api.getSettings });
  const [paymentTarget, setPaymentTarget] = useState<{
    id: string;
    name: string;
    type: "customer" | "supplier";
    balance: string;
  } | null>(null);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const paymentMutation = useMutation({
    mutationFn: ({ target, amount, method, reference }: {
      target: NonNullable<typeof paymentTarget>;
      amount: string;
      method: string;
      reference: string | null;
    }) => target.type === "customer"
      ? api.recordCustomerAccountPayment(target.id, { amount, method, reference, notes: "" })
      : api.recordSupplierAccountPayment(target.id, { amount, method, reference, notes: "" }),
    onSuccess: async () => {
      setPaymentTarget(null);
      setPaymentAmount("");
      setPaymentReference("");
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      await queryClient.invalidateQueries({ queryKey: ["account-payments"] });
    },
  });

  const applyRange = form.handleSubmit((value) => setRange(value));
  const summary = summaryQuery.data;

  return (
    <div className="settings-page records-page reports-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">BUSINESS PERFORMANCE</span>
          <h1>Reports</h1>
          <p>Review recorded sales, payments, purchases, expenses, stock warnings, and outstanding balances.</p>
        </div>
      </div>
      <form className="settings-card report-filter-card" onSubmit={applyRange}>
        <div className="settings-field-row">
          <label className="field"><span>From</span><input type="date" {...form.register("from")} />{form.formState.errors.from && <small className="field-error">{form.formState.errors.from.message}</small>}</label>
          <label className="field"><span>To</span><input type="date" {...form.register("to")} />{form.formState.errors.to && <small className="field-error">{form.formState.errors.to.message}</small>}</label>
        </div>
        <div className="report-filter-actions">
          <span className="settings-hint">Figures reflect saved manual business records, not bank-verified activity.</span>
          <button className="button button-primary" disabled={summaryQuery.isFetching} type="submit">
            {summaryQuery.isFetching ? <LoaderCircle className="spin" size={16} /> : <BarChart3 size={16} />} Apply dates
          </button>
        </div>
      </form>

      {summaryQuery.isError && <p className="form-alert" role="alert">{summaryQuery.error instanceof ApiError ? summaryQuery.error.message : "Unable to load report summary."}</p>}
      {outstandingQuery.isError && <p className="form-alert" role="alert">{outstandingQuery.error instanceof ApiError ? outstandingQuery.error.message : "Unable to load outstanding balances."}</p>}
      {accountPaymentsQuery.isError && <p className="form-alert" role="alert">{accountPaymentsQuery.error instanceof ApiError ? accountPaymentsQuery.error.message : "Unable to load account payment history."}</p>}
      {settingsQuery.isError && <p className="form-alert" role="alert">{settingsQuery.error instanceof ApiError ? settingsQuery.error.message : "Unable to load payment methods."}</p>}
      {summaryQuery.isPending || outstandingQuery.isPending || settingsQuery.isPending ? (
        <div className="loading-panel"><LoaderCircle className="spin" size={20} /> Loading reports…</div>
      ) : summary && outstandingQuery.data && (
        <>
          <div className="report-grid">
            <article className="report-card"><span>Sales invoiced</span><strong>{formatNaira(summary.sales_total)}</strong><small>{range.from} to {range.to}</small></article>
            <article className="report-card"><span>Payments received</span><strong>{formatNaira(summary.payments_received)}</strong><small>Payments recorded in this period</small></article>
            <article className="report-card"><span>Purchases</span><strong>{formatNaira(summary.purchases_total)}</strong><small>Supplier invoices recorded</small></article>
            <article className="report-card"><span>Supplier payments</span><strong>{formatNaira(summary.payments_made)}</strong><small>Payments recorded in this period</small></article>
            <article className="report-card"><span>Expenses</span><strong>{formatNaira(summary.expenses_total)}</strong><small>Manually recorded outgoings</small></article>
            <article className="report-card"><span>Low-stock products</span><strong>{summary.low_stock_count}</strong><small>Active products at or below threshold</small></article>
          </div>
          <section className="settings-card transaction-history-card">
            <div className="settings-card-heading report-section-heading">
              <span className="settings-heading-icon"><BarChart3 size={18} /></span>
              <div><h2>Outstanding balances</h2><p>Opening balances + invoices − recorded payments. Opening entries remain separate from historical invoices.</p></div>
              <button className="button button-secondary" onClick={() => {
                const outstanding = outstandingQuery.data;
                downloadCsv("mjd-square-outstanding-balances.csv", [
                  ["Account type", "Name", "Balance due (NGN)"],
                  ...outstanding.customer_balances.map((item) => ["Customer", item.name, item.balance_due]),
                  ...outstanding.supplier_balances.map((item) => ["Supplier", item.name, item.balance_due]),
                ]);
              }} type="button"><Download size={15} /> Export balances</button>
            </div>
            {outstandingQuery.data && (
              <div className="outstanding-grid">
                <div>
                  <h3>Customers owing MJD Square</h3>
                  {outstandingQuery.data.customer_balances.length === 0 ? <p className="empty-staff">No customer balances due.</p> : (
                    outstandingQuery.data.customer_balances.map((item) => (
                      <div className="balance-row" key={item.id}>
                        <span>{item.name}</span><strong>{formatNaira(item.balance_due)}</strong>
                        <button className="button button-secondary record-action" onClick={() => {
                          setPaymentTarget({ id: item.id, name: item.name, type: "customer", balance: item.balance_due });
                          setPaymentAmount(item.balance_due);
                          setPaymentMethod(settingsQuery.data?.payment_methods[0] ?? "");
                        }} type="button">Record payment</button>
                      </div>
                    ))
                  )}
                </div>
                <div>
                  <h3>Payables to suppliers</h3>
                  {outstandingQuery.data.supplier_balances.length === 0 ? <p className="empty-staff">No supplier balances due.</p> : (
                    outstandingQuery.data.supplier_balances.map((item) => (
                      <div className="balance-row" key={item.id}>
                        <span>{item.name}</span><strong>{formatNaira(item.balance_due)}</strong>
                        <button className="button button-secondary record-action" onClick={() => {
                          setPaymentTarget({ id: item.id, name: item.name, type: "supplier", balance: item.balance_due });
                          setPaymentAmount(item.balance_due);
                          setPaymentMethod(settingsQuery.data?.payment_methods[0] ?? "");
                        }} type="button">Record payment</button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
            {paymentTarget && (
              <form className="payment-inline-form account-payment-form" onSubmit={(event) => {
                event.preventDefault();
                paymentMutation.mutate({
                  target: paymentTarget,
                  amount: paymentAmount,
                  method: paymentMethod,
                  reference: paymentReference.trim() || null,
                });
              }}>
                <strong>
                  {paymentTarget.type === "customer" ? "Payment received from" : "Payment made to"} {paymentTarget.name}
                </strong>
                <label className="field"><span>Amount (NGN)</span><input type="number" min="0.01" max={paymentTarget.balance} step="0.01" required value={paymentAmount} onChange={(event) => setPaymentAmount(event.target.value)} /></label>
                <label className="field"><span>Payment method</span><select required value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)}>{(settingsQuery.data?.payment_methods ?? []).map((method) => <option key={method}>{method}</option>)}</select></label>
                <label className="field"><span>Reference</span><input value={paymentReference} onChange={(event) => setPaymentReference(event.target.value)} /></label>
                {paymentMutation.isError && <p className="form-alert" role="alert">{paymentMutation.error instanceof ApiError ? paymentMutation.error.message : "Unable to record account payment."}</p>}
                <div className="record-form-actions">
                  <button className="button button-secondary" onClick={() => setPaymentTarget(null)} type="button">Cancel</button>
                  <button className="button button-primary" disabled={paymentMutation.isPending || !settingsQuery.data?.payment_methods.length} type="submit">{paymentMutation.isPending ? "Saving…" : "Save payment"}</button>
                </div>
              </form>
            )}
          </section>
          <section className="settings-card transaction-history-card account-payment-history">
            <div className="settings-card-heading report-section-heading">
              <span className="settings-heading-icon"><BarChart3 size={18} /></span>
              <div><h2>Account payment proof</h2><p>Saved receipts for customer and supplier account payments.</p></div>
            </div>
            {accountPaymentsQuery.isPending ? (
              <div className="loading-panel"><LoaderCircle className="spin" size={18} /> Loading account payments…</div>
            ) : accountPaymentsQuery.data?.length ? (
              <div className="account-payment-history-list">
                {accountPaymentsQuery.data.map((payment) => (
                  <article className="account-payment-history-row" key={payment.id}>
                    <div>
                      <strong>{payment.account_name}</strong>
                      <small>{payment.account_type === "customer" ? "Customer payment received" : "Supplier payment made"} · {payment.method} · {new Intl.DateTimeFormat("en-NG", { dateStyle: "medium", timeZone: "Africa/Lagos" }).format(new Date(payment.received_at))}</small>
                      {payment.reference && <small>Reference: {payment.reference}</small>}
                    </div>
                    <strong>{formatNaira(payment.amount)}</strong>
                    <PaymentEvidenceFiles
                      accountPayment
                      canDownload
                      canUpload
                      canDelete={user.role.name === "Owner"}
                      onUploaded={() => void queryClient.invalidateQueries({ queryKey: ["account-payments"] })}
                      onDeleted={() => void queryClient.invalidateQueries({ queryKey: ["account-payments"] })}
                      paymentId={payment.id}
                      receipts={payment.receipts}
                    />
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-staff">No customer or supplier account payments have been recorded.</p>
            )}
          </section>
          <button className="button button-secondary report-export" onClick={() => downloadCsv("mjd-square-period-summary.csv", [
            ["Metric", "Amount / count"],
            ["Sales invoiced (NGN)", summary.sales_total],
            ["Payments received (NGN)", summary.payments_received],
            ["Purchases (NGN)", summary.purchases_total],
            ["Supplier payments (NGN)", summary.payments_made],
            ["Expenses (NGN)", summary.expenses_total],
            ["Low-stock products", String(summary.low_stock_count)],
          ])} type="button"><Download size={15} /> Export period summary</button>
        </>
      )}
    </div>
  );
}
