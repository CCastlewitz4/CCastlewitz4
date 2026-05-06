# obsidian_bridge.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Keeps your Obsidian vault in sync with the DnD AI DM system.
#
# WHAT IT DOES:
#   • Writes notes to your Obsidian vault whenever the DM saves world data
#   • Reads notes back so the AI can recall information between sessions
#   • Separates STATIC info (names, lore, location desc) from DYNAMIC info
#     (last seen, HP, mood, relationship changes, plot history)
#   • Updates only the dynamic section of a note when things change —
#     the static section you write by hand is never overwritten
#
# VAULT FOLDER STRUCTURE:
#   DND Memory/
#   ├── Characters/          ← One note per NPC / player character
#   ├── Locations/           ← One note per city, dungeon, region, etc.
#   ├── Nations/             ← One note per faction / kingdom
#   ├── Plot Events/         ← Chronological story log (one note per event)
#   ├── Relationships/       ← One note per entity listing all their bonds
#   └── Session Recaps/      ← Auto-generated "Previously on..." summaries
#
# HOW NOTES ARE STRUCTURED:
#   Every note has two clearly delimited sections:
#
#     ## 📌 Static Info
#     (written once — you can edit this freely in Obsidian, it won't be
#      overwritten unless you explicitly call write_static=True)
#
#     ## 🔄 Dynamic Info  ← AUTO-MANAGED
#     (updated automatically every time the AI changes this entity's data)
#
# HOW TO INTEGRATE:
#   1.  Set OBSIDIAN_VAULT_PATH below to your vault's root folder
#       (the path you already told me: DND Memory/)
#   2.  Import ObsidianBridge in dm_agent.py (see INTEGRATION GUIDE at bottom)
#   3.  Call bridge.sync_from_world_state(world, graph) after each turn
#       to push changes to Obsidian
#   4.  Call bridge.load_context_for_prompt(entity_name) when building
#       the system prompt to pull in extra Obsidian notes as context
#
# DEPENDENCIES: None beyond Python stdlib. No pip installs needed.
#
# LOCATION: dnd_ai_dm/obsidian_bridge.py
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path


# ── Configuration ─────────────────────────────────────────────────────────────
# Set this to your Obsidian vault path. Supports both Windows backslashes and
# forward slashes — Path() normalizes them automatically.

OBSIDIAN_VAULT_PATH = r"C:\Users\colin\Desktop\DND_AI_DM Backup\DND_AI_DM\dnd_ai_dm\data\DND Memory"

# Subfolder names inside your vault. Change these if you rename the folders.
VAULT_FOLDERS = {
    'characters':    'Characters',
    'locations':     'Locations',
    'nations':       'Nations',
    'plot_events':   'Plot Events',
    'relationships': 'Relationships',
    'recaps':        'Session Recaps',
}

# These markers delimit the two sections in every note.
# The text between them is auto-managed. Do NOT edit these marker lines in Obsidian.
STATIC_MARKER  = "## 📌 Static Info"
DYNAMIC_MARKER = "## 🔄 Dynamic Info  ← AUTO-MANAGED — do not edit below this line"
DYNAMIC_END    = "---"  # A horizontal rule marks the end of the dynamic block


# ── ObsidianBridge Class ───────────────────────────────────────────────────────

