---
name: StaxCloud
description: "Run your business. Grow your business. One intelligent system."
colors:
  # Light theme (:root / [data-theme="light"], crates/openfang-api/static/css/theme.css)
  canvas-parchment: "#f4f2ec"
  chrome-linen: "#f1eee7"
  surface-white: "#ffffff"
  raised-sand: "#e9e5db"
  border-stone: "#d9d4c8"
  border-stone-light: "#c9c3b4"
  border-hairline: "#e3ded2"
  border-taupe-strong: "#b3ac9c"
  ink: "#1b1a17"
  ink-secondary: "#3f3c36"
  ink-dim: "#55524b"
  ink-muted: "#8a867c"
  accent-teal: "#146e68"
  accent-teal-light: "#1d857e"
  accent-teal-deep: "#0f5a55"
  accent-teal-glow: "rgba(20, 110, 104, 0.12)"
  accent-teal-subtle: "rgba(20, 110, 104, 0.06)"
  user-bubble-mint: "#e6f2f0"
  on-accent-white: "#FFFFFF"
  success-forest: "#226d3c"
  error-brick: "#9f2520"
  warning-umber: "#8a5410"
  info-slate-blue: "#3f6486"
  section-studio-plum: "#885264"
  section-system-slate: "#576373"
  # Dark theme ([data-theme="dark"], theme.css)
  canvas-night: "#0c0c0e"
  surface-graphite: "#121214"
  elevated-graphite: "#18181b"
  raised-graphite: "#1e1e21"
  border-iron: "#2a2a2e"
  border-iron-light: "#3a3a3f"
  border-hairline-dark: "#222226"
  border-strong-dark: "#4a4a50"
  ink-dark: "#e8e4dc"
  ink-secondary-dark: "#cac5ba"
  ink-dim-dark: "#9a9aa0"
  ink-muted-dark: "#6f6f76"
  accent-sea-glass: "#5cbcae"
  accent-sea-glass-light: "#7fd1c5"
  accent-sea-glass-glow: "rgba(92, 188, 174, 0.15)"
  user-bubble-deep-teal: "#0f2a27"
  success-dark: "#73d391"
  error-dark: "#ff8179"
  warning-dark: "#e3a857"
  info-dark: "#86acd1"
  section-channels-dark: "#7fa3c4"
  section-studio-dark: "#c98ea1"
  section-system-dark: "#9aa6b6"
typography:
  display:
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "clamp(30px, 7.4vw, 40px)"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    letterSpacing: "-0.025em"
  title:
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    letterSpacing: "-0.015em"
  page-title:
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  body:
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  body-base:
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  label:
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "11.5px"
    fontWeight: 700
    lineHeight: "32px"
    letterSpacing: "0.07em"
  dock-label:
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "10.5px"
    fontWeight: 600
    letterSpacing: ".01em"
  mono:
    fontFamily: "'Geist Mono', 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace"
    fontSize: "12px"
rounded:
  xs: "4px"
  sm: "6px"
  md: "10px"
  lg: "14px"
  xl: "16px"
  pill: "999px"
