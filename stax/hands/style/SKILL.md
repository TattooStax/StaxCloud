---
name: style-skill
version: "1.0.0"
description: Learns each artist's tattoo style from the studio's portfolio — one portfolio/ record per picture, one style/ profile per artist — which image_generate reads when asked for a design in an artist's style
runtime: prompt_only
---

# Style Skill

The bookkeeping is code, not the model. `style_learn` reads `setup/profile` and `artist/*` for the website and portfolio links, follows the site's portfolio, gallery and artist pages, and lists their pictures. A picture's identity ignores size and cache suffixes, so the same photo at two sizes is one picture. Pictures already learned (`portfolio/<artist-slug>/<picture-id>`) or already found not to be tattoos (`portfolioskip/<picture-id>`) are never read again. Each new picture is read by the vision model with one fixed question and stored under its artist: the artist whose page it was on, or the one its alt text names; otherwise "unassigned". Up to twelve per call; the rest wait in `stylequeue`.

From an artist's records the code rebuilds `style/<artist-slug>`: category counts, top specialties, a note assembled from what the readings said, up to three example pictures per top category, and the clock's date. Fields the owner sets by hand (listed in `owner_set`) are kept. Records written by the older model-run helper are re-keyed by picture identity on the next sweep, merging duplicates.

`style_correct` moves or re-labels one picture and rebuilds both profiles. `image_generate` with `artist` reads the profile: the note and top categories go into the prompt and the best matching examples ride along as references.

Schedules are declared in HAND.toml and kept by the kernel: a catch-up every 15 minutes that only reaches the model while `stylequeue` holds pictures, and a weekly re-check of the website.
