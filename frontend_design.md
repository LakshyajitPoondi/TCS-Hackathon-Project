# frontend_design.md — Production Intelligence & RCA

> **Build order:** This is the LAST phase. Do not start until all backend phases are complete and APIs are stable. Read `progress.md` for the final endpoint list and response shapes before building any page.
> **Reference site:** https://www.ciklum.com (visual language only — do not copy logos, copy text, videos or brand marks).
> **Hard rule:** Light theme only. No dark mode, no theme toggle, no `prefers-color-scheme` handling.

---

## 0. How to use this document (for the coding agent)

1. Read the whole file before writing any UI code. Then read `progress.md` for real endpoint names, IDs (INC-xxx, IMM-01..03), event codes, batch names and signal names. Use those exactly in the UI — never invent new names.
2. Set up the design tokens in §2–§4 first (CSS variables + Tailwind config). Every component must use tokens — no raw hex values inside components.
3. Build shared components (§6) before pages (§7).
4. Build the robot (§8) as an isolated component and test it on a blank page before putting it into the auth screen.
5. Run the checklist in §11 before calling the frontend done.

Stack: React + Vite + TypeScript + Tailwind CSS, talking to the existing FastAPI backend. Animation: `framer-motion`. Icons: `lucide-react`. Charts: `recharts`.

---

## 1. Design theme — what the site "feels" like

**One-line summary:** *Clean enterprise white canvas + deep indigo authority + a glowing indigo→cyan→mint "AI aura".*

Key traits observed on ciklum.com:

| Trait | Description |
|---|---|
| Canvas | Pure white page, lots of empty space, content left-aligned in a wide container. |
| Authority color | Deep royal indigo used for primary buttons, accent headline lines, and key numbers. |
| AI accent | A soft, blurred radial "orb" of violet → blue → cyan → mint glowing behind hero visuals. Faint binary/matrix texture inside the glow. |
| Glassmorphism | Frosted translucent cards with thin white borders sitting on top of the glow. |
| Shape language | Everything is rounded: pill buttons, pill navbar, 20–28px card radii. Nothing sharp. |
| Typography | Large, bold, tight-tracked geometric sans headlines; light, airy body text in slate gray. |
| Headline device | Multi-line hero where line 1 is dark navy, lines 2–3 are indigo, and the last word fades into a teal/mint gradient. |
| Motion | Calm and premium: slow glow drift, soft fades/slides on scroll, count-up numbers. No bouncy or flashy motion except the robot. |
| Buttons | Pill-shaped, label on the left, arrow icon on the right. Primary = indigo, Secondary = mint. |

---

## 2. Color tokens

> Values were sampled from the live site's rendered hero (not from source CSS). They are close matches; if exact brand hex is needed, verify with DevTools on ciklum.com and only update the token values.

```css
:root {
  color-scheme: light;               /* force light, browsers must not auto-darken */

  /* Brand */
  --c-indigo-900: #141B7A;           /* pressed state, deep text accent */
  --c-indigo-700: #1F2AB3;           /* PRIMARY — buttons, accent headlines */
  --c-indigo-600: #2E3BD1;           /* hover */
  --c-indigo-500: #4652E6;           /* links, focus ring base */
  --c-indigo-100: #E7E9FD;           /* tinted backgrounds, chips */
  --c-indigo-50:  #F3F4FF;

  --c-mint-400:   #8EF2C2;           /* SECONDARY button bg */
  --c-mint-300:   #B5F7D6;           /* secondary hover */
  --c-mint-100:   #E6FCF1;

  --c-cyan-400:   #3CD7F0;           /* glow mid tone */
  --c-violet-500: #6C5CF2;           /* glow top tone */
  --c-teal-500:   #5E9FAE;           /* end of headline gradient */

  /* Neutrals */
  --c-ink-900:    #0B1230;           /* headings */
  --c-ink-700:    #2A3150;           /* strong body */
  --c-slate-600:  #4B5470;           /* body text */
  --c-slate-500:  #6B7390;           /* muted / captions */
  --c-slate-300:  #C9CEDD;           /* borders strong */
  --c-slate-200:  #E3E6EF;           /* borders */
  --c-slate-100:  #F1F3F8;           /* input bg, section alt bg */
  --c-white:      #FFFFFF;

  /* Semantic */
  --c-bg:          var(--c-white);
  --c-surface:     var(--c-white);
  --c-surface-alt: #F7F8FC;
  --c-text:        var(--c-slate-600);
  --c-heading:     var(--c-ink-900);
  --c-primary:     var(--c-indigo-700);
  --c-secondary:   var(--c-mint-400);
  --c-border:      var(--c-slate-200);

  --c-success: #12B886;
  --c-warning: #F2A33A;
  --c-danger:  #E5484D;
  --c-info:    var(--c-indigo-500);

  /* Incident severity (saturated but not neon) */
  --c-sev-critical: #D92D4A;
  --c-sev-high:     #F0703A;
  --c-sev-medium:   #F2B33A;
  --c-sev-low:      #3BA3F0;

  /* Machine status */
  --c-machine-running:     #12B886;
  --c-machine-idle:        #8A93AD;
  --c-machine-fault:       #E5484D;
  --c-machine-maintenance: #F2A33A;

  /* RCA confidence (used on cause ranking bars) */
  --c-conf-high:   var(--c-indigo-700);
  --c-conf-medium: var(--c-indigo-500);
  --c-conf-low:    var(--c-slate-300);
}
```

