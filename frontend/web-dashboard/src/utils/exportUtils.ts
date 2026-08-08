const EXCLUDE_KEYS = new Set([
  'id', 'deletedAt', 'created_by', 'updated_by', 'deleted_by', 
  'version', 'password_hash', 'userId', 'driverId', 'vehicleId', 
  'customerId', 'tripId', 'isActive'
]);

function formatHeaderLabel(key: string): string {
  const map: Record<string, string> = {
    ref_id: 'Job / Ref ID',
    first_name: 'First Name',
    last_name: 'Last Name',
    phone_primary: 'Primary Phone',
    contact_phone: 'Contact Phone',
    plate_number: 'Plate Number',
    capacity_kg: 'Capacity (KG)',
    asset_type: 'Vehicle Type',
    ai_risk_score: 'AI Safety Risk Score',
    credit_limit: 'Credit Limit (SAR)',
    total_amount: 'Total Amount (SAR)',
    subtotal: 'Subtotal (SAR)',
    billing_amount: 'Billing Amount (SAR)',
    waiting_labor_charges: 'Waiting / Labor Charges (SAR)',
    additional_stop_charges: 'Additional Stop Charges (SAR)',
    trip_charges: 'Trip Charges (SAR)',
    balance_amount: 'Net Balance (SAR)',
    carrier_name: 'Carrier / Provider',
    createdAt: 'Created Date',
    updatedAt: 'Updated Date',
    actual_start: 'Start Date',
    actual_end: 'End Date',
    planned_start: 'Planned Start',
    planned_end: 'Planned End',
    due_date: 'Due Date',
    issue_date: 'Issue Date',
    expiry_date: 'Expiry Date',
    status: 'Status',
    cargo_type: 'Cargo Type',
    cost: 'Maintenance Cost (SAR)',
    service_date: 'Service Date',
    odometer_reading: 'Odometer Reading (KM)',
    workshop_name: 'Workshop Name',
  };

  if (map[key]) return map[key];
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
}

function extractValue(val: any): string {
  if (val === null || val === undefined) return '';
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  if (typeof val === 'number') return String(val);
  
  if (typeof val === 'object') {
    if (Array.isArray(val)) {
      return val.map((item) => extractValue(item)).filter(Boolean).join('; ');
    }
    // Unwrap nested relational objects nicely
    if (val.name) return String(val.name);
    if (val.first_name || val.last_name) {
      return `${val.first_name || ''} ${val.last_name || ''}`.trim();
    }
    if (val.plate_number) return String(val.plate_number);
    if (val.ref_id) return String(val.ref_id);
    if (val.company_name) return String(val.company_name);
    if (val.username) return String(val.username);
    if (val.title) return String(val.title);
    return '';
  }

  // Format ISO Dates
  if (typeof val === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(val)) {
    try {
      const d = new Date(val);
      if (!isNaN(d.getTime())) {
        return d.toISOString().slice(0, 10);
      }
    } catch (e) {
      // fallback
    }
  }

  return String(val);
}

