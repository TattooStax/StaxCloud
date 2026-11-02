"""Per-artist element library + stamp kits (owner delta 2026-11-02).

Artists pool the elements they save — line, shading, stamp and raster
pieces split out of earlier designs — into their OWN permanent
library, group them into stamp kits, and pull them into later designs
without regenerating. Permanence is a rule of this module, not a
default:

- an element NEVER auto-expires — there is no TTL, no expires field,
  no sweep, anywhere in this module;
- the ONLY way an element leaves the library is the owning artist
  explicitly deleting it (`delete_element`).

Scoping matches the profile store (PLAN §4): the AGENT sees every
artist's library (it routes and recomposes across the studio), an
ARTIST's view shows only their own elements and kits, and kit
membership can only reference the owning artist's own elements.
"""

from __future__ import annotations

import copy
import json

ELEMENT_KINDS = ("line", "shading", "stamp", "raster")


class ElementLibrary:
    def __init__(self) -> None:
        self._elements: dict[str, dict[str, dict]] = {}
        self._kits: dict[str, dict[str, dict]] = {}
        self._kit_counter = 0

    # -- elements ------------------------------------------------------
    def save_element(self, artist_id: str, record: dict) -> dict:
        """Save (or replace) one element in an artist's library.

        Record: {element_id, name, kind, source_design_id, tags,
        created_ts}. The stored record carries exactly those fields
        plus the owning artist_id — and NO expiry field of any kind:
        elements are reusable indefinitely until the artist deletes
        them."""
        kind = record["kind"]
        if kind not in ELEMENT_KINDS:
            raise ValueError(f"unknown element kind: {kind!r}")
        stored = {
            "element_id": record["element_id"],
            "artist_id": artist_id,
            "name": record.get("name", record["element_id"]),
            "kind": kind,
            "source_design_id": record.get("source_design_id", ""),
            "tags": list(record.get("tags", [])),
            "created_ts": record.get("created_ts"),
        }
        self._elements.setdefault(artist_id, {})[stored["element_id"]] = stored
        return copy.deepcopy(stored)

    def get_element(self, artist_id: str, element_id: str) -> dict:
        try:
            return copy.deepcopy(self._elements[artist_id][element_id])
        except KeyError:
            raise KeyError(f"artist {artist_id!r} has no library element {element_id!r}") from None

    def list_elements(self, artist_id: str) -> list[dict]:
        return [copy.deepcopy(r) for r in self._elements.get(artist_id, {}).values()]

    def delete_element(self, artist_id: str, element_id: str) -> None:
        """The ONLY removal path, and it is the artist's explicit act.
        The element also leaves any of the artist's kits it was in."""
        self.get_element(artist_id, element_id)  # raises if absent
        del self._elements[artist_id][element_id]
        for kit in self._kits.get(artist_id, {}).values():
            if element_id in kit["element_ids"]:
                kit["element_ids"].remove(element_id)

    def element_provenance(self, artist_id: str, element_id: str) -> dict:
        """Provenance for reusing a library element as a layer in a
        (possibly different, later) design: attach this to the new
        layer and the reuse is on record through save/load."""
        record = self.get_element(artist_id, element_id)
        return {
            "source": "library",
            "artist_id": artist_id,
            "element_id": element_id,
            "element_kind": record["kind"],
            "source_design_id": record["source_design_id"],
        }

    # -- stamp kits ------------------------------------------------------
    def create_kit(self, artist_id: str, name: str) -> dict:
        """A stamp kit belongs to exactly one artist."""
        self._kit_counter += 1
        kit = {
            "kit_id": f"K{self._kit_counter}",
            "artist_id": artist_id,
            "name": name,
            "element_ids": [],
        }
        self._kits.setdefault(artist_id, {})[kit["kit_id"]] = kit
        return copy.deepcopy(kit)

    def get_kit(self, artist_id: str, kit_id: str) -> dict:
        try:
            return copy.deepcopy(self._kits[artist_id][kit_id])
        except KeyError:
            raise KeyError(f"artist {artist_id!r} has no kit {kit_id!r}") from None

    def list_kits(self, artist_id: str) -> list[dict]:
        return [copy.deepcopy(k) for k in self._kits.get(artist_id, {}).values()]

    def add_to_kit(self, artist_id: str, kit_id: str, element_id: str) -> dict:
        """Add one of the artist's OWN elements to their kit (another
        artist's element id fails the ownership check)."""
        self.get_element(artist_id, element_id)  # must be theirs
        self.get_kit(artist_id, kit_id)          # must exist and be theirs
        kit = self._kits[artist_id][kit_id]
        if element_id not in kit["element_ids"]:
            kit["element_ids"].append(element_id)
        return copy.deepcopy(kit)

    def remove_from_kit(self, artist_id: str, kit_id: str, element_id: str) -> dict:
        self.get_kit(artist_id, kit_id)  # must exist and be theirs
        stored = self._kits[artist_id][kit_id]
        if element_id in stored["element_ids"]:
            stored["element_ids"].remove(element_id)
        return copy.deepcopy(stored)

    # -- scoped views ----------------------------------------------------
    def agent_view(self) -> dict:
        """The agent sees every artist's full library and kits."""
        artist_ids = set(self._elements) | set(self._kits)
        return {a: {"elements": self.list_elements(a), "kits": self.list_kits(a)}
                for a in sorted(artist_ids)}

    def artist_view(self, artist_id: str) -> dict:
        """An artist's UI sees ONLY their own library and kits."""
        return {"elements": self.list_elements(artist_id),
                "kits": self.list_kits(artist_id)}

    # -- persistence -------------------------------------------------------
    def to_json(self) -> str:
        return json.dumps({
            "elements": {a: list(m.values()) for a, m in self._elements.items()},
            "kits": {a: list(m.values()) for a, m in self._kits.items()},
            "kit_counter": self._kit_counter,
        }, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "ElementLibrary":
        data = json.loads(text)
        lib = cls()
        for artist_id, records in data.get("elements", {}).items():
            for record in records:
                lib.save_element(artist_id, record)
        for artist_id, kits in data.get("kits", {}).items():
            for kit in kits:
                stored = {
                    "kit_id": kit["kit_id"],
                    "artist_id": artist_id,
                    "name": kit["name"],
                    "element_ids": list(kit["element_ids"]),
                }
                lib._kits.setdefault(artist_id, {})[stored["kit_id"]] = stored
        lib._kit_counter = int(data.get("kit_counter", 0))
        return lib
