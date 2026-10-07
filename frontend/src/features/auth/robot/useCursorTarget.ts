import { useEffect, useRef, type RefObject } from "react";

export interface CursorTarget {
  /** Normalised offset of the pointer from the robot's head centre, clamped to -1..1. */
  nx: number;
  ny: number;
  /** performance.now() of the last pointer/touch/orientation movement (0 = never). */
  lastMove: number;
  /** False after the pointer left the window or a touch ended: the robot returns to centre. */
  active: boolean;
}

const clamp = (v: number) => Math.max(-1, Math.min(1, v));

/**
 * Pointer, touch and (already-permitted) device orientation -> normalised target, stored in a ref.
 * Never sets React state per movement (§8.3.6); the robot's animation loop reads the ref.
 */
export function useCursorTarget(headRef: RefObject<SVGGElement | null>) {
  const target = useRef<CursorTarget>({ nx: 0, ny: 0, lastMove: 0, active: false });
  useEffect(() => {
    let centre = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const measure = () => {
      const r = headRef.current?.getBoundingClientRect();
      if (r && r.width) centre = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    };
    const point = (x: number, y: number) => {
      target.current = {
        nx: clamp((x - centre.x) / (window.innerWidth / 2)),
        ny: clamp((y - centre.y) / (window.innerHeight / 2)),
        lastMove: performance.now(), active: true,
      };
    };
    const onPointer = (e: PointerEvent) => point(e.clientX, e.clientY);
    const onTouch = (e: TouchEvent) => { const t = e.touches[0]; if (t) point(t.clientX, t.clientY); };
    const release = () => { target.current = { ...target.current, nx: 0, ny: 0, active: false, lastMove: performance.now() }; };
    const onLeave = (e: PointerEvent) => { if (!e.relatedTarget) release(); };
    // Device orientation only if the browser already delivers it without a permission prompt (never prompt).
    const DOE = (window as unknown as { DeviceOrientationEvent?: { requestPermission?: unknown } }).DeviceOrientationEvent;
    const orientationAllowed = !!DOE && typeof DOE.requestPermission !== "function";
    const onOrientation = (e: DeviceOrientationEvent) => {
      if (e.gamma === null || e.beta === null) return;
      if (performance.now() - target.current.lastMove < 2000 && target.current.active) return; // pointer/touch wins
      target.current = { nx: clamp(e.gamma / 30), ny: clamp((e.beta - 45) / 30), lastMove: performance.now(), active: true };
    };
    measure();
    window.addEventListener("pointermove", onPointer, { passive: true });
    window.addEventListener("touchmove", onTouch, { passive: true });
    window.addEventListener("touchend", release, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, { passive: true });
    if (orientationAllowed) window.addEventListener("deviceorientation", onOrientation);
    const ro = new ResizeObserver(measure);
    if (headRef.current) ro.observe(headRef.current as unknown as Element);
    return () => {
      window.removeEventListener("pointermove", onPointer);
      window.removeEventListener("touchmove", onTouch);
      window.removeEventListener("touchend", release);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure);
      if (orientationAllowed) window.removeEventListener("deviceorientation", onOrientation);
      ro.disconnect();
    };
  }, [headRef]);
  return target;
}