### Gradients

```css
:root {
  /* Logo-style ring gradient (indigo → cyan → mint) */
  --g-brand: linear-gradient(135deg, #1F2AB3 0%, #3C7BF0 45%, #3CD7F0 70%, #8EF2C2 100%);

  /* Headline last-word fade */
  --g-headline: linear-gradient(90deg, #2E3BD1 0%, #4E7FD0 55%, #6FB3B8 100%);

  /* The AI aura orb — use as stacked radial gradients + blur */
  --g-aura:
    radial-gradient(40% 40% at 50% 30%, rgba(108, 92, 242, 0.85) 0%, transparent 70%),
    radial-gradient(45% 45% at 35% 55%, rgba(60, 123, 240, 0.75) 0%, transparent 70%),
    radial-gradient(45% 45% at 65% 60%, rgba(60, 215, 240, 0.70) 0%, transparent 70%),
    radial-gradient(50% 45% at 50% 80%, rgba(142, 242, 194, 0.80) 0%, transparent 70%);
}
```

Usage rules:
- Indigo is for **actions and emphasis**, never for large background fills.
- The aura is **decorative only**, max 1 per screen, always behind content, `filter: blur(40px–60px)`, `pointer-events: none`.
- Mint is only for the secondary button, success states, "running" machines and the robot's eye glow.
- Severity and machine-status colors are only for badges, chart markers and status dots — never for buttons.
- Body text is never pure black — use `--c-text`.

---

## 3. Typography

The site uses a modern geometric grotesk with bold, tight headlines and light body copy. The exact commercial font could not be confirmed from the page source; use the closest free match:

| Role | Font | Fallback |
|---|---|---|
| Headings + UI | **Plus Jakarta Sans** (Google Fonts) | `Inter, system-ui, sans-serif` |
| Body | **Plus Jakarta Sans** 400 | same |
| Mono (incident IDs, machine IDs, batch IDs, event codes, signal names, timestamps, sensor values) | **JetBrains Mono** | `ui-monospace, monospace` |

> Verification step: open ciklum.com → DevTools → inspect the hero `h1` → Computed → `font-family`. If a free font is used, swap `--font-sans` to it. Do not change any other token.

```css
:root {
  --font-sans: "Plus Jakarta Sans", Inter, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}
```

### Type scale (desktop → mobile)

| Token | Size | Weight | Line-height | Tracking | Use |
|---|---|---|---|---|---|
| `display` | 64px → 40px | 700 | 1.08 | -0.02em | Landing hero only |
| `h1` | 48px → 34px | 700 | 1.12 | -0.02em | Page titles |
| `h2` | 36px → 28px | 700 | 1.2 | -0.015em | Section titles |
| `h3` | 24px → 20px | 600 | 1.3 | -0.01em | Card titles |
| `h4` | 18px | 600 | 1.4 | 0 | Small headings |
| `eyebrow` | 14px | 600 | 1.4 | 0.02em | Small label above section titles — indigo color |
| `body-lg` | 20px → 18px | 400 | 1.55 | 0 | Hero sub-copy |
| `body` | 16px | 400 | 1.6 | 0 | Default |
| `body-sm` | 14px | 400 | 1.5 | 0 | Table cells, meta |
| `caption` | 12px | 500 | 1.4 | 0.02em | Badges, helper text |
| `stat` | 56px → 40px | 700 | 1 | -0.02em | KPI numbers (indigo) |

