/**
 * Sequential, zero-padded reference ID generator (e.g. "TRP-0001", "INV-0001", "DRV-0001", "TRK-0001").
 *
 * Fills numerical gaps starting from 1 (e.g., if TRP-0211 was deleted, 0211 is freed
 * and will be generated if 0210 is the preceding record).
 */

export interface RefIdOptions {
  /** Format number with zero padding, e.g. 4 digits ("0001"). Default 4. */
  padLength?: number;
  /** Include the current year, e.g. "INV-2026-0001". Default false. */
  year?: boolean;
}

/**
 * Generate a sequential reference ID for the given prefix.
 * `getAllRefIds` should fetch active records select { ref_id: true }.
 */
export async function generateSequentialRefId(
  prefix: string,
  getAllRefIds: () => Promise<{ ref_id: string | null }[]>,
  opts: RefIdOptions = {},
): Promise<string> {
  const { padLength = 4, year = false } = opts;
  const yearPart = year ? `${new Date().getFullYear()}-` : '';
  const fullPrefix = `${prefix}-${yearPart}`;

  const records = await getAllRefIds();
  const existingNumbers = new Set<number>();

  for (const record of records) {
    if (!record.ref_id || !record.ref_id.startsWith(fullPrefix)) continue;
    const numPart = record.ref_id.slice(fullPrefix.length);
    const num = parseInt(numPart, 10);
    if (!isNaN(num) && num > 0) {
      existingNumbers.add(num);
    }
  }

  let nextNum = 1;
  while (existingNumbers.has(nextNum)) {
    nextNum++;
  }

  const paddedNum = String(nextNum).padStart(padLength, '0');
  return `${fullPrefix}${paddedNum}`;
}

export async function generateRefId(
  prefix: string,
  getAllRefIds: () => Promise<{ ref_id: string | null }[]>,
  opts: RefIdOptions = {},
): Promise<string> {
  return generateSequentialRefId(prefix, getAllRefIds, opts);
}
