import { describe, expect, it } from "vitest";
import { createReceiptPdf } from "./receiptPdf";

describe("createReceiptPdf", () => {
  it("creates a PDF with receipt details and printable currency text", async () => {
    const pdf = await createReceiptPdf({
      businessName: "MJD Square",
      receiptNumber: "RCP-123",
      details: [
        { label: "Received from", value: "Charles" },
        { label: "Amount received", value: "₦50,000.00" },
      ],
      disclaimer: "Manually recorded—not independently verified.",
    });

    expect(pdf.output()).toContain("%PDF-");
    expect(pdf.output()).toContain("RCP-123");
    expect(pdf.output()).toContain("NGN 50,000.00");
  });

  it("adds pages when long receipt details exceed a page", async () => {
    const pdf = await createReceiptPdf({
      businessName: "MJD Square",
      receiptNumber: "RCP-LONG",
      details: Array.from({ length: 40 }, (_, index) => ({
        label: `Detail ${index + 1}`,
        value: "A long receipt detail that needs space on the page.",
      })),
      disclaimer: "Manually recorded.",
    });

    expect(pdf.getNumberOfPages()).toBeGreaterThan(1);
  });
});
