import { lazy, Suspense, useEffect, useRef, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Activity, Eye, EyeOff, Lock, Mail, User as UserIcon } from "lucide-react";
import { useAuth } from "../auth";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";
import { errorMessage, request } from "../api/client";
import { RobotProvider, useRobotBus } from "../features/auth/robot/RobotContext";
import { RobotFallback, ROBOT_SIZE } from "../features/auth/robot/RobotFallback";

// The robot and framer-motion live in their own chunk (§8.8); the fallback has the same size (no layout shift).
const RcaRobot = lazy(() => import("../features/auth/robot/RcaRobot"));

interface DemoProfile { label: string; role: string; email: string; password?: string }
interface PublicConfig { app_version: string; demo_users_enabled: boolean; demo_profiles: DemoProfile[]; signup_enabled: boolean }
type Mode = "signin" | "signup";

const CHIPS = [
  { title: "Detect", body: "Sensor anomalies", dot: "bg-mint-400" },
  { title: "Diagnose", body: "Ranked hypotheses", dot: "bg-indigo-700" },
  { title: "Learn", body: "Memory of past incidents", dot: "bg-mint-400" },
];

function useEngine() {
  const [online, setOnline] = useState<boolean | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  useEffect(() => {
    let alive = true;
    request<{ status: string }>("/health").then(() => alive && setOnline(true)).catch(() => alive && setOnline(false));
    request<PublicConfig>("/api/public/config").then((c) => alive && setConfig(c)).catch(() => {});
    return () => { alive = false; };
  }, []);
  return { online, config };
}

function StatusDot({ on, children }: { on: boolean | null; children: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs font-semibold text-ink-700">
      <span className={`h-2 w-2 rounded-full ${on === false ? "bg-warning" : "bg-success"} ${on ? "animate-pulse" : ""}`} aria-hidden="true" />
      {children}
    </span>
  );
}

function AuthForm({ config, onCelebrate }: { config: PublicConfig | null; onCelebrate: (on: boolean) => void }) {
  const { login } = useAuth();
  const robot = useRobotBus();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [shake, setShake] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  const caret = (el: HTMLInputElement) => robot.emit({ type: "caret", ratio: el.value.length ? (el.selectionStart ?? el.value.length) / el.value.length : 0 });
  const switchMode = (m: Mode) => { if (m === mode) return; setMode(m); setError(""); setNotice(""); robot.emit({ type: "modeToggle" }); };
  const fail = (message: string) => {
    setError(message); robot.emit({ type: "error" });
    setShake(true); window.setTimeout(() => setShake(false), 220);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(""); setNotice("");
    robot.emit({ type: "submit" });
    try {
      if (mode === "signup") {
        const r = await request<{ message: string }>("/api/auth/signup", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, email, password }),
        });
        robot.emit({ type: "success" });
        setNotice(r.message); setMode("signin"); setPassword("");
        window.setTimeout(() => robot.emit({ type: "reset" }), 1200);
        return;
      }
      onCelebrate(true);
      await login(email, password);
      robot.emit({ type: "success" });
      // Hold the success pose for 900 ms (§8.5), instantly with reduced motion.
      window.setTimeout(() => navigate("/", { replace: true }), reduced ? 0 : 900);
    } catch (err) {
      onCelebrate(false);
      fail(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const fillDemo = (p: DemoProfile) => {
    setMode("signin"); setEmail(p.email); setPassword(p.password ?? ""); setError("");
    robot.emit({ type: "demoProfile" });
    emailRef.current?.focus({ preventScroll: true });
  };

  const field = `h-[52px] w-full rounded-md border bg-slate-100 pl-11 pr-4 text-base text-ink-900 transition-colors duration-150 focus:border-indigo-500 focus:bg-white focus:shadow-ring focus:outline-none ${error ? "border-danger" : "border-transparent"} ${shake ? "rr-input-shake" : ""}`;
  const demo = (config?.demo_profiles ?? []).filter((p) => p.password);

  return (
    <section className="p-6 sm:p-10 lg:p-12">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">Plant access</span>
        <div role="tablist" aria-label="Sign in or sign up" className="inline-flex rounded-full bg-slate-100 p-1">
          {(["signin", "signup"] as Mode[]).map((m) => (
            <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => switchMode(m)}
              className={`rounded-full px-4 py-1.5 text-sm font-semibold transition-colors duration-150 ${mode === m ? "bg-white text-indigo-700 shadow-card" : "text-slate-600 hover:text-ink-900"}`}>
              {m === "signin" ? "Sign in" : "Sign up"}
            </button>
          ))}
        </div>
      </div>
      <h1 className="mt-6 text-3xl font-bold tracking-tight text-ink-900 sm:text-4xl">{mode === "signin" ? "Welcome back" : "Request access"}</h1>
      <p className="mt-2 text-[15px] text-slate-600">
        {mode === "signin" ? "Sign in to investigate incidents on the line." : "New accounts start as viewers and need an administrator to activate them."}
      </p>
      <form onSubmit={submit} noValidate className="mt-8 space-y-5">
        {mode === "signup" && (
          <div>
            <label htmlFor="auth-name" className="mb-1.5 block text-[13px] font-semibold text-ink-700">Full name</label>
            <div className="relative">
              <UserIcon size={20} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden="true" />
              <input id="auth-name" className={field} autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} />
            </div>
          </div>
        )}
        <div>
          <label htmlFor="auth-email" className="mb-1.5 block text-[13px] font-semibold text-ink-700">Email</label>
          <div className="relative">
            <Mail size={20} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden="true" />
            <input id="auth-email" ref={emailRef} className={field} type="email" autoComplete="username" required value={email}
              aria-invalid={!!error} aria-describedby={error ? "auth-error" : undefined}
              onFocus={(e) => { robot.emit({ type: "emailFocus" }); caret(e.currentTarget); }}
              onBlur={() => robot.emit({ type: "emailBlur" })}
              onChange={(e) => { setEmail(e.target.value); caret(e.target); }}
              onSelect={(e) => caret(e.currentTarget)} />
          </div>
        </div>
        <div>
          <label htmlFor="auth-password" className="mb-1.5 block text-[13px] font-semibold text-ink-700">Password</label>
          <div className="relative">
            <Lock size={20} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden="true" />
            <input id="auth-password" className={`${field} pr-12`} type={show ? "text" : "password"} required minLength={mode === "signup" ? 10 : undefined}
              autoComplete={mode === "signin" ? "current-password" : "new-password"} value={password}
              aria-invalid={!!error} aria-describedby={error ? "auth-error" : undefined}
              onFocus={() => robot.emit({ type: "passwordFocus" })} onBlur={() => robot.emit({ type: "passwordBlur" })}
              onChange={(e) => setPassword(e.target.value)} />
            <button type="button" onClick={() => { const next = !show; setShow(next); robot.emit({ type: "passwordVisibility", visible: next }); }}
              onMouseDown={(e) => e.preventDefault()}
              aria-label={show ? "Hide password" : "Show password"} aria-pressed={show}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-2 text-slate-500 hover:bg-white hover:text-indigo-700 focus-visible:shadow-ring">
              {show ? <EyeOff size={20} aria-hidden="true" /> : <Eye size={20} aria-hidden="true" />}
            </button>
          </div>
          {mode === "signup" && <p className="mt-1 text-xs text-slate-500">10–72 characters.</p>}
        </div>
        {error && <p id="auth-error" role="alert" className="text-[13px] font-medium text-danger-ink">{error}</p>}
        {notice && <Alert tone="success" title="Account created">{notice}</Alert>}
        {mode === "signin" && (
          // Height is reserved before /api/public/config answers, so the card never shifts (§8.8).
          <div className="min-h-[112px]">
            {demo.length > 0 ? (
              <>
                <p className="mb-2 text-[13px] font-semibold text-ink-700">Quick demo profiles</p>
                {/* Fixed 2 x 2 grid: the layout does not change when the web font arrives. */}
                <div className="grid grid-cols-2 gap-2">
                  {demo.map((p) => (
                    <Button key={p.email} type="button" size="sm" variant="outline" className="w-full" onClick={() => fillDemo(p)}>{p.label}</Button>
                  ))}
                </div>
              </>
            ) : config ? (
              <p className="pt-2 text-sm text-slate-500">Accounts are created by an administrator. New here? Use Sign up to request access.</p>
            ) : null}
          </div>
        )}
        <Button type="submit" size="lg" loading={busy} arrow className="w-full">{mode === "signin" ? "Open dashboard" : "Create account"}</Button>
      </form>
    </section>
  );
}

