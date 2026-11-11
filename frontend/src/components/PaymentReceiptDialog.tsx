import { Download, MessageCircle, Printer, Share2, X } from "lucide-react";
import { useState } from "react";
import { formatNaira } from "../lib/format";

export interface PaymentReceiptDetails {
  receiptNumber: string;
  invoiceNumber: string;
  customerName: string;
  customerPhone: string | null;
  whatsappReceiptStatus: string | null;
  amount: string;
  method: string;
  reference: string | null;
  receivedAt: string;
  invoiceTotal: string;
  balanceDue: string;
}

interface PaymentReceiptDialogProps {
  receipt: PaymentReceiptDetails;
  businessName: string;
  onClose: () => void;
}

function formattedTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en-NG", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Africa/Lagos",
  }).format(new Date(value));
}

function whatsappUrl(receipt: PaymentReceiptDetails, businessName: string): string | null {
  if (!receipt.customerPhone) return null;
  let number = receipt.customerPhone.replace(/\D/g, "");
  if (number.startsWith("0")) number = `234${number.slice(1)}`;
  if (number.length < 8 || number.length > 15) return null;
  const message = [
    `Hello ${receipt.customerName},`,
    `${businessName} recorded your payment of ${formatNaira(receipt.amount)}.`,
    `Receipt: ${receipt.receiptNumber}.`,
    `Invoice: ${receipt.invoiceNumber}.`,
    `Method: ${receipt.method}.`,
    `Date: ${formattedTimestamp(receipt.receivedAt)}.`,
    `Remaining invoice balance: ${formatNaira(receipt.balanceDue)}.`,
    "This receipt documents a manual record and is not independent confirmation from a bank or payment provider.",
  ].join("\n");
  return `https://wa.me/${number}?text=${encodeURIComponent(message)}`;
}

function whatsappStatusText(status: string): string {
  const messages: Record<string, string> = {
    not_opted_in: "Not sent: customer has not opted in to WhatsApp receipts.",
    no_number: "Not sent: no WhatsApp number is recorded.",
    invalid_number: "Not sent: the recorded WhatsApp number is invalid.",
    not_configured: "Not sent: WhatsApp delivery is not configured.",
    pending: "WhatsApp receipt is pending.",
    accepted: "WhatsApp accepted the receipt; delivery is not yet confirmed.",
    sent: "WhatsApp sent the receipt; delivery is not yet confirmed.",
    delivered: "WhatsApp delivered the receipt.",
    read: "WhatsApp reports that the customer read the receipt.",
    failed: "WhatsApp receipt delivery failed. The payment remains recorded.",
  };
  return messages[status] ?? "WhatsApp receipt status is unavailable.";
}

export function PaymentReceiptDialog({
  receipt,
  businessName,
  onClose,
}: PaymentReceiptDialogProps) {
  const [shareError, setShareError] = useState("");
  const waLink = whatsappUrl(receipt, businessName);
  const receiptText = [
    `${businessName} payment receipt ${receipt.receiptNumber}`,
    `Customer: ${receipt.customerName}`,
    `Amount received: ${formatNaira(receipt.amount)}`,
    `Method: ${receipt.method}`,
    `Date: ${formattedTimestamp(receipt.receivedAt)}`,
    `Invoice: ${receipt.invoiceNumber}`,
    `Invoice total: ${formatNaira(receipt.invoiceTotal)}`,
    `Remaining balance: ${formatNaira(receipt.balanceDue)}`,
    "Manually recorded—not independently verified by a bank or payment provider.",
  ].join("\n");

  const printReceipt = () => {
    setShareError("");
    const cleanup = () => {
      document.body.classList.remove("printing-receipt");
      window.removeEventListener("afterprint", cleanup);
    };
    document.body.classList.add("printing-receipt");
    window.addEventListener("afterprint", cleanup);
    window.setTimeout(() => window.print(), 0);
  };

  const shareReceipt = async () => {
    setShareError("");
    if (!navigator.share) {
      setShareError("Device sharing is not available in this browser. Use Print / Save PDF or WhatsApp.");
      return;
    }
    try {
      await navigator.share({ title: `Receipt ${receipt.receiptNumber}`, text: receiptText });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setShareError("Unable to open device sharing. You can still print the receipt or use WhatsApp.");
    }
  };

  return (
    <div
      className="receipt-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        aria-labelledby="payment-receipt-title"
        aria-modal="true"
        className="receipt-dialog"
        role="dialog"
      >
        <div className="receipt-dialog-toolbar">
          <div>
            <span className="eyebrow">PAYMENT RECEIPT</span>
            <h2 id="payment-receipt-title">Receipt {receipt.receiptNumber}</h2>
          </div>
          <button aria-label="Close receipt" className="icon-button" onClick={onClose} type="button">
            <X size={18} />
          </button>
        </div>

        <article className="payment-receipt-print">
          <header className="payment-receipt-header">
            <span className="eyebrow">MJD SQUARE</span>
            <h1>{businessName}</h1>
            <p>Payment receipt</p>
            <strong>{receipt.receiptNumber}</strong>
          </header>
          <dl className="payment-receipt-details">
            <div><dt>Received from</dt><dd>{receipt.customerName}</dd></div>
            <div><dt>Amount received</dt><dd>{formatNaira(receipt.amount)}</dd></div>
            <div><dt>Payment method</dt><dd>{receipt.method}</dd></div>
            <div><dt>Payment date</dt><dd>{formattedTimestamp(receipt.receivedAt)}</dd></div>
            {receipt.reference && <div><dt>Transaction reference</dt><dd>{receipt.reference}</dd></div>}
            <div><dt>Invoice</dt><dd>{receipt.invoiceNumber}</dd></div>
            <div><dt>Invoice total</dt><dd>{formatNaira(receipt.invoiceTotal)}</dd></div>
            <div><dt>Balance remaining</dt><dd>{formatNaira(receipt.balanceDue)}</dd></div>
          </dl>
          <p className="payment-receipt-verification">
            Manually recorded—not independently verified by a bank or payment provider.
          </p>
          <p className="payment-receipt-thanks">Thank you for your business.</p>
        </article>

        {shareError && <p className="form-alert" role="alert">{shareError}</p>}
        {receipt.whatsappReceiptStatus && (
          <p aria-live="polite" className="payment-receipt-verification" role="status">
            {whatsappStatusText(receipt.whatsappReceiptStatus)}
          </p>
        )}
        <div className="receipt-dialog-actions">
          <button className="button button-secondary" onClick={printReceipt} type="button">
            <Printer size={15} /> Print / Save PDF
          </button>
          <button className="button button-secondary" onClick={() => void shareReceipt()} type="button">
            <Share2 size={15} /> Share
          </button>
          {waLink ? (
            <a className="button button-primary" href={waLink} rel="noreferrer" target="_blank">
              <MessageCircle size={15} /> Prepare WhatsApp
            </a>
          ) : (
            <span className="receipt-share-hint">
              <Download size={14} /> No valid customer phone number for WhatsApp.
            </span>
          )}
        </div>
        <p className="receipt-dialog-note">
          WhatsApp delivery status does not independently verify settlement. Use the prepared-message option if automatic delivery was unavailable.
        </p>
      </section>
    </div>
  );
}
