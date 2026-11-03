# Owner Corrections Round 2 — Icons (family + tier swap) and the System corner (2026-11-02)

Base: HEAD f4bacb4 on stax-ux (Step 2 + patch, live binary b067997e…). Presentation layer only: `crates/openfang-api/static/**` plus permitted webchat.rs include_str! lines if a new template file is unavoidable. No new machinery, no new routes, no kernel/hand/sidecar changes. Standing builder rules apply: your own browser self-check on staging before reporting; written found/fixed and found/not-fixed lists; icons only through the single sprite system.

The owner reviewed the live app on his phone. The side card itself is accepted. Two corrections follow.

## PART A — Icons: our family, tiers swapped

Two things are wrong today: the glyphs are STOCK line icons (not ours), and the color tiers landed backwards. The owner's words: the more colorful shapes belong for the drawer icons; inside the drawer are the subtle shapes; and everything must have a tattoo studio feel.

Family sources (staged beside the tree at ~/openfang-build/icon-assets/):
- The StaxBox Icon System (~/workspace/your_files/staxbox-icons/ on the parent VM; ICONS.md + preview.html + palette.css describe it; folders: nav/, folders/, system/, social/, email/, mascot/, avatars/). Its nav/ set includes home, inbox, contacts, forms, studio, settings, calendar, records, projects.
- Style reference: reference/ui-direction icon family (American-traditional flash) — bold simple shapes, limited palette, hand-drawn weight. Match the vocabulary; do not trace artwork.

What changes:
1. OUTER level goes COLORFUL: the bottom dock icons (Stax, Work, Boards, Leads, Channels) and the drawer's section headers (CHANNELS, STUDIO, SYSTEM) get filled, colorful shapes in our palette — the tattoo-studio feel lives here. Section accents already exist (blue / dusty pink / slate); the dock may use the product teal + section hues.
2. INNER rows go SUBTLE: the app rows inside the drawer (Inbox; Forms, Library, Contacts, Canvas; Settings, Connections) LOSE the colored tile chips added in the Step 2 patch and return to subtle single-tone glyphs. (The drawer brand mark and TEAM avatars are not part of this swap.)
3. Replace stock glyphs with our family's marks wherever the set has an equivalent; map sensibly (inbox→Inbox, forms→Forms, contacts→Contacts, records→Library, settings→Settings, studio→STUDIO header, projects→Boards, home/mascot→Stax dock). For destinations the set lacks (Work, Leads, the Channels dock icon, Connections, Canvas if no fit), draw simple marks in the same family discipline — same viewBox, stroke/fill language, readable at 20–24px, NOT busy. Report an adopted-vs-drawn list for every icon you ship.
4. Everything resolves through the ONE sprite system (dock included, if it does not already). No icon fonts, no raster images, no mixed styles.
5. Do not regress the patch: sections still start closed, the tiles strip stays gone, the OWNER block stays in-flow.

## PART B — The System corner: Settings and Connections become owner surfaces

Today the drawer's SYSTEM rows lead to stock consoles: the owner screenshotted Settings showing a chip wall (Connections · Settings · Advanced), a tab row (Providers · Models · Config · Tools · Security), "OpenFang ships with 42 built-in providers", and API-key fields. That is machinery the owner must never land on. Fix the whole corner:

1. The top chip wall (Connections · Settings · Advanced) is REMOVED from these pages. The corner's sub-navigation becomes a bottom module dock — Settings · Connections · Advanced — in the same pattern as the Forms and Texts module docks (sits above the main dock). No other sub-nav may compete with it.
2. SETTINGS landing = ONE plain list (the Muse / StaxCloud shape). Rows only for things that exist: Appearance (the existing theme control, working); a row into Advanced; Report a bug and Sign out (existing behaviors); shop/version identity in plain words. Any setting that has no existing owner control becomes an "Ask Stax" row that opens the Stax conversation (agent-first: settings the agent manages get changed by asking) — never a fake toggle. NO provider names, NO model names, NO API-key fields, NO environment-variable names anywhere on this landing. Report the final row list you shipped.
3. The stock Settings console (Providers / Models / Config / Tools / Security, provider catalog, key fields) moves INTACT into the Advanced page, joining the machinery already demoted there. Wiring law: demoted, never deleted — every existing control must still work from Advanced.
4. CONNECTIONS landing = plain rows: the connections this shop actually has (from the data the page already uses), each with a plain-language status word. The integrations catalog and provider machinery demote to Advanced intact, same as Settings.
5. Text scan of both landings: no kernel terms, no provider/model/key vocabulary, no raw ids.

## Gate (staging, final binary, 390×844 + desktop, dark + light)
- Drawer open: section headers colorful, app rows subtle (no tile chips), sections closed at open, OWNER in flow.
- Bottom dock: colorful family icons, labels intact.
- Settings landing: the plain list, zero machinery vocabulary (scan output reported).
- Connections landing: plain rows, plain statuses.
- Advanced: the stock Settings console reachable inside it (Providers visible) — demotion proven, not deletion; the R4 machinery still there too.
- Chip wall absent on Settings, Connections, and Advanced.
- Zero console errors. Screenshots filed per configuration.
Two local commits on stax-ux (one per part) preferred. Build + stage only; no deploy, no push.
