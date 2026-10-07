import { useEffect, useReducer } from "react";
import type { RobotEvent } from "./RobotContext";
import { POSES, type Pose, type RobotState } from "./poses";

interface Machine {
  focus: "none" | "email" | "password";
  passwordVisible: boolean;
  /** Transient phases override the focus-derived state. */
  phase: "none" | "thinking" | "success" | "error";
}

const initial: Machine = { focus: "none", passwordVisible: false, phase: "none" };

function reducer(m: Machine, e: RobotEvent | { type: "phaseEnd" }): Machine {
  switch (e.type) {
    case "emailFocus": return { ...m, focus: "email" };
    case "passwordFocus": return { ...m, focus: "password" };
    case "emailBlur": return m.focus === "email" ? { ...m, focus: "none" } : m;
    case "passwordBlur": return m.focus === "password" ? { ...m, focus: "none" } : m;
    case "passwordVisibility": return { ...m, passwordVisible: e.visible };
    case "submit": return { ...m, phase: "thinking" };
    case "success": return { ...m, phase: "success" };
    case "error": return { ...m, phase: "error" };
    case "phaseEnd": case "reset": return { ...m, phase: "none" };
    default: return m;
  }
}

/** Single state machine (§8.5): focus + show-password + request phase -> one of the eight robot states. */
export function deriveState(m: Machine): RobotState {
  if (m.phase !== "none") return m.phase;
  if (m.focus === "password") return m.passwordVisible ? "peeking" : "privacy";
  if (m.focus === "email") return "watchingEmail";
  return "tracking";
}

export function useRobotState(): { state: RobotState; pose: Pose; dispatch: (e: RobotEvent) => void } {
  const [machine, dispatch] = useReducer(reducer, initial);
  // Error face holds 1.5 s, then the robot returns to tracking (§8.5). Success holds until navigation.
  useEffect(() => {
    if (machine.phase !== "error") return;
    const t = window.setTimeout(() => dispatch({ type: "phaseEnd" }), 1500);
    return () => window.clearTimeout(t);
  }, [machine.phase]);
  const state = deriveState(machine);
  return { state, pose: POSES[state], dispatch };
}
