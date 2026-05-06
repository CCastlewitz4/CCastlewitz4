# agent/context_builder.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Assembles all relevant world information into the AI's system prompt
#          for each turn. This is what gives the AI its "awareness" of the world.
#
# WHY THIS MATTERS:
#   A local LLM has no memory between API calls. Every single call starts fresh.
#   The context builder solves this by dynamically injecting everything the DM
#   needs to know RIGHT NOW into the system prompt before each response:
#     - Who the player is
#     - Where the player is
#     - What time/day it is in-game
#     - Who is nearby and what they look like
#     - How the player's relationships stand
#     - What has recently happened in the story
#
# LOCATION: dnd_ai_dm/agent/context_builder.py
# ─────────────────────────────────────────────────────────────────────────────

import json

from memory.world_state import WorldState
from memory.relationship_graph import RelationshipGraph


class ContextBuilder:
    """
    Builds the dynamic system prompt sent to the AI before each DM response.
    The quality of the DM's output depends directly on how well this context
    is assembled.
    """

    def __init__(self, world: WorldState, graph: RelationshipGraph):
        """
        Parameters:
          world — The WorldState instance (database of all entities)
          graph — The RelationshipGraph instance (all relationship data)
        """
        self.world = world
        self.graph = graph

    def _build_dm_persona(self) -> str:
        """
        Returns the GM persona instruction block for the currently active game system.

        Reads the 'dm_persona' field from config.ACTIVE_SYSTEM so each system
        gets its own rules, tone, and mechanical instructions injected here.
        Falls back to a generic GM persona if no system is active.
        """
        import config as _cfg
        system = getattr(_cfg, 'ACTIVE_SYSTEM', None)
        if system and system.get('dm_persona'):
            return system['dm_persona']

        # Generic fallback if no system is selected yet
        return (
            "You are the Game Master of a living tabletop RPG world. "
            "You are omniscient — you know everything about the world. "
            "You control ALL entities except the player character. "
            "Never break character. Never acknowledge you are an AI. "
            "Generate all encounters, events, and plot developments autonomously."
        )

    def _build_location_context(self, current_location_id: str) -> str:
        """
        Retrieves and formats the current location's description.
        Falls back to a placeholder if no location ID is provided.
        """
        if not current_location_id:
            return "Location: Unknown — player has not yet established a starting location."

        loc = self.world.get_location(current_location_id)
        if not loc:
            return "Location: Unknown area."

        # Build a rich location description from available fields
        loc_lines = [
            f"Name: {loc.get('name', 'Unnamed')}",
            f"Type: {loc.get('type', 'unknown')}",
            f"Nation: {loc.get('nation', 'Unknown')}",
            f"Description: {loc.get('description', 'No description available.')}",
        ]
        # Include notable features if stored
        if loc.get('notable_features'):
            loc_lines.append(f"Notable Features: {loc.get('notable_features')}")
        if loc.get('current_events'):
            loc_lines.append(f"Current Events Here: {loc.get('current_events')}")

        return '\n'.join(loc_lines)

    def _build_nearby_characters(self, location_description: str) -> str:
        """
        Retrieves NPCs associated with the current location using semantic search.
        Returns a formatted summary of nearby characters for the DM to reference.
        """
        # Search for characters linked to this location
        nearby = self.world.get_all_characters_in_location(location_description[:80], n=8)

        if not nearby:
            return "No notable characters currently in this location."

        lines = []
        for char in nearby:
            name = char.get('name', 'Unknown')
            race = char.get('race', '')
            char_class = char.get('class', char.get('occupation', ''))
            appearance = char.get('appearance', 'No appearance on record.')
            personality = char.get('personality', '')
            mood = char.get('current_mood', '')

            line = f"  • {name} ({race} {char_class})"
            line += f"\n    Appearance: {appearance}"
            if personality:
                line += f"\n    Personality: {personality}"
            if mood:
                line += f"\n    Current Mood: {mood}"
            lines.append(line)

        return '\n'.join(lines)

    def _build_recent_plot(self) -> str:
        """
        Retrieves the most recent plot events from the world database
        and formats them as a story-so-far summary.
        """
        events = self.world.get_recent_plot_events(n=6)
        if not events:
            return "Campaign is just beginning — no major events on record yet."

        lines = []
        for event in events:
            date = event.get('in_game_date', 'Unknown date')
            desc = event.get('description', '')
            event_type = event.get('type', '')
            # Truncate very long event descriptions to keep the prompt concise
            if len(desc) > 200:
                desc = desc[:200] + '...'
            lines.append(f"  [{date}] ({event_type}) {desc}")

        return '\n'.join(lines)

    def _build_player_relationships(self, player_id: str) -> str:
        """
        Gets all relationships the player character has and formats them
        for the DM to reference when writing NPC reactions.
        """
        return self.graph.summarize_for_prompt(player_id)

    def _build_spell_context(self, player_character: dict) -> str:
        """
        Builds a spell access summary for injection into the system prompt.
        Tells the DM exactly what spells the character can access at their level,
        including school restrictions for Arcane Trickster / Eldritch Knight,
        auto-granted bonus spells for domain/oath/patron subclasses, and what
        new spell access unlocks at the next character level.

        Returns an empty string for non-spellcasting characters.
        """
        char_class = player_character.get('class', '')
        subclass   = player_character.get('subclass', '')
        char_level = int(player_character.get('level', 1))

        if not char_class:
            return ''

        try:
            from wiki_scraper import get_subclass_spell_context
            return get_subclass_spell_context(char_class, subclass, char_level)
        except Exception:
            pass

        # Absolute fallback: brief one-liner
        return f'Character is a level {char_level} {char_class} ({subclass or "no subclass"}).'

    def build_system_prompt(
        self,
        player_character: dict,
        current_location_id: str = None,
        extra_context: str = ''
    ) -> str:
        """
        Assembles the complete dynamic system prompt for this turn.

        This is called before EVERY AI response. Each call produces a freshly
        assembled prompt with up-to-date world information.

        Parameters:
          player_character     — Dict with all player character data
          current_location_id  — ID of the player's current location (or None)
          extra_context        — Optional additional context (e.g., web search results)

        Returns a single formatted string ready to be sent as the 'system'
        message in the Ollama API call.
        """

        # ── 1. DM Persona ──────────────────────────────────────────────────
        persona_block = self._build_dm_persona()

        # ── 2. World Time ──────────────────────────────────────────────────
        current_date = self.world.get_current_date_str()

        # ── 3. Player Character Sheet ──────────────────────────────────────
        # Format the player's character as pretty-printed JSON for clarity
        pc_json = json.dumps(player_character, indent=2)

        # ── 4. Current Location ────────────────────────────────────────────
        location_block = self._build_location_context(current_location_id)

        # ── 5. Nearby Characters ───────────────────────────────────────────
        # Use the location description as the search query
        location_desc_for_search = location_block[:80]
        nearby_block = self._build_nearby_characters(location_desc_for_search)

        # ── 6. Recent Plot Events ──────────────────────────────────────────
        plot_block = self._build_recent_plot()

        # ── 7. Player Relationships ────────────────────────────────────────
        player_id = player_character.get('id', 'player_character')
        rel_block = self._build_player_relationships(player_id)

        # ── 8. Assemble final prompt ───────────────────────────────────────
        # Sections are clearly labeled so the AI can parse them easily.
        import config as _cfg
        system = getattr(_cfg, 'ACTIVE_SYSTEM', None)
        system_name = system['name'] if system else 'Tabletop RPG'

        sections = [
            f"GAME SYSTEM: {system_name}",
            "",
            persona_block,
            "",
            "=" * 60,
            "CURRENT WORLD STATE",
            "=" * 60,
            f"In-Game Date & Time: {current_date}",
            "",
            "--- CURRENT LOCATION ---",
            location_block,
            "",
            "--- PLAYER CHARACTER ---",
            pc_json,
            "",
            "--- PLAYER'S KNOWN RELATIONSHIPS ---",
            rel_block,
            "",
            "--- CHARACTERS IN THIS LOCATION ---",
            nearby_block,
            "",
            "--- RECENT STORY EVENTS ---",
            plot_block,
        ]

        # ---- Spell context (school restrictions, accessible levels, bonus spells) ----
        # Only injected for spellcasting characters; empty string for martials.
        spell_block = self._build_spell_context(player_character)
        if spell_block and spell_block.strip():
            sections += [
                "",
                "--- SPELL ACCESS & RESTRICTIONS ---",
                spell_block,
            ]

        # Only add the extra context section if there's something to add
        if extra_context and extra_context.strip():
            sections += [
                "",
                "--- ADDITIONAL CONTEXT (Web Search / Research) ---",
                extra_context,
            ]

        # Inject campaign preferences (notes, GM instructions, content limits, etc.)
        # These are set once during campaign setup and persist for the entire session.
        # They appear at the END of the prompt so they're close to the generation point
        # and less likely to be lost in a long context window.
        import config as _cfg2
        prefs_block = getattr(_cfg2, 'CAMPAIGN_PREFS_BLOCK', '')
        if prefs_block and prefs_block.strip():
            sections += ["", prefs_block]

        return '\n'.join(sections)
