import { TXN_TYPE_LABELS, type Ledger } from "./api";
import { formatDisplayDate } from "./dates";
import { absoluteAmount, balanceMarker, formatAmount, formatBalance } from "./money";

/**
 * pdfmake plus its embedded Roboto set is ~2.5 MB — most of the app's
 * weight, for a feature a phone user may never touch. It's loaded on
 * demand instead of shipped in the initial bundle, so opening the ledger
 * on a patchy connection doesn't pay for the export button.
 */
type VfsCarrier = { pdfMake?: { vfs?: unknown }; vfs?: unknown; default?: VfsCarrier };

type PdfDoc = {
  download: (filename?: string) => void;
  open: () => void;
  getBlob: (cb: (blob: Blob) => void) => void;
  getBase64: (cb: (data: string) => void) => void;
};

/** The font table has sat in a different place in almost every pdfmake
 * release (module.vfs, module.pdfMake.vfs, a global side effect, or — as
 * in the current build — the module namespace *being* the map itself),
 * and the CJS→ESM interop adds another layer. So rather than guess a
 * path, look for the object that actually holds .ttf entries.
 *
 * Worth being strict here: with no fonts, createPdf hangs forever instead
 * of throwing, which is a miserable thing to debug from a stuck button. */
function looksLikeVfs(value: unknown): value is Record<string, string> {
  return (
    typeof value === "object" &&
    value !== null &&
    Object.keys(value).some((key) => key.toLowerCase().endsWith(".ttf"))
  );
}

function extractVfs(mod: VfsCarrier): Record<string, string> | undefined {
  const candidates = [
    mod?.vfs,
    mod?.pdfMake?.vfs,
    mod?.default?.vfs,
    mod?.default?.pdfMake?.vfs,
    mod?.default,
    mod,
    (globalThis as { pdfMake?: { vfs?: unknown } }).pdfMake?.vfs,
  ];
  return candidates.find(looksLikeVfs);
}

async function loadPdfMake() {
  const [pdfMakeMod, fontsMod] = await Promise.all([
    import("pdfmake/build/pdfmake"),
    import("pdfmake/build/vfs_fonts"),
  ]);

  const pdfMake = ((pdfMakeMod as { default?: unknown }).default ?? pdfMakeMod) as {
    vfs: unknown;
    createPdf: (doc: unknown) => PdfDoc;
  };

  const vfs = extractVfs(fontsMod as VfsCarrier);
  if (!vfs) throw new Error("pdfmake font table could not be located");
  pdfMake.vfs = vfs;

  return pdfMake;
}

/**
 * Printed on a cheap mono laser printer, so nothing here may depend on
 * colour to carry meaning: direction is shown with Dr/Cr markers and
 * column placement, weight is used for emphasis, and the only greys are
 * hairline rules. Every figure is formatted through the same helpers the
 * screen uses, so the two cannot disagree.
 */
