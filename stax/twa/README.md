# stax/twa — the StaxCloud Android wrapper (TWA) source

The Bubblewrap project that produces the installable Android app for
https://fang.sefer.team — package `ai.tattoostax.fang`, label
"StaxCloud", versionCode 4. The app is a Trusted Web Activity: it renders
the live site full-screen; all content updates ship from the server, so
the APK rarely needs rebuilding.

## Contents

- `twa-manifest.json` — the Bubblewrap project manifest (host, icons,
  theme #146e68, background #0c0c0e, signing alias `fang`).
- `settings.gradle`, `build.gradle`, `gradle.properties`,
  `app/build.gradle`, `gradlew`/`gradlew.bat`, `gradle/wrapper/` — the
  generated Gradle project.
- `app/src/` — the generated Android sources and resources (launcher and
  maskable icons rendered from the canonical reaper mascot,
  `stax-mascot-phone.png` in TattooStax/StaxCloud `staxos/web/icons/`).
- `icon-512.png`, `store_icon.png`, `logo-repo.png` — project icon assets.
- `manifest-build.json`, `manifest-checksum.txt` — build metadata from
  the v4 build.

## Rebuild sketch

Install Bubblewrap (`npm i -g @bubblewrap/cli`), open this directory,
`bubblewrap build`. Signing needs the release keystore, which is NOT in
this repo (see below) — its certificate SHA-256 fingerprint is
`13:72:1C:6F:73:21:52:24:CD:A2:3B:04:F0:55:A1:53:02:DE:18:38:D0:23:B9:69:B9:19:FB:69:91:AD:C5:EB`,
and that fingerprint is what https://fang.sefer.team/.well-known/assetlinks.json
trusts, so a differently-signed build will fall back to a browser tab.

## Excluded on purpose

- The signing keystore (`*.keystore`/`*.jks`) and its password (vaulted,
  never in git).
- Build outputs (`*.apk`, `*.aab`, `build/`, `.gradle/`) — the signed APK
  is published as the **`twa-v4` release asset** (`staxcloud.apk`), and
  is also served at https://fang.sefer.team/download/staxcloud.apk.
- Operator working files from the build session (driving scripts, logs,
  answer files) — several contain credentials by design and stay off-repo.
