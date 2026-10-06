import { useEffect, useState } from "react";
import { getSop } from "../../api/endpoints";
import { errorMessage } from "../../api/client";
import type { Sop } from "../../types/api";
import { Modal } from "../ui/Modal";
import { Alert } from "../ui/Alert";
import { Spinner } from "../ui/Spinner";

/** Minimal renderer for the SOP markdown: headings, numbered steps, bold labels, paragraphs. */
function SopContent({ content }: { content: string }) {
  const lines = content.split(/\r?\n/).filter((l, i) => !(i === 0 && l.startsWith("# ")));
  const bold = (text: string) =>
    text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith("**") ? (
        <strong key={i} className="font-semibold text-ink-900">
          {part.slice(2, -2)}
        </strong>
      ) : (
        part
      ),
    );
  return (
    <div className="space-y-2 text-sm leading-relaxed text-ink-700">
      {lines.map((line, i) => {
        if (!line.trim()) return null;
        if (line.startsWith("## ")) {
          return (
            <h3 key={i} className="pt-3 text-sm font-bold uppercase tracking-wider text-slate-500">
              {line.slice(3)}
            </h3>
          );
        }
        const step = line.match(/^(\d+)\.\s+(.*)$/);
        if (step) {
          return (
            <div key={i} className="flex gap-3">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-50 font-mono text-[11px] font-semibold text-indigo-700">
                {step[1]}
              </span>
              <p className="min-w-0 break-words">{bold(step[2])}</p>
            </div>
          );
        }
        return (
          <p key={i} className="break-words">
            {bold(line.replace(/^[-*]\s+/, "• "))}
          </p>
        );
      })}
    </div>
  );
}

export function SopModal({ sopId, onClose }: { sopId: string | null; onClose: () => void }) {
  const [sop, setSop] = useState<Sop | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sopId) return;
    let alive = true;
    setSop(null);
    setError(null);
    getSop(sopId)
      .then((value) => alive && setSop(value))
      .catch((e) => alive && setError(errorMessage(e)));
    return () => { alive = false; };
  }, [sopId]);

  return (
    <Modal
      open={sopId !== null}
      onClose={onClose}
      wide
      title={
        <span className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-mono text-indigo-700">{sopId}</span>
          {sop && <span>{sop.title}</span>}
        </span>
      }
    >
      {error && <Alert tone="danger" title="Could not load this SOP">{error}</Alert>}
      {!error && !sop && <Spinner label="Loading procedure…" />}
      {sop && <SopContent content={sop.content} />}
    </Modal>
  );
}
