# App Formats Research — OpenFang pilot (fang.sefer.team)

Researched 2026-11-02. Owner direction: wrap the Fang web app in two formats — (1) a TWA, (2) a native mobile app chosen by research. Owner law held throughout: Fang's wiring and the existing web UI are **not** rewritten; packaging wraps what exists. Sources are live pages pulled the same day; anything not verified against a live source is marked **[unverified]**.

**Bottom line up front**

- **TWA is feasible and cheap** for fang.sefer.team. The app already has the two hard parts (a manifest and a fetch-handling service worker). The real gaps are serving `/.well-known/assetlinks.json` from the origin and confirming the manifest's fields. A TWA gives app-store presence and a chrome-less icon on the phone — and **zero** native capability. It cannot touch SMS or telephony, by design.
- **Recommended native format: Capacitor.** It is the only candidate where the InkStax SMS module becomes a *reusable plugin package* — a typed JS interface over a Kotlin implementation — which is exactly the owner's stated purpose ("that same module… natively inside our OpenFang fork and other telephony apps"). It also has a documented zero-change way to load the existing web app (point the shell at the Fang origin), so the web UI and wiring stay untouched.

---

## A. TWA for fang.sefer.team

### What a TWA is, and its hard limit

A Trusted Web Activity is an Android app that opens your PWA full-screen inside Chrome, with ownership proven by Digital Asset Links. The enclosing app **cannot read or modify the web content** — per the Chromium Blog's TWA criteria, "the content of a TWA is protected and cannot be read or modified by the enclosing application," and state can only be passed in as query parameters at launch. There is no native code seam at all: no `SmsManager`, no telephony, no plugins. Whatever the web platform can't do, the TWA can't do. Web push, background sync, and the rest of Chrome's web platform *do* work, and the TWA shares Chrome's cookies/storage.

### Requirement checklist vs. Fang's current state

| # | Requirement | Fang today |
|---|---|---|
| 1 | HTTPS origin | ✅ fang.sefer.team via Cloudflare tunnel |
| 2 | Installable PWA — manifest with `name`/`short_name`, icons incl. **192px and 512px**, `start_url`, `display` one of standalone/minimal-ui/fullscreen/window-controls-overlay, `prefer_related_applications` absent or false (web.dev installability criteria, via the web.dev Lighthouse audit source) | ⚠️ A manifest.json ships with the app (project record), but its **field-level compliance was not read in this pass** — the site serves an authenticated SPA shell, so icon sizes / `display` / `prefer_related_applications` are **[unverified]** until someone reads the served manifest directly |
| 3 | Service worker | ✅ **Even under the strict reading.** Chrome removed the fetch-handler requirement for menu install in Chrome 108 (mobile) / 112 (desktop), and MDN now treats a service worker as optional for installability; the automatic install *prompt* algorithm still weighs having one. Fang's service worker **has** a fetch handler (a network pass-through), so it satisfies the old and new criteria alike |
| 4 | Offline behaviour | ⚠️ The pass-through worker + `no-store` page headers mean **no offline at all** — offline, the TWA shows Chrome's offline error handling, and Chrome's published TWA quality criteria treat failed asset-link verification, offline non-200 responses, and 404/5xx at launch as failing/crash-equivalent conditions. `no-store` does **not** block installability (nothing in the criteria inspects cache headers); the cost is only that Fang-in-a-TWA is online-only — which matches the product, since the UI is a client of the Fang server anyway |
| 5 | Performance bar | ⚠️ Chromium's published TWA quality criteria require meeting PWA installability **and** a Lighthouse performance score of 80 at the start URL. That wording dates from the Chrome 86 era **[current enforcement unverified]**, but Bubblewrap still ships a `validate` command that "validates a PWA against the Quality Criteria for being used in a Trusted Web Activity." Performance is measured against a small box behind a tunnel — worth an early measurement, not an assumption |
| 6 | **Digital Asset Links** — serve `https://fang.sefer.team/.well-known/assetlinks.json` containing `relation: ["delegate_permission/common.handle_all_urls"]`, the app's `package_name`, and `sha256_cert_fingerprints` (format per developer.chrome.com's TWA docs). If Play-distributed with Play App Signing, the file must carry **both** the local keystore fingerprint **and** Google's Play signing-certificate fingerprint. Verification failure → the app falls back to a Custom Tab **with** a URL bar. The file must come from the origin itself, as JSON, without redirect tricks | ❌ **The gap.** Nothing in the current setup is known to serve this path. Someone must make the origin return it — either the Fang binary serves the file from its statics, or a Cloudflare-side rule/Worker on fang.sefer.team does. Small, but it is *the* gating item for a chrome-less TWA |
| 7 | Tooling | Bubblewrap CLI (`@bubblewrap/cli`, Node 18+): `bubblewrap init --manifest https://fang.sefer.team/manifest.json`, then `bubblewrap build` → signed AAB/APK. On first run it offers to download and install JDK 17 and the Android SDK into `~/.bubblewrap`, so no host toolchain prep is needed. Alternative: **PWABuilder** (web UI) generates the Android package and emits the assetlinks snippet to paste |
| 8 | Signing & distribution | **Play:** developer account, AAB upload, Play App Signing fingerprint added to assetlinks (item 6), and Play's ordinary app requirements (target API level, listing assets incl. 512 icon and screenshots). **Sideload:** the same Bubblewrap APK signed with your own keystore installs directly; asset links are still required for chrome-less full screen; updates are manual (re-install), and content updates need no new APK at all — the TWA always loads the live site, so only shell changes (name, icon, target SDK) ever need a rebuild |

