import type { jsPDF } from "jspdf";

export interface ReceiptPdfDetail {
  label: string;
  value: string;
}

export interface ReceiptPdfOptions {
  businessName: string;
  receiptNumber: string;
  details: ReceiptPdfDetail[];
  disclaimer: string;
}

function pdfText(value: string): string {
  return value
    .replaceAll("₦", "NGN ")
    .replaceAll("—", "-")
    .replaceAll("–", "-")
    .replaceAll("·", "|");
}

function safeFilename(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-|-$/g, "") || "receipt";
}

export async function createReceiptPdf(options: ReceiptPdfOptions): Promise<jsPDF> {
  const { jsPDF: JsPDF } = await import("jspdf");
  const document = new JsPDF({ format: "a4", unit: "mm" });
  const pageWidth = document.internal.pageSize.getWidth();
  const margin = 20;
  const contentWidth = pageWidth - margin * 2;
  let y = 24;

  document.setFont("helvetica", "bold");
  document.setFontSize(10);
  document.setTextColor(22, 126, 109);
  document.text("MJD SQUARE", margin, y);

  y += 12;
  document.setFontSize(20);
  document.setTextColor(31, 48, 69);
  document.text(pdfText(options.businessName), margin, y, { maxWidth: contentWidth });

  y += 9;
  document.setFont("helvetica", "normal");
  document.setFontSize(11);
  document.setTextColor(92, 107, 124);
  document.text("Payment receipt", margin, y);

  y += 8;
  document.setFont("helvetica", "bold");
  document.setFontSize(12);
  document.setTextColor(31, 48, 69);
  document.text(pdfText(options.receiptNumber), margin, y, { maxWidth: contentWidth });

  y += 7;
  document.setDrawColor(225, 232, 238);
  document.line(margin, y, pageWidth - margin, y);
  y += 10;

  const labelWidth = 48;
  const valueX = margin + labelWidth;
  const valueWidth = contentWidth - labelWidth;
  document.setFontSize(10);

  for (const detail of options.details) {
    const lines = document.splitTextToSize(pdfText(detail.value), valueWidth) as string[];
    const rowHeight = Math.max(7, lines.length * 5);
    if (y + rowHeight > 260) {
      document.addPage();
      y = 24;
    }

    document.setFont("helvetica", "normal");
    document.setTextColor(92, 107, 124);
    document.text(pdfText(detail.label), margin, y);
    document.setFont("helvetica", "bold");
    document.setTextColor(31, 48, 69);
    document.text(lines, valueX, y);
    y += rowHeight + 3;
  }

  y += 4;
  const disclaimerLines = document.splitTextToSize(
    pdfText(options.disclaimer),
    contentWidth,
  ) as string[];
  const disclaimerHeight = disclaimerLines.length * 5 + 6;
  if (y + disclaimerHeight + 12 > 277) {
    document.addPage();
    y = 24;
  }
  document.setDrawColor(225, 232, 238);
  document.line(margin, y, pageWidth - margin, y);
  y += 9;
  document.setFont("helvetica", "normal");
  document.setFontSize(9);
  document.setTextColor(92, 107, 124);
  document.text(disclaimerLines, margin, y);
  y += disclaimerHeight;
  document.setFont("helvetica", "bold");
  document.setTextColor(22, 126, 109);
  document.text("Thank you for your business.", margin, y);

  return document;
}

export async function downloadReceiptPdf(options: ReceiptPdfOptions): Promise<void> {
  const document = await createReceiptPdf(options);
  document.save(`${safeFilename(options.receiptNumber)}.pdf`);
}
