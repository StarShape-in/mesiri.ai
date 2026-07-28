// Shared CSV export helper. Several pages (FinanceReportsPage, LabourReportsPage,
// AttendancePage, WorkersPage, PettyCashPage) each hand-rolled the same
// `data:text/csv;charset=utf-8,` + encodeURI + anchor-click idiom. That approach
// has two real limits a Blob download doesn't: encodeURI leaves `#` unescaped
// (truncates the file at the first `#` in any field), and browsers cap
// data-URI downloads around a few MB -- both become real problems once
// exports grow past a handful of rows. This is the one place to fix it.

/** Escapes a single CSV field: wraps in quotes and doubles any embedded quotes
 * whenever the value contains a comma, quote, or newline. */
function escapeCsvField(value: unknown): string {
  const str = value === null || value === undefined ? '' : String(value)
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

/** Builds a CSV string (with header row) from column headers and row objects. */
export function toCsv(headers: string[], rows: (string | number | null | undefined)[][]): string {
  const lines = [headers.map(escapeCsvField).join(',')]
  for (const row of rows) {
    lines.push(row.map(escapeCsvField).join(','))
  }
  // CRLF is the CSV-spec line ending and what Excel expects without a BOM dance.
  return lines.join('\r\n')
}

/** Triggers a browser download of `content` as a file named `filename`, via a
 * Blob + object URL rather than a data: URI (see module docstring for why). */
export function downloadTextFile(filename: string, content: string, mimeType = 'text/csv;charset=utf-8'): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/** Convenience wrapper: builds CSV from headers/rows and downloads it. */
export function exportCsv(filename: string, headers: string[], rows: (string | number | null | undefined)[][]): void {
  downloadTextFile(filename, toCsv(headers, rows))
}

/** Triggers a browser download of a Blob (e.g. a PDF fetched from the backend)
 * under `filename`. */
export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
