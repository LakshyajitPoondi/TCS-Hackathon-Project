import { createContext, useContext, useState, type ReactNode } from "react";
import { ShieldAlert } from "lucide-react";

/** Identical to backend WARNING; replaced by the API's `warning` field once an analysis returns. */
export const WARNING_TEXT =
  "These are hypotheses, not confirmed root causes. Engineering validation is required before corrective action.";

const WarningContext = createContext<{ warning: string; setWarning: (w: string) => void }>({
  warning: WARNING_TEXT,
  setWarning: () => {},
});

export function WarningProvider({ children }: { children: ReactNode }) {
  const [warning, setWarning] = useState(WARNING_TEXT);
  return <WarningContext.Provider value={{ warning, setWarning }}>{children}</WarningContext.Provider>;
}

export const useWarning = () => useContext(WarningContext);

export function ValidationBanner() {
  const { warning } = useWarning();
  return (
    <div role="note" aria-label="Validation required" className="border-b border-warning/40 bg-warning-tint">
      <p className="flex items-start gap-2 px-4 py-2 text-[13px] font-medium leading-snug text-ink-900 sm:items-center lg:px-6">
        <ShieldAlert size={16} className="mt-0.5 shrink-0 text-warning-ink sm:mt-0" aria-hidden="true" />
        <span>
          <span className="font-semibold">Validation required · </span>
          {warning}
        </span>
      </p>
    </div>
  );
}