class ObsidianBridge:
    """
    Reads from and writes to an Obsidian markdown vault.

    Every entity type (characters, locations, nations, plot events, relationships)
    gets its own subfolder. Notes use a two-section structure:
      - Static section: stable lore you write in Obsidian and own
      - Dynamic section: auto-updated data the AI maintains

    Usage:
        bridge = ObsidianBridge()
        bridge.upsert_character(character_dict)   # called after save_character()
        bridge.upsert_location(location_dict)     # called after save_location()
        bridge.upsert_nation(nation_dict)         # called after save_nation()
        bridge.log_plot_event(event_dict)         # called after log_plot_event()
        bridge.upsert_relationship(entity_id, entity_name, relationships_list)
        bridge.write_session_recap(session_id, recap_text)
        context = bridge.load_entity_note(folder_key, entity_name)
    """

    def __init__(self, vault_path: str = OBSIDIAN_VAULT_PATH):
        self.vault = Path(vault_path)
        self._ensure_folders()

    # ── Folder Setup ──────────────────────────────────────────────────────────

    def _ensure_folders(self):
        """Creates all vault subfolders if they don't exist yet."""
        for folder_name in VAULT_FOLDERS.values():
            (self.vault / folder_name).mkdir(parents=True, exist_ok=True)

    def _note_path(self, folder_key: str, title: str) -> Path:
        """
        Returns the full Path for a note file.

        Parameters:
          folder_key — Key from VAULT_FOLDERS ('characters', 'locations', etc.)
          title      — The note's title / filename (without .md extension)

        Sanitizes the title so it's a safe filename on Windows and macOS.
        Obsidian does not allow: \ / : * ? " < > | in filenames.
        """
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', title).strip()
        folder_name = VAULT_FOLDERS[folder_key]
        return self.vault / folder_name / f"{safe_title}.md"

    # ── Note Read / Write Helpers ─────────────────────────────────────────────

    def _read_note(self, path: Path) -> str:
        """Reads a note file and returns its full text. Returns '' if not found."""
        if path.exists():
            return path.read_text(encoding='utf-8')
        return ''

    def _write_note(self, path: Path, content: str):
        """Writes content to a note file, creating parent dirs as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def _split_note(self, existing_text: str) -> tuple[str, str]:
        """
        Splits an existing note into (static_section, dynamic_section).

        The static section is everything up to and including the DYNAMIC_MARKER.
        The dynamic section is everything after the DYNAMIC_MARKER.

        If the note doesn't have the marker yet (first write or hand-crafted note),
        static_section = entire existing text, dynamic_section = ''.

        Returns:
          (static_text, dynamic_text)
        """
        if DYNAMIC_MARKER in existing_text:
            parts = existing_text.split(DYNAMIC_MARKER, 1)
            return parts[0], parts[1]
        return existing_text, ''

    def _build_note(self, static_section: str, dynamic_section: str) -> str:
        """
        Assembles a complete note from its two sections.

        Parameters:
          static_section  — Everything above the dynamic marker (your lore)
          dynamic_section — Auto-generated data block (will be replaced each update)
        """
        return f"{static_section.rstrip()}\n\n{DYNAMIC_MARKER}\n{dynamic_section.strip()}\n"

    # ── Public Methods: Write ─────────────────────────────────────────────────

    def upsert_character(self, character: dict, write_static: bool = False):
        """
        Creates or updates a character note in the Characters/ folder.

        STATIC section (written once, then never overwritten unless write_static=True):
          - Name, race, class/occupation
          - Appearance (as first described)
          - Personality and backstory
          - Secrets and goals (good place to add your own notes in Obsidian)

        DYNAMIC section (updated every call):
          - Last known location
          - Current mood
          - Last seen date (in-game)
          - Relationship summary tag list
          - Source (auto_extracted vs manually_created)

        Parameters:
          character    — Character dict from WorldState.save_character()
          write_static — If True, rewrites the static section even if the note
                         already exists. Use this when the AI updates appearance
                         after a new scene description.
        """
        name = character.get('name', 'Unknown')
        path = self._note_path('characters', name)
        existing = self._read_note(path)
        static_old, _ = self._split_note(existing)

        # Only write the static section on first creation or if forced
        if not existing or write_static:
            race       = character.get('race', 'Unknown')
            occ        = character.get('class', character.get('occupation', 'Unknown'))
            appearance = character.get('appearance', 'Not yet described.')
            personality= character.get('personality', 'Not yet observed.')
            backstory  = character.get('backstory', '')
            goals      = character.get('goals', '')
            secrets    = character.get('secrets', '')
            faction    = character.get('faction', '')
            speech     = character.get('speech_style', '')

            static_lines = [
                f"# {name}",
                f"",
                STATIC_MARKER,
                f"",
                f"**Race:** {race}",
                f"**Class / Occupation:** {occ}",
            ]
            if faction:
                static_lines.append(f"**Faction:** {faction}")
            static_lines += [
                f"",
                f"### Appearance",
                appearance,
                f"",
                f"### Personality",
                personality,
            ]
            if speech:
                static_lines += ["", f"**Speech Style:** {speech}"]
            if backstory:
                static_lines += ["", f"### Backstory", backstory]
            if goals:
                static_lines += ["", f"**Goals:** {goals}"]
            if secrets:
                static_lines += ["", f"**Secrets:** {secrets}"]
            static_lines += ["", f"### Your Notes", "_Add your own lore, hooks, or reminders here._", ""]
            static_section = '\n'.join(static_lines)
        else:
            static_section = static_old

        # Always rebuild the dynamic section
        location    = character.get('location', 'Unknown')
        mood        = character.get('current_mood', '')
        first_seen  = character.get('first_seen', '')
        last_updated= character.get('last_updated', datetime.utcnow().isoformat())[:10]
        source      = character.get('source', 'manual')
        entity_id   = character.get('id', '')

        dynamic_lines = [
            f"",
            f"**Last Known Location:** {location}",
        ]
        if mood:
            dynamic_lines.append(f"**Current Mood:** {mood}")
        if first_seen:
            dynamic_lines.append(f"**First Seen:** {first_seen}")
        dynamic_lines += [
            f"**Last Updated (real):** {last_updated}",
            f"**Source:** {source}",
            f"**Internal ID:** `{entity_id}`",
            f"",
            f"_Tags: [[Characters]] {self._location_tag(location)}_",
            f"",
            DYNAMIC_END,
        ]
        dynamic_section = '\n'.join(dynamic_lines)

        self._write_note(path, self._build_note(static_section, dynamic_section))

    def upsert_location(self, location: dict, write_static: bool = False):
        """
        Creates or updates a location note in the Locations/ folder.

        STATIC section: name, type, nation, description, notable features, dangers
        DYNAMIC section: current events, last visited, in-game date of last update
        """
        name = location.get('name', 'Unknown Location')
        path = self._note_path('locations', name)
        existing = self._read_note(path)
        static_old, _ = self._split_note(existing)

        if not existing or write_static:
            loc_type   = location.get('type', 'place')
            nation     = location.get('nation', 'Unknown')
            desc       = location.get('description', 'No description available.')
            features   = location.get('notable_features', '')
            atmosphere = location.get('atmosphere', '')
            dangers    = location.get('dangers', '')
            population = location.get('population', '')

            static_lines = [
                f"# {name}",
                f"",
                STATIC_MARKER,
                f"",
                f"**Type:** {loc_type}",
                f"**Nation / Region:** {nation}",
            ]
            if population:
                static_lines.append(f"**Population:** {population}")
            static_lines += [
                f"",
                f"### Description",
                desc,
            ]
            if features:
                static_lines += ["", f"### Notable Features", features]
            if atmosphere:
                static_lines += ["", f"**Atmosphere:** {atmosphere}"]
            if dangers:
                static_lines += ["", f"### Known Dangers", dangers]
            static_lines += ["", f"### Your Notes", "_Quests, rumours, shop lists, map notes…_", ""]
            static_section = '\n'.join(static_lines)
        else:
            static_section = static_old

        current_events  = location.get('current_events', '')
        last_updated    = location.get('last_updated', datetime.utcnow().isoformat())[:10]
        entity_id       = location.get('id', '')

        dynamic_lines = [
            f"",
        ]
        if current_events:
            dynamic_lines += [f"**Current Events Here:** {current_events}", ""]
        dynamic_lines += [
            f"**Last Updated (real):** {last_updated}",
            f"**Internal ID:** `{entity_id}`",
            f"",
            f"_Tags: [[Locations]] [[{location.get('nation','World')}]]_",
            f"",
            DYNAMIC_END,
        ]
        dynamic_section = '\n'.join(dynamic_lines)

        self._write_note(path, self._build_note(static_section, dynamic_section))

    def upsert_nation(self, nation: dict, write_static: bool = False):
        """
        Creates or updates a nation note in the Nations/ folder.

        STATIC section: government type, ruler, culture, economy, military
        DYNAMIC section: current conflicts, last updated
        """
        name = nation.get('name', 'Unknown Nation')
        path = self._note_path('nations', name)
        existing = self._read_note(path)
        static_old, _ = self._split_note(existing)

        if not existing or write_static:
            gov      = nation.get('government', 'Unknown')
            ruler    = nation.get('current_ruler', 'Unknown')
            culture  = nation.get('culture', '')
            military = nation.get('military_strength', '')
            economy  = nation.get('economy', '')
            desc     = nation.get('description', '')
            laws     = nation.get('notable_laws', '')

            static_lines = [
                f"# {name}",
                f"",
                STATIC_MARKER,
                f"",
                f"**Government:** {gov}",
                f"**Current Ruler:** {ruler}",
            ]
            if military:
                static_lines.append(f"**Military Strength:** {military}")
            if economy:
                static_lines.append(f"**Economy:** {economy}")
            if culture:
                static_lines += ["", f"### Culture", culture]
            if desc:
                static_lines += ["", f"### Overview", desc]
            if laws:
                static_lines += ["", f"### Notable Laws", laws]
            static_lines += ["", f"### Your Notes", "_Alliances, history, plot hooks…_", ""]
            static_section = '\n'.join(static_lines)
        else:
            static_section = static_old

        conflicts   = nation.get('current_conflicts', '')
        last_updated= nation.get('last_updated', datetime.utcnow().isoformat())[:10]
        entity_id   = nation.get('id', '')

        dynamic_lines = [""]
        if conflicts:
            dynamic_lines += [f"**Current Conflicts:** {conflicts}", ""]
        dynamic_lines += [
            f"**Last Updated (real):** {last_updated}",
            f"**Internal ID:** `{entity_id}`",
            f"",
            f"_Tags: [[Nations]]_",
            f"",
            DYNAMIC_END,
        ]

        self._write_note(path, self._build_note(static_section, dynamic_lines[0]))

        # Rebuild properly
        dynamic_section = '\n'.join(dynamic_lines)
        self._write_note(path, self._build_note(static_section, dynamic_section))

    def log_plot_event(self, event: dict):
        """
        Appends a plot event to the Plot Events/ folder.

        Each event gets its own note, named by in-game date and a short slug of
        the event description. This means your Plot Events folder becomes a
        chronological story log that you can read and search in Obsidian.

        Note title format:  "[Year 1 Month 3 Day 7] Guards ambush player..."
        """
        in_game_date = event.get('in_game_date', 'Unknown Date')
        description  = event.get('description', '')
        event_type   = event.get('type', 'general')
        real_ts      = event.get('real_timestamp', datetime.utcnow().isoformat())[:10]
        entity_id    = event.get('id', '')

        # Build a short slug from the first ~50 chars of the description
        slug = re.sub(r'[\\/:*?"<>|]', '', description[:50]).strip().rstrip('.')
        title = f"[{in_game_date}] {slug}"

        path = self._note_path('plot_events', title)

        # Plot event notes are write-once (they're historical records)
        if path.exists():
            return  # Already logged, don't overwrite history

        lines = [
            f"# {title}",
            f"",
            f"**Type:** {event_type}",
            f"**In-Game Date:** {in_game_date}",
            f"**Recorded (real):** {real_ts}",
            f"**Internal ID:** `{entity_id}`",
            f"",
            f"## What Happened",
            f"",
            description,
            f"",
            f"_Tags: [[Plot Events]] [[{event_type.replace('_',' ').title()}]]_",
        ]
        self._write_note(path, '\n'.join(lines))

    def upsert_relationship(self, entity_id: str, entity_name: str,
                             relationships: list[dict]):
        """
        Creates or updates a Relationships note for one entity.

        Each entity gets a note in Relationships/ listing everyone they know,
        their relationship type, sentiment, and any history notes.

        This is separate from the character note so relationships can be updated
        frequently without touching your hand-crafted character lore.

        Parameters:
          entity_id     — The entity's internal UUID
          entity_name   — Display name (used as the note title)
          relationships — List of dicts from RelationshipGraph.get_all_relationships()
        """
        path = self._note_path('relationships', f"{entity_name} - Relationships")
        last_updated = datetime.utcnow().strftime('%Y-%m-%d %H:%M')

        lines = [
            f"# {entity_name} — Relationships",
            f"",
            f"_Auto-updated: {last_updated}_",
            f"**Entity ID:** `{entity_id}`",
            f"",
            f"## Known Bonds",
            f"",
        ]

        if not relationships:
            lines.append("_No established relationships on record._")
        else:
            # Group by sentiment so positive relationships come first
            positive = [r for r in relationships if r.get('sentiment', 0) > 0.1]
            neutral  = [r for r in relationships if -0.1 <= r.get('sentiment', 0) <= 0.1]
            negative = [r for r in relationships if r.get('sentiment', 0) < -0.1]

            def _row(r):
                target  = r.get('target_name', r.get('target_id', 'Unknown'))
                rtype   = r.get('type', 'neutral')
                sent    = r.get('sentiment', 0.0)
                notes   = r.get('notes', '')
                bar     = self._sentiment_bar(sent)
                row = f"- **[[{target}]]** — {rtype} `{bar}` ({sent:+.2f})"
                if notes and notes != 'No established relationship.':
                    row += f"\n  - _{notes}_"
                return row

            if positive:
                lines += ["### 💚 Positive", ""]
                lines += [_row(r) for r in sorted(positive, key=lambda x: -x.get('sentiment',0))]
                lines.append("")
            if neutral:
                lines += ["### ⬜ Neutral", ""]
                lines += [_row(r) for r in neutral]
                lines.append("")
            if negative:
                lines += ["### ❤️ Negative", ""]
                lines += [_row(r) for r in sorted(negative, key=lambda x: x.get('sentiment',0))]
                lines.append("")

        lines += [
            f"",
            f"_Tags: [[Relationships]] [[{entity_name}]]_",
        ]
        self._write_note(path, '\n'.join(lines))

    def write_session_recap(self, session_id: str, recap_text: str,
                             mode: str = 'full', world_date: str = ''):
        """
        Saves an AI-generated session recap to the Session Recaps/ folder.

        Call this after generate_recap() in session_recap.py to archive
        every "Previously on…" summary in your vault for easy reference.

        Parameters:
          session_id  — The ConversationStore session ID string
          recap_text  — The full recap text returned by generate_recap()
          mode        — 'brief', 'full', or 'bullet'
          world_date  — Current in-game date string
        """
        real_date = datetime.now().strftime('%Y-%m-%d')
        title     = f"Recap — {session_id} ({real_date})"
        path      = self._note_path('recaps', title)

        lines = [
            f"# {title}",
            f"",
            f"**Session ID:** `{session_id}`",
            f"**Recap Style:** {mode}",
            f"**World Date at Recap:** {world_date}",
            f"**Written:** {real_date}",
            f"",
            f"## Previously on…",
            f"",
            recap_text,
            f"",
            f"_Tags: [[Session Recaps]]_",
        ]
        self._write_note(path, '\n'.join(lines))

    # ── Public Methods: Read ──────────────────────────────────────────────────

    def load_entity_note(self, folder_key: str, entity_name: str) -> str:
        """
        Returns the full text of an entity's note (both sections combined).

        Used by ContextBuilder to inject extra Obsidian context into the prompt.
        If the note doesn't exist, returns an empty string (safe to use directly).

        Parameters:
          folder_key  — 'characters', 'locations', 'nations', etc.
          entity_name — The entity's display name (must match the note filename)

        Example:
          extra = bridge.load_entity_note('characters', 'Aldric Vane')
          # Returns the full markdown text of Characters/Aldric Vane.md
        """
        path = self._note_path(folder_key, entity_name)
        return self._read_note(path)

    def load_static_section(self, folder_key: str, entity_name: str) -> str:
        """
        Returns only the STATIC section of an entity note (your hand-written lore).

        This is what gets injected into the DM's context — it gives the AI access
        to your own notes without the noisy auto-generated dynamic data.

        Returns '' if no note exists.
        """
        text = self.load_entity_note(folder_key, entity_name)
        if not text:
            return ''
        static, _ = self._split_note(text)
        return static.strip()

    def search_notes(self, folder_key: str, query_words: list[str],
                     max_results: int = 5) -> list[dict]:
        """
        Simple keyword search across all notes in a vault folder.

        Not semantic (no vectors here) — this is a fast plain-text grep that's
        useful for finding Obsidian notes by name or content keywords.

        Parameters:
          folder_key  — Which subfolder to search
          query_words — List of lowercase words to search for (ANY match = included)
          max_results — Maximum number of results to return

        Returns a list of dicts: [{'title': str, 'path': str, 'snippet': str}]
        """
        folder = self.vault / VAULT_FOLDERS[folder_key]
        if not folder.exists():
            return []

        results = []
        q_lower = [w.lower() for w in query_words]

        for md_file in sorted(folder.iterdir()):
            if not md_file.suffix == '.md':
                continue
            text = self._read_note(md_file)
            text_lower = text.lower()

            if any(word in text_lower for word in q_lower):
                # Grab a short snippet around the first match
                for word in q_lower:
                    idx = text_lower.find(word)
                    if idx != -1:
                        start   = max(0, idx - 40)
                        end     = min(len(text), idx + 120)
                        snippet = text[start:end].replace('\n', ' ').strip()
                        break
                else:
                    snippet = text[:120].replace('\n', ' ').strip()

                results.append({
                    'title':   md_file.stem,
                    'path':    str(md_file),
                    'snippet': snippet,
                })

            if len(results) >= max_results:
                break

        return results

    def build_context_for_entity(self, entity_name: str,
                                  include_relationships: bool = True) -> str:
        """
        Assembles a compact context block for one entity by pulling from all
        relevant Obsidian notes (character + relationships).

        This is what you'd inject into the DM's extra_context argument when
        the player interacts with a named NPC the AI might have forgotten.

        Returns a formatted plain-text string, or '' if no notes found.
        """
        blocks = []

        # Try character note first
        char_static = self.load_static_section('characters', entity_name)
        if char_static:
            blocks.append(f"[Obsidian Notes: {entity_name}]\n{char_static}")

        # Try location note
        if not char_static:
            loc_static = self.load_static_section('locations', entity_name)
            if loc_static:
                blocks.append(f"[Obsidian Notes: {entity_name}]\n{loc_static}")

        # Optionally include relationship note
        if include_relationships:
            rel_text = self.load_entity_note('relationships', f"{entity_name} - Relationships")
            if rel_text:
                # Only include the "Known Bonds" section, not the full note header
                if "## Known Bonds" in rel_text:
                    bonds = rel_text.split("## Known Bonds", 1)[1].strip()
                    bonds = bonds.split("_Tags:")[0].strip()
                    if bonds:
                        blocks.append(f"[Relationships for {entity_name}]\n{bonds}")

        return '\n\n'.join(blocks)

    # ── Sync Method: Push All WorldState Data to Obsidian ─────────────────────

    def sync_from_world_state(self, world, graph):
        """
        Pushes ALL current WorldState and RelationshipGraph data to Obsidian.

        Call this once per session to do a full vault sync, or after any
        significant world update. It's safe to call repeatedly — existing notes
        are updated, not duplicated.

        Parameters:
          world — A WorldState instance
          graph — A RelationshipGraph instance

        Typical usage in dm_agent.py after each turn:
          self.obsidian.sync_from_world_state(self.world, self.graph)

        Or call it manually from main.py with:
          dm.obsidian.sync_from_world_state(dm.world, dm.graph)
        """
        from memory.world_state import CHARACTERS, LOCATIONS, NATIONS, PLOT_EVENTS

        print('[Obsidian] Syncing world state to vault…')

        # ── Characters ─────────────────────────────────────────────────────
        characters = world._get_all_entities(CHARACTERS)
        for char in characters:
            try:
                self.upsert_character(char)
            except Exception as e:
                print(f'  [Obsidian] Character sync error ({char.get("name","?")}): {e}')

        # ── Locations ──────────────────────────────────────────────────────
        locations = world._get_all_entities(LOCATIONS)
        for loc in locations:
            try:
                self.upsert_location(loc)
            except Exception as e:
                print(f'  [Obsidian] Location sync error ({loc.get("name","?")}): {e}')

        # ── Nations ────────────────────────────────────────────────────────
        nations = world._get_all_entities(NATIONS)
        for nation in nations:
            try:
                self.upsert_nation(nation)
            except Exception as e:
                print(f'  [Obsidian] Nation sync error ({nation.get("name","?")}): {e}')

        # ── Plot Events ────────────────────────────────────────────────────
        events = world._get_all_entities(PLOT_EVENTS)
        for event in events:
            try:
                self.log_plot_event(event)
            except Exception as e:
                print(f'  [Obsidian] Plot event sync error: {e}')

        # ── Relationships ──────────────────────────────────────────────────
        # Write one relationships note per entity that has outgoing edges
        for node_id in graph.graph.nodes:
            try:
                name  = graph.get_entity_name(node_id)
                rels  = graph.get_all_relationships(node_id)
                if rels:
                    self.upsert_relationship(node_id, name, rels)
            except Exception as e:
                print(f'  [Obsidian] Relationship sync error ({node_id}): {e}')

        print(f'[Obsidian] Sync complete. Vault: {self.vault}')

    def sync_single_character(self, character: dict, graph=None):
        """
        Syncs just one character to Obsidian (faster than a full sync).

        Call this in dm_agent.py right after _extract_and_save_npcs() saves
        a new NPC, so the note appears in Obsidian immediately.

        Parameters:
          character — The character dict returned / saved by WorldState
          graph     — Optional RelationshipGraph to also update relationships note
        """
        try:
            self.upsert_character(character)
            if graph:
                char_id   = character.get('id', '')
                char_name = character.get('name', '')
                rels      = graph.get_all_relationships(char_id)
                self.upsert_relationship(char_id, char_name, rels)
        except Exception as e:
            print(f'  [Obsidian] Single character sync error: {e}')

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _sentiment_bar(sentiment: float) -> str:
        """
        Converts a -1.0 to +1.0 sentiment float into a small visual bar.
        Example: +0.75 → '████░'   -0.5 → '░░██░'   0.0 → '░░░░░'
        """
        filled = round((sentiment + 1.0) / 2.0 * 5)  # 0-5 filled blocks
        filled = max(0, min(5, filled))
        return '█' * filled + '░' * (5 - filled)

    @staticmethod
    def _location_tag(location_name: str) -> str:
        """Converts a location name to an Obsidian wikilink tag, or '' if unknown."""
        if not location_name or location_name.lower() in ('unknown', ''):
            return ''
        return f"[[{location_name}]]"

    def get_vault_summary(self) -> dict:
        """
        Returns a count of all notes in each vault folder.
        Useful for debugging or a 'vault status' command.
        """
        summary = {}
        for key, folder_name in VAULT_FOLDERS.items():
            folder = self.vault / folder_name
            if folder.exists():
                summary[key] = len([f for f in folder.iterdir() if f.suffix == '.md'])
            else:
                summary[key] = 0
        return summary


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION GUIDE
# ─────────────────────────────────────────────────────────────────────────────
#
# ── Step 1: Import in dm_agent.py ─────────────────────────────────────────
#
#   Add at the top of dm_agent.py (after existing imports):
#
#       from obsidian_bridge import ObsidianBridge
#
#
# ── Step 2: Initialize in DMAgent.__init__() ──────────────────────────────
#
#   Add after the existing subsystem initializations:
#
#       # ── Obsidian vault bridge ──────────────────────────────────────────
#       self.obsidian = ObsidianBridge()
#       # Do an initial sync so Obsidian is up to date when the session starts
#       self.obsidian.sync_from_world_state(self.world, self.graph)
#
#
# ── Step 3: Sync after each NPC is saved ──────────────────────────────────
#
#   In DMAgent._extract_and_save_npcs(), right after the line:
#       self.npcs_saved_this_turn.append(name)
#
#   Add:
#       # Push the new NPC to Obsidian immediately
#       self.obsidian.sync_single_character(
#           self.world.get_character(npc_id),
#           self.graph
#       )
#
#
# ── Step 4: Sync plot events as they happen ───────────────────────────────
#
#   In DMAgent._parse_and_update_world(), right after world.log_plot_event():
#
#       # We need to get the event we just saved to pass to Obsidian
#       recent = self.world.get_recent_plot_events(n=1)
#       if recent:
#           self.obsidian.log_plot_event(recent[0])
#
#
# ── Step 5: Load Obsidian notes into the DM's context ─────────────────────
#
#   In context_builder.py, inside build_system_prompt(), you can inject
#   your hand-written Obsidian notes for any NPC the player is near.
#
#   Example — add this near the top of build_system_prompt():
#
#       # Pull Obsidian notes for the current location if available
#       obsidian = getattr(_cfg, 'OBSIDIAN_BRIDGE', None)
#       obsidian_context = ''
#       if obsidian and current_location_id:
#           loc = self.world.get_location(current_location_id)
#           if loc:
#               obsidian_context = obsidian.build_context_for_entity(loc.get('name',''))
#
#   Then include obsidian_context in extra_context:
#       extra_context = (obsidian_context + '\n' + extra_context).strip()
#
#   And in config.py, add after set_active_system():
#       from obsidian_bridge import ObsidianBridge
#       OBSIDIAN_BRIDGE = ObsidianBridge()
#
#
# ── Step 6: Archive session recaps ────────────────────────────────────────
#
#   In session_recap.py, inside generate_recap(), after getting recap_text:
#
#       import config as _cfg
#       obsidian = getattr(_cfg, 'OBSIDIAN_BRIDGE', None)
#       if obsidian:
#           obsidian.write_session_recap(
#               session_id = dm.conv.session_id,
#               recap_text = recap_text,
#               mode       = mode,
#               world_date = dm.world.get_current_date_str()
#           )
#
#
# ── Step 7 (optional): vault status command in main.py ────────────────────
#
#   Add this case inside the main game loop's command handler:
#
#       elif lower_input == 'vault':
#           import config as _cfg
#           obsidian = getattr(_cfg, 'OBSIDIAN_BRIDGE', None)
#           if obsidian:
#               summary = obsidian.get_vault_summary()
#               console.print('[bold cyan]Obsidian Vault Status:[/bold cyan]')
#               for k, v in summary.items():
#                   console.print(f'  {k:15} {v} notes')
#           continue
#
# ─────────────────────────────────────────────────────────────────────────────
