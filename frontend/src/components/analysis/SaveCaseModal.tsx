import { useEffect, useState, type FormEvent } from "react";
import { CheckCircle2 } from "lucide-react";
import { saveCase } from "../../api/endpoints";
import { errorMessage } from "../../api/client";
import { ALL_CATEGORIES, type Category, type Subcause } from "../../types/api";
import { categoryLabel } from "../../lib/format";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { Alert } from "../ui/Alert";

const field =
  "block h-12 w-full rounded-md border border-transparent bg-slate-100 px-3 text-[15px] text-ink-900 transition-colors duration-150 focus:border-indigo-500 focus:bg-white focus:shadow-ring focus:outline-none";
const labelCls = "mb-1.5 block text-[13px] font-semibold text-ink-700";

export function SaveCaseModal({
  open,
  onClose,
  incidentId,
  draft,
}: {
  open: boolean;
  onClose: () => void;
  incidentId: string;
  draft: string;
}) {
  const [category, setCategory] = useState<Category | "">("");
  const [subcause, setSubcause] = useState<Exclude<Subcause, null> | "">("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (open) {
      setCategory("");
      setSubcause("");
      setNotes("");
      setError(null);
      setSavedId(null);
      setTouched(false);
    }
  }, [open]);

  const needsSubcause = category === "machine";
  const categoryMissing = touched && !category;
  const subcauseMissing = touched && needsSubcause && !subcause;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!category || (needsSubcause && !subcause)) return;
    setSaving(true);
    setError(null);
    try {
      const res = await saveCase({
        incident_id: incidentId,
        rca_draft: draft,
        confirmed_category: category,
        confirmed_subcause: needsSubcause ? (subcause as Exclude<Subcause, null>) : null,
        notes: notes.trim() || null,
      });
      setSavedId(res.case_id);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Save as Validated Case">
      {savedId ? (
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-md bg-success-tint p-4 text-sm text-ink-900" role="status">
            <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-success-ink" aria-hidden="true" />
            <p>
              Case saved to Experience Memory · <span className="font-mono font-semibold">{savedId}</span>. The validated signal
              signature can now support future incident investigations.
            </p>
          </div>
          <div className="flex justify-end">
            <Button onClick={onClose}>Done</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} noValidate className="space-y-4">
          <p className="rounded-md bg-warning-tint px-3 py-2 text-sm font-semibold text-ink-900">
            Confirm only after engineering validation.
          </p>
          <p className="text-sm text-slate-600">
            Incident <span className="font-mono font-semibold text-ink-900">{incidentId}</span> · the edited draft will be saved with this case.
          </p>

          <div>
            <label htmlFor="confirmed-category" className={labelCls}>
              Confirmed category <span className="text-danger-ink">*</span>
            </label>
            <select
              id="confirmed-category"
              required
              value={category}
              onChange={(e) => {
                setCategory(e.target.value as Category);
                if (e.target.value !== "machine") setSubcause("");
              }}
              aria-invalid={categoryMissing}
              aria-describedby={categoryMissing ? "category-error" : undefined}
              className={`${field} ${categoryMissing ? "border-danger" : ""}`}
            >
              <option value="" disabled>
                Select the validated category…
              </option>
              {ALL_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {categoryLabel(c)}
                </option>
              ))}
            </select>
            {categoryMissing && (
              <p id="category-error" className="mt-1 text-[13px] text-danger-ink">
                Select a confirmed category.
              </p>
            )}
          </div>

          {needsSubcause && (
            <div className="fade-in">
              <label htmlFor="confirmed-subcause" className={labelCls}>
                Subcause <span className="text-danger-ink">*</span>
              </label>
              <select
                id="confirmed-subcause"
                required
                value={subcause}
                onChange={(e) => setSubcause(e.target.value as "cooling" | "mechanical")}
                aria-invalid={subcauseMissing}
                aria-describedby={subcauseMissing ? "subcause-error" : undefined}
                className={`${field} ${subcauseMissing ? "border-danger" : ""}`}
              >
                <option value="" disabled>
                  Select a subcause…
                </option>
                <option value="cooling">Cooling</option>
                <option value="mechanical">Mechanical</option>
              </select>
              {subcauseMissing && (
                <p id="subcause-error" className="mt-1 text-[13px] text-danger-ink">
                  Select a subcause for a machine case.
                </p>
              )}
            </div>
          )}

          <div>
            <label htmlFor="case-notes" className={labelCls}>
              Notes <span className="font-normal text-slate-500">(optional)</span>
            </label>
            <textarea
              id="case-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className={`${field} h-auto py-2.5`}
              placeholder="What was checked and confirmed on the line?"
            />
          </div>

          {error && <Alert tone="danger" title="Case not saved">{error}</Alert>}

          <div className="flex flex-wrap justify-end gap-3 pt-1">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={saving} arrow>
              Save case
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
