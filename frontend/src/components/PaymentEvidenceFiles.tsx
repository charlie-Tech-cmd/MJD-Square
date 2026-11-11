import { Trash2 } from "lucide-react";
import { useState } from "react";
import { ApiError, api } from "../lib/api";
import type { PaymentEvidence } from "../types";

interface PaymentEvidenceFilesProps {
  paymentId: string;
  receipts: PaymentEvidence[];
  accountPayment?: boolean;
  canUpload: boolean;
  canDownload: boolean;
  canDelete: boolean;
  onUploaded: () => void;
  onDeleted: () => void;
}

function formattedUploadDate(value: string): string {
  return new Intl.DateTimeFormat("en-NG", {
    dateStyle: "medium",
    timeZone: "Africa/Lagos",
  }).format(new Date(value));
}

export function PaymentEvidenceFiles({
  paymentId,
  receipts,
  accountPayment = false,
  canUpload,
  canDownload,
  canDelete,
  onUploaded,
  onDeleted,
}: PaymentEvidenceFilesProps) {
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [uploadError, setUploadError] = useState(false);

  const upload = async (file: File | undefined, input: HTMLInputElement) => {
    if (!file) return;
    setMessage("");
    setUploadError(false);
    if (file.size === 0) {
      setMessage("The selected file is empty.");
      setUploadError(true);
      input.value = "";
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setMessage("Choose a receipt that is 10 MB or smaller.");
      setUploadError(true);
      input.value = "";
      return;
    }
    setUploading(true);
    try {
      await api.uploadPaymentEvidence(paymentId, file, accountPayment);
      setMessage("Proof of payment saved.");
      onUploaded();
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "Unable to save this receipt.");
      setUploadError(true);
    } finally {
      setUploading(false);
      input.value = "";
    }
  };

  const remove = async (receipt: PaymentEvidence) => {
    if (!window.confirm(`Permanently remove ${receipt.filename}?`)) return;
    setMessage("");
    setUploadError(false);
    setDeletingId(receipt.id);
    try {
      await api.deletePaymentEvidence(receipt.id);
      setMessage("Receipt removed.");
      onDeleted();
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "Unable to remove this receipt.");
      setUploadError(true);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="payment-evidence">
      {canUpload && (
        <label className="payment-evidence-upload button button-secondary">
          {uploading ? "Uploading proof…" : "Attach proof"}
          <input
            accept="application/pdf,image/jpeg,image/png,image/webp"
            aria-label="Upload proof of payment (PDF or image, up to 10 MB)"
            disabled={uploading}
            onChange={(event) => void upload(event.currentTarget.files?.[0], event.currentTarget)}
            type="file"
          />
        </label>
      )}
      {receipts.length > 0 && (
        <ul className="payment-evidence-list" aria-label="Saved proof of payment">
          {receipts.map((receipt) => (
            <li key={receipt.id}>
              {canDownload ? (
                <a
                  href={api.paymentEvidenceDownloadPath(receipt.id)}
                  rel="noreferrer"
                  target="_blank"
                >
                  {receipt.filename}
                </a>
              ) : (
                <span>{receipt.filename}</span>
              )}
              <small>{formattedUploadDate(receipt.uploaded_at)}</small>
              {canDelete && (
                <button
                  aria-label={`Remove ${receipt.filename}`}
                  className="button button-secondary payment-evidence-delete"
                  disabled={deletingId !== null}
                  onClick={() => void remove(receipt)}
                  type="button"
                >
                  {deletingId === receipt.id ? "Removing…" : <Trash2 size={15} />}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {message && (
        <small className={uploadError ? "payment-evidence-error" : "payment-evidence-success"} role={uploadError ? "alert" : "status"}>
          {message}
        </small>
      )}
    </div>
  );
}
