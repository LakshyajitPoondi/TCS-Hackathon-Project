import { useEffect, useRef, useState } from "react";
import { animate, useAnimationFrame, useMotionValue, useReducedMotion, useSpring, useTransform, type MotionValue } from "framer-motion";
import "./robot.css";
import { RobotSvg, type RobotMotion } from "./RobotSvg";
import { useCursorTarget } from "./useCursorTarget";
import { useRobotState } from "./useRobotState";
import { useRobotBus } from "./RobotContext";
import { RANGE, SPRINGS, type EyeMode } from "./poses";

const IDLE_AFTER_MS = 4000;
const EASTER_EGG_GAP_MS = 1500;
const rand = (a: number, b: number) => a + Math.random() * (b - a);

/**
 * Interactive auth mascot (§8). Cursor tracking with lagged springs, idle behaviours and form-aware reactions.
 * One animation loop (framer-motion's frame loop) writes motion values; React re-renders only on state changes.
 * Lazy-loaded from the login page; `size` classes must match RobotFallback to avoid layout shift.
 */
export default function RcaRobot({ className = "" }: { className?: string }) {
  const bus = useRobotBus();
  const { state, pose, dispatch } = useRobotState();
  const reduced = !!useReducedMotion();
  const headRef = useRef<SVGGElement | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const cursor = useCursorTarget(headRef);
  const [eyeOverride, setEyeOverride] = useState<EyeMode | null>(null);

  // Raw targets (set every frame) and spring-smoothed outputs (eyes fast, head medium, body slow).
  const raw = {
    eyeX: useMotionValue(0), eyeY: useMotionValue(0), headX: useMotionValue(0), headY: useMotionValue(0),
    headRotate: useMotionValue(0), glossX: useMotionValue(0), earsX: useMotionValue(0), bodyRotate: useMotionValue(0),
    shadowX: useMotionValue(0), armL: useMotionValue(0), armR: useMotionValue(0), armsY: useMotionValue(0), eyeScaleL: useMotionValue(1), eyeScaleR: useMotionValue(1),
  };
  const spring = {
    eyeX: useSpring(raw.eyeX, SPRINGS.eyes), eyeY: useSpring(raw.eyeY, SPRINGS.eyes),
    headX: useSpring(raw.headX, SPRINGS.head), headY: useSpring(raw.headY, SPRINGS.head), headRotate: useSpring(raw.headRotate, SPRINGS.head),
    glossX: useSpring(raw.glossX, SPRINGS.head), earsX: useSpring(raw.earsX, SPRINGS.head),
    bodyRotate: useSpring(raw.bodyRotate, SPRINGS.body), shadowX: useSpring(raw.shadowX, SPRINGS.body),
    armL: useSpring(raw.armL, SPRINGS.arms), armR: useSpring(raw.armR, SPRINGS.arms), armsY: useSpring(raw.armsY, SPRINGS.arms),
    eyeScaleL: useSpring(raw.eyeScaleL, SPRINGS.eyes), eyeScaleR: useSpring(raw.eyeScaleR, SPRINGS.eyes),
  };
  // One-off gestures layered on top of the tracked pose.
  const blink = useMotionValue(1), shake = useMotionValue(0), sway = useMotionValue(0), nod = useMotionValue(0);
  const hop = useMotionValue(0), wave = useMotionValue(0), squash = useMotionValue(1), glance = useMotionValue(0);
  const chestGlow = useMotionValue(0), chestFlash = useMotionValue(0), shadowScale = useMotionValue(1);
  const pick = <T,>(s: T, r: T) => (reduced ? r : s);
  // Hooks below run unconditionally and in the same order on every render.
  const sum = (a: MotionValue<number>, ...rest: MotionValue<number>[]) =>
    useTransform([a, ...rest], (v: number[]) => v.reduce((x, y) => x + y, 0));
  const mv: RobotMotion = {
    eyeX: sum(pick(spring.eyeX, raw.eyeX), glance), eyeY: pick(spring.eyeY, raw.eyeY),
    eyeScaleL: useTransform([pick(spring.eyeScaleL, raw.eyeScaleL), blink], ([a, b]: number[]) => a * b),
    eyeScaleR: useTransform([pick(spring.eyeScaleR, raw.eyeScaleR), blink], ([a, b]: number[]) => a * b),
    headX: sum(pick(spring.headX, raw.headX), shake, sway), headY: sum(pick(spring.headY, raw.headY), nod),
    headRotate: pick(spring.headRotate, raw.headRotate), headScaleY: squash,
    glossX: pick(spring.glossX, raw.glossX), earsX: pick(spring.earsX, raw.earsX),
    bodyRotate: pick(spring.bodyRotate, raw.bodyRotate), hopY: hop, shadowX: pick(spring.shadowX, raw.shadowX), shadowScale,
    armL: pick(spring.armL, raw.armL), armR: sum(pick(spring.armR, raw.armR), wave), armsY: pick(spring.armsY, raw.armsY),
    chestGlow, chestFlash,
  };

  // Mutable loop inputs (refs, never React state per frame).
  const live = useRef({ state, pose, reduced, caret: 0.5, keystrokes: 0, look: { nx: 0, ny: 0 }, nextLook: 0,
                        override: null as { nx: number; ny: number; until: number } | null, idle: false });
  live.current.state = state; live.current.pose = pose; live.current.reduced = reduced;

  useAnimationFrame((time) => {
    if (document.hidden) return;
    const L = live.current, c = cursor.current, now = performance.now();
    let nx = 0, ny = 0, idle = false;
    if (L.override && now < L.override.until) {
      ({ nx, ny } = L.override);
    } else if (!L.pose.tracking) {
      ({ nx, ny } = L.pose.look ?? { nx: 0, ny: 0 });
    } else if (L.state === "watchingEmail") {
      nx = -0.1 + 0.9 * L.caret; ny = 0.45;   // follow the caret across the email field (right of the robot)
    } else if (c.active && now - c.lastMove < IDLE_AFTER_MS) {
      nx = c.nx; ny = c.ny;
    } else if (!c.active && now - c.lastMove < 600) {
      nx = 0; ny = 0;                           // pointer left: return to centre, then look around
    } else {
      idle = true;                              // look around: drift to a random point every 1.5–2.5 s, slowly
      if (now > L.nextLook) { L.look = { nx: rand(-0.7, 0.7), ny: rand(-0.5, 0.5) }; L.nextLook = now + rand(1500, 2500); }
      const k = 0.03;
      nx = (raw.eyeX.get() / RANGE.eyeX) + (L.look.nx - raw.eyeX.get() / RANGE.eyeX) * k;
      ny = (raw.eyeY.get() / RANGE.eyeY) + (L.look.ny - raw.eyeY.get() / RANGE.eyeY) * k;
    }
    if (idle !== L.idle) { L.idle = idle; rootRef.current?.setAttribute("data-robot-idle", String(idle)); }
    const r = L.reduced;
    raw.eyeX.set(nx * (r ? RANGE.reducedEye : RANGE.eyeX));
    raw.eyeY.set(ny * (r ? RANGE.reducedEye : RANGE.eyeY));
    raw.headX.set(r ? 0 : nx * RANGE.headX);
    raw.headRotate.set(r ? 0 : nx * RANGE.headRotate);
    raw.headY.set(r ? 0 : ny * RANGE.headY);
    raw.glossX.set(r ? 0 : -nx * RANGE.gloss);
    raw.bodyRotate.set(r ? 0 : nx * RANGE.bodyRotate);
    raw.earsX.set(r ? 0 : nx * RANGE.ears);
    raw.shadowX.set(r ? 0 : -nx * RANGE.shadow);
    raw.armL.set(L.pose.armL); raw.armR.set(L.pose.armR); raw.armsY.set(L.pose.armsY);
    raw.eyeScaleL.set(L.pose.eyeScaleL); raw.eyeScaleR.set(L.pose.eyeScaleR);
    // Shadow shrinks while the CSS float lifts the robot (same 3.2 s period).
    shadowScale.set(r ? 1 : 1 - 0.1 * (0.5 - 0.5 * Math.cos((2 * Math.PI * (time % 3200)) / 3200)));
  });

  // Blink: random 2.5–5.5 s, 15 % chance of a double blink; paused while the tab is hidden.
  useEffect(() => {
    let timer = 0;
    const once = () => animate(blink, [1, 0.1, 1], { duration: 0.14, ease: "easeInOut" });
    const schedule = () => {
      timer = window.setTimeout(async () => {
        if (!document.hidden) { await once(); if (Math.random() < 0.15) { await new Promise((r) => setTimeout(r, 90)); await once(); } }
        schedule();
      }, rand(2500, 5500));
    };
    schedule();
    return () => window.clearTimeout(timer);
  }, [blink]);

  // State-entry reactions (§8.5). Reduced motion: no hop or head shake; pose swaps are instant.
  useEffect(() => {
    rootRef.current?.setAttribute("data-robot-state", state);
    const stops: { stop: () => void }[] = [];
    if (state === "thinking" && !reduced) stops.push(animate(sway, [0, -4, 4, 0], { duration: 1.2, repeat: Infinity, ease: "easeInOut" }));
    if (state === "peeking" && !reduced) stops.push(animate(glance, [0, 7, 7, 0], { duration: 1.4, times: [0, 0.3, 0.7, 1] }));
    if (state === "success") {
      stops.push(animate(chestFlash, [0, 0.9, 0], { duration: 0.9 }));
      if (!reduced) {
        stops.push(animate(hop, [0, -18, 0], { type: "spring", stiffness: 260, damping: 12, duration: 0.6 }));
        stops.push(animate(wave, [0, -140, -105, -140, 0], { duration: 0.9 }));
      }
    }
    if (state === "error" && !reduced) stops.push(animate(shake, [0, -10, 10, -10, 10, -10, 0], { duration: 0.4 }));
    return () => { stops.forEach((s) => s.stop()); sway.set(0); glance.set(0); };
  }, [state, reduced, sway, glance, chestFlash, hop, wave, shake]);

  // Form events from the auth page.
  useEffect(() => bus.subscribe((e) => {
    const L = live.current;
    if (e.type === "caret") {
      L.caret = Math.max(0, Math.min(1, e.ratio));
      L.keystrokes += 1;
      if (L.keystrokes % 6 === 0 && !L.reduced) animate(nod, [0, 4, 0], { duration: 0.35 });
      return;
    }
    if (e.type === "demoProfile") {
      L.override = { nx: 0.8, ny: 0.45, until: performance.now() + 1000 };   // look at the filled field
      if (!L.reduced) animate(wave, [0, -140, -105, -140, 0], { duration: 0.9 });
      return;
    }
    if (e.type === "modeToggle") {
      L.override = { nx: 0.9, ny: -0.7, until: performance.now() + 900 };   // turn toward the toggle
      if (!L.reduced) animate(hop, [0, -8, 0], { duration: 0.35 });
      return;
    }
    if (e.type === "passwordBlur") animate(blink, [0.1, 1], { duration: 0.14 });   // eyes reopen with a blink
    dispatch(e);
  }), [bus, dispatch, blink, nod, wave, hop]);

  // Easter eggs (§8.6), at most one per 1.5 s.
  const lastEgg = useRef(0);
  const giggle = () => {
    const now = performance.now();
    if (now - lastEgg.current < EASTER_EGG_GAP_MS) return;
    lastEgg.current = now;
    setEyeOverride("giggle");
    if (!reduced) animate(squash, [1, 0.92, 1], { duration: 0.3 });
    window.setTimeout(() => setEyeOverride(null), 400);
  };

  return (
    <div ref={rootRef} role="img" aria-label="Animated assistant robot" data-robot-state={state} data-reduced={String(reduced)} data-eye-mode={eyeOverride ?? pose.eyeMode}
      className={`rca-robot pointer-events-none select-none ${className}`}>
      <RobotSvg mv={mv} eyeMode={eyeOverride ?? pose.eyeMode} headRef={headRef} onHeadClick={giggle}
        onChestEnter={() => animate(chestGlow, 1, { duration: 0.2 })} onChestLeave={() => animate(chestGlow, 0, { duration: 0.3 })} />
    </div>
  );
}
