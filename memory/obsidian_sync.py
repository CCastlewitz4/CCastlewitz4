# memory/obsidian_sync.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Two-way sync between the DnD AI DM system and an Obsidian vault.
#
# WHAT THIS DOES:
#   Every entity the AI saves (characters, locations, nations, plot events)
#   gets a corresponding Markdown note in your Obsidian vault. The vault
#   is organized into folders that mirror the game's data model.
#
#   WRITES to Obsidian automatically when:
#     - A new character/location/nation is created
#     - A character is updated (appearance, mood, last seen, etc.)
#     - A plot event is logged
#     - A relationship changes
#     - In-game time advances
#
#   READS from Obsidian when:
#     - You manually edit a note and want those changes loaded back into the AI
#     - The DM needs to recall info that was edited by hand
#
# VAULT FOLDER STRUCTURE:
#   DND Memory/
#   ├── Characters/          ← One note per NPC/PC. Static fields + dynamic updates.
#   ├── Locations/           ← Cities, dungeons, taverns, etc.
#   ├── Nations/             ← Kingdoms, empires, factions.
#   ├── Plot Events/         ← Chronicle of major story beats, in-game dated.
#   ├── Relationships/       ← One note per entity listing all their connections.
#   └── Campaign/
#       ├── Session Log.md   ← Every conversation turn, auto-appended.
#       └── World Clock.md   ← Current in-game date/time, updated each turn.
#
# STATIC vs DYNAMIC FIELDS:
#   Static  — Set once, rarely change: name, race, class, backstory, appearance.
#             These sit in a "## Identity" section at the top of each note.
#   Dynamic — Change during play: current mood, last seen location, last seen date,
#             actions taken, relationship sentiment.
#             These sit in a "## Current Status" section that gets overwritten
#             each update. The "## History" section APPENDS new entries so you
#             have a full log of changes over time.
#
# HOW TO USE:
#   1. Set OBSIDIAN_VAULT_PATH in config.py (see below).
#   2. Import and call sync functions from dm_agent.py (see INTEGRATION section).
#   3. Open Obsidian. Everything appears automatically.
#
# READING BACK EDITS:
#   If you edit a note in Obsidian (e.g. you correct an NPC's description),
#   call obsidian_sync.read_character_note(name) to get the updated dict back.
#   Then pass it to world_state.save_character() to load it into the AI.
#
# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION — add these calls to dm_agent.py:
#
#   At the top of dm_agent.py, add:
#       from memory.obsidian_sync import ObsidianSync
#
#   In DMAgent.__init__(), after self.world is created, add:
#       self.obs = ObsidianSync()
#
#   At the END of _extract_and_save_npcs(), after each world.save_character():
#       self.obs.write_character(character_data)
#
#   At the END of _parse_and_update_world(), after log_plot_event():
#       self.obs.write_plot_event(event_data)
#       self.obs.write_world_clock(self.world.get_current_date_str())
#
#   In respond(), after self.conv.add(role='assistant', ...), add:
#       self.obs.append_session_log(
#           player_input, dm_response, self.world.get_current_date_str()
#       )
#
#   In set_relationship(), after self.graph.set_relationship(...), add:
#       self.obs.write_relationship(from_id, to_id, rel_type, sentiment, notes)
#
#   In world_builder.py, after save_location() / save_nation():
#       self.obs.write_location(location_data)
#       self.obs.write_nation(nation_data)
# ─────────────────────────────────────────────────────────────────────────────

import os
import re
import json
from datetime import datetime

# ── Vault path ─────────────────────────────────────────────────────────────
# This is read from config if set there, otherwise falls back to the default.
# To override: add OBSIDIAN_VAULT = "C:/your/path/here" to config.py
try:
    import config as _cfg
    VAULT_PATH = getattr(
        _cfg, 'OBSIDIAN_VAULT',
        r'C:\Users\colin\Desktop\DND_AI_DM Backup\DND_AI_DM\dnd_ai_dm\data\DND Memory'
    )
