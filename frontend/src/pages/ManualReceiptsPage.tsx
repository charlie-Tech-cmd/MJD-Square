import { zodResolver } from "@hookform/resolvers/zod";
import { Download, LoaderCircle, MessageCircle, Printer, ReceiptText } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { hasPermission } from "../lib/permissions";
import { downloadReceiptPdf } from "../lib/receiptPdf";
import type { ManualPaymentReceipt, User } from "../types";

const todayInBusinessTimezone = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Lagos" }).format(new Date());

const manualReceiptSchema = z.object({
  payer_name: z.string().trim().min(1, "Enter the payer's name.").max(160),
  payer_phone: z.string().trim().max(40),
  purpose: z.string().trim().min(1, "Enter what the payment was for.").max(240),
  amount: z.string()
    .regex(/^\d{1,12}(?:\.\d{1,2})?$/, "Enter an amount with up to 2 decimals.")
    .refine((value) => Number(value) > 0, "Enter an amount greater than zero."),
  payment_method: z.string().min(1, "Choose a payment method."),
  paid_on: z.string().min(1, "Choose the payment date."),
});

type ManualReceiptValues = z.infer<typeof manualReceiptSchema>;
const NO_PAYMENT_METHODS: string[] = [];

interface ManualReceiptsPageProps {
  user: User;
}

function formatAmount(amount: string, currency: string): string {
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(Number(amount));
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-NG", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value.slice(0, 10)}T00:00:00Z`));
}

function whatsappUrl(receipt: ManualPaymentReceipt): string | null {
  if (!receipt.payer_phone) return null;
  let number = receipt.payer_phone.replace(/\D/g, "");
  if (number.startsWith("0")) number = `234${number.slice(1)}`;
  if (number.length < 8 || number.length > 15) return null;
  const message = [
    `Hello ${receipt.payer_name},`,
    `${receipt.business_name} recorded your payment of ${formatAmount(receipt.amount, receipt.currency)}.`,
    `Receipt: ${receipt.receipt_number}.`,
    `For: ${receipt.purpose}.`,
    `Method: ${receipt.payment_method}.`,
    `Date: ${formatDate(receipt.paid_on)}.`,
    "This receipt documents a manual record and is not independent confirmation from a bank or payment provider.",
    "Thank you for your business.",
  ].join("\n");
  return `https://wa.me/${number}?text=${encodeURIComponent(message)}`;
}