Headline pattern (signature look — use on landing hero and auth left panel):
```
Line 1  → color: --c-heading            "Find the Root Cause."
Line 2  → color: --c-primary            "Read Every Signal."
Line 3  → first words --c-primary,
          last word background: --g-headline; background-clip: text; color: transparent
                                         "Prevent the Next Failure."
```

---

## 4. Spacing, radius, shadows, layout

```css
:root {
  /* 4px base scale */
  --s-1: 4px;  --s-2: 8px;  --s-3: 12px; --s-4: 16px; --s-5: 20px;
  --s-6: 24px; --s-8: 32px; --s-10: 40px; --s-12: 48px; --s-16: 64px;
  --s-20: 80px; --s-24: 96px; --s-32: 128px;

  --r-sm: 8px;
  --r-md: 12px;     /* inputs, small chips */
  --r-lg: 20px;     /* cards */
  --r-xl: 28px;     /* hero glass panels, auth card */
  --r-pill: 9999px; /* buttons, navbar, badges */

  --sh-nav:   0 8px 30px rgba(11, 18, 48, 0.06);
  --sh-card:  0 2px 6px rgba(11, 18, 48, 0.04), 0 12px 32px rgba(11, 18, 48, 0.06);
  --sh-hover: 0 4px 10px rgba(11, 18, 48, 0.06), 0 20px 48px rgba(31, 42, 179, 0.12);
  --sh-glow:  0 0 0 1px rgba(255,255,255,0.6), 0 20px 60px rgba(60, 123, 240, 0.25);
  --ring:     0 0 0 4px rgba(70, 82, 230, 0.18);
}
```

Layout:
- Container max width **1320px**, side padding 24px (mobile 16px).
- Section vertical padding: **96px** desktop, **64px** mobile.
- 12-column grid, 24px gutter.
- Hero split: text 5 columns left, visual 7 columns right.
- Breakpoints: `sm 640`, `md 768`, `lg 1024`, `xl 1280`, `2xl 1536`.

---

## 5. Motion principles

| Token | Value |
|---|---|
| `--ease-out` | `cubic-bezier(0.22, 1, 0.36, 1)` |
| `--ease-in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` |
| `--dur-fast` | 150ms (hover, focus) |
| `--dur-base` | 250ms (dropdowns, tabs) |
| `--dur-slow` | 600ms (section reveals) |

- **Scroll reveal:** fade + translateY(24px → 0), 600ms, stagger children 80ms. Trigger once at 20% visibility.
- **Hover on cards:** translateY(-4px) + `--sh-hover`, 250ms.
- **Buttons:** arrow icon slides 4px right on hover.
- **Aura orb:** slow drift — each radial layer moves ±3% and rotates over 18–24s, infinite, alternate.
- **Stats:** count up from 0 when visible, 1.6s, ease-out.
- **Charts:** lines draw in left→right over 800ms on first load only; no animation on data refresh.
- Respect `prefers-reduced-motion: reduce` → disable drift, reveals become instant opacity, robot uses reduced mode (§8.9).

---

## 6. Components

### 6.1 Navbar
- Floating **pill** container, centered, max-width 1320px, top offset 16px, height 72px.
- Background `rgba(255,255,255,0.85)` + `backdrop-filter: blur(16px)`, shadow `--sh-nav`, radius `--r-pill`.
- Left: logo (gear/pulse icon inside a `--g-brand` ring + wordmark "Production Intelligence" in ink-900, 700; a small "RCA" chip after it in `--c-indigo-50`/indigo).
- Center: nav links, 16px / 500 / `--c-ink-700`. Items with a dropdown show a tiny 4px indigo dot after the label (as on Ciklum).
- Right: outline pill CTA — 1px `--c-indigo-700` border, indigo label, with a 44px filled indigo circle on the right containing a white arrow.
- Sticky; on scroll > 24px, increase background opacity to 0.95.
- Mobile (< lg): logo + hamburger; menu opens as a full-width white sheet sliding down.

### 6.2 Buttons
| Variant | Style |
|---|---|
| **Primary** | bg `--c-primary`, text white 16px/600, height 56px, padding 0 28px, radius pill, trailing `ArrowRight` 20px. Hover bg `--c-indigo-600`, active `--c-indigo-900`. |
| **Secondary** | bg `--c-secondary` (mint), text `--c-ink-900`, same shape. Hover `--c-mint-300`. |
| **Outline** | transparent, 1px indigo border, indigo text. Hover bg `--c-indigo-50`. |
| **Ghost** | text indigo, no border, underline on hover. Used for "View all" / "Open incident" links. |
| **Danger** | bg `--c-danger`, white text. Only for destructive confirmations. |
| Sizes | `lg` 56px, `md` 48px, `sm` 36px (14px text). |
| Disabled | opacity 0.45, no hover. Loading: spinner replaces arrow, label stays. |
| Focus | `box-shadow: var(--ring)`. Always visible on keyboard focus. |

