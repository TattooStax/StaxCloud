---
name: style-skill
version: "1.0.0"
description: Learns each artist's tattoo style from the studio's portfolio — one portfolio/ record per picture, one style/ profile per artist — which image_generate reads when asked for a design in an artist's style
runtime: prompt_only
---

# Style Skill

The Style helper starts from `setup/profile` (website, artists, portfolio links), lists the pictures on the portfolio pages with `page_images`, saves each new one with `image_fetch`, and classifies it with `image_describe` into one of thirteen fixed categories. Each picture becomes a `portfolio/<artist-slug>/<file_id>` record. Pictures on an artist's own page are that artist's; pictures in a shared gallery are "unassigned" unless the alt text names the artist.

From an artist's portfolio records it rebuilds `style/<artist-slug>`: category counts, top specialties, a short style note written from the descriptions, and up to three exemplar pictures per top category. Fields the owner sets by hand (listed in `owner_set`) are never overwritten.

`image_generate` with `artist` reads that profile: the style note and top categories go into the prompt, and the best matching exemplars ride along as reference pictures, so a design comes back in that artist's linework and shading rather than a generic look.

It works in batches of twelve pictures per wake, keeps a "style catch-up" schedule while pictures remain, and a "style weekly" schedule to pick up new portfolio work.