except ImportError:
    VAULT_PATH = r'C:\Users\colin\Desktop\DND_AI_DM Backup\DND_AI_DM\dnd_ai_dm\data\DND Memory'

# ── Subfolder names inside the vault ───────────────────────────────────────
FOLDER_CHARACTERS   = 'Characters'
FOLDER_LOCATIONS    = 'Locations'
FOLDER_NATIONS      = 'Nations'
FOLDER_PLOT_EVENTS  = 'Plot Events'
FOLDER_RELATIONSHIPS = 'Relationships'
FOLDER_CAMPAIGN     = 'Campaign'

ALL_FOLDERS = [
    FOLDER_CHARACTERS,
    FOLDER_LOCATIONS,
    FOLDER_NATIONS,
    FOLDER_PLOT_EVENTS,
    FOLDER_RELATIONSHIPS,
    FOLDER_CAMPAIGN,
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _safe_filename(name: str) -> str:
    """
    Converts an entity name into a safe filename.
    Strips characters that are illegal in Windows/Mac/Linux filenames.
    Example: 'Guard Captain: Hern' -> 'Guard Captain Hern'
    """
    # Replace illegal filename characters with a space
    safe = re.sub(r'[\\/:*?"<>|]', ' ', name or 'Unknown')
    # Collapse multiple spaces and strip edges
    safe = re.sub(r'\s+', ' ', safe).strip()
    return safe or 'Unknown'


def _note_path(folder: str, name: str) -> str:
    """Returns the full path to a note file inside the vault."""
    return os.path.join(VAULT_PATH, folder, f'{_safe_filename(name)}.md')


def _write_note(path: str, content: str):
    """
    Writes content to a Markdown note file.
    Creates parent directories if they don't exist.
    Always overwrites the file (use _append_to_note for adding history lines).
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def _append_to_note(path: str, content: str):
    """
    Appends content to an existing note without overwriting it.
    Creates the file first (with the content) if it doesn't exist yet.
    Used for the History section of character/location notes and session logs.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(content)


def _read_note(path: str) -> str:
    """Reads and returns the full text of a note. Returns '' if file not found."""
    if not os.path.exists(path):
        return ''
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _extract_section(note_text: str, section_header: str) -> str:
    """
    Extracts the content of a Markdown section (## Header) from a note.
    Returns everything between that header and the next ## header (or end of file).
    Returns '' if the section doesn't exist.

    Example: _extract_section(text, '## Current Status') returns lines
    under that heading up to the next heading or end of file.
    """
    pattern = rf'^{re.escape(section_header)}\s*$(.*?)(?=^##|\Z)'
    match = re.search(pattern, note_text, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ''


def _replace_section(note_text: str, section_header: str, new_content: str) -> str:
    """
    Replaces the content of a named Markdown section in a note string.
    If the section doesn't exist, appends it at the end.

    Used to update the '## Current Status' block on character notes
    without touching the static '## Identity' block above it.

    Parameters:
      note_text      — Full text of the existing note
      section_header — The ## heading line to find and replace under
      new_content    — The new text to put under that heading

    Returns the full note text with the section replaced.
    """
    new_section = f'{section_header}\n{new_content}\n'
    pattern = rf'(^{re.escape(section_header)}\s*$)(.*?)(?=^##|\Z)'
    if re.search(pattern, note_text, re.MULTILINE | re.DOTALL):
        return re.sub(
            pattern,
            new_section,
            note_text,
            flags=re.MULTILINE | re.DOTALL
        )
    # Section not found — append it
    return note_text.rstrip() + '\n\n' + new_section


def _now_real() -> str:
    """Returns the current real-world UTC timestamp as a readable string."""
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')


# ══════════════════════════════════════════════════════════════════════════════
# OBSIDIAN SYNC CLASS
# ══════════════════════════════════════════════════════════════════════════════

class ObsidianSync:
    """
    Manages all reads and writes between the AI system and the Obsidian vault.

    One instance per DMAgent session. Call its write_* methods whenever
    an entity is created or updated. Call its read_* methods to pull
    manually-edited vault notes back into the AI's memory.
    """

    def __init__(self, vault_path: str = None):
        """
        Parameters:
          vault_path — Override the default vault path for this session.
                       If None, uses the VAULT_PATH constant defined above.
        """
        self.vault = vault_path or VAULT_PATH
        self._ensure_vault_structure()

    def _ensure_vault_structure(self):
        """
        Creates all required subfolders inside the vault if they don't exist.
        Safe to call on every startup — exist_ok=True prevents errors.
        """
        for folder in ALL_FOLDERS:
            os.makedirs(os.path.join(self.vault, folder), exist_ok=True)
        print(f'[ObsidianSync] Vault ready at: {self.vault}')

    # ══════════════════════════════════════════════════════════════════════
    # CHARACTER NOTES
    # ══════════════════════════════════════════════════════════════════════

    def write_character(self, char: dict):
        """
        Writes or updates a character note in the Characters/ folder.

        STRUCTURE OF THE GENERATED NOTE:
        ┌─────────────────────────────────────────────────────┐
        │  # Character Name                                   │
        │  *tags: #character #race #class*                    │
        │                                                     │
        │  ## Identity           ← STATIC, written once       │
        │  | Field | Value |                                  │
        │  Race, class, age, faction, appearance, backstory   │
        │                                                     │
        │  ## Current Status     ← DYNAMIC, overwritten each  │
        │  - Location:           update                       │
        │  - Last Seen:                                       │
        │  - Current Mood:                                    │
        │  - Goals:                                           │
        │                                                     │
        │  ## History            ← APPEND-ONLY, never erased  │
        │  - [date] First entry                               │
        │  - [date] Subsequent updates                        │
        └─────────────────────────────────────────────────────┘

        If the note already exists, only '## Current Status' is replaced.
        '## Identity' and '## History' are preserved exactly as written.
        Manually edited Identity text is kept intact.
        """
        name       = char.get('name', 'Unknown')
        race       = char.get('race', '')
        char_class = char.get('class', char.get('occupation', ''))
        path       = _note_path(FOLDER_CHARACTERS, name)
        in_game    = char.get('last_seen_date', char.get('last_updated', ''))
        real_now   = _now_real()

        existing = _read_note(path)

        if not existing:
            # ── New note — write full template ────────────────────────────
            tags = ' '.join(filter(None, [
                '#character',
                f'#{race.lower().replace(" ", "_")}' if race else '',
                f'#{char_class.lower().replace(" ", "_")}' if char_class else '',
            ]))

            identity_table = (
                '| Field | Value |\n'
                '|---|---|\n'
                + '\n'.join(
                    f'| **{k.replace("_", " ").title()}** | {v} |'
                    for k, v in [
                        ('Name',        name),
                        ('Race',        race),
                        ('Class',       char_class),
                        ('Age',         char.get('age', '')),
                        ('Faction',     char.get('faction', '')),
                        ('Alignment',   char.get('alignment', '')),
                        ('Appearance',  char.get('appearance', '')),
                        ('Personality', char.get('personality', '')),
                        ('Speech Style',char.get('speech_style', '')),
                        ('Backstory',   char.get('backstory', '')),
                        ('Secrets',     char.get('secrets', '')),
                        ('Entity ID',   char.get('id', '')),
                    ]
                    if v  # Skip blank rows
                )
            )

            current_status = (
                f'- **Location:** {char.get("location", "Unknown")}\n'
                f'- **Last Seen (in-game):** {in_game}\n'
                f'- **Current Mood:** {char.get("current_mood", "Unknown")}\n'
                f'- **Goals:** {char.get("goals", "Unknown")}\n'
                f'- **Last Updated (real):** {real_now}'
            )

            history_entry = (
                f'- [{real_now}] Character first introduced.'
                + (f' Mood: {char.get("current_mood", "")}.' if char.get('current_mood') else '')
                + (f' Location: {char.get("location", "")}.' if char.get('location') else '')
            )

            note = (
                f'# {name}\n'
                f'*{tags}*\n\n'
                f'## Identity\n'
                f'{identity_table}\n\n'
                f'## Current Status\n'
                f'{current_status}\n\n'
                f'## History\n'
                f'{history_entry}\n'
            )
            _write_note(path, note)

        else:
            # ── Existing note — update Current Status, append to History ──

            # Build the new Current Status block
            new_status = (
                f'- **Location:** {char.get("location", "Unknown")}\n'
                f'- **Last Seen (in-game):** {in_game}\n'
                f'- **Current Mood:** {char.get("current_mood", "Unknown")}\n'
                f'- **Goals:** {char.get("goals", "Unknown")}\n'
                f'- **Last Updated (real):** {real_now}'
            )

            updated = _replace_section(existing, '## Current Status', new_status)

            # Append a history entry
            history_line = (
                f'\n- [{real_now}] Updated.'
                + (f' Mood: {char.get("current_mood", "")}.' if char.get('current_mood') else '')
                + (f' Location: {char.get("location", "")}.' if char.get('location') else '')
            )

            # Insert history line after the ## History header
            if '## History' in updated:
                updated = updated.replace(
                    '## History\n',
                    '## History\n' + history_line + '\n',
                    1
                )
            else:
                updated += f'\n\n## History\n{history_line}\n'

            _write_note(path, updated)

    def read_character_note(self, name: str) -> dict:
        """
        Reads a character note from the vault and returns a dict
        that can be passed directly to world_state.save_character().

        Use this when you've manually edited a note in Obsidian
        and want those changes loaded back into the AI's memory.

        Parses the Identity table for all key/value pairs.
        Returns an empty dict if the note doesn't exist.

        Example usage in main.py or a manual admin script:
            updated = obs.read_character_note('Mira the Merchant')
            if updated:
                dm.world.save_character(updated)
        """
        path = _note_path(FOLDER_CHARACTERS, name)
        text = _read_note(path)
        if not text:
            return {}

        char = {}

        # Parse the Identity table rows: | **Field Name** | Value |
        for match in re.finditer(r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|', text):
            key   = match.group(1).strip().lower().replace(' ', '_')
            value = match.group(2).strip()
            if value and value != '—':
                char[key] = value

        # Rename table keys back to the dict keys the system expects
        rename = {
            'class':       'class',
            'speech_style': 'speech_style',
            'entity_id':   'id',
        }
        for old_key, new_key in rename.items():
            if old_key in char and old_key != new_key:
                char[new_key] = char.pop(old_key)

        # Parse Current Status section for dynamic fields
        status_text = _extract_section(text, '## Current Status')
        for line in status_text.splitlines():
            for label, key in [
                ('Location:', 'location'),
                ('Last Seen (in-game):', 'last_seen_date'),
                ('Current Mood:', 'current_mood'),
                ('Goals:', 'goals'),
            ]:
                if label in line:
                    value = line.split(label, 1)[-1].strip().lstrip('*').rstrip('*').strip()
                    if value and value not in ('Unknown', ''):
                        char[key] = value

        return char

    # ══════════════════════════════════════════════════════════════════════
    # LOCATION NOTES
    # ══════════════════════════════════════════════════════════════════════

    def write_location(self, loc: dict):
        """
        Writes or updates a location note in the Locations/ folder.

        Static fields (name, type, nation, description, notable features)
        sit in '## Description' — written once, manually editable.

        Dynamic fields (current events, atmosphere, dangers) sit in
        '## Current Situation' — overwritten on each update.

        History entries (when the player visited, what happened) are
        appended to '## Visit Log' and are never erased.
        """
        name     = loc.get('name', 'Unknown Location')
        path     = _note_path(FOLDER_LOCATIONS, name)
        real_now = _now_real()
        in_game  = loc.get('last_updated', '')

        existing = _read_note(path)

        if not existing:
            loc_type = loc.get('type', 'place')
            tags = f'#location #{loc_type.lower().replace(" ", "_")}'
            if loc.get('nation'):
                tags += f' #{loc.get("nation", "").lower().replace(" ", "_")}'

            description_table = (
                '| Field | Value |\n'
                '|---|---|\n'
                + '\n'.join(
                    f'| **{k}** | {v} |'
                    for k, v in [
                        ('Type',             loc.get('type', '')),
                        ('Nation',           loc.get('nation', '')),
                        ('Population',       loc.get('population', '')),
                        ('Description',      loc.get('description', '')),
                        ('Notable Features', loc.get('notable_features', '')),
                        ('Entity ID',        loc.get('id', '')),
                    ]
                    if v
                )
            )

            current_situation = (
                f'- **Current Events:** {loc.get("current_events", "None noted")}\n'
                f'- **Atmosphere:** {loc.get("atmosphere", "Unknown")}\n'
                f'- **Known Dangers:** {loc.get("dangers", "None noted")}\n'
                f'- **Last Updated (real):** {real_now}'
            )

            note = (
                f'# {name}\n'
                f'*{tags}*\n\n'
                f'## Description\n'
                f'{description_table}\n\n'
                f'## Current Situation\n'
                f'{current_situation}\n\n'
                f'## Visit Log\n'
                f'- [{real_now}] Location created.\n'
            )
            _write_note(path, note)

        else:
            new_situation = (
                f'- **Current Events:** {loc.get("current_events", "None noted")}\n'
                f'- **Atmosphere:** {loc.get("atmosphere", "Unknown")}\n'
                f'- **Known Dangers:** {loc.get("dangers", "None noted")}\n'
                f'- **Last Updated (real):** {real_now}'
            )
            updated = _replace_section(existing, '## Current Situation', new_situation)

            visit_line = f'\n- [{real_now}] Location updated.'
            if '## Visit Log' in updated:
                updated = updated.replace('## Visit Log\n', '## Visit Log\n' + visit_line + '\n', 1)
            else:
                updated += f'\n\n## Visit Log\n{visit_line}\n'

            _write_note(path, updated)

    def read_location_note(self, name: str) -> dict:
        """
        Reads a location note back into a dict for world_state.save_location().
        Useful if you've manually edited location details in Obsidian.
        """
        path = _note_path(FOLDER_LOCATIONS, name)
        text = _read_note(path)
        if not text:
            return {}

        loc = {}
        for match in re.finditer(r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|', text):
            key   = match.group(1).strip().lower().replace(' ', '_')
            value = match.group(2).strip()
            if value and value != '—':
                loc[key] = value

        if 'entity_id' in loc:
            loc['id'] = loc.pop('entity_id')

        status = _extract_section(text, '## Current Situation')
        for line in status.splitlines():
            for label, key in [
                ('Current Events:', 'current_events'),
                ('Atmosphere:', 'atmosphere'),
                ('Known Dangers:', 'dangers'),
            ]:
                if label in line:
                    value = line.split(label, 1)[-1].strip().lstrip('*').rstrip('*').strip()
                    if value not in ('None noted', 'Unknown', ''):
                        loc[key] = value

        return loc

    # ══════════════════════════════════════════════════════════════════════
    # NATION NOTES
    # ══════════════════════════════════════════════════════════════════════

    def write_nation(self, nation: dict):
        """
        Writes or updates a nation note in the Nations/ folder.

        Static: government type, culture, economy, capital.
        Dynamic: current ruler, military strength, active conflicts.
        History: appended entries recording political changes.
        """
        name     = nation.get('name', 'Unknown Nation')
        path     = _note_path(FOLDER_NATIONS, name)
        real_now = _now_real()

        existing = _read_note(path)

        if not existing:
            gov = nation.get('government', 'nation')
            tags = f'#nation #{gov.lower().replace(" ", "_")}'

            identity_table = (
                '| Field | Value |\n'
                '|---|---|\n'
                + '\n'.join(
                    f'| **{k}** | {v} |'
                    for k, v in [
                        ('Government',    nation.get('government', '')),
                        ('Capital City',  nation.get('capital_city_id', '')),
                        ('Culture',       nation.get('culture', '')),
                        ('Economy',       nation.get('economy', '')),
                        ('Notable Laws',  nation.get('notable_laws', '')),
                        ('Description',   nation.get('description', '')),
                        ('Entity ID',     nation.get('id', '')),
                    ]
                    if v
                )
            )

            current_state = (
                f'- **Current Ruler:** {nation.get("current_ruler", "Unknown")}\n'
                f'- **Military Strength:** {nation.get("military_strength", "Unknown")}\n'
                f'- **Active Conflicts:** {nation.get("current_conflicts", "None")}\n'
                f'- **Last Updated (real):** {real_now}'
            )

            note = (
                f'# {name}\n'
                f'*{tags}*\n\n'
                f'## Identity\n'
                f'{identity_table}\n\n'
                f'## Current State\n'
                f'{current_state}\n\n'
                f'## Political History\n'
                f'- [{real_now}] Nation created.\n'
            )
            _write_note(path, note)

        else:
            new_state = (
                f'- **Current Ruler:** {nation.get("current_ruler", "Unknown")}\n'
                f'- **Military Strength:** {nation.get("military_strength", "Unknown")}\n'
                f'- **Active Conflicts:** {nation.get("current_conflicts", "None")}\n'
                f'- **Last Updated (real):** {real_now}'
            )
            updated = _replace_section(existing, '## Current State', new_state)

            history_line = f'\n- [{real_now}] Nation updated.'
            if '## Political History' in updated:
                updated = updated.replace(
                    '## Political History\n',
                    '## Political History\n' + history_line + '\n', 1
                )
            else:
                updated += f'\n\n## Political History\n{history_line}\n'

            _write_note(path, updated)

    # ══════════════════════════════════════════════════════════════════════
    # PLOT EVENTS
    # ══════════════════════════════════════════════════════════════════════

    def write_plot_event(self, event: dict):
        """
        Appends a new plot event to a dedicated note in Plot Events/.

        Each event gets its own note named by the in-game date + a short title.
        Example filename: 'Year 1 Month 2 Day 5 - story_beat.md'

        The note lists: in-game date, event type, full description, and which
        entities were involved. This builds a complete campaign chronicle
        that you can browse in Obsidian's calendar or graph view.
        """
        in_game  = event.get('in_game_date', 'Unknown Date')
        etype    = event.get('type', 'event')
        desc     = event.get('description', '')
        involved = event.get('involved_entities', [])
        real_now = _now_real()

        # Use date + type as the filename for easy chronological browsing
        safe_date = re.sub(r'[^\w\s\-]', '', in_game).strip().replace(' ', '_')
        note_name = f'{safe_date}_{etype}'
        path      = _note_path(FOLDER_PLOT_EVENTS, note_name)

        # Format involved entities as wiki-links so Obsidian connects them
        entity_links = ', '.join(f'[[{e}]]' for e in involved) if involved else 'None'

        note = (
            f'# Plot Event: {in_game}\n'
            f'*#plot_event #{etype.replace(" ", "_")}*\n\n'
            f'| Field | Value |\n'
            f'|---|---|\n'
            f'| **In-Game Date** | {in_game} |\n'
            f'| **Event Type** | {etype} |\n'
            f'| **Recorded (real)** | {real_now} |\n'
            f'| **Entities Involved** | {entity_links} |\n\n'
            f'## Description\n'
            f'{desc}\n'
        )
        _write_note(path, note)

    # ══════════════════════════════════════════════════════════════════════
    # RELATIONSHIP NOTES
    # ══════════════════════════════════════════════════════════════════════

    def write_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        sentiment: float,
        notes: str = '',
        from_name: str = '',
        to_name: str = '',
    ):
        """
        Updates a Relationships/ note for the source entity.

        Each entity gets ONE relationship note that lists ALL their connections.
        When a relationship is added or updated, the relevant line is updated
        in-place. This gives you a single-page view of all an entity's bonds.

        SENTIMENT KEY:
          -1.0 = Sworn enemy    -0.5 = Hostile     0.0 = Neutral
          +0.5 = Friendly       +1.0 = Deeply loyal

        The note uses Obsidian wiki-links ([[Name]]) so the graph view
        automatically draws lines between connected characters.
        """
        # Display names fall back to IDs if not provided
        src_label  = from_name or from_id
        tgt_label  = to_name or to_id
        path       = _note_path(FOLDER_RELATIONSHIPS, src_label)
        real_now   = _now_real()

        # Build a sentiment word for readability
        if sentiment <= -0.75:   sent_word = 'Sworn Enemy'
        elif sentiment <= -0.4:  sent_word = 'Hostile'
        elif sentiment <= -0.1:  sent_word = 'Cold'
        elif sentiment <= 0.1:   sent_word = 'Neutral'
        elif sentiment <= 0.4:   sent_word = 'Friendly'
        elif sentiment <= 0.7:   sent_word = 'Trusting'
        else:                    sent_word = 'Deeply Loyal'

        new_rel_line = (
            f'| [[{tgt_label}]] | {rel_type} | {sentiment:+.2f} ({sent_word}) | {notes} |'
        )

        existing = _read_note(path)

        if not existing:
            note = (
                f'# Relationships: {src_label}\n'
                f'*#relationships*\n\n'
                f'## Connections\n'
                f'| Target | Type | Sentiment | Notes |\n'
                f'|---|---|---|---|\n'
                f'{new_rel_line}\n\n'
                f'## Change Log\n'
                f'- [{real_now}] Relationship with [[{tgt_label}]] set to {sent_word}.\n'
            )
            _write_note(path, note)
        else:
            # Replace existing row for this target if it exists, else append it
            safe_target = re.escape(f'[[{tgt_label}]]')
            row_pattern = rf'^\|\s*{safe_target}\s*\|.*$'
            if re.search(row_pattern, existing, re.MULTILINE):
                updated = re.sub(row_pattern, new_rel_line, existing, flags=re.MULTILINE)
            else:
                # Append new row after table header
                updated = existing.replace(
                    '| Target | Type | Sentiment | Notes |\n|---|---|---|---|\n',
                    f'| Target | Type | Sentiment | Notes |\n|---|---|---|---|\n{new_rel_line}\n'
                )

            # Append change log entry
            log_line = (
                f'\n- [{real_now}] Relationship with [[{tgt_label}]]: '
                f'{rel_type}, {sent_word}.'
                + (f' "{notes}"' if notes else '')
            )
            if '## Change Log' in updated:
                updated = updated.replace('## Change Log\n', '## Change Log\n' + log_line + '\n', 1)
            else:
                updated += f'\n\n## Change Log\n{log_line}\n'

            _write_note(path, updated)

    # ══════════════════════════════════════════════════════════════════════
    # SESSION LOG
    # ══════════════════════════════════════════════════════════════════════

    def append_session_log(self, player_input: str, dm_response: str, in_game_date: str):
        """
        Appends one conversation turn to Campaign/Session Log.md.

        The session log is a continuous record of every player action and
        DM response, tagged with the in-game date. You can scroll through
        this in Obsidian to replay the whole campaign chronologically.

        DM responses are truncated to 600 characters in the log to keep
        the file readable — full responses are in the JSON session files.

        Parameters:
          player_input — What the player typed
          dm_response  — The DM's full response text
          in_game_date — The in-game timestamp at the time of this turn
        """
        path     = os.path.join(self.vault, FOLDER_CAMPAIGN, 'Session Log.md')
        real_now = _now_real()

        # Truncate long DM responses for readability in the log
        dm_snippet = dm_response[:600] + ('…' if len(dm_response) > 600 else '')

        entry = (
            f'\n---\n'
            f'**[{in_game_date}]** *(logged: {real_now})*\n\n'
            f'**Player:** {player_input}\n\n'
            f'**DM:** {dm_snippet}\n'
        )

        # Create the file with a header if it doesn't exist yet
        if not os.path.exists(path):
            header = (
                '# Session Log\n'
                '*A continuous record of the campaign, turn by turn.*\n'
                '*DM responses shown up to 600 characters. Full text is in the JSON session files.*\n'
            )
            _write_note(path, header)

        _append_to_note(path, entry)

    # ══════════════════════════════════════════════════════════════════════
    # WORLD CLOCK
    # ══════════════════════════════════════════════════════════════════════

    def write_world_clock(self, date_str: str):
        """
        Overwrites Campaign/World Clock.md with the current in-game date.

        This gives you a quick reference in Obsidian that always shows
        the current date without having to look at any other file.

        Parameters:
          date_str — The formatted date string from world_state.get_current_date_str()
        """
        path     = os.path.join(self.vault, FOLDER_CAMPAIGN, 'World Clock.md')
        real_now = _now_real()

        content = (
            f'# World Clock\n\n'
            f'## Current In-Game Date\n'
            f'**{date_str}**\n\n'
            f'---\n'
            f'*Last updated (real): {real_now}*\n'
        )
        _write_note(path, content)

    # ══════════════════════════════════════════════════════════════════════
    # BULK SYNC — pull all existing JSON data into Obsidian at once
    # ══════════════════════════════════════════════════════════════════════

    def sync_all_from_world_state(self, world_state):
        """
        One-time bulk sync: reads every entity from WorldState's JSON files
        and writes a corresponding Obsidian note for each one.

        Run this once to populate a fresh vault with all existing campaign data.
        Safe to re-run — it just overwrites the dynamic sections.

        Usage (e.g. in main.py or a standalone script):
            from memory.obsidian_sync import ObsidianSync
            from memory.world_state import WorldState
            ws = WorldState()
            obs = ObsidianSync()
            obs.sync_all_from_world_state(ws)
        """
        from memory.world_state import CHARACTERS, LOCATIONS, NATIONS, PLOT_EVENTS

        print('[ObsidianSync] Starting bulk sync from WorldState...')

        characters = world_state._get_all_entities(CHARACTERS)
        for c in characters:
            self.write_character(c)
        print(f'  ✓ {len(characters)} characters synced.')

        locations = world_state._get_all_entities(LOCATIONS)
        for loc in locations:
            self.write_location(loc)
        print(f'  ✓ {len(locations)} locations synced.')

        nations = world_state._get_all_entities(NATIONS)
        for n in nations:
            self.write_nation(n)
        print(f'  ✓ {len(nations)} nations synced.')

        events = world_state._get_all_entities(PLOT_EVENTS)
        for e in events:
            self.write_plot_event(e)
        print(f'  ✓ {len(events)} plot events synced.')

        self.write_world_clock(world_state.get_current_date_str())
        print('  ✓ World clock synced.')

        print('[ObsidianSync] Bulk sync complete.')


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE BULK SYNC SCRIPT
# Run this directly to populate Obsidian from existing campaign data:
#   python memory/obsidian_sync.py
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print('=' * 60)
    print('  DnD AI DM — Obsidian Vault Sync')
    print('=' * 60)
    print()

    from memory.world_state import WorldState
    ws  = WorldState()
    obs = ObsidianSync()
    obs.sync_all_from_world_state(ws)

    print()
    print(f'Vault location: {obs.vault}')
    print('Open Obsidian and point it to this folder to see your notes.')
