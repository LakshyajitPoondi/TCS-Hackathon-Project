import { motion, type MotionValue } from "framer-motion";
import type { RefObject } from "react";
import type { EyeMode } from "./poses";

/** Motion values driven by RcaRobot's single animation loop; only transform and opacity change. */
export interface RobotMotion {
  eyeX: MotionValue<number>; eyeY: MotionValue<number>;
  eyeScaleL: MotionValue<number>; eyeScaleR: MotionValue<number>;
  headX: MotionValue<number>; headY: MotionValue<number>; headRotate: MotionValue<number>; headScaleY: MotionValue<number>;
  glossX: MotionValue<number>; earsX: MotionValue<number>;
  bodyRotate: MotionValue<number>; hopY: MotionValue<number>; shadowX: MotionValue<number>; shadowScale: MotionValue<number>;
  armL: MotionValue<number>; armR: MotionValue<number>; armsY: MotionValue<number>;
  chestGlow: MotionValue<number>; chestFlash: MotionValue<number>;
}

const fillBox = { transformBox: "fill-box" as const };

/**
 * Pure SVG layers (§8.2): shadow, body, arms (L, R), neck, head, visor, eyes (L, R), pupil highlights, ears (L, R).
 * viewBox 340 x 400. Colours come from design tokens or robot.css custom properties.
 */
