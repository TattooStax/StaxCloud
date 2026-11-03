# Round 3 — Drawer gestures + the reaper becomes the brand (2026-11-02)

Base: HEAD 1f03d4b on stax-ux (Corrections Round 2, live binary f1015029…). Presentation layer only: `crates/openfang-api/static/**` plus permitted webchat.rs include_str! lines if a new static file must be served. No new machinery, no new routes on the server, no kernel/hand/sidecar changes. Standing builder rules: own browser self-check on staging; found/fixed + found/not-fixed lists; icons through the single sprite where vector, images as static assets where raster.

Owner direction, two parts.

## PART A — The side card moves like a card

Today the drawer opens from the hamburger and closes from an X inside the drawer. The owner wants it to behave like a real side card:

1. **The X inside the drawer is REMOVED.** The drawer header keeps brand + wordmark only.
2. **The hamburger (three-line) button is the toggle**: tap it to open the card, tap it again to close it. It must work from every surface that shows it.
3. **Edge swipe opens**: a drag starting at the left screen edge (a ~24px grab zone) pulls the card out — the card FOLLOWS the finger; releasing past roughly 40% of the card's width (or with a quick flick) opens it fully; releasing earlier snaps it shut.
4. **Swipe closes**: with the card open, dragging the card (or the dimmed page beside it) leftward follows the finger and closes past the same threshold; a quick leftward swipe on the card closes it outright. Tapping the dimmed page still closes it.
5. Implementation: Pointer Events, transforms only (no layout thrash); do not hijack vertical scrolling or drags that begin on interactive elements outside the edge zone; ESC closes on desktop; honor prefers-reduced-motion (fall back to the plain toggle, no follow-drag). The drawer's internals do not change: one scroll container, sections start closed, OWNER block in flow, no tiles strip.

## PART B — The grim reaper is the brand

The app's current brand mark is the circular-arrow (staxclaw-mark) — that is an identity glyph, NOT our character. The brand is the **grim reaper mascot**. Canonical assets are staged at ~/openfang-build/icon-assets/reaper/ (fetched from TattooStax/StaxCloud `staxos/web/icons/` @ 58937fab, hash-verified): `stax-avatar.svg` (the reaper in small vector form), `stax-mascot-phone.png` (the reaper working a phone, large raster), `stax-mascot-idle.jpg` (the reaper at rest). Consume them as-is — never redraw the character.

Apply:
1. **Drawer brand tile** (the teal square beside "StaxCloud"): the reaper avatar replaces the arrow.
2. **Stax's avatar everywhere it represents Stax**: Home header avatar, the TEAM Stax row, the Stax card (tap target from Part B of Step 1), and the dock's Stax icon — the reaper avatar (vector form) replaces the arrow orb / mascot-head glyph. (The dock's other four icons stay as Round 2 left them.)
3. **The Home centerpiece**: the large orb becomes the reaper mascot, large and centered (the owner's StaxCloud reference composition) — use stax-mascot-phone.png if it holds up at ~180px, else stax-mascot-idle.jpg; report which you shipped. The status pill, greeting, one action, and composer do not move.
4. **The sign-in screen's brand mark**: reaper replaces the arrow tile.
5. The arrow mark disappears from owner surfaces. If the tree has an About/Advanced corner where it belongs as a historical identity mark, it may live there; otherwise it simply leaves the owner surface (the asset files stay in the tree untouched). Report what you did with it.
6. If the favicon is a static asset, point it at the reaper avatar too and report it.

Explicitly OUT of this round: redrawing the other icons (Work/Boards/Leads/Channels and the drawer rows). The deep traditional-style illustrated tile set is a separate design production with an owner approval gate; Round 2's family holds as the placeholder until it lands. Do not touch it.

## Gate (staging, final binary, 390×844 + desktop, dark + light)
- Gesture evidence from your own browser pass: hamburger opens AND closes; edge-drag partial release snaps shut; edge-drag past threshold opens; swipe-left on the open card closes; scrim tap closes; a mid-drag capture if your tooling allows. State plainly any gesture you could not exercise in the harness (owner's phone is the fallback proof for those).
- No X anywhere in the drawer (markup scan + captures).
- Branding captures: sign-in, Home (mascot centerpiece), drawer (brand tile + TEAM row), Stax card, dock — reaper present, arrow absent from owner surfaces.
- Non-regression: sections closed at open; Settings plain list intact; System module dock intact; vocabulary scans clean; zero console errors.
Two local commits on stax-ux (one per part) preferred. Build + stage only; no deploy, no push.