export function downloadCSV<T extends Record<string, any>>(data: T[], filename: string = 'mercon_export.csv') {
  if (!data || !data.length) {
    return;
  }

  // Filter raw keys to exclude internal system fields unless specifically mapped
  const rawKeys = Object.keys(data[0]).filter(k => !EXCLUDE_KEYS.has(k));
  const headers = rawKeys.map(formatHeaderLabel);

  const csvRows: string[] = [];
  
  // Add header row
  csvRows.push(headers.join(','));

  // Add data rows
  for (const row of data) {
    const values = rawKeys.map(key => {
      let val = extractValue(row[key]);
      val = val.replace(/"/g, '""'); // Escape double quotes for CSV
      if (/[",\n]/.test(val)) {
        val = `"${val}"`;
      }
      return val;
    });
    csvRows.push(values.join(','));
  }

  const csvString = csvRows.join('\n');
  const blob = new Blob(['\uFEFF' + csvString], { type: 'text/csv;charset=utf-8;' }); // UTF-8 BOM for Excel compatibility
  
  const link = document.createElement('a');
  if (link.download !== undefined) {
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}

export function downloadExcel(title: string, headers: string[], rows: any[][], filename: string = 'mercon_export.xls') {
  let html = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">`;
  html += `<head><meta charset="utf-8" />`;
  html += `<!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>${title.slice(0,30).replace(/[\\*?:/[\]]/g, '')}</x:Name><x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->`;
  html += `<style>
    body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
    table { border-collapse: collapse; width: 100%; margin-top: 10px; }
    th { background-color: #4F46E5; color: #FFFFFF; font-weight: bold; text-align: center; border: 0.5pt solid #CBD5E1; padding: 10px 14px; font-size: 11px; }
    td { border: 0.5pt solid #E2E8F0; padding: 8px 12px; font-size: 10px; color: #334155; }
    .title-row { font-size: 16px; font-weight: bold; color: #1E293B; height: 35px; border: none; }
    .subtitle-row { font-size: 11px; color: #64748B; height: 20px; border: none; padding-bottom: 10px; }
    .even { background-color: #F8FAFC; }
    .odd { background-color: #FFFFFF; }
    .total-row td { font-weight: bold; background-color: #F1F5F9; border-top: 1pt solid #475569; border-bottom: 2.5pt double #475569; color: #0F172A; }
    .text { mso-number-format: "\\@"; text-align: left; }
    .number { mso-number-format: "#,##0"; text-align: right; }
    .decimal { mso-number-format: "#,##0.00"; text-align: right; }
    .currency { mso-number-format: "[$SAR ]#,##0.00"; text-align: right; }
    .date { mso-number-format: "YYYY-MM-DD"; text-align: center; }
    .status-active { background-color: #DCFCE7; color: #166534; font-weight: bold; text-align: center; }
    .status-inactive { background-color: #FEE2E2; color: #991B1B; font-weight: bold; text-align: center; }
    .charges-cell { color: #DC2626; font-weight: bold; text-align: right; mso-number-format: "[$SAR ]#,##0.00"; }
    .balance-cell { color: #4F46E5; font-weight: bold; text-align: right; mso-number-format: "[$SAR ]#,##0.00"; }
  </style></head><body>`;
  
  html += `<table>`;
  // Title Row
  html += `<tr><td colspan="${headers.length}" class="title-row" style="border:none;">${title}</td></tr>`;
  html += `<tr><td colspan="${headers.length}" class="subtitle-row" style="border:none;">Generated on ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString()} | MERCON Logistics Platform</td></tr>`;
  html += `<tr><td colspan="${headers.length}" style="border:none; height: 10px;"></td></tr>`; // Spacing row

  // Headers Row
  html += `<tr>`;
  headers.forEach(h => {
    html += `<th>${h}</th>`;
  });
  html += `</tr>`;

  // Data Rows
  rows.forEach((row, rIdx) => {
    const isTotalRow = row[0] === 'TOTALS' || row[0] === 'Total' || row[0] === 'Totals';
    const rowClass = isTotalRow ? 'total-row' : (rIdx % 2 === 0 ? 'even' : 'odd');
    
    html += `<tr class="${rowClass}">`;
    row.forEach((cell, cIdx) => {
      let cellClass = 'text';
      const headerLower = headers[cIdx]?.toLowerCase() || '';

      if (isTotalRow) {
        if (typeof cell === 'number') {
          cellClass = (headerLower.includes('charges') || headerLower.includes('amount') || headerLower.includes('billing') || headerLower.includes('revenue') || headerLower.includes('cost') || headerLower.includes('total') || headerLower.includes('balance')) 
            ? 'currency' 
            : 'number';
        }
      } else {
        if (typeof cell === 'number') {
          if (headerLower.includes('charges') || headerLower.includes('amount') || headerLower.includes('billing') || headerLower.includes('revenue') || headerLower.includes('cost') || headerLower.includes('total') || headerLower.includes('balance')) {
            cellClass = 'currency';
            if (headerLower.includes('trip charges') || headerLower.includes('maintenance cost')) {
              cellClass = 'charges-cell';
            } else if (headerLower.includes('balance amount') || headerLower.includes('net balance')) {
              cellClass = 'balance-cell';
            }
          } else if (headerLower.includes('odometer') || headerLower.includes('capacity') || headerLower.includes('trips')) {
            cellClass = 'number';
          } else {
            cellClass = 'number';
          }
        } else if (typeof cell === 'string') {
          // Date format detection
          if (/^\d{4}-\d{2}-\d{2}$/.test(cell) || /^\d{2}-\d{2}-\d{4}$/.test(cell)) {
            cellClass = 'date';
          } else if (headerLower.includes('status')) {
            if (cell.toLowerCase().includes('active') || cell.toLowerCase().includes('completed') || cell.toLowerCase().includes('delivered') || cell.toLowerCase().includes('paid')) {
              cellClass = 'status-active';
            } else if (cell.toLowerCase().includes('inactive') || cell.toLowerCase().includes('cancelled') || cell.toLowerCase().includes('overdue')) {
              cellClass = 'status-inactive';
            } else {
              cellClass = 'center';
            }
          }
        }
      }

      html += `<td class="${cellClass}">${cell !== null && cell !== undefined ? cell : ''}</td>`;
    });
    html += `</tr>`;
  });

  html += `</table></body></html>`;

  const blob = new Blob([html], { type: 'application/vnd.ms-excel;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/** Opens a print-formatted HTML table in a new tab so the user can "Save as PDF"
 *  from the browser's print dialog — same no-dependency approach already used
 *  for the per-invoice Print/PDF action, applied here to a whole table. */
export function downloadPDF<T extends Record<string, any>>(data: T[], title: string = 'MERCON Export') {
  if (!data || !data.length) {
    return;
  }

  const rawKeys = Object.keys(data[0]).filter(k => !EXCLUDE_KEYS.has(k));
  const headers = rawKeys.map(formatHeaderLabel);

  let html = `<!doctype html><html><head><meta charset="utf-8" /><title>${title}</title>`;
  html += `<style>
    body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; margin: 24px; color: #1E293B; }
    h1 { font-size: 16px; margin: 0 0 4px; }
    p.subtitle { font-size: 11px; color: #64748B; margin: 0 0 16px; }
    table { border-collapse: collapse; width: 100%; }
    th { background-color: #E8450F; color: #FFFFFF; font-weight: bold; text-align: left; border: 0.5pt solid #CBD5E1; padding: 6px 10px; font-size: 10px; }
    td { border: 0.5pt solid #E2E8F0; padding: 6px 10px; font-size: 10px; color: #334155; }
    tr:nth-child(even) td { background-color: #F8FAFC; }
    @media print { body { margin: 0.5cm; } }
  </style></head><body>`;
  html += `<h1>${title}</h1>`;
  html += `<p class="subtitle">Generated on ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString()} · MERCON Logistics Platform · ${data.length} record${data.length === 1 ? '' : 's'}</p>`;

  html += `<table><thead><tr>`;
  headers.forEach(h => { html += `<th>${h}</th>`; });
  html += `</tr></thead><tbody>`;

  for (const row of data) {
    html += `<tr>`;
    rawKeys.forEach(key => {
      const val = extractValue(row[key]);
      html += `<td>${val.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</td>`;
    });
    html += `</tr>`;
  }

  html += `</tbody></table></body></html>`;

  const win = window.open('', '_blank');
  if (!win) return;
  win.document.open();
  win.document.write(html);
  win.document.close();
  win.focus();
  win.onload = () => win.print();
}

export const exportToCSV = downloadCSV;

