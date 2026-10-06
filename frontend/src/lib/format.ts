import type { Category, Subcause } from "../types/api";

const CATEGORY_LABEL: Record<Category, string> = {
  machine: "Machine",
  material: "Material",
  method: "Method",
  measurement: "Measurement",
  people: "People",
  environment: "Environment",
};

export const categoryLabel = (c: Category) => CATEGORY_LABEL[c];
export const subcauseLabel = (s: Subcause) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : null);
export const categoryWithSubcause = (c: Category, s: Subcause) =>
  [categoryLabel(c), subcauseLabel(s)].filter(Boolean).join(" · ");

/** "2026-03-01T06:38:00" → "2026-03-01 06:38" (kept in the data's own clock, no TZ shift). */
export const fmtDateTime = (iso: string) => iso.replace("T", " ").slice(0, 16);
export const fmtTime = (iso: string) => iso.slice(11, 16);

export function fmtNumber(n: number, digits = 2) {
  return Number.isInteger(n) ? String(n) : n.toFixed(digits).replace(/\.?0+$/, "");
}

export function fmtValue(v: number | string | null): string | null {
  if (v === null || v === undefined || v === "") return null;
  return typeof v === "number" ? fmtNumber(v) : v;
}

export function fmtBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}