export function ManualReceiptsPage({ user }: ManualReceiptsPageProps) {
  const queryClient = useQueryClient();
  const [selectedReceiptId, setSelectedReceiptId] = useState("");
  const [actionError, setActionError] = useState("");
  const receiptsQuery = useQuery({
    queryKey: ["manual-payment-receipts"],
    queryFn: api.manualPaymentReceipts,
  });
  const form = useForm<ManualReceiptValues>({
    resolver: zodResolver(manualReceiptSchema),
    defaultValues: {
      payer_name: "",
      payer_phone: "",
      purpose: "",
      amount: "",
      payment_method: "",
      paid_on: todayInBusinessTimezone(),
    },
  });
  const methods = receiptsQuery.data?.payment_methods ?? NO_PAYMENT_METHODS;
  const createMutation = useMutation({
    mutationFn: api.createManualPaymentReceipt,
    onSuccess: async (receipt) => {
      setSelectedReceiptId(receipt.id);
      form.reset({
        payer_name: "",
        payer_phone: "",
        purpose: "",
        amount: "",
        payment_method: receipt.payment_method,
        paid_on: todayInBusinessTimezone(),
      });
      await queryClient.invalidateQueries({ queryKey: ["manual-payment-receipts"] });
    },
  });

  useEffect(() => {
    if (methods.length > 0 && !form.getValues("payment_method")) {
      form.setValue("payment_method", methods[0], { shouldValidate: true });
    }
  }, [form, methods]);

  if (receiptsQuery.isPending) {
    return <div className="loading-panel"><LoaderCircle className="spin" size={20} /> Loading manual receipts…</div>;
  }
  if (receiptsQuery.isError) {
    return (
      <p className="form-alert" role="alert">
        {receiptsQuery.error instanceof ApiError
          ? receiptsQuery.error.message
          : "Unable to load manual receipts. Please try again."}
      </p>
    );
  }

  const receipts = receiptsQuery.data.receipts;
  const selectedReceipt = receipts.find((receipt) => receipt.id === selectedReceiptId) ?? receipts[0];
  const selectedWhatsAppUrl = selectedReceipt ? whatsappUrl(selectedReceipt) : null;
  const canCreate = hasPermission(user, "payments:create");

  const submit = form.handleSubmit((values) => {
    createMutation.mutate({
      ...values,
      payer_phone: values.payer_phone.trim() || null,
    });
  });

  const printReceipt = () => {
    const cleanup = () => {
      document.body.classList.remove("printing-manual-receipt");
      window.removeEventListener("afterprint", cleanup);
    };
    document.body.classList.add("printing-manual-receipt");
    window.addEventListener("afterprint", cleanup);
    window.setTimeout(() => window.print(), 0);
  };

  const downloadReceipt = async (receipt: ManualPaymentReceipt) => {
    setActionError("");
    try {
      await downloadReceiptPdf({
        businessName: receipt.business_name,
        receiptNumber: receipt.receipt_number,
        details: [
          { label: "Received from", value: receipt.payer_name },
          ...(receipt.payer_phone ? [{ label: "Phone", value: receipt.payer_phone }] : []),
          { label: "Amount received", value: formatAmount(receipt.amount, receipt.currency) },
          { label: "Payment for", value: receipt.purpose },
          { label: "Payment method", value: receipt.payment_method },
          { label: "Payment date", value: formatDate(receipt.paid_on) },
        ],
        disclaimer: "This documents a manually recorded payment and is not independently verified by a bank or payment provider.",
      });
    } catch (error) {
      setActionError(
        error instanceof Error
          ? `Unable to download the receipt PDF: ${error.message}`
          : "Unable to download the receipt PDF. Please try again.",
      );
    }
  };

  return (
    <div className="settings-page records-page manual-receipts-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">PAYMENTS</span>
          <h1>Manual receipts</h1>
          <p>Record a payment without linking it to an invoice, then download its PDF or prepare a WhatsApp message.</p>
        </div>
      </div>
      {actionError && <p className="form-alert" role="alert">{actionError}</p>}

      <div className="manual-receipts-layout">
        <div className="manual-receipts-entry">
          {canCreate && (
            <form className="settings-card manual-receipt-form" onSubmit={submit}>
              <div className="settings-card-heading">
                <span className="settings-heading-icon"><ReceiptText size={18} /></span>
                <div>
                  <h2>Record a payment</h2>
                  <p>This standalone receipt does not change invoice balances or financial reports.</p>
                </div>
              </div>
              <div className="settings-fields manual-receipt-fields">
                <label className="field">
                  <span>Payer name</span>
                  <input autoComplete="name" {...form.register("payer_name")} aria-invalid={Boolean(form.formState.errors.payer_name)} />
                  {form.formState.errors.payer_name && <small className="field-error">{form.formState.errors.payer_name.message}</small>}
                </label>
                <label className="field">
                  <span>Phone number <small>(optional, for WhatsApp)</small></span>
                  <input
                    autoComplete="tel"
                    placeholder="+2348012345678"
                    type="tel"
                    {...form.register("payer_phone")}
                    aria-invalid={Boolean(form.formState.errors.payer_phone)}
                  />
                  <small className="field-help">Include the country code to prepare a WhatsApp receipt message.</small>
                  {form.formState.errors.payer_phone && <small className="field-error">{form.formState.errors.payer_phone.message}</small>}
                </label>
                <label className="field">
                  <span>Payment purpose</span>
                  <input placeholder="e.g. Drinks and snacks" {...form.register("purpose")} aria-invalid={Boolean(form.formState.errors.purpose)} />
                  {form.formState.errors.purpose && <small className="field-error">{form.formState.errors.purpose.message}</small>}
                </label>
                <div className="manual-receipt-fields-row">
                  <label className="field">
                    <span>Amount ({receiptsQuery.data.currency})</span>
                    <input inputMode="decimal" placeholder="0.00" {...form.register("amount")} aria-invalid={Boolean(form.formState.errors.amount)} />
                    {form.formState.errors.amount && <small className="field-error">{form.formState.errors.amount.message}</small>}
                  </label>
                  <label className="field">
                    <span>Payment date</span>
                    <input type="date" {...form.register("paid_on")} aria-invalid={Boolean(form.formState.errors.paid_on)} />
                    {form.formState.errors.paid_on && <small className="field-error">{form.formState.errors.paid_on.message}</small>}
                  </label>
                </div>
                <label className="field">
                  <span>Payment method</span>
                  <select {...form.register("payment_method")} aria-invalid={Boolean(form.formState.errors.payment_method)}>
                    <option value="">Choose method</option>
                    {methods.map((method) => <option key={method} value={method}>{method}</option>)}
                  </select>
                  {form.formState.errors.payment_method && <small className="field-error">{form.formState.errors.payment_method.message}</small>}
                </label>
              </div>
              {createMutation.isError && (
                <p className="form-alert" role="alert">
                  {createMutation.error instanceof ApiError
                    ? createMutation.error.message
                    : "Unable to save this receipt. Please try again."}
                </p>
              )}
              {createMutation.isSuccess && <p className="success-alert" role="status">Receipt saved successfully.</p>}
              <div className="settings-card-footer">
                <span className="settings-hint">Only record payments you have actually received.</span>
                <button className="button button-primary" disabled={createMutation.isPending || methods.length === 0} type="submit">
                  {createMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <ReceiptText size={16} />}
                  Save receipt
                </button>
              </div>
              {methods.length === 0 && <p className="manual-receipt-no-methods">Add payment methods in Business settings first.</p>}
            </form>
          )}

          <section className="settings-card manual-receipt-history" aria-label="Recent manual receipts">
            <div className="settings-card-heading">
              <span className="settings-heading-icon"><ReceiptText size={18} /></span>
              <div>
                <h2>Recent receipts</h2>
                <p>Latest {receipts.length} standalone receipt records.</p>
              </div>
            </div>
            {receipts.length === 0 ? (
              <p className="empty-staff">No manual receipts recorded yet.</p>
            ) : (
              <div className="record-list">
                {receipts.map((receipt) => (
                  <button
                    className={`manual-receipt-history-row${receipt.id === selectedReceipt?.id ? " selected" : ""}`}
                    key={receipt.id}
                    onClick={() => setSelectedReceiptId(receipt.id)}
                    type="button"
                  >
                    <span className="record-details">
                      <strong>{receipt.payer_name}</strong>
                      <small>{receipt.receipt_number} · {formatDate(receipt.paid_on)}</small>
                    </span>
                    <strong className="record-amount">{formatAmount(receipt.amount, receipt.currency)}</strong>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>

        <section className="settings-card manual-receipt-preview" aria-label="Receipt preview">
          {selectedReceipt ? (
            <>
              <div className="manual-receipt-toolbar">
                <span className="eyebrow">RECEIPT PREVIEW</span>
                <div>
                  <button className="button button-primary" onClick={() => void downloadReceipt(selectedReceipt)} type="button">
                    <Download size={15} /> Download PDF
                  </button>
                  <button className="button button-secondary" onClick={printReceipt} type="button">
                    <Printer size={15} /> Print / Save PDF
                  </button>
                  {selectedWhatsAppUrl ? (
                    <a className="button button-primary" href={selectedWhatsAppUrl} rel="noreferrer" target="_blank">
                      <MessageCircle size={15} /> Prepare WhatsApp
                    </a>
                  ) : (
                    <span className="manual-receipt-no-phone">Add a valid payer phone to prepare WhatsApp.</span>
                  )}
                </div>
              </div>
              <article className="payment-receipt-print manual-receipt-paper">
                <header className="payment-receipt-header">
                  <span className="eyebrow">MJD SQUARE</span>
                  <h1>{selectedReceipt.business_name}</h1>
                  <p>Standalone payment receipt</p>
                  <strong>{selectedReceipt.receipt_number}</strong>
                </header>
                <dl className="payment-receipt-details">
                  <div><dt>Received from</dt><dd>{selectedReceipt.payer_name}</dd></div>
                  {selectedReceipt.payer_phone && <div><dt>Phone</dt><dd>{selectedReceipt.payer_phone}</dd></div>}
                  <div><dt>Amount received</dt><dd>{formatAmount(selectedReceipt.amount, selectedReceipt.currency)}</dd></div>
                  <div><dt>Payment for</dt><dd>{selectedReceipt.purpose}</dd></div>
                  <div><dt>Payment method</dt><dd>{selectedReceipt.payment_method}</dd></div>
                  <div><dt>Payment date</dt><dd>{formatDate(selectedReceipt.paid_on)}</dd></div>
                </dl>
                <p className="payment-receipt-verification">
                  This documents a manually recorded payment and is not independently verified by a bank or payment provider.
                </p>
                <p className="payment-receipt-thanks">Thank you for your business.</p>
              </article>
              <p className="manual-receipt-share-note">WhatsApp opens a message for you to review and send. It does not attach a PDF.</p>
            </>
          ) : (
            <div className="manual-receipt-preview-empty">
              <span className="settings-heading-icon"><ReceiptText size={18} /></span>
              <h2>Your receipt will appear here</h2>
              <p>Record a payment to preview and share its receipt.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