### What a TWA cannot do — stated plainly

No native telephony or SMS access of any kind; no native code; no access to the page's storage from the shell; requires Chrome on the device; Android-only. The TWA is the *presence* format — icon, store listing, full-screen — and contributes nothing to Fang's self-dependent telephony goal.

---

## B. Native format — candidates scored

### The Android SMS ground truth (same for every native candidate)

Platform rules (Android Developers Blog, "Getting Your SMS Apps Ready for KitKat" — the contract Android still runs on):

- **Sending:** any app holding the `SEND_SMS` runtime permission can send via `SmsManager`. If the sending app is *not* the default SMS app, the system automatically writes its sent messages to the SMS Provider; the default app must write its own.
- **Receiving:** any app with `RECEIVE_SMS` can listen for the `SMS_RECEIVED` broadcast. Only the user-selected **default SMS app** receives `SMS_DELIVER` and can **write** to the SMS Provider (store threads, mark read, delete).
- **Reading history:** querying the SMS Provider needs `READ_SMS` (runtime-granted).

Play policy layer (Google Play Help, "Permissions and APIs that access sensitive information" — applies **only to Play-distributed apps**):

- The SMS permission group (`READ_SMS`, `SEND_SMS`, `WRITE_SMS`, `RECEIVE_SMS`, `RECEIVE_WAP_PUSH`, `RECEIVE_MMS`) may only be declared and used by an app **actively registered as the default SMS or Assistant handler**, with a declaration form submitted in Play Console, and the app must stop using the permissions the moment it stops being the default handler.
- Practical consequence: a **Play-distributed** Fang that sends/receives shop SMS in the background must *be* the phone's default SMS app — a product decision, not an implementation detail. A **sideloaded / self-distributed** build is outside Play policy entirely; only the platform rules above apply. (For a dedicated shop phone whose job is the shop line, default-handler is actually coherent — flagged for the owner, not decided here.)
- Permissionless alternatives (SMS Retriever API, SMS User Consent API) cover OTP-style code reading only — not a general messaging channel.
- ⚠️ Secondary (non-official) sources report Android 15 classifying SMS permissions as hard-restricted, adding "allow restricted settings" friction for sideloaded apps. **Not verified against official Android documentation in this pass** — check before promising a sideload flow on Android 15+ devices.

### Scorecard

Scored 1–5 against the owner's four tests: **(1)** reuses the existing web UI + Fang wiring with no rewrite · **(2)** credible path to native SMS/telephony · **(3)** build/maintenance weight for a tiny team (5 = lightest) · **(4)** Android-first fit.

| Candidate | 1 · No-rewrite reuse | 2 · SMS path | 3 · Weight | 4 · Android fit | Total |
|---|---|---|---|---|---|
| **Capacitor** | 5 | 5 | 4 | 5 | **19** |
| Tauri Mobile (v2) | 3 | 3 | 3 | 4 | 13 |
| Plain Kotlin WebView shell | 5 | 5 | 2 | 5 | 17 |
| React Native / Flutter | 1 | 3 | 2 | 3 | 9 — ruled out |

### Capacitor — recommended

