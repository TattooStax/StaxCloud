# Step 2 Patch — Owner corrections to the side card (2026-11-02)

Base: HEAD f7824cb on stax-ux (Step 2, deployed live, binary 20451972…). Presentation layer only: `crates/openfang-api/static/**`; no other paths; no new machinery; no new routes. The owner reviewed the live drawer on his own phone ("It's a million times better") and named three corrections. This patch is exactly those three, plus the standing builder rules (own browser self-check, found/fixed list, icon changes through the single sd-* sprite only).

## 1. Sections start CLOSED
The CHANNELS / STUDIO / SYSTEM sections open COLLAPSED every time the drawer opens. (Today they can present expanded.) Chevron state must read closed at open. No persistence that reopens them.

## 2. The bottom tiles strip is REMOVED
Delete the Shortcuts/tiles strip from the drawer entirely. First verify every destination it reached exists as a section row, and report the mapping: Inbox → CHANNELS; Forms, Library, Contacts, Canvas → STUDIO; Settings → SYSTEM. No destination may be lost; if one is missing from the sections, add the row to its section instead of keeping the strip.

## 3. The OWNER footer stops being anchored
Report a bug / Sign out become the final block INSIDE the drawer's single scroll flow — the bottom of the side card's content, reached by scrolling to the end. No pinned strip, no seam, no content row cut in half at a fixed boundary. After this change the drawer is: header, TEAM, sections, CHATS, OWNER — one scroll, ending at Sign out.

## 4. In-section app rows get TILE styling
Each app row inside a section (Inbox; Forms, Library, Contacts, Canvas; Settings, Connections) carries its icon in a colored rounded tile chip — reuse the removed strip's tile visual language (its per-destination colors and corner treatment), applied inside the rows. The section header icons (CHANNELS / STUDIO / SYSTEM) keep the current single line-glyph sprite treatment unchanged — do NOT draw new icons in this patch; the traditional-style redraw is a separate later slice.

## Gate
Fresh staging instance on the final binary; builder's own browser pass at 390×844 and desktop, dark + light: drawer at open (sections closed), scrolled to the end (OWNER block in flow, Sign out fully visible, nothing cut), tile-styled rows visible in expanded sections, zero raw ids, no approval cards. Written found/fixed + found/not-fixed list. Build + stage only; no deploy, no push, no git operations beyond local commits on stax-ux.
