"""Artist profiles, approved libraries, and visibility scoping (PLAN-v2 §4/§5).

One store, three scoped views — the scoping is enforced here, in the
deterministic core, not left to whichever UI sits on top:

- the AGENT reads ALL profiles and libraries (it needs them to route
  and to style-match);
- an ARTIST's UI shows only their own profile, library and designs;
- a CUSTOMER sees only their own designs, and only once the artist has
  approved them.

Customer-facing generation is opt-in per artist:
`allow_customer_designs` defaults to False, and the offer ("shoot me a
prompt and I can make you a design") may only be made when the
best-fit artist has it on (PLAN §5, Gate 1). Pricing never lives in a
profile — estimates stay under the standing pricing rule.

Owner deltas 2026-11-02: `versions_per_request` is a per-artist
setting (product DEFAULT 1; Shawn sets his to 3 — 3 is his setting,
not the product default), and a profile may carry a free-text
`style_note` refining the style anchor used in generation prompts
(Shawn's: his work leans slightly more realistic, same simplified
value concept).
"""

from __future__ import annotations

import json


class ProfileStore:
    def __init__(self, profiles: list[dict] | None = None):
        self._profiles: dict[str, dict] = {}
        for profile in profiles or []:
            self.add(profile)

    # -- store ---------------------------------------------------------
    def add(self, profile: dict) -> dict:
        versions = int(profile.get("versions_per_request", 1))
        if versions < 1:
            raise ValueError("versions_per_request must be at least 1")
        profile = {
            "artist_id": profile["artist_id"],
            "display_name": profile.get("display_name", profile["artist_id"]),
            "styles": list(profile.get("styles", [])),
            "specialties": list(profile.get("specialties", [])),
            "style_note": profile.get("style_note", ""),
            "approved_library": list(profile.get("approved_library", [])),
            "allow_customer_designs": bool(profile.get("allow_customer_designs", False)),
            "versions_per_request": versions,
            "generated_history": list(profile.get("generated_history", [])),
        }
        self._profiles[profile["artist_id"]] = profile
        return profile

    def get(self, artist_id: str) -> dict:
        if artist_id not in self._profiles:
            raise KeyError(f"no artist profile {artist_id!r}")
        return self._profiles[artist_id]

    def set_customer_designs(self, artist_id: str, allowed: bool) -> None:
        self.get(artist_id)["allow_customer_designs"] = bool(allowed)

    def can_offer_customer_designs(self, artist_id: str) -> bool:
        """PLAN §5 Gate 1: the offer exists only if the artist opted in."""
        return self.get(artist_id)["allow_customer_designs"]

    def set_versions_per_request(self, artist_id: str, count: int) -> None:
        """Per-artist versions setting (owner delta 2026-11-02)."""
        count = int(count)
        if count < 1:
            raise ValueError("versions_per_request must be at least 1")
        self.get(artist_id)["versions_per_request"] = count

    def get_versions_per_request(self, artist_id: str) -> int:
        """How many versions a request to this artist plans by default.

        Product default is 1 (owner delta 2026-11-02); an artist's own
        setting overrides it (Shawn's seed sets 3)."""
        return int(self.get(artist_id).get("versions_per_request", 1))

    def to_json(self) -> str:
        return json.dumps(list(self._profiles.values()), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "ProfileStore":
        return cls(json.loads(text))

    # -- scoped views ----------------------------------------------------
    def agent_view(self) -> list[dict]:
        """The agent sees every artist's full profile and library."""
        return list(self._profiles.values())

    def artist_view(self, artist_id: str) -> dict:
        """An artist's UI sees ONLY their own profile."""
        return self.get(artist_id)

    @staticmethod
    def customer_view(customer_id: str, designs: list[dict]) -> list[dict]:
        """A customer sees only their own designs, and only approved
        ones (PLAN §5 Gate 2: artist approval is absolute). Each design
        record: {id, customer_id, artist_id, approved, preview_ref}."""
        return [d for d in designs
                if d.get("customer_id") == customer_id and d.get("approved") is True]


def seed_fargo_tattoo() -> ProfileStore:
    """Fargo Tattoo seeding from the approved artist positioning
    (2026-10-26): fine line is Shawn's specialty, never Leni's."""
    return ProfileStore([
        {
            "artist_id": "shawn",
            "display_name": "Shawn Lowe",
            "styles": ["realism", "semi-realism", "black & grey", "fine line",
                       "minimalist", "street style"],
            "specialties": ["black & grey realism", "fine-line florals",
                            "red ink work"],
            # Owner feedback 2026-11-02 on the dagger/rose proof:
            # clean and tattooable, close to his style, his own work
            # leans slightly more realistic — same value concept.
            "style_note": "Leans slightly more realistic — semi-realism "
                          "toward realism, same simplified value concept",
            "approved_library": [],
            "allow_customer_designs": False,
            # Shawn's own setting (owner delta 2026-11-02); the
            # product default for an unset artist is 1.
            "versions_per_request": 3,
        },
        {
            "artist_id": "leni",
            "display_name": "Leni Dickey",
            "styles": ["neo-traditional", "bold color", "illustrative", "graphic"],
            "specialties": ["bold neo-traditional color work"],
            "approved_library": [],
            "allow_customer_designs": False,
        },
    ])