### 6.3 Cards
- **Standard card:** white, 1px `--c-border`, radius `--r-lg`, padding 32px, `--sh-card`. Hover lift.
- **Glass card** (only on top of the aura): `background: rgba(255,255,255,0.35)`, `backdrop-filter: blur(18px) saturate(140%)`, `border: 1.5px solid rgba(255,255,255,0.7)`, radius `--r-lg`, text indigo/ink. Highlighted number inside is indigo 700.
- **Feature card:** icon in a 56px rounded-square tile filled with `--c-indigo-50`, icon stroke indigo; then h3, body, ghost link.
- **Stat / KPI card:** big `stat` number in indigo, label h4 below, caption muted under it (e.g. "Open incidents", "Machines in fault", "Avg time to root cause", "RCA accuracy vs answer key").
- **Root-cause card:** rank number (1, 2, 3) in a 40px indigo circle, cause title h3, confidence bar (8px pill track `--c-slate-100`, fill `--c-conf-*`, % label in mono), then an "Evidence" list where each item shows a signal name chip (mono), machine ID, and the observed vs normal value (e.g. `81.2°C vs 65.0°C`). Rank 1 card gets a 2px indigo border.

### 6.4 Inputs
- Height 52px, radius `--r-md`, bg `--c-slate-100`, border 1px transparent, text `--c-ink-900` 16px.
- Label above: 13px / 600 / `--c-ink-700`, sentence case.
- Leading icon 20px `--c-slate-500`.
- Focus: bg white, border `--c-indigo-500`, `--ring`.
- Error: border `--c-danger`, helper text 13px danger below, input shakes 4px × 3 (200ms).
- Password field: trailing eye toggle button (also drives robot "peek", §8).

### 6.5 File upload (CSV)
- Dashed 2px `--c-slate-300` dropzone, radius `--r-lg`, bg `--c-surface-alt`, upload icon in an indigo-50 tile, "Drop a CSV or browse" text.
- Drag-over: border `--c-indigo-500`, bg `--c-indigo-50`.
- After select: file row with name (mono), size, remove button, and a primary "Upload" button.
- Backend 422 errors (missing column, empty file, bad dates, text in number columns, broken CSV) are shown in a danger-tinted alert inside the dropzone using the backend's message text as-is.

### 6.6 Badges / chips
- Pill, 24–28px tall, 12px/600 text.
- Status "Engine online": bg `--c-mint-100`, text `#0A7A4F`, 6px pulsing mint dot.
- Severity badges: tinted bg (10% of severity color) + solid severity text.
- Machine status: 8px dot in machine-status color + label ("Running", "Fault"…).
- Signal chips (e.g. `temp_up`): mono 12px, bg `--c-indigo-50`, text indigo-700.
- Mock marker: if any API response is still marked `[MOCK]`, show a small warning-tinted "Mock data" chip next to that section's title. Never hide this.

### 6.7 Tables (incidents, raw readings, cases)
- White surface, header row bg `--c-surface-alt`, header 13px/600 `--c-slate-500`.
- Row height 56px, divider 1px `--c-border`, hover bg `--c-indigo-50`, whole row clickable for incidents.
- Incident IDs, machine IDs, batch IDs, event codes, timestamps and numeric readings in `--font-mono` 13px; numbers right-aligned.
- Raw readings table: sticky header, virtualized if > 500 rows, out-of-normal values shown in danger text.

### 6.8 Charts (sensor readings)
- Library: `recharts`. White card container, 320px tall (240px mobile).
- Grid: horizontal lines only, `--c-slate-200`, dashed 3 3. Axes text 12px `--c-slate-500`, timestamps in mono.
- Series colors in order: `--c-indigo-700`, `--c-cyan-400`, `--c-violet-500`, `--c-teal-500`. Line 2px, no dots except hovered point.
- **Normal baseline:** dashed `--c-slate-500` horizontal line with a label ("Normal 65°C").
- **Incident window:** shaded band `rgba(229, 72, 77, 0.08)` between incident start/end, with a small "Incident" label at the top.
- **Events:** vertical 1px lines at event timestamps, with an event-code chip on hover.
- Tooltip: white card, `--sh-card`, radius `--r-md`, mono values.

