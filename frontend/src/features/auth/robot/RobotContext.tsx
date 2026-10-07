import { createContext, useContext, useMemo, type ReactNode } from "react";

/** Events the auth form sends to the robot (§8.5). The robot is decoupled from form logic. */
export type RobotEvent =
  | { type: "emailFocus" } | { type: "emailBlur" } | { type: "caret"; ratio: number }
  | { type: "passwordFocus" } | { type: "passwordBlur" } | { type: "passwordVisibility"; visible: boolean }
  | { type: "submit" } | { type: "success" } | { type: "error" }
  | { type: "demoProfile" } | { type: "modeToggle" } | { type: "reset" };

type Listener = (event: RobotEvent) => void;

export interface RobotBus {
  emit: (event: RobotEvent) => void;
  subscribe: (listener: Listener) => () => void;
}

export function createRobotBus(): RobotBus {
  const listeners = new Set<Listener>();
  return {
    emit: (event) => listeners.forEach((l) => l(event)),
    subscribe: (listener) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
  };
}

const RobotContext = createContext<RobotBus | null>(null);

export function RobotProvider({ children }: { children: ReactNode }) {
  const bus = useMemo(createRobotBus, []);
  return <RobotContext.Provider value={bus}>{children}</RobotContext.Provider>;
}

/** Stable bus; emitting never re-renders the form or the robot. */
export function useRobotBus(): RobotBus {
  const bus = useContext(RobotContext);
  if (!bus) throw new Error("useRobotBus must be used inside RobotProvider");
  return bus;
}
