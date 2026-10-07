/** Numeric pose targets per robot state (§8.5). Springs move from the current pose to these targets. */
export type RobotState = "idle" | "tracking" | "watchingEmail" | "privacy" | "peeking" | "thinking" | "success" | "error";
export type EyeMode = "normal" | "line" | "dots" | "happy" | "sad" | "giggle";

export interface Pose {
  /** Follow the cursor (or the email caret) with the lagged springs. */
  tracking: boolean;
  eyeMode: EyeMode;
  /** Eye height multiplier per eye (1 open, 0.15 thin line). */
  eyeScaleL: number;
  eyeScaleR: number;
  /** Arm rotation in degrees around the shoulder (0 = resting; left arm negative / right arm positive swing up over the visor). */
  armL: number;
  armR: number;
  /** Vertical lift of both arms in px (negative = up), so raised hands reach the eyes. */
  armsY: number;
  /** Fixed gaze when not tracking, as normalised -1..1 offsets. */
  look?: { nx: number; ny: number };
}

export const POSES: Record<RobotState, Pose> = {
  idle: { tracking: true, eyeMode: "normal", eyeScaleL: 1, eyeScaleR: 1, armL: 0, armR: 0, armsY: 0 },
  tracking: { tracking: true, eyeMode: "normal", eyeScaleL: 1, eyeScaleR: 1, armL: 0, armR: 0, armsY: 0 },
  watchingEmail: { tracking: true, eyeMode: "normal", eyeScaleL: 1, eyeScaleR: 1, armL: 0, armR: 0, armsY: 0 },
  // Arms rise and cover the visor; eyes become thin lines looking down; tracking pauses.
  privacy: { tracking: false, eyeMode: "line", eyeScaleL: 0.15, eyeScaleR: 0.15, armL: -158, armR: 158, armsY: -44, look: { nx: 0, ny: 0.7 } },
  // One arm lowers a little and one eye peeks through the gap at the password field.
  peeking: { tracking: false, eyeMode: "normal", eyeScaleL: 0.15, eyeScaleR: 1, armL: -158, armR: 112, armsY: -44, look: { nx: 0.6, ny: 0.55 } },
  thinking: { tracking: false, eyeMode: "dots", eyeScaleL: 1, eyeScaleR: 1, armL: 0, armR: 0, armsY: 0, look: { nx: 0, ny: 0 } },
  success: { tracking: false, eyeMode: "happy", eyeScaleL: 1, eyeScaleR: 1, armL: 0, armR: 0, armsY: 0, look: { nx: 0, ny: -0.2 } },
  error: { tracking: false, eyeMode: "sad", eyeScaleL: 1, eyeScaleR: 1, armL: 10, armR: -10, armsY: 0, look: { nx: 0, ny: 0.35 } },
};

/** Movement ranges from §8.3 (pixels in the 340-unit viewBox, degrees). */
export const RANGE = {
  eyeX: 10, eyeY: 7, headX: 8, headRotate: 6, headY: 4, gloss: 6, bodyRotate: 2.5, ears: 3, shadow: 6,
  reducedEye: 4,
};

/** Spring configs from §8.3: eyes fast, head medium, body slow (the lag hierarchy that makes it feel alive). */
export const SPRINGS = {
  eyes: { stiffness: 300, damping: 25 },
  head: { stiffness: 120, damping: 18 },
  body: { stiffness: 60, damping: 14 },
  arms: { stiffness: 170, damping: 20 },
  slow: { stiffness: 40, damping: 14 },
};
