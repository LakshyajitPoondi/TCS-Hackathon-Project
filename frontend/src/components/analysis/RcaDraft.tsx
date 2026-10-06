import { useState } from "react";
import { Check, Copy, RotateCcw, Save, ShieldAlert } from "lucide-react";
import { Card, SectionTitle } from "../ui/Card";
import { Button } from "../ui/Button";

export function RcaDraft({
  value,
  original,
  onChange,
  warning,
  onSave,
}: {
  value: string;
  original: string;
  onChange: (v: string) => void;
  warning: string;
  onSave: () => void;
}) {
  const [copied, setCopied] = useState<"idle" | "ok" | "fail">("idle");
  const edited = value !== original;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied("ok");
    } catch {
      setCopied("fail");
    }
    window.setTimeout(() => setCopied("idle"), 2000);
  };

  return (
    <section>
      <SectionTitle
        title="RCA Draft"
        sub="Edit the draft to reflect engineering findings. Your edits are kept until a new analysis is run."
        right={
          <div className="flex flex-wrap gap-2">
            {edited && (
              <Button variant="ghost" size="sm" onClick={() => onChange(original)} icon={<RotateCcw size={15} aria-hidden="true" />}>
                Revert edits
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={copy}
              icon={copied === "ok" ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}
            >
              {copied === "ok" ? "Copied" : copied === "fail" ? "Copy failed" : "Copy"}
            </Button>
          </div>
        }
      />
      <Card className="p-4 sm:p-5">
        <label htmlFor="rca-draft" className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink-700">
          Draft text
          {edited && <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] text-indigo-700">Edited</span>}
        </label>
        <textarea
          id="rca-draft"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={14}
          spellCheck
          className="block min-h-[260px] w-full resize-y rounded-md border border-transparent bg-slate-100 p-4 font-mono text-[13px] leading-relaxed text-ink-900 transition-colors duration-150 focus:border-indigo-500 focus:bg-white focus:shadow-ring focus:outline-none"
        />
        <p className="mt-3 flex items-start gap-2 rounded-md bg-warning-tint px-3 py-2 text-sm font-medium text-ink-900">
          <ShieldAlert size={16} className="mt-0.5 shrink-0 text-warning-ink" aria-hidden="true" />
          {warning}
        </p>
        <div className="mt-4 flex flex-wrap items-center justify-end gap-3">
          <p className="text-xs text-slate-500">Confirm only after engineering validation.</p>
          <Button onClick={onSave} arrow icon={<Save size={17} aria-hidden="true" />} disabled={!value.trim()}>
            Save as Validated Case
          </Button>
        </div>
      </Card>
    </section>
  );
}
