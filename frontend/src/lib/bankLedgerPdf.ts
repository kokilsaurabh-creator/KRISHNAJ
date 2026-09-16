import logoFullRaw from "../assets/krishna-jewellers-logo-full.svg?raw";
import { TXN_TYPE_LABELS, type BankLedger } from "./api";
import { formatDisplayDate } from "./dates";
import { absoluteAmount, balanceMarker, formatAmount, formatBalance } from "./money";

/** Same PDF pipeline as ledgerPdf.ts — see that file for why pdfmake is
 * loaded on demand rather than bundled, and why the logo's metadata block
 * is stripped. Deliberately not shared code: the two documents' content
 * differs enough (bank identity vs. party identity, the closing-balance
 * caption) that a shared builder would need almost as many branches as
 * just writing it twice, for a one-screen feature. */
const LOGO_SVG = logoFullRaw.replace(/<metadata>[\s\S]*?<\/metadata>/, "");

type VfsCarrier = { pdfMake?: { vfs?: unknown }; vfs?: unknown; default?: VfsCarrier };

type PdfDoc = {
  download: (filename?: string) => void;
  open: () => void;
  getBlob: (cb: (blob: Blob) => void) => void;
  getBase64: (cb: (data: string) => void) => void;
};

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

export function buildBankLedgerDocDefinition(bankLedger: BankLedger) {
  const { bank } = bankLedger;

  const identity = [bank.account_number ? `A/C ${bank.account_number}` : null, bank.branch]
    .filter(Boolean)
    .join(", ");

  const period = `${formatDisplayDate(bankLedger.from_date)} to ${formatDisplayDate(bankLedger.to_date)}`;

  const header = ["Date", "Type", "Document", "Narration", "Debit", "Credit", "Balance"].map((text) => ({
    text,
    bold: true,
    fontSize: 9,
    margin: [0, 4, 0, 4] as [number, number, number, number],
  }));

  const openingRow = [
    { text: formatDisplayDate(bankLedger.from_date), fontSize: 9 },
    { text: "Opening balance", fontSize: 9, bold: true, colSpan: 3 },
    {},
    {},
    { text: "", fontSize: 9 },
    { text: "", fontSize: 9 },
    { text: formatBalance(bankLedger.opening), fontSize: 9, bold: true, alignment: "right" as const },
  ];

  const txnRows = bankLedger.rows.map((row) => [
    { text: formatDisplayDate(row.date), fontSize: 9 },
    { text: TXN_TYPE_LABELS[row.type], fontSize: 9 },
    { text: row.doc_no ?? "—", fontSize: 9 },
    { text: row.narration ?? "", fontSize: 9 },
    { text: row.debit === "0.00" ? "" : formatAmount(row.debit), fontSize: 9, alignment: "right" as const },
    { text: row.credit === "0.00" ? "" : formatAmount(row.credit), fontSize: 9, alignment: "right" as const },
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
    { text: formatAmount(bankLedger.total_debit), fontSize: 9, bold: true, alignment: "right" as const },
    { text: formatAmount(bankLedger.total_credit), fontSize: 9, bold: true, alignment: "right" as const },
    { text: "", fontSize: 9 },
  ];

  const body = [header, openingRow, ...(txnRows.length > 0 ? txnRows : [emptyRow]), totalsRow];

  const docDefinition = {
    pageSize: "A4",
    pageMargins: [32, 32, 32, 44] as [number, number, number, number],
    defaultStyle: { font: "Roboto", fontSize: 10, color: "#000000" },
    content: [
      { svg: LOGO_SVG, width: 168 },
      { text: "Bank ledger", fontSize: 11, margin: [0, 6, 0, 10] as [number, number, number, number] },

      {
        table: {
          widths: ["*", "auto"],
          body: [
            [
              {
                stack: [
                  { text: bank.name, bold: true, fontSize: 12 },
                  ...(identity ? [{ text: identity, fontSize: 9, margin: [0, 2, 0, 0] as [number, number, number, number] }] : []),
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
                text: `${formatAmount(absoluteAmount(bankLedger.closing))} ${balanceMarker(bankLedger.closing)}`,
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
        text: "Dr = balance in the bank.  Cr = account overdrawn.",
        fontSize: 8,
        margin: [0, 10, 0, 0] as [number, number, number, number],
      },
      {
        text: "Cancelled payments are excluded from this statement.",
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

export async function buildBankLedgerPdf(bankLedger: BankLedger) {
  const pdfMake = await loadPdfMake();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return pdfMake.createPdf(buildBankLedgerDocDefinition(bankLedger) as any);
}

export function bankLedgerPdfFilename(bankLedger: BankLedger): string {
  const safeName = bankLedger.bank.name.replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `bank-ledger-${safeName}-${bankLedger.from_date}-to-${bankLedger.to_date}.pdf`;
}

export async function downloadBankLedgerPdf(bankLedger: BankLedger): Promise<void> {
  const pdf = await buildBankLedgerPdf(bankLedger);
  pdf.download(bankLedgerPdfFilename(bankLedger));
}