export function LoginPage() {
  const { user } = useAuth();
  const [celebrating, setCelebrating] = useState(false);
  const { online, config } = useEngine();
  if (user && !celebrating) return <Navigate to="/" replace />;
  return (
    <RobotProvider>
      <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white p-4 sm:p-8">
        <div aria-hidden="true" className="aura absolute h-[760px] w-[760px] max-w-none opacity-60" />
        <div className="relative grid w-full max-w-[1080px] overflow-hidden rounded-xl border border-white bg-white shadow-glow md:grid-cols-2">
          <section className="auth-glass relative flex flex-col p-5 sm:p-8 md:p-10">
            <div className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-700 text-white ring-4 ring-cyan-400/40" aria-hidden="true"><Activity size={18} /></span>
                <span className="font-bold text-ink-900">Production Intelligence <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] text-indigo-700">RCA</span></span>
              </span>
              <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${online === false ? "bg-warning-tint text-warning-ink" : "bg-mint-100 text-success-ink"}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${online === false ? "bg-warning" : "bg-success animate-pulse"}`} aria-hidden="true" />
                {online === false ? "Engine offline" : "Engine online"}
              </span>
            </div>
            <h2 className="mt-6 hidden text-[28px] font-bold leading-tight tracking-tight md:block">
              <span className="block text-ink-900">Read every signal.</span>
              <span className="block text-indigo-700">Rank every hypothesis.</span>
              <span className="block text-indigo-700">Prevent the next <span className="text-gradient-headline">failure.</span></span>
            </h2>
            <div className="mt-4 flex flex-1 flex-col items-center gap-4 md:mt-6 md:flex-row md:items-center">
              <Suspense fallback={<RobotFallback className={ROBOT_SIZE} />}>
                <RcaRobot className={`${ROBOT_SIZE} shrink-0`} />
              </Suspense>
              <ul className="hidden w-full flex-col gap-3 md:flex md:w-auto">
                {CHIPS.map((c) => (
                  <li key={c.title} className="glass-chip rounded-lg px-4 py-3">
                    <span className="flex items-center gap-2 text-sm font-bold text-indigo-700"><span className={`h-2 w-2 rounded-full ${c.dot}`} aria-hidden="true" />{c.title}</span>
                    <span className="mt-0.5 block text-xs text-ink-700">{c.body}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="mt-4 hidden flex-wrap justify-between gap-3 border-t border-white/70 pt-4 md:flex">
              <StatusDot on={online}>{`RCA engine v${config?.app_version ?? "…"}`}</StatusDot>
              <StatusDot on={online}>{online === false ? "Data source unavailable" : "Data source connected"}</StatusDot>
            </div>
          </section>
          <AuthForm config={config} onCelebrate={setCelebrating} />
        </div>
      </main>
    </RobotProvider>
  );
}