spacing:
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "6": "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent-teal}"
    textColor: "{colors.on-accent-white}"
    typography: "{typography.body-base}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.accent-teal-deep}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-dim}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
    height: "44px"
  button-ghost-hover:
    backgroundColor: "{colors.chrome-linen}"
    textColor: "{colors.ink}"
  home-cta:
    backgroundColor: "{colors.accent-teal}"
    textColor: "{colors.canvas-parchment}"
    rounded: "{rounded.pill}"
    padding: "0 30px"
    height: "52px"
  home-card-button:
    backgroundColor: "{colors.accent-teal}"
    textColor: "{colors.canvas-parchment}"
    rounded: "{rounded.pill}"
    height: "48px"
  home-send:
    backgroundColor: "{colors.accent-teal}"
    textColor: "{colors.canvas-parchment}"
    rounded: "{rounded.pill}"
    size: "44px"
  home-reply:
    backgroundColor: "{colors.surface-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "44px"
  home-reply-on:
    backgroundColor: "{colors.accent-teal-glow}"
    textColor: "{colors.accent-teal}"
  chip:
    backgroundColor: "{colors.surface-white}"
    textColor: "{colors.ink-dim}"
    rounded: "{rounded.pill}"
    padding: "6px 13px"
    height: "34px"
  chip-active:
    backgroundColor: "rgba(20,110,104,.14)"
    textColor: "{colors.accent-teal}"
  card:
    backgroundColor: "{colors.surface-white}"
    rounded: "{rounded.lg}"
    padding: "16px"
  home-brief:
    backgroundColor: "{colors.surface-white}"
    rounded: "{rounded.lg}"
    padding: "18px 20px 6px"
  sys-list:
    backgroundColor: "{colors.surface-white}"
    rounded: "{rounded.lg}"
  sys-row:
    textColor: "{colors.ink}"
    padding: "10px 16px"
    height: "60px"
  input:
    backgroundColor: "{colors.canvas-parchment}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "9px 12px"
  compose-box:
    backgroundColor: "{colors.surface-white}"
    rounded: "26px"
    padding: "5px"
  message-agent:
    backgroundColor: "{colors.surface-white}"
    textColor: "{colors.ink}"
    padding: "11px 15px"
  message-user:
    backgroundColor: "{colors.user-bubble-mint}"
    textColor: "{colors.ink}"
    padding: "10px 15px"
  dock:
    backgroundColor: "{colors.chrome-linen}"
  dock-button:
    textColor: "{colors.ink-dim}"
    typography: "{typography.dock-label}"
    padding: "6px 2px"
    height: "58px"
  dock-button-active:
    textColor: "{colors.accent-teal}"
  drawer:
    backgroundColor: "{colors.surface-white}"
    width: "min(360px, 88vw)"
  drawer-row:
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 10px 0 36px"
    height: "44px"
  segmented:
    backgroundColor: "{colors.chrome-linen}"
    rounded: "{rounded.pill}"
    padding: "3px"
  segmented-option-on:
    backgroundColor: "{colors.surface-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    height: "36px"
  badge:
    rounded: "20px"
    padding: "3px 8px"
---

# Design System: StaxCloud

Scan source: `crates/openfang-api/static/**` on branch `stax-ux` at `3b0d474e`
(Round A through Build T0 statics). Token values above are the shipped
values; where they differ from the Verdict #1 token list of record, the
difference is recorded in **Colors → Token Reconciliation — Verdict #1**
and nowhere is one value silently preferred. Dark-theme components use the
same component shapes with the dark color tokens. The theme follows the OS
by default (`themeMode` falls back to `'system'` in `js/app.js`), with
manual Light / Dark override in Settings.

## Overview

**Creative North Star: "Phone-Calm Parchment"**

The name comes from the shipped code. `layout.css` holds wide screens to "a
phone-calm measure", and the light canvas is a warm off-white paper tone
rather than white. The look is a quiet, warm-neutral working surface with one
teal accent. It is built phone-first: a bottom dock, a left drawer, bottom
sheets, safe-area insets, and pill-shaped touch controls. The center of the
product is a conversation with Stax (Home). Everything else is a plain list,
a card, or a sheet.