### 6.9 Sidebar (app shell after login)
- 264px, white, right border `--c-border`.
- Nav item: 44px tall, radius `--r-md`, icon + label. Active: bg `--c-indigo-50`, text + icon indigo, 3px indigo bar on left.
- Collapsed: 80px icon-only with tooltips.

### 6.10 Toasts / alerts
- Top-right, white card, 4px left border in semantic color, icon + title + body, auto-dismiss 5s.

### 6.11 Empty / not-built states
- For endpoints that return 501 ("not built yet"), show a friendly empty state card: small aura (320px, opacity 0.5), icon, "Coming soon" h3, one line of body. Never show raw error JSON.

### 6.12 Aura component (`<Aura />`)
- Absolutely positioned div, size ~720–900px circle, `background: var(--g-aura)`, `filter: blur(48px)`, opacity 0.9.
- Overlay a faint binary texture: an SVG/CSS pattern of tiny "0 1" glyphs in white at 8–12% opacity, masked with a radial gradient so it only shows in the center.
- Drift animation per §5. `aria-hidden="true"`.

---

## 7. Page layouts

### 7.1 Auth page (Sign in / Sign up) — the only page with the robot

```
┌──────────────────────── page bg: white ────────────────────────┐
│                     <Aura/> centered behind the card            │
│  ┌──────────────── auth card (max 1080px, r-xl) ──────────────┐ │
│  │ LEFT PANEL (glass, 50%)        │ RIGHT PANEL (white, 50%)   │ │
│  │ Logo + "Engine online" badge   │ Eyebrow chip "Plant access" │ │
│  │                                │            [Sign in|Sign up]│ │
│  │      <RcaRobot/> (~340px)      │ h1 "Welcome back"           │ │
│  │                                │ body "Sign in to investigate │ │
│  │ Right of robot: 3 glass chips  │  incidents on the line."    │ │
│  │  • Detect – Sensor anomalies   │ Email input                 │ │
│  │  • Diagnose – Ranked root cause│ Password input (+eye)       │ │
│  │  • Learn – Memory of past      │ Quick demo profiles:        │ │
│  │    incidents                   │  [Plant engineer] [QA lead] │ │
│  │                                │ [Open dashboard →] primary   │ │
│  │ Footer: ● RCA engine v1.0      │ ● Data source connected     │ │
│  └────────────────────────────────┴─────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

- Card: white, radius `--r-xl`, `--sh-glow`, 1px white border.
- Left panel bg: `linear-gradient(160deg, #F3F4FF 0%, #E9F7FF 55%, #E6FCF1 100%)` with the aura partly bleeding in. Capability chips are glass cards; status dot is mint (Detect, Learn) and indigo (Diagnose).
- Sign in / Sign up toggle: segmented pill, track `--c-slate-100`, active segment white with `--sh-card` and indigo text.
- Mobile: left panel collapses to a 220px-tall strip with a smaller robot (200px) above the form.
- If the backend has no auth endpoint by the time the frontend is built, the auth page still ships (demo profiles log in client-side) — confirm with `progress.md`.

### 7.2 App shell (post-login)
- Top bar 72px (white, bottom border), sidebar per §6.9, content bg `--c-surface-alt`.
- Page header: eyebrow + h1 + right-aligned primary action.
- Content in standard cards on a 12-col grid.
- **No aura and no robot** inside the app shell — keep it calm and data-focused. Aura only on empty states (§6.11).

Sidebar items (map to real endpoints in `progress.md`): Dashboard, Incidents, Upload data, Cases, Evaluations.

### 7.3 Dashboard
- Row 1: 4 KPI cards (§6.3).
- Row 2: "Recent incidents" table (8 cols) + "Machines" card (4 cols) listing IMM-01..03 with status dots.
- Row 3: "Top recurring causes" card — horizontal bars using `--c-conf-*` colors.

### 7.4 Incidents list
- Filter bar: search (incident ID), machine select, severity select, date range — all pill-shaped inputs in one row.
- Table per §6.7: ID, machine, start time, duration, severity, top cause, status.

### 7.5 Incident detail / RCA result (the most important page)
- Header: incident ID (mono, h1 size), severity badge, machine chip, time window, primary "Run analysis" button (calls `/analyze`; robot not used here — use a button spinner).
- Left (8 cols): sensor chart (§6.8) with baseline + incident band + events; below it, tabs: Summary | Raw readings | Events.
- Right (4 cols): ranked root-cause cards (§6.3), then "Similar past incidents" list (from memory) with ghost links.
- Bottom: "Recommended actions" checklist card.

### 7.6 Upload data
- Centered 720px column: h1, short explainer, dropzone (§6.5), then "Expected columns" card listing required columns in mono chips.

### 7.7 Cases & Evaluations
- Cases: card grid of saved investigations (ID, machine, cause, date).
- Evaluations: KPI row (accuracy, top-3 accuracy, incidents evaluated) + table comparing predicted cause vs expected cause per incident, with a green check / red cross column.
- Both show §6.11 empty state while the endpoints return 501.

### 7.8 Landing page (if built)
Section order mirroring Ciklum's rhythm:
1. Hero: 3-line gradient headline (§3), body-lg sub-copy (max 520px), Primary ("Open dashboard") + Secondary ("See how it works") buttons; right side Aura + glass panel with product name and 4 glass stat chips in a 2×2 grid (e.g. "18 incidents analyzed", "3 machines monitored", "Top-3 cause accuracy", "Memory of past incidents").
2. Eyebrow + h2 + 3 feature cards (Detect / Diagnose / Learn).
3. Stats band: 4 stat cards with count-up.
4. "How it works" alternating text/visual rows: Upload data → Detect anomalies → Rank causes → Learn.
5. CTA band: large rounded panel (r-xl) with aura behind, h2 + primary button.
6. Footer: white, link columns, 14px links in `--c-slate-600`, bottom bar with © and team/hackathon credit.

---

## 8. RCA robot — interactive auth mascot

### 8.1 Purpose
A friendly 3D-looking robot on the auth screen that **reacts to the cursor and to the form**, making login feel alive. It exists **only** on the auth route and must be lazy-loaded so it never affects app bundle size. Component name: `RcaRobot`.

### 8.2 Visual design (light theme)
Built as **layered SVG** (no 3D engine needed) with gradients to fake depth.

| Part | Look |
|---|---|
| Head | Rounded rectangle (radius ~38% of width), glossy white→`#EEF0FA` vertical gradient, subtle 1px `#DDE1F0` rim, top-left specular highlight (white ellipse, 60% opacity). |
| Visor/screen | Inset rounded rect, deep indigo gradient `#141B7A → #1F2AB3`, inner shadow, faint reflection streak. |
| Eyes | Two vertical rounded pills, fill mint `#8EF2C2` with `--c-cyan-400` outer glow (`filter: drop-shadow(0 0 8px #3CD7F0)`). |
| Ear pods / headphones | Circular discs on each side, gradient `--g-brand`, glossy ring. |
| Neck | Short dark indigo cylinder. |
| Body | Rounded egg-shaped torso, white glossy; small gear/pulse emblem on chest in `--g-brand` with a soft pulse. |
| Arms | Rounded flipper arms, white with mint/cyan cuffs. |
| Base | Two wheel pods with mint glowing rims. |
| Shadow | Soft ellipse under the robot, `rgba(31,42,179,0.15)`, blur 12px; scales with the float animation. |

Size: 340px wide desktop, 200px mobile. Group the SVG into separately transformable layers: `shadow`, `body`, `arms(L,R)`, `neck`, `head`, `visor`, `eyes(L,R)`, `pupil-highlights`, `ears(L,R)`.

### 8.3 Cursor tracking (core behaviour)
On `pointermove` over the **whole window** (not just the card):

1. Compute the robot's head center `(cx, cy)` from `getBoundingClientRect()` (recompute on resize/scroll).
2. `dx = clientX - cx`, `dy = clientY - cy`.
3. Normalize: `nx = clamp(dx / (window.innerWidth / 2), -1, 1)`, `ny = clamp(dy / (window.innerHeight / 2), -1, 1)`.
4. Map to targets:

| Layer | Property | Range |
|---|---|---|
| Eyes (both) | translate x / y | ±10px / ±7px (inside visor bounds) |
| Head | translateX + rotate | translateX ±8px, rotate ±6° (tilt toward cursor) |
| Head | translateY | ±4px (looks up/down) |
| Visor reflection | translate opposite direction | ∓6px (parallax gloss) |
| Body | rotate | ±2.5° (lean, lags behind head) |
| Ears | translateX | ±3px (parallax) |
| Shadow | translateX | ±6px opposite of lean |

5. **Smoothing:** never set values directly. Use a `requestAnimationFrame` loop that lerps current → target:
   - eyes `lerp 0.25` (snappy), head `0.12`, body `0.06` (heavy, delayed). This lag hierarchy is what makes it feel alive.
   - Or framer-motion `useSpring`: eyes `{stiffness: 300, damping: 25}`, head `{stiffness: 120, damping: 18}`, body `{stiffness: 60, damping: 14}`.
6. Store the latest pointer in a ref and read it inside the rAF loop; never set React state per mousemove.

### 8.4 Idle behaviours
| Behaviour | Rule |
|---|---|
| Float | Whole robot translateY 0 → -8px → 0, 3.2s ease-in-out infinite; shadow scales 1 → 0.9 in sync. |
| Blink | Eyes scaleY 1 → 0.1 → 1 over 140ms; random interval 2.5–5.5s; 15% chance of a double-blink. |
| Look around | If no pointer movement for 4s, eyes/head drift to random points every 1.5–2.5s (slow springs). Any movement resumes tracking instantly. |
| Chest pulse | Emblem glow opacity 0.6 ↔ 1, 2.4s. |
| Pointer leaves window | Return to center over 600ms, then idle look-around. |

### 8.5 Form-aware reactions (state machine)

States: `idle | tracking | watchingEmail | privacy | peeking | thinking | success | error`

| Trigger | State | Robot reaction |
|---|---|---|
| Pointer moves | `tracking` | §8.3 |
| Email input focused | `watchingEmail` | Eyes look toward the input; while typing, eye X follows caret position (`input.selectionStart / value.length` mapped across input width), head tilts slightly. Small nod every ~6 keystrokes. |
| Password input focused | `privacy` | Arms rise and cover the visor (300ms spring), eyes shrink to thin lines and look down; cursor tracking paused. |
| Show-password toggled ON | `peeking` | One arm lowers a little; one eye peeks through the gap, glancing at the field, then back. Toggle OFF → back to `privacy`. |
| Password blur | back to `tracking` | Arms lower, eyes reopen with a blink. |
| Submit clicked (request pending) | `thinking` | Eyes become a 3-dot loading animation inside the visor (dots pulse in sequence), head slight side-to-side 1.2s. Tracking paused. |
| Login success | `success` | Eyes morph to happy arcs (`^ ^`), body does one hop (translateY -18px, spring), arms wave once, chest emblem flashes mint. Hold 900ms, then navigate. |
| Login error | `error` | Head shakes "no" (translateX ±10px × 3, 400ms), eyes tint `--c-danger` and become slanted/sad for 1.5s, then back to `tracking`. Form input shake (§6.4) fires at the same time. |
| Quick demo profile clicked | — | Quick wave with right arm; eyes look at the filled field. |
| Sign in ↔ Sign up toggle | — | Head turns toward the toggle, small hop. |

Implementation: a single `useReducer` state machine; each state defines target poses; springs handle transitions. Form components emit events through a `RobotContext` (`onEmailFocus`, `onPasswordFocus`, `onPasswordVisibility`, `onCaret`, `onSubmit`, `onSuccess`, `onError`) so the robot is decoupled from form logic.

### 8.6 Click / hover easter eggs
- Click on robot head → giggle: quick squash (scaleY 0.92 → 1) + eyes become `> <` for 400ms.
- Hover over the chest emblem → emblem glow brightens.
- Max 1 easter-egg animation per 1.5s (debounce).

### 8.7 Touch devices
- On `touchmove` treat the touch point like the cursor; when touch ends, return to center.
- Optional: if `DeviceOrientationEvent` is available and already permitted, map `gamma/beta` to `nx/ny` (±1 at ±30°). Never prompt for permission automatically.
- Form-aware reactions (§8.5) work the same on mobile.

### 8.8 Performance rules
- Only animate `transform` and `opacity` (plus `filter` on the eye glow only).
- One rAF loop for the whole robot; cancel it on unmount or when `document.hidden` is true.
- Lazy-load: `const RcaRobot = lazy(() => import('./RcaRobot'))` with a static SVG fallback of the same size (no layout shift).
- Target 60fps on a mid-range laptop; the robot must not cause input lag in the form.

### 8.9 Accessibility
- Robot wrapper: `role="img"` + `aria-label="Animated assistant robot"`; inner layers `aria-hidden`.
- Purely decorative — errors still appear as text under inputs.
- `prefers-reduced-motion: reduce` → no float, hop or head shake; eyes still follow the cursor with max ±4px and no head movement; state changes are instant pose swaps.
- Must not steal focus or intercept clicks on form controls.

### 8.10 Suggested file structure
```
frontend/src/features/auth/robot/
  RcaRobot.tsx            // composes layers, runs rAF loop
  RobotSvg.tsx            // pure SVG layers with refs
  useCursorTarget.ts      // pointer/touch/orientation → normalized nx, ny
  useRobotState.ts        // state machine + target poses
  poses.ts                // numeric pose definitions per state
  RobotContext.tsx        // event bus used by the auth form
  robot.css               // keyframes: float, blink, pulse
```

---

## 9. Iconography & imagery
- Icons: `lucide-react`, 1.75px stroke, 20px default (24px in feature tiles), color inherits. Suggested: `Activity` (signals), `Factory`/`Cog` (machines), `AlertTriangle` (incidents), `GitBranch` (root cause), `Upload`, `Brain` (memory), `CheckCircle2` (evals).
- Feature icon tiles: 56px, radius 16px, bg `--c-indigo-50`, icon indigo.
- Illustrations: abstract only — aura glows, glass panels, grid/binary textures. No stock photos in the app shell.
- Do not use Ciklum's logo, PRODIGY name, videos or brand assets.

---

## 10. Tailwind config (summary)

```js
// tailwind.config.js
export default {
  darkMode: false,            // light only — do not add any `dark:` classes anywhere
  theme: {
    extend: {
      colors: {
        indigo: { 50:'#F3F4FF',100:'#E7E9FD',500:'#4652E6',600:'#2E3BD1',700:'#1F2AB3',900:'#141B7A' },
        mint:   { 100:'#E6FCF1',300:'#B5F7D6',400:'#8EF2C2' },
        cyan:   { 400:'#3CD7F0' },
        violet: { 500:'#6C5CF2' },
        ink:    { 700:'#2A3150',900:'#0B1230' },
        slate:  { 100:'#F1F3F8',200:'#E3E6EF',300:'#C9CEDD',500:'#6B7390',600:'#4B5470' },
        sev:    { critical:'#D92D4A', high:'#F0703A', medium:'#F2B33A', low:'#3BA3F0' },
        machine:{ running:'#12B886', idle:'#8A93AD', fault:'#E5484D', maintenance:'#F2A33A' },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: { md:'12px', lg:'20px', xl:'28px' },
      boxShadow: {
        nav:  '0 8px 30px rgba(11,18,48,0.06)',
        card: '0 2px 6px rgba(11,18,48,0.04), 0 12px 32px rgba(11,18,48,0.06)',
        hover:'0 4px 10px rgba(11,18,48,0.06), 0 20px 48px rgba(31,42,179,0.12)',
      },
      maxWidth: { container: '1320px' },
    },
  },
};
```
(On Tailwind v4, put the same values in `@theme` in CSS and do not define a dark variant.)

Global CSS must include:
```css
html { color-scheme: light; background: #FFFFFF; }
body { font-family: var(--font-sans); color: var(--c-text); -webkit-font-smoothing: antialiased; }
```
Also add `<meta name="color-scheme" content="light">` in `index.html`.

---

## 11. Done checklist
- [ ] No `dark:` classes, no theme toggle, no `prefers-color-scheme` queries; page stays light with OS in dark mode.
- [ ] All colors/radii/shadows come from tokens.
- [ ] All IDs, machine names, event codes and signal names match `progress.md` / backend data exactly.
- [ ] Hero/auth headline uses the 3-line navy → indigo → gradient pattern.
- [ ] Buttons are pills with trailing arrows; focus ring visible.
- [ ] Incident detail shows chart with normal baseline, incident band and events; root causes ranked with confidence and evidence.
- [ ] Backend 422 messages shown cleanly on upload; 404 shows a "not found" page; 501 shows "Coming soon".
- [ ] Any `[MOCK]` data is visibly labelled "Mock data".
- [ ] Aura appears max once per screen and never inside the app shell (except empty states).
- [ ] Robot: eyes/head/body follow cursor with lagged springs; blinks; idles after 4s.
- [ ] Robot covers eyes on password focus, peeks on show-password, thinks on submit, celebrates on success, shakes on error.
- [ ] Robot works on touch, honors reduced motion, is lazy-loaded, and keeps 60fps.
- [ ] Layout holds at 375px, 768px, 1280px, 1536px.
- [ ] Text contrast ≥ 4.5:1 (slate-600 on white passes; never put body text on the aura without a glass card).