export function RobotSvg({ mv, eyeMode, headRef, onHeadClick, onChestEnter, onChestLeave }: {
  mv: RobotMotion;
  eyeMode: EyeMode;
  headRef: RefObject<SVGGElement | null>;
  onHeadClick: () => void;
  onChestEnter: () => void;
  onChestLeave: () => void;
}) {
  const show = (on: boolean) => ({ opacity: on ? 1 : 0, transition: "opacity 150ms ease-out" });
  const normal = eyeMode === "normal" || eyeMode === "line";
  return (
    <svg viewBox="0 0 340 400" className="h-full w-full overflow-visible" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="rr-head" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" style={{ stopColor: "var(--color-white)" }} />
          <stop offset="1" style={{ stopColor: "var(--robot-shade)" }} />
        </linearGradient>
        <linearGradient id="rr-visor" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" style={{ stopColor: "var(--color-indigo-900)" }} />
          <stop offset="1" style={{ stopColor: "var(--color-indigo-700)" }} />
        </linearGradient>
        <linearGradient id="rr-brand" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" style={{ stopColor: "var(--color-indigo-700)" }} />
          <stop offset="0.45" style={{ stopColor: "var(--robot-blue)" }} />
          <stop offset="0.7" style={{ stopColor: "var(--color-cyan-400)" }} />
          <stop offset="1" style={{ stopColor: "var(--color-mint-400)" }} />
        </linearGradient>
        <filter id="rr-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feDropShadow dx="0" dy="0" stdDeviation="4" style={{ floodColor: "var(--color-cyan-400)" }} />
        </filter>
        <filter id="rr-glow-red" x="-80%" y="-80%" width="260%" height="260%">
          <feDropShadow dx="0" dy="0" stdDeviation="4" style={{ floodColor: "var(--color-danger)" }} />
        </filter>
        <filter id="rr-soft" x="-30%" y="-200%" width="160%" height="500%"><feGaussianBlur stdDeviation="6" /></filter>
      </defs>

      {/* shadow: slides opposite to the lean and shrinks while floating */}
      <motion.g style={{ x: mv.shadowX, scaleX: mv.shadowScale, ...fillBox, originX: 0.5, originY: 0.5 }}>
        <ellipse className="rr-shadow" cx="170" cy="384" rx="92" ry="12" filter="url(#rr-soft)" />
      </motion.g>

      <g className="rr-float">
        <motion.g style={{ y: mv.hopY }}>
          {/* body: leans slowly (heaviest spring) */}
          <motion.g data-part="body" style={{ rotate: mv.bodyRotate, ...fillBox, originX: 0.5, originY: 1 }}>
            <ellipse cx="124" cy="360" rx="31" ry="16" fill="url(#rr-head)" className="rr-rim" strokeWidth="1" />
            <ellipse cx="216" cy="360" rx="31" ry="16" fill="url(#rr-head)" className="rr-rim" strokeWidth="1" />
            <ellipse cx="124" cy="366" rx="24" ry="7" fill="none" className="rr-wheel" strokeWidth="3" />
            <ellipse cx="216" cy="366" rx="24" ry="7" fill="none" className="rr-wheel" strokeWidth="3" />
            <path d="M170 222 C 232 222 258 268 252 304 C 246 342 210 358 170 358 C 130 358 94 342 88 304 C 82 268 108 222 170 222 Z"
              fill="url(#rr-head)" className="rr-rim" strokeWidth="1.5" />
            <ellipse cx="138" cy="250" rx="22" ry="9" fill="var(--color-white)" opacity="0.7" transform="rotate(-18 138 250)" />
            <g onPointerEnter={onChestEnter} onPointerLeave={onChestLeave} style={{ pointerEvents: "auto", cursor: "default" }}>
              <circle cx="170" cy="292" r="24" fill="url(#rr-brand)" />
              <circle cx="170" cy="292" r="15" fill="var(--color-white)" />
              <polyline points="158,293 164,293 167,285 171,300 175,289 178,293 183,293" fill="none" stroke="var(--color-indigo-700)"
                strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
              <circle className="rr-pulse" cx="170" cy="292" r="27" fill="none" stroke="var(--color-cyan-400)" strokeWidth="3" />
              <motion.circle cx="170" cy="292" r="27" fill="none" stroke="var(--color-cyan-400)" strokeWidth="4" style={{ opacity: mv.chestGlow }} />
              <motion.circle cx="170" cy="292" r="30" fill="var(--color-mint-400)" style={{ opacity: mv.chestFlash }} />
            </g>
          </motion.g>

          {/* neck */}
          <rect x="152" y="200" width="36" height="30" rx="10" fill="url(#rr-visor)" />

          {/* head: tilts toward the cursor (medium spring) */}
          <motion.g ref={headRef} data-part="head" style={{ x: mv.headX, y: mv.headY, rotate: mv.headRotate, scaleY: mv.headScaleY, ...fillBox, originX: 0.5, originY: 1 }}>
            <motion.g style={{ x: mv.earsX }}>
              <circle cx="64" cy="128" r="25" fill="url(#rr-brand)" />
              <circle cx="64" cy="128" r="14" fill="none" stroke="var(--color-white)" strokeOpacity="0.7" strokeWidth="3" />
              <circle cx="276" cy="128" r="25" fill="url(#rr-brand)" />
              <circle cx="276" cy="128" r="14" fill="none" stroke="var(--color-white)" strokeOpacity="0.7" strokeWidth="3" />
            </motion.g>
            <g onClick={onHeadClick} style={{ pointerEvents: "auto", cursor: "pointer" }}>
              <rect x="68" y="40" width="204" height="176" rx="76" fill="url(#rr-head)" className="rr-rim" strokeWidth="1.5" />
              <ellipse cx="122" cy="66" rx="36" ry="13" fill="var(--color-white)" opacity="0.6" transform="rotate(-18 122 66)" />
              <rect x="92" y="80" width="156" height="100" rx="46" fill="url(#rr-visor)" />
              <rect x="95" y="83" width="150" height="94" rx="43" fill="none" stroke="var(--color-indigo-900)" strokeOpacity="0.6" strokeWidth="5" />
            </g>
            {/* visor reflection: parallax opposite to the gaze */}
            <motion.g style={{ x: mv.glossX }} pointerEvents="none">
              <path d="M112 106 Q 130 90 156 88" fill="none" stroke="var(--color-white)" strokeOpacity="0.22" strokeWidth="6" strokeLinecap="round" />
              <path d="M210 166 Q 226 158 232 146" fill="none" stroke="var(--color-white)" strokeOpacity="0.1" strokeWidth="4" strokeLinecap="round" />
            </motion.g>
            {/* eyes: fastest spring */}
            <motion.g data-part="eyes" style={{ x: mv.eyeX, y: mv.eyeY }} pointerEvents="none">
              <g style={show(normal)}>
                <motion.g data-part="eyeL" style={{ scaleY: mv.eyeScaleL, ...fillBox, originX: 0.5, originY: 0.5 }}>
                  <rect x="135" y="106" width="20" height="44" rx="10" fill="var(--color-mint-400)" filter="url(#rr-glow)" />
                  <circle cx="141" cy="116" r="3.2" fill="var(--color-white)" opacity="0.85" />
                </motion.g>
                <motion.g data-part="eyeR" style={{ scaleY: mv.eyeScaleR, ...fillBox, originX: 0.5, originY: 0.5 }}>
                  <rect x="185" y="106" width="20" height="44" rx="10" fill="var(--color-mint-400)" filter="url(#rr-glow)" />
                  <circle cx="191" cy="116" r="3.2" fill="var(--color-white)" opacity="0.85" />
                </motion.g>
              </g>
              <g style={show(eyeMode === "happy")} fill="none" stroke="var(--color-mint-400)" strokeWidth="7" strokeLinecap="round" filter="url(#rr-glow)">
                <path d="M133 134 Q 145 112 157 134" />
                <path d="M183 134 Q 195 112 207 134" />
              </g>
              <g style={show(eyeMode === "giggle")} fill="none" stroke="var(--color-mint-400)" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" filter="url(#rr-glow)">
                <path d="M137 116 L 153 128 L 137 140" />
                <path d="M203 116 L 187 128 L 203 140" />
              </g>
              <g style={show(eyeMode === "sad")} filter="url(#rr-glow-red)">
                <rect x="135" y="112" width="20" height="36" rx="10" fill="var(--color-danger)" transform="rotate(-18 145 130)" />
                <rect x="185" y="112" width="20" height="36" rx="10" fill="var(--color-danger)" transform="rotate(18 195 130)" />
              </g>
              <g style={show(eyeMode === "dots")} fill="var(--color-mint-400)" filter="url(#rr-glow)">
                <circle className="rr-dot rr-dot-1" cx="150" cy="128" r="7" />
                <circle className="rr-dot rr-dot-2" cx="170" cy="128" r="7" />
                <circle className="rr-dot rr-dot-3" cx="190" cy="128" r="7" />
              </g>
            </motion.g>
          </motion.g>

          {/* arms last so they can cover the visor (§8.5 privacy); they lean with the body */}
          <motion.g style={{ rotate: mv.bodyRotate, y: mv.armsY, ...fillBox, originX: 0.5, originY: 1 }}>
            <motion.g data-part="armL" style={{ rotate: mv.armL, ...fillBox, originX: 0.5, originY: 0.08 }}>
              <rect x="70" y="244" width="32" height="108" rx="16" fill="url(#rr-head)" className="rr-rim" strokeWidth="1.5" />
              <rect x="70" y="326" width="32" height="18" rx="8" fill="var(--color-mint-400)" opacity="0.9" />
            </motion.g>
            <motion.g data-part="armR" style={{ rotate: mv.armR, ...fillBox, originX: 0.5, originY: 0.08 }}>
              <rect x="238" y="244" width="32" height="108" rx="16" fill="url(#rr-head)" className="rr-rim" strokeWidth="1.5" />
              <rect x="238" y="326" width="32" height="18" rx="8" fill="var(--color-cyan-400)" opacity="0.9" />
            </motion.g>
          </motion.g>
        </motion.g>
      </g>
    </svg>
  );
}
