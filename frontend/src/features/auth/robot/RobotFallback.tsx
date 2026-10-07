/**
 * Static stand-in shown while the RcaRobot chunk loads (and if it fails). Same box size as RcaRobot, so the
 * auth card never shifts. Lives outside the lazy chunk; deliberately tiny.
 */
export function RobotFallback({ className = "" }: { className?: string }) {
  return (
    <div role="img" aria-label="Assistant robot" className={className}>
      <svg viewBox="0 0 340 400" className="h-full w-full" aria-hidden="true" focusable="false">
        <ellipse cx="170" cy="384" rx="92" ry="12" fill="var(--color-indigo-100)" />
        <path d="M170 222 C 232 222 258 268 252 304 C 246 342 210 358 170 358 C 130 358 94 342 88 304 C 82 268 108 222 170 222 Z" fill="var(--color-white)" stroke="var(--color-slate-200)" strokeWidth="2" />
        <circle cx="170" cy="292" r="22" fill="var(--color-indigo-100)" />
        <rect x="152" y="200" width="36" height="30" rx="10" fill="var(--color-indigo-700)" />
        <circle cx="64" cy="128" r="25" fill="var(--color-indigo-100)" />
        <circle cx="276" cy="128" r="25" fill="var(--color-indigo-100)" />
        <rect x="68" y="40" width="204" height="176" rx="76" fill="var(--color-white)" stroke="var(--color-slate-200)" strokeWidth="2" />
        <rect x="92" y="80" width="156" height="100" rx="46" fill="var(--color-indigo-700)" />
        <rect x="135" y="106" width="20" height="44" rx="10" fill="var(--color-mint-400)" />
        <rect x="185" y="106" width="20" height="44" rx="10" fill="var(--color-mint-400)" />
        <rect x="70" y="244" width="32" height="108" rx="16" fill="var(--color-white)" stroke="var(--color-slate-200)" strokeWidth="2" />
        <rect x="238" y="244" width="32" height="108" rx="16" fill="var(--color-white)" stroke="var(--color-slate-200)" strokeWidth="2" />
      </svg>
    </div>
  );
}

/** Shared size classes: 200 px tall on mobile, 340 x 400 on desktop (§8.2). */
export const ROBOT_SIZE = "h-[200px] w-[170px] md:h-[400px] md:w-[340px]";