Two layers are present in the statics, and they need to be told apart. The
**StaxCloud shell** (`stax-*`, `sd-*`, `home-*`, `sys-*` rules in
`layout.css`, plus the R2 cards at the end of `components.css`) is the
current design language: pills, 44px rows, a 15px reading size, `color-mix`
tints, and a calm ease-out motion curve. The **inherited OpenFang console
components** (`.btn`, `.card`, `.badge`, tables, the wizard, logs, the trader
dashboard, and others in `components.css`) were re-skinned only through the
token values ("Slice 1: values from StaxCloud tokens.css; variable names
unchanged"). They keep the older density: 13px controls, 6px button corners,
uppercase micro-labels, spring easing, and some hard-coded off-palette hues.
New work follows the shell layer.

The shell code describes itself as "Quiet everywhere except one moment",
meaning the mascot and greeting on first open.

**Key Characteristics:**
- Warm parchment light theme and a near-black graphite dark theme, with the same token names in both.
- A single teal accent family that marks the active, focused, primary, and current states.
- Surfaces are layered by tone and hairline borders. Shadows are small and soft.
- Pill controls on the shell, and 10px/14px corners on rows and cards.
- A centered measure on wide screens (920px shell, 680px reading column) instead of a stretched layout.
- Phone-first chrome: bottom dock, left drawer, bottom-sheet cards, and `env(safe-area-inset-*)` on every edge bar.

## Colors

Warm, low-chroma neutrals (paper, linen, and stone in light; graphite and
iron in dark), with one teal accent and muted, earthy status colors.

### Primary
- **Counter Teal** (`accent-teal`): the light-theme accent. It is used for primary buttons, the Home CTA, send, active dock tab and chip text, focus outlines, links, the selection highlight, the needs-you count, the streaming border, and the `theme-color` meta and manifest. Its hover state is **Deep Teal** (`accent-teal-deep`), and **Light Teal** (`accent-teal-light`) is used for the go-reply hover and inline code.
- **Sea Glass** (`accent-sea-glass`): the dark-theme accent in the same roles. Its light step is `accent-sea-glass-light`. In dark mode the `--accent-dim` slot holds Counter Teal (`#146e68`).
- **Teal Glow** (`accent-teal-glow` / `accent-sea-glass-glow`): the translucent accent wash. It forms the 4px focus halo, the active dock-pill background, the on-state of quick replies, and the halo on the current-chat dot.

### Secondary (section accents)
These are used only in the drawer and avatars. Section heads and the current row are tinted with the section's color (`--sec`).
- **Channels Slate Blue** (light value shared with `info-slate-blue`; dark `section-channels-dark`).
- **Studio Plum** (`section-studio-plum`; dark `section-studio-dark`). The drawer also ships the steps `#a0566b` / `#6f4357` (light) and `#d79aac` / `#b9849a` (dark).
- **System Slate** (`section-system-slate`; dark `section-system-dark`).

### Neutral
- **Parchment** (`canvas-parchment`) / **Night** (`canvas-night`): the page canvas, Home, form-input fills, and the compose strip.
- **Linen** (`chrome-linen`): the light-theme chrome tier, used for the page header, dock, and segmented-control track. In dark, the chrome tier equals Night.
- **White** (`surface-white`) / **Graphite** (`surface-graphite`): cards, lists, the drawer, the agent bubble, and the compose box.
- **Sand** (`raised-sand`) / **Raised Graphite** (`raised-graphite`): table heads, system messages, and the on-state of the dark segmented control.
- **Elevated Graphite** (`elevated-graphite`): the dark-theme `--bg-elevated` / `--surface2`, used for the Stax card sheet. In light, elevated equals White.
- **Stone** borders (`border-stone`, `border-stone-light`, `border-hairline`, `border-taupe-strong`) and **Iron** borders (`border-iron`, `border-iron-light`, `border-hairline-dark`, `border-strong-dark`). Hairlines separate list rows. The strong step outlines quick replies.
- **Ink** (`ink` / `ink-dark`) for body text, plus three lighter steps (`ink-secondary`, `ink-dim`, `ink-muted` and their dark pairs) for secondary text, metadata, and placeholders.
- **Mint bubble** (`user-bubble-mint`) / **Deep teal bubble** (`user-bubble-deep-teal`): the user's own chat messages.
- **Status**: `success-forest`, `error-brick`, `warning-umber`, `info-slate-blue` (light) and `success-dark`, `error-dark`, `warning-dark`, `info-dark` (dark).

### Named Rules
**The One Teal Rule.** The teal family is the only accent. It marks what is active, focused, current, or primary, and nothing decorative. Status meaning is carried by the status colors, never by the accent.

**The Color Lives One Level Up Rule.** This is shipped doctrine (`layout.css`): "App rows stay quiet: one-tone family glyphs, no tile faces. Color lives one level up, on the section heads and the dock." Rows are ink. The colorful family tiles and section accents belong to the dock and the section heads.

### Token Reconciliation — Verdict #1

The four radii in Verdict #1 ("6 / 10 / 14 + pill") are split into four rows.
Rows U1 to U11 cover shipped values that Verdict #1 never names. Each is a
disagreement by definition, so the count is complete in one place.

| # | Item | Verdict #1 value | Shipped value | Verdict |
|---|---|---|---|---|
| 1 | Canvas (light) | `#f4f2ec` | `--bg: #f4f2ec` | AGREE |
| 2 | Canvas (dark) | `#0c0c0e` | `--bg: #0c0c0e` | AGREE |
| 3 | Surface (light) | `#ffffff` | `--surface: #ffffff` | AGREE |
| 4 | Surface (dark) | `#121214` | `--surface: #121214` | AGREE |
| 5 | Border (light) | `#d9d4c8` | `--border: #d9d4c8` | AGREE |
| 6 | Border (dark) | `#2a2a2e` | `--border: #2a2a2e` | AGREE |
| 7 | Text (light) | `#1b1a17` | `--text: #1b1a17` | AGREE |
| 8 | Text (dark) | `#e8e4dc` | `--text: #e8e4dc` | AGREE |
| 9 | Accent teal | `#146e68` | `--accent: #146e68` (light) | AGREE |
| 10 | Dark accent | `#5cbcae` | `--accent: #5cbcae` (dark) | AGREE |
| 11 | Radius 6 | `6px` | `--radius-sm: 6px` | AGREE |
| 12 | Radius 10 | `10px` | `--radius-md: 10px` | AGREE |
| 13 | Radius 14 | `14px` | `--radius-lg: 14px` | AGREE |
| 14 | Radius pill | pill | literal `999px` (no token); legacy pills at `20px` | DISAGREE |
| 15 | Minimum hit area | `44px` | `--hit-min: 44px` defined but never consumed; several controls ship below 44px | DISAGREE |
| 16 | Typeface | DM Sans | `--font-sans: 'DM Sans', …` (400/500/600/700 loaded) | AGREE |
| 17 | Tagline | "Run your business. Grow your business. One intelligent system." | same text, auth prompt only | AGREE |
| U1 | Extra light/neutral surface tiers | (not named) | `#f1eee7` (`--bg-primary`, `--surface2`), `#e9e5db` (`--surface3`) | DISAGREE |
| U2 | Extra dark surface tiers | (not named) | `#18181b` (`--bg-elevated`, `--surface2`), `#1e1e21` (`--surface3`) | DISAGREE |
| U3 | Extra border steps | (not named) | light `#c9c3b4` `#e3ded2` `#b3ac9c`; dark `#3a3a3f` `#222226` `#4a4a50` | DISAGREE |
| U4 | Extra text steps | (not named) | light `#3f3c36` `#55524b` `#8a867c`; dark `#cac5ba` `#9a9aa0` `#6f6f76` | DISAGREE |
| U5 | Accent family beyond the two accents | (not named) | `#1d857e`, `#0f5a55`, `#7fd1c5`, glow/subtle rgba washes | DISAGREE |
| U6 | Status colors | (not named) | light `#226d3c` `#9f2520` `#8a5410` `#3f6486`; dark `#73d391` `#ff8179` `#e3a857` `#86acd1` | DISAGREE |
| U7 | Section accents | (not named) | `#3f6486` `#885264` `#576373` (+ studio steps, dark set) | DISAGREE |
| U8 | Chat tints and on-accent text | (not named) | `#e6f2f0` / `#0f2a27`; `--text-on-accent: #FFFFFF` in both themes | DISAGREE |
| U9 | Radii beyond 6/10/14/pill | (not named) | `--radius-xs: 4px`, `--radius-xl: 16px`; literals 2, 3, 8, 12, 24, 26, 28px, 24% | DISAGREE |
| U10 | Second typeface | (not named) | `--font-mono: 'Geist Mono', …`; literal `monospace` in 5 inline styles | DISAGREE |
| U11 | Off-system literal colors | (not named) | Tailwind-family hexes and rgba tints in legacy components; undefined-var fallbacks | DISAGREE |

**Totals:** 28 rows. **15 AGREE, 13 DISAGREE.** Of the 17 Verdict #1 items, 15
agree and 2 disagree (rows 14, 15). The other 11 disagreements are shipped
values Verdict #1 never names (U1 to U11).

**Disagreement notes:**
- **14 Pill.** There is no pill token in `css/theme.css`. Shell pills use the literal `999px` (12 rules in `css/layout.css`). Legacy pills in `css/components.css` (badge, filter pill, model switcher, tier badge) and inline styles in `index_body.html` use `20px`, and `.queue-badge` uses `10px`. The shape is the same at their heights, but there are three values for one role.
- **15 Hit area.** `--hit-min: 44px` is declared in `css/theme.css` but no rule reads it. Every 44px in use is a literal. `.btn` is 44px tall and the shell rows are 44 to 60px, but these controls ship smaller: `.stax-chip` 34px (`css/layout.css`; one use overrides to 44px inline), `.sys-seg button` 36px, `.sd-new` 36px (extended to 44px by an `::after` inset), `.sd-more` 40px, `.btn-send`/`.btn-stop` 40px, `.message-action-btn` 28px, and `.toggle` 20px (28px under `pointer: coarse`) in `css/components.css`. The API-key auth input and button in `index_body.html` have no min-height.
- **U1–U2 Surface tiers.** `css/theme.css` ships a third light tier (Linen `#f1eee7`, used by the page header, dock, and input area) and a raised tier (Sand). Dark ships an elevated tier `#18181b`, which differs from its surface, while light `--bg-elevated` equals surface `#ffffff`.
- **U3–U4 Border/text steps.** These are in `css/theme.css`. In light, `--border-light` (`#c9c3b4`) is *darker* than `--border`, despite its name.
- **U5 Accent family.** In `css/theme.css`. The dark `--accent-dim` is Verdict #1's light teal `#146e68`. `.stax-chip.active` hard-codes `rgba(20,110,104,.14)` (`css/layout.css`), so the dark theme also gets the light-teal tint.
- **U6 Status.** In `css/theme.css`. The `-subtle`/`-muted` washes use Tailwind-family rgba bases (for example `rgba(34, 197, 94, …)`) instead of the shipped status hexes. The dark `-dim` steps are Tailwind hexes (`#22C55E`, `#B91C1C`, `#D97706`, `#2563EB`).
- **U7 Section accents.** Light values are in `css/theme.css` (`--stax-channels/studio/system`) and repeated in `css/layout.css` (`.stax-side`). Dark values exist only inside `.stax-side`, so `--stax-*` aliases do not change with the theme.
- **U8 On-accent text.** Legacy `.btn-primary`/`.btn-send` put `--text-on-accent: #FFFFFF` on the accent in both themes. On dark Sea Glass that is about 2.3:1 contrast. Shell controls (`.home-cta`, `.home-send`, `.home-card-btn`, `.home-reply--go`, `.home-needs-count`) use `var(--bg)` instead, which is Parchment on teal in light and Night on Sea Glass in dark. `.stax-dock-badge` and `.side-msg-user` hard-code `#fff`. There are two conventions for one role.
- **U9 Radii.** `--radius-xs`/`--radius-xl` are in `css/theme.css`. The literals are in `css/layout.css`: raw `10px` (duplicating `--radius-md` without using it) and `12px`, plus the 24px mascot, 26px compose box, 28px Home sheet top corners, and 24% tiles. Others are in `css/components.css` (3px, 8px, 12px, 4px) and in `index_body.html` inline styles (2px ×15, 4px, 8px, 14px).
- **U10 Mono.** Geist Mono is loaded in `index_head.html` and set in `css/theme.css`. Five inline `font-family:monospace` styles in `index_body.html` skip the token.
- **U11 Off-system literals.** In `css/components.css`: model/tier badges use `#a855f7`, `#3b82f6`, `#22c55e`, `#f59e0b`; `.setting-option-selected` uses `rgba(99, 102, 241, 0.08)`; badge tints use `rgba(74,222,128,…)` and similar. Also, `var()` references to names that `theme.css` never defines: `--danger` (Boards "Delete board" falls back to `#e5534b`), `--primary`, `--bg-hover`, `--text-primary`, `--radius`, `--card-bg`, `--surface-alt`, and others. Auth-prompt inline fallbacks (`#1e1e2e`, `#151520`, `#333`) are inert while the variables resolve.
- **17 Tagline (observation, still AGREE).** The text appears once, on the sign-in prompt in `index_body.html`, with a line break before "One intelligent system." `manifest.json` still carries `"OpenFang Agent OS"` / `"Open-source Agent Operating System"` rather than the StaxCloud name or tagline.

## Typography

**Body Font:** DM Sans (with -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif)
**Label/Mono Font:** Geist Mono (with 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace)

Both are loaded from Google Fonts at weights 400/500/600/700 (`index_head.html`).

**Character:** A single geometric-humanist sans with tight negative tracking
(body −0.01em, headings −0.02em to −0.035em). Weight builds the hierarchy
more than size does. Mono is used only for data.

### Hierarchy
- **Display** (600, clamp(30px, 7.4vw, 40px), 1.1): the first-open Home greeting. Balanced wrapping. It appears once per surface.
- **Headline** (700, 22px): the Stax card title.
- **Title** (700, 16px): card heads such as the morning brief. The drawer wordmark is 18px/700.
- **Page title** (600, 15px): every page header `h2`.
- **Body** (400, 15px, 1.55): conversation messages, the brief (15.5px/1.6, max 68ch), list-row names (15.5px/600), and drawer rows (15px/500). The compose field uses 16px to prevent mobile zoom.
- **Body base** (400, 14px, 1.5, −0.01em): the `body` default. Legacy console content runs at 12–13.5px.
- **Label** (700, 11.5px, 0.07em, uppercase): drawer section labels and section names. Legacy form labels, table heads, and badges use 10–11px uppercase at 0.04–1px tracking.
- **Dock label** (600, 10.5px, .01em). The active tab steps up to 700.

### Named Rules
**The Mono-Is-Data Rule.** This is shipped doctrine (`theme.css`: "Mono text utility — only for code/data"). Geist Mono is for code, stat values, cron strings, and badges of machine state. Prose and controls are never mono.

## Layout

- **Shell:** a full-height column (`100dvh`, top padded by `env(safe-area-inset-top)`). From top to bottom: an optional shell bar holding the 44px menu button, the page (header, then a scrolling body), and the bottom dock (bottom padded by `env(safe-area-inset-bottom)`). Navigation lives in the dock (four primary tabs: Stax, Work, Boards, Leads) and in a left drawer (`min(360px, 88vw)`). The System corner and the Forms and Texts modules swap in their own docks, each ending in "Done" to return to Stax.
- **Measure:** at ≥1024px the main column and dock center at `max-width: 920px`, with side borders on the dock. The Home column is 680px, the Home sheet is 760px, and System pages are 680px. Text measures are 52–68ch.
- **Rhythm:** a 4px-based scale. Utilities ship `gap-2/3/4` = 8/12/16 and `mb-6` = 24. Page body padding is 24px, 16px at ≤1024px, and 12px at ≤480px. Cards pad 16px, Home stacks at 20px gaps, threads at 14px, and drawer rows at 12px icon gaps.
- **Breakpoints observed:** `max-width` 420 / 480 / 1024px, `min-width` 720 / 1024 / 1400px, plus `pointer: coarse` (which forces 44px on `.btn` and form fields). The legacy trader dashboard adds 540 / 768 / 900px.
- **Card grids:** `auto-fill, minmax(280px, 1fr)`, with a 240px minimum at ≤1024px, one column at ≤480px, and a 320px minimum at ≥1400px.
- **Sheets:** the Stax card is a bottom sheet on phones and becomes a centered 400px card at ≥720px.

## Elevation & Depth

Depth is a hybrid. Tonal layering does most of the work (canvas → linen
chrome → white/graphite surface → sand/raised), with 1px borders. A small
shadow scale supports it. Shadows are near-invisible on light (4–10% black)
and heavier on dark (30–40%). Hover lifts in the legacy layer use −1px/−2px
translate plus a shadow step.

### Shadow Vocabulary
- **xs** (`0 1px 2px rgba(0,0,0,0.04)`): resting cards, the brief, and buttons. Often paired with `--shadow-inset` (a 1px top highlight).
- **sm / md** (`0 1px 3px …, 0 1px 2px …` / `0 4px 12px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.04)`): the compose box, and card hover/focus.
- **lg / xl** (`0 12px 28px …` / `0 20px 40px rgba(0,0,0,0.1), 0 8px 16px rgba(0,0,0,0.06)`): dropdowns, modals, and the centered Stax card.
- **accent** (`0 4px 16px rgba(20, 110, 104, 0.18)`; dark uses Sea Glass at 0.2): the Home CTA and primary-button hover.
- **Drawer / sheet** (`12px 0 32px rgba(0,0,0,0.18)`, `0 -12px 32px rgba(0,0,0,0.18)`, Home sheet `0 -10px 30px rgba(0,0,0,0.07)`): off-canvas panels. The drawer drops its shadow when closed.
- **Scrims:** `rgba(10,10,12,0.45)` for the drawer and card. Legacy modals use `rgba(8,7,6,0.8)` with an 8px backdrop blur.
- **Focus:** a 2px accent outline at 2px offset plus a 4px accent-glow ring. Fields use a 3px glow ring with an accent border.

### Named Rules
**The One Raised Sheet Rule.** This is shipped doctrine (`layout.css`: "One focal point, then one quiet raised sheet holding everything else"). Home has a single raised surface with 28px top corners. Its inner cards return to the canvas tone instead of stacking more elevation.

## Shapes

- **Shell controls are pills** (999px): chips, CTAs, quick replies, send, segmented controls, count badges, the "New chat" button, and the active dock-mark backdrop.
- **Rows and small tiles use 10px:** drawer rows, people rows, the menu button, and the mark tile.
- **Cards and lists use 14px:** cards, the brief, System lists, the Stax card, and table wraps. Modals use 16px.
- **Legacy buttons and fields use 6px.**
- **Chat bubbles have one tight corner:** the agent card is 6px at top-left, the user bubble 6px at bottom-right, and the rest 14px. Legacy chat bubbles do the same at the bottom corner.
- **Avatars and dots are circles.** Brand tiles are 24% squircles. The compose box is 26px, and the mascot frame is 24px.
- **Borders are always 1px** in border or hairline tones. Accent left-borders (3px) mark tool cards, pending approvals, and streaming messages.

## Components

### Buttons
Shell buttons are pill-shaped, bold (700), and teal. Legacy buttons are compact rectangles.
- **Shell primary** (Home CTA, card button, go-reply): teal fill with canvas-colored text, pill shape, 52px / 48px / 44px tall, 15–16px/700. The CTA hover lifts 1px with a glow shadow.
- **Legacy primary `.btn-primary`:** teal fill with white text, 6px corners, 44px minimum height, 8px 16px padding, 13px/600. Hover moves to Deep Teal with a −1px lift, and press scales to 0.97. Disabled is 0.4 opacity.
- **Ghost:** transparent with a stone border and dim ink text. Hover fills with Linen.
- **Quiet** (`.home-card-btn--quiet`, `.home-quiet-link`): a bordered pill, or an underlined dim text link with a 44px target.
- **Danger / success:** `.btn-danger` uses the error fill with white text, and `.btn-success` uses the success fill with black text.

### Chips
- **Style:** a white or graphite pill with a stone border, dim ink, 12.5px/600, and a 34px minimum height (see reconciliation row 15).
- **Active:** a teal-tinted fill with a teal border and teal text.
- **Quick replies:** 44px pills with a strong border. The `is-on` state is a teal glow. Status pills (`.home-status`) are non-interactive 30px pills with a toned dot.

### Cards / Containers
- **Corner Style:** 14px.
- **Background:** surface white / graphite.
- **Shadow Strategy:** xs at rest. Legacy cards lift −2px to md on hover, and focus-within shows an accent border.
- **Border:** 1px stone. It moves to the strong tone on hover.
- **Internal Padding:** 16px (legacy) and 18–20px (brief).

### Inputs / Fields
- **Style:** canvas fill, 1px stone border, 6px corners, 9px 12px padding, 13px text. The compose box is a 26px-radius white field holding a borderless 16px textarea, an attach button, and a 44px round send button.
- **Focus:** an accent border plus a 3px accent-glow ring. The compose box shows the same on `:focus-within`.
- **Disabled:** send drops to 0.35 opacity. Buttons drop to 0.4–0.55.

### Navigation
- **Dock:** a Linen bar with a top border and four equal buttons at least 58px tall. Each has a 26px family tile (raster art from `brand/tiles-128.css`) or a 22px glyph, over a 10.5px/600 label. On the active tab the label turns teal and bold and a glow pill sits behind the mark. The padding is always reserved, so the active state never shifts the layout. Count badges (Work, Forms submissions) are 17px teal pills.
- **Drawer:** a left off-canvas card that slides in over 0.32s with `cubic-bezier(0.22, 1, 0.36, 1)` and can be dragged. It holds people rows (52px, 36px avatars), uppercase section heads with family tiles, 44–46px app rows, chat rows with a current-dot halo, and an owner block ending at Sign out. A bottom fade cues that more content is below. Hover and press use 5% / 9% ink `color-mix` washes.
- **System corner:** plain inset lists (14px, hairline-separated, rows at least 60px) with a trailing control, status word, "Ask Stax" link, or chevron. The 36px segmented pill switches Light / System / Dark.

### Conversation (signature)
- The agent message is a white card with a 6px top-left corner beside a 28px Stax avatar, at 15px/1.55. User messages are a right-aligned mint / deep-teal bubble capped at 82% width. System notes are centered dim 13.5px text. Inline app links render as 44px teal pills.
- **Morning brief:** the first card on Home. It ends in a full-bleed 52px "needs you" row with a teal count pill.
- **Stax card:** a bottom sheet with a facts list (`dl`, hairline rows) and stacked pill actions.

### Boards
- A list of the shared `.card` (title 15px/600, block count in dim small text) in the standard card grid. The detail view uses a chip "← All boards" back button, then blocks built from inline-styled headings (18px/700), text, stat cards (20px/700 values), and list cards. Boards have no dedicated stylesheet rules; they are assembled from shared components and inline styles in `index_body.html`.

## Do's and Don'ts

### Do:
- **Do** read every color, radius, and font through the `theme.css` variables, so light and dark flip together.
- **Do** use the shell vocabulary for new StaxCloud surfaces: pill controls, 10px rows, 14px cards and lists, 15px reading text, and DM Sans with negative tracking.
- **Do** give every interactive control a 44px minimum, as `.btn`, the drawer rows, quick replies, compose controls, and the menu button already do.
- **Do** put `var(--bg)` text on accent fills (the shell convention), so contrast holds on both teal and Sea Glass.
- **Do** clear the system bars with `env(safe-area-inset-top/bottom)` on any new edge bar, sheet, or dock.
- **Do** center wide layouts at the shipped measures (920px shell, 680px column) instead of stretching them.
- **Do** honor `prefers-reduced-motion`. Every shell transition and the mascot animation already turn off under it.
- **Do** use `cubic-bezier(0.22, 1, 0.36, 1)` (or `0.16, 1, 0.3, 1` for arrivals) for shell motion.

### Don't:
- **Don't** introduce colors outside the token set. Hard-coded Tailwind hexes and undefined `var()` names (U11) are known drift, not precedent.
- **Don't** put white `#FFFFFF` text on the dark-theme accent. That legacy `.btn-primary` pairing is about 2.3:1.
- **Don't** hard-code teal rgba tints (the `.stax-chip.active` pattern). They do not follow the dark theme.
- **Don't** add color to drawer or app rows. Color belongs on the dock and section heads.
- **Don't** use mono for prose or controls.
- **Don't** stack more raised surfaces inside the Home sheet. Inner cards return to the canvas tone.
- **Don't** copy the legacy console density (10–11px uppercase labels, 6px buttons, spring-bounce lifts) onto shell surfaces.