- **Reuse, zero-change path:** Capacitor's config supports `server.url`, loading the web app live from a remote origin — the shell can point straight at `https://fang.sefer.team` and the served web app runs untouched. (Ionic's team documents the option while steering store-bound apps away from it on UX-review grounds, mainly Apple's; for a self-distributed Android client of a server product, the trade is explicit and acceptable.) The alternative — bundling `static/**` as `webDir` — would force the SPA to call the API cross-origin, i.e. a change to the served app, so it is *not* the no-rewrite path.
- **SMS path, the decisive point:** Capacitor's own docs describe the pattern as first-class — "the easiest way to communicate between JavaScript and native code is to build a custom Capacitor plugin that is local to your app": a Kotlin/Java class extending `com.getcapacitor.Plugin` with `@CapacitorPlugin` / `@PluginMethod`, registered in `MainActivity`, called from JS via `registerPlugin()`. Plugins can also be built as standalone publishable packages with a typed TS interface. A telephony plugin wraps `SmsManager` + an `SMS_RECEIVED` receiver and pushes inbound messages into the WebView as plugin listener events; permission check/request plumbing is part of the plugin API.
- **Weight:** one npm toolchain + generated Android Studio/Gradle project that you own outright; mature docs and plugin ecosystem for anything later (push, files, camera) instead of hand-builds.
- **Why it wins for *this* owner:** the deliverable isn't just an app — it's the InkStax SMS module as a **self-contained plug-in package** (the platform's existing plug-in law). A Capacitor plugin is exactly that shape: one package, dropped into Fang's app today and into other telephony apps later. The Kotlin shell scores the same on reuse and SMS but has no package boundary — reuse there means copying code.

### Tauri Mobile — credible runner-up

Tauri v2's mobile support is production-ready (GA with 2.0, 2024) and its mobile plugins are Kotlin classes extending `app.tauri.plugin.Plugin` with `@Command` methods callable from Rust or JS. Two frictions for this job: Tauri's architecture expects a bundled frontend talking to an **in-app Rust core** via `invoke` — Fang's core is a *remote* server, so the Rust layer becomes mostly dead weight and remote-URL loading is not its documented shape **[fit detail unverified beyond the plugin docs]**; and there is no telephony/SMS plugin in the official catalogue, so the SMS work is the same Kotlin code as Capacitor's *plus* a Rust/JS bridge definition on top. The team's Rust fluency (Fang itself is Rust) lowers the learning curve, and if the phone shell ever needs real on-device Rust logic, Tauri becomes the right answer. For "WebView + one native feature," it is more machinery than the job needs.

### Plain Kotlin WebView shell — the honest minimalist option

An Activity + WebView loading the Fang origin, a JS bridge (`addJavascriptInterface` / WebMessageListener), and `SmsManager` + receiver in the same process. Reuse is perfect and the SMS path is the most direct of all — no framework between you and the telephony APIs. It loses on weight *over time*: bridge security (origin discipline on the JS interface), WebView configuration, permission flows, shell updates, and every future native need are bespoke, with no ecosystem to borrow — and, decisively, no package boundary for the cross-app reuse the owner asked for.

### React Native / Flutter — ruled out

Both are UI frameworks whose entire value is rendering native UI from their own component models. Adopting either means **rewriting Fang's UI**, which owner law forbids; using them merely as WebView wrappers (react-native-webview, webview_flutter) pays a new toolchain to become a worse shell, and SMS still drops down to Kotlin native modules underneath. No benefit on any of the four tests.

### What the InkStax SMS module must become inside Capacitor

A standalone Capacitor plugin package (the "Fang SMS" plugin), in two halves:

- **Kotlin side:** `SmsManager` send — single and multipart, with sent/delivery `PendingIntent` callbacks mapped to the delivery read-backs Fang's Texts flow already expects; an `SMS_RECEIVED` `BroadcastReceiver` forwarding inbound messages to the web layer as plugin events; SMS Provider thread/history reads where permission allows; runtime permission check/request methods; and a default-SMS-role check (RoleManager) so the app can report which capabilities it currently holds (send-only vs. full default-handler).
- **JS/TS side:** the same message/thread shapes the existing Fang Texts surface and the InkStax module already exchange, so the web layer calls the plugin at exactly the seam where the interim Dell relay calls sit today. On a device without the plugin (plain browser, or the TWA), the web layer keeps using the server path — the plugin is an enhancement seam in the client, not a fork of the UI.
- **Baked-in distribution decision:** sideload → platform rules only (permission prompts at runtime). Play → the app must be the default SMS handler to use the SMS permission group at all, with the Play Console declaration filed. That choice belongs to the owner; the plugin should be built so both remain possible (capability reporting above is what makes the UI able to degrade honestly).

---

## C. Mini-PC and single-board targets — what "two formats" means there

Be precise about sides: **both new formats are client formats.** The server side doesn't get a format at all — Fang's server is one Rust binary, and it already runs on Sarah's box (a small Linux box) behind the tunnel.

- **Mini-PC:** the same story as Sarah's box on x86 Linux — the binary runs the shop; the *client* on that machine is the browser, or the same PWA installed from desktop Chrome/Edge (desktop installability shares the criteria in §A; Chrome dropped the service-worker fetch requirement for desktop install in Chrome 112). No third format is needed.
- **Single-board computer:** the same server binary built for the board's architecture (an ARM target for a typical SBC). That's a build-target change in the existing Rust lane, not a new app — and it has **not yet been produced or proven** for this fork **[project state, not web-verified]**. A screen attached to the board is, again, just the browser/PWA client.
- **Why Sarah's box first is consistent:** it is already the pilot's server *and* the public origin. Every client artifact in this report points at that one origin — the assetlinks file must be served by it, Bubblewrap/PWABuilder validate against it, and the Capacitor shell's `server.url` loads from it. Proving order that follows from the current state: **(1)** serve assetlinks + wrap the TWA against the existing origin; **(2)** the Capacitor shell pointed at the same origin, with the SMS plugin on a real Android phone — the first end-to-end proof of Fang telephony running on a phone's own radio, which is what eventually retires the interim relay for that device.

---

## Open gaps & unverified items (consolidated)

1. Manifest field-level compliance (icon sizes, `display`, `start_url`, `prefer_related_applications`) — not read in this pass; the pilot serves an authenticated SPA shell.
2. `/.well-known/assetlinks.json` — not known to be served today; treated as a gap to close, not probed directly.
3. Android 15 hard-restricted SMS permission claims — secondary sources only; unverified against official Android docs.
4. Lighthouse-80 TWA performance bar — from Chromium's published quality criteria (Chrome 86 era); Bubblewrap's `validate` still checks "Quality Criteria," but current enforcement wording is unverified. Fang's actual Lighthouse score over the tunnel is unmeasured.
5. Tauri remote-URL loading — "not the documented shape" is an inference from Tauri's documented bundled-frontend + `invoke` architecture, not an exhaustive check.
6. ARM/SBC build of the Fang binary — not yet produced, per project state.

## Sources (live, pulled 2026-11-02)

- Digital Asset Links format & TWA multi-origin setup — developer.chrome.com: https://developer.chrome.com/docs/android/trusted-web-activity/multi-origin
- TWA quality criteria & content protection — Chromium Blog, "Introducing Trusted Web Activities" (via blog.chromium.org TWA label): https://blog.chromium.org/search/label/trusted%20web%20activities
- Installability criteria — web.dev "What does it take to be installable?" / Lighthouse installable-manifest audit source: https://github.com/samdutton/web.dev/blob/HEAD/src/site/content/en/lighthouse-pwa/installable-manifest/index.md ; Chrome's install-criteria revision (fetch-handler removal, Chrome 108/112) as summarized from Chrome for Developers: http://dev.to/wingo-ui/react-pwa-install-prompt-for-chrome-edge-and-iphone-983
- Bubblewrap CLI (init/build/validate, JDK 17 + Android SDK auto-install, Node 18+) — npm.io package page: https://npm.io/package/@bubblewrap/cli ; dual-fingerprint assetlinks practice & PWABuilder alternative: https://github.com/sstern42/socionics-match/issues/974
- Play SMS/Call Log permission policy — Google Play Help: https://support.google.com/googleplay/android-developer/answer/16909972
- Default SMS app platform contract — Android Developers Blog: https://android-developers.googleblog.com/2013/10/getting-your-sms-apps-ready-for-kitkat.html
- Capacitor custom plugins & Android plugin guide — Capacitor docs: https://capacitorjs.com/docs/plugins/android ; config incl. `server`: https://capacitorjs.com/docs/v7/config ; live-reload/`server.url` mechanics: https://capacitorjs.com/docs/next/guides/live-reload ; remote-URL trade-off, Ionic team discussion: https://github.com/ionic-team/capacitor/discussions/5025
- Tauri mobile plugin development — Tauri v2 docs: https://v2.tauri.app/develop/plugins/develop-mobile/