export function buildLedgerDocDefinition(ledger: Ledger) {
  const { party } = ledger;

  const address = [party.address_line, party.city, party.state, party.pincode]
    .filter(Boolean)
    .join(", ");

  const period = `${formatDisplayDate(ledger.from_date)} to ${formatDisplayDate(ledger.to_date)}`;

  const header = ["Date", "Type", "Document", "Narration", "Debit", "Credit", "Balance"].map((text) => ({
    text,
    bold: true,
    fontSize: 9,
    margin: [0, 4, 0, 4] as [number, number, number, number],
  }));

  const openingRow = [
    { text: formatDisplayDate(ledger.from_date), fontSize: 9 },
    { text: "Opening balance", fontSize: 9, bold: true, colSpan: 3 },
    {},
    {},
    { text: "", fontSize: 9 },
    { text: "", fontSize: 9 },
    { text: formatBalance(ledger.opening), fontSize: 9, bold: true, alignment: "right" as const },
  ];

  const txnRows = ledger.rows.map((row) => [
    { text: formatDisplayDate(row.date), fontSize: 9 },
    { text: TXN_TYPE_LABELS[row.type], fontSize: 9 },
    { text: row.doc_no ?? "—", fontSize: 9 },
    { text: row.narration ?? "", fontSize: 9 },
    {
      text: row.debit === "0.00" ? "" : formatAmount(row.debit),
      fontSize: 9,
      alignment: "right" as const,
    },
    {
      text: row.credit === "0.00" ? "" : formatAmount(row.credit),
      fontSize: 9,
      alignment: "right" as const,
    },
    { text: formatBalance(row.balance), fontSize: 9, alignment: "right" as const },
  ]);

  const emptyRow = [
    {
      text: "No transactions in this period.",
      fontSize: 9,
      italics: true,
      colSpan: 7,
      alignment: "center" as const,
      margin: [0, 8, 0, 8] as [number, number, number, number],
    },
    {},
    {},
    {},
    {},
    {},
    {},
  ];

  const totalsRow = [
    { text: "Totals for period", fontSize: 9, bold: true, colSpan: 4 },
    {},
    {},
    {},
    { text: formatAmount(ledger.total_debit), fontSize: 9, bold: true, alignment: "right" as const },
    { text: formatAmount(ledger.total_credit), fontSize: 9, bold: true, alignment: "right" as const },
    { text: "", fontSize: 9 },
  ];

  const body = [header, openingRow, ...(txnRows.length > 0 ? txnRows : [emptyRow]), totalsRow];

  const docDefinition = {
    pageSize: "A4",
    pageMargins: [32, 32, 32, 44] as [number, number, number, number],
    defaultStyle: { font: "Roboto", fontSize: 10, color: "#000000" },
    content: [
      { text: "Krishna Jewellers", fontSize: 16, bold: true },
      { text: "Party ledger", fontSize: 11, margin: [0, 2, 0, 10] as [number, number, number, number] },

      {
        table: {
          widths: ["*", "auto"],
          body: [
            [
              {
                stack: [
                  { text: party.name, bold: true, fontSize: 12 },
                  ...(address ? [{ text: address, fontSize: 9, margin: [0, 2, 0, 0] as [number, number, number, number] }] : []),
                  ...(party.phone ? [{ text: `Phone: ${party.phone}`, fontSize: 9 }] : []),
                ],
                border: [false, false, false, false],
              },
              {
                stack: [
                  { text: `Period: ${period}`, fontSize: 9, alignment: "right" as const },
                  {
                    text: `Generated on: ${formatDisplayDate(new Date().toISOString().slice(0, 10))}`,
                    fontSize: 9,
                    alignment: "right" as const,
                  },
                ],
                border: [false, false, false, false],
              },
            ],
          ],
        },
        layout: "noBorders",
        margin: [0, 0, 0, 12] as [number, number, number, number],
      },

      {
        table: {
          widths: ["auto", "auto", "auto", "*", "auto", "auto", "auto"],
          headerRows: 1,
          body,
        },
        layout: {
          hLineWidth: (i: number, node: { table: { body: unknown[] } }) =>
            i === 0 || i === 1 || i === node.table.body.length - 1 || i === node.table.body.length ? 1 : 0.5,
          vLineWidth: () => 0,
          hLineColor: (i: number) => (i === 1 ? "#000000" : "#BBBBBB"),
          paddingTop: () => 4,
          paddingBottom: () => 4,
        },
      },

      {
        table: {
          widths: ["*", "auto"],
          body: [
            [
              { text: "Closing balance", bold: true, fontSize: 12, border: [false, false, false, false] },
              {
                text: `${formatAmount(absoluteAmount(ledger.closing))} ${balanceMarker(ledger.closing)}`,
                bold: true,
                fontSize: 12,
                alignment: "right" as const,
                border: [false, false, false, false],
              },
            ],
          ],
        },
        layout: "noBorders",
        margin: [0, 12, 0, 0] as [number, number, number, number],
      },

      {
        text: "Dr = receivable (party owes us).  Cr = payable (we owe party).",
        fontSize: 8,
        margin: [0, 10, 0, 0] as [number, number, number, number],
      },
      {
        text: "Cancelled documents are excluded from this statement.",
        fontSize: 8,
        margin: [0, 2, 0, 0] as [number, number, number, number],
      },
    ],
    footer: (currentPage: number, pageCount: number) => ({
      text: `Page ${currentPage} of ${pageCount}`,
      fontSize: 8,
      alignment: "center" as const,
      margin: [0, 12, 0, 0] as [number, number, number, number],
    }),
  };

  return docDefinition;
}

/** The document definition is the PDF's entire content, so the same figures
 * can be asserted against the API response without rendering the binary. */
export async function buildLedgerPdf(ledger: Ledger) {
  const pdfMake = await loadPdfMake();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return pdfMake.createPdf(buildLedgerDocDefinition(ledger) as any);
}

export function ledgerPdfFilename(ledger: Ledger): string {
  const safeName = ledger.party.name.replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `ledger-${safeName}-${ledger.from_date}-to-${ledger.to_date}.pdf`;
}

export async function downloadLedgerPdf(ledger: Ledger): Promise<void> {
  const pdf = await buildLedgerPdf(ledger);
  pdf.download(ledgerPdfFilename(ledger));
}
