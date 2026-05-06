# agent/dm_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: The core DM engine. Orchestrates the full turn cycle and now also
#          automatically extracts and saves characters the DM introduces.
#
# NEW IN THIS VERSION:
#   - Auto NPC extraction: After every DM response, a second Ollama call
#     asks the model to extract any newly introduced characters and return
#     them as structured JSON. Those characters are saved to WorldState
#     automatically so they persist across sessions and are available for
#     portrait generation.
#
#   - Player character save: update_player_character() lets main.py save
#     changes to the player's character sheet mid-session (HP changes,
#     new inventory, level ups, etc.)
#
# HOW NPC AUTO-EXTRACTION WORKS:
#   After the DM writes its narrative response, we send that response to
#   Ollama again with a specific prompt that says:
#   "Extract any NEW characters introduced in this text and return them
#    as a JSON array." The model returns structured data like:
#   [{"name": "Mira", "race": "Human", "appearance": "...", ...}]
#   We parse that JSON and call world_state.save_character() for each one.
#   This happens silently in the background — the player never sees it.
#
# WHY A SECOND OLLAMA CALL?
#   The alternative is asking the DM to output structured JSON alongside
#   its narrative every turn, which makes responses awkward and inconsistent.
#   A dedicated extraction call is cleaner — the DM writes naturally,
#   then a separate quick call handles the data extraction.
#   This call uses a small context window and low token limit so it's fast.
#
# LOCATION: dnd_ai_dm/agent/dm_agent.py
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re

import ollama

import config
from agent.context_builder import ContextBuilder
from agent.image_generator import generate_image, generate_character_portrait, unload_for_llm
from agent.web_search import search_web, format_search_results, should_search
from memory.conversation_store import ConversationStore
from memory.relationship_graph import RelationshipGraph
from memory.world_state import WorldState


# ── NPC Introduction Trigger Phrases ──────────────────────────────────────
# If the DM response contains any of these, we attempt NPC extraction.
# This avoids running the extraction call on turns where no new character
# was introduced (saves time and API calls).
NPC_INTRODUCTION_PHRASES = [
    'introduces themselves',
    'introduces herself',
    'introduces himself',
    'you meet ',
    'a man named',
    'a woman named',
    'an elf named',
    'a dwarf named',
    'a halfling named',
    'a gnome named',
    'a half-orc named',
    'a tiefling named',
    'a dragonborn named',
    'enters the room',
    'approaches you',
    'steps forward',
    'stands before you',
    'greets you',
    'calls themselves',
    'known as ',
    'goes by the name',
    'the innkeeper',
    'the guard',
    'the merchant',
    'the blacksmith',
    'the barkeep',
    'the wizard',
    'the priest',
    'the knight',
    'the rogue',
    'mysterious figure',
    'hooded figure',
    'cloaked figure',
]

# ── Plot Event Trigger Phrases ─────────────────────────────────────────────
# Responses containing these phrases get logged as plot events in WorldState.
PLOT_TRIGGER_PHRASES = [
    'introduces themselves as',
    'you meet ',
    'enters the room',
    'arrives at',
    'a new settlement',
    'the kingdom of',
    'war has broken out',
    'war breaks out',
    'has died',
    'is killed',
    'falls in battle',
    'is now allied with',
    'relationship changes',
    'betrays',
    'swears loyalty',
    'a new faction',
    'is crowned',
    'the city of',
    'a mysterious figure',
    'quest begins',
]

# ── Location Change Phrases ────────────────────────────────────────────────
LOCATION_CHANGE_PHRASES = [
    'you arrive at',
    'you enter ',
    'you reach ',
    'you travel to',
    'you step into',
    'you find yourself in',
    'you are now in',
]


class DMAgent:
    """
    The primary controller for DnD AI DM sessions.
    Manages one active session including memory, world state, AI calls,
    automatic NPC saving, and player character persistence.
    """

    def __init__(self, player_character: dict, session_id: str = None):
        """
        Initializes a DM session with a player character.

        Parameters:
          player_character — Dict containing all player character data.
          session_id       — Optional ID of an existing session to resume.
        """
        self.player_character = player_character

        # ── Initialize all subsystems ──────────────────────────────────────
        self.world = WorldState()
        self.conv  = ConversationStore(session_id)
        self.graph = RelationshipGraph()
        self.ctx   = ContextBuilder(self.world, self.graph)

        # ── Register player in relationship graph ──────────────────────────
        player_id = player_character.get('id', 'player_character')
        if not self.graph.entity_exists(player_id):
            self.graph.add_entity(
                entity_id=player_id,
                entity_type='character',
                name=player_character.get('name', 'The Player')
            )

        # ── Also save player character to WorldState so portraits work ─────
        # The player character needs to exist in the world database so that
        # 'portrait <player name>' works the same as for any NPC.
        self.world.save_character(player_character)

        # ── Track current location ─────────────────────────────────────────
        self.current_location_id = player_character.get('starting_location_id')

        # ── Turn counter ───────────────────────────────────────────────────
        self.turn_count = len(self.conv.messages) // 2

        # ── Last generated image path (read by main.py after each turn) ────
        # None means no image was generated this turn.
        self.last_image_path: str | None = None

        # ── Track names of NPCs saved this session (for display in main.py) ─
        # main.py reads this list after each turn to tell the player which
        # new characters were saved. Cleared at the start of each turn.
        self.npcs_saved_this_turn: list[str] = []

    # ══════════════════════════════════════════════════════════════════════
    # NPC AUTO-EXTRACTION
    # ══════════════════════════════════════════════════════════════════════

    def _extract_and_save_npcs(self, dm_response: str):
        """
        Sends the DM's response to Ollama and asks it to extract any newly
        introduced characters as structured JSON, then saves them to WorldState.

        HOW IT WORKS:
          1. Check if the response contains any NPC_INTRODUCTION_PHRASES.
             If not, skip — no characters were likely introduced this turn.
          2. Build a short extraction prompt asking Ollama to pull out
             character data from the narrative.
          3. Parse the JSON response.
          4. For each character found, call world_state.save_character()
             and add them to the relationship graph.
          5. Store saved character names in self.npcs_saved_this_turn
             so main.py can notify the player.

        The extraction prompt is carefully designed to:
          - Return ONLY a JSON array, nothing else
          - Skip characters the player already knows (the player character)
          - Include as much visual/personality detail as was described
          - Return an empty array [] if no new characters were introduced

        Parameters:
          dm_response — The full DM narrative text from this turn
        """
        self.npcs_saved_this_turn = []

        # Step 1: Quick check — did this response likely introduce anyone?
        lower = dm_response.lower()
        if not any(phrase in lower for phrase in NPC_INTRODUCTION_PHRASES):
            return  # No characters introduced, skip extraction entirely

        # Step 2: Build the extraction prompt
        # We truncate the response to 800 chars — enough context to extract
        # all character details without wasting tokens
        truncated = dm_response[:800]

        player_name = self.player_character.get('name', 'the player')

        extraction_prompt = (
            f'Extract any NEW non-player characters introduced in this DnD scene.\n'
            f'The player character is "{player_name}" — do NOT include them.\n\n'
            f'SCENE TEXT:\n{truncated}\n\n'
            f'Return a JSON array of character objects. Each object must have:\n'
            f'  "name":        string  (character\'s name or title if no name given)\n'
            f'  "race":        string  (Human/Elf/Dwarf/etc, or "Unknown")\n'
            f'  "occupation":  string  (their job/role, e.g. "innkeeper", "guard")\n'
            f'  "appearance":  string  (physical description from the text)\n'
            f'  "personality": string  (personality/demeanor from the text)\n'
            f'  "location":    string  (where they were encountered)\n\n'
            f'STRICT RULES:\n'
            f'- Return ONLY the JSON array, no explanation, no markdown, no backticks\n'
            f'- If no new characters were introduced, return exactly: []\n'
            f'- Only include characters clearly present in the scene text\n'
            f'- Use "Unknown" for any field not mentioned in the text\n\n'
            f'JSON:'
        )

        # Step 3: Call Ollama for extraction
        try:
            response = ollama.chat(
                model=config.MODEL_NAME,
                messages=[{'role': 'user', 'content': extraction_prompt}],
                options={
                    # Small context window — extraction is a focused short task
                    'num_ctx':     2048,
                    # Very low temperature — we want structured JSON, not creativity
                    'temperature': 0.1,
                    # Enough tokens for a few character objects in JSON
                    'num_predict': 600,
                }
            )

            raw = response['message']['content'].strip()

            # Step 4: Clean up the response
            # Some models wrap JSON in ```json ``` markdown blocks despite instructions
            raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
            raw = re.sub(r'```\s*$', '', raw, flags=re.MULTILINE)
            raw = raw.strip()

            # Find the JSON array in the response
            # Some models add text before or after the array
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if not match:
                return  # No JSON array found

            characters = json.loads(match.group())

            # Step 5: Validate and save each extracted character
            if not isinstance(characters, list):
                return

            for char_data in characters:
                # Skip if not a dict or missing a name
                if not isinstance(char_data, dict):
                    continue
                name = char_data.get('name', '').strip()
                if not name or name.lower() in ('unknown', ''):
                    continue

                # Skip if this looks like the player character
                if name.lower() == player_name.lower():
                    continue

                # Build a clean character dict for WorldState
                character_to_save = {
                    'name':        name,
                    'race':        char_data.get('race', 'Unknown'),
                    'class':       char_data.get('occupation', 'Unknown'),
                    'occupation':  char_data.get('occupation', 'Unknown'),
                    'appearance':  char_data.get('appearance', 'Unknown'),
                    'personality': char_data.get('personality', 'Unknown'),
                    'location':    char_data.get('location', 'Unknown'),
                    'first_seen':  self.world.get_current_date_str(),
                    'source':      'auto_extracted',
                }

                # Save to WorldState (generates search vector, writes JSON file)
                npc_id = self.world.save_character(character_to_save)

                # Register in relationship graph if not already there
                if not self.graph.entity_exists(npc_id):
                    self.graph.add_entity(
                        entity_id=npc_id,
                        entity_type='character',
                        name=name
                    )

                    # Add a default neutral relationship between player and this NPC
                    self.graph.set_relationship(
                        from_id=self.player_character.get('id', 'player_character'),
                        to_id=npc_id,
                        rel_type='neutral',
                        sentiment=0.0,
                        notes=f'Met on {self.world.get_current_date_str()}',
                        current_date=self.world.get_current_date_str()
                    )

                self.npcs_saved_this_turn.append(name)
                print(f'  [WorldState] Saved NPC: {name} ({char_data.get("race", "?")} {char_data.get("occupation", "")})')

        except json.JSONDecodeError:
            # JSON parsing failed — the model returned malformed JSON
            # This is not a crash-worthy error, just skip saving this turn
            pass
        except Exception as e:
            # Any other error — log quietly and continue
            print(f'  [WorldState] NPC extraction error (non-critical): {e}')

    # ══════════════════════════════════════════════════════════════════════
    # PLAYER CHARACTER MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════

    def update_player_character(self, updates: dict):
        """
        Updates the player character's data and saves it to both the
        in-memory dict and the WorldState database.

        Called by main.py when the player uses the 'savechar' command,
        or can be called programmatically to apply HP changes, inventory
        updates, level-ups, etc. mid-session.

        Parameters:
          updates — Dict of fields to update on the player character.
                    Only the fields provided are changed; others are kept.
                    Example: {'hit_points': {'current': 8, 'maximum': 11}}
                    Example: {'level': 2, 'inventory': [...updated list...]}
        """
        # Merge the updates into the existing character dict
        # This means only the specified fields change — others are preserved
        self.player_character.update(updates)

        # Save back to WorldState so the new data is searchable and persistent
        self.world.save_character(self.player_character)

        print(f'  [CharSave] Player character updated: {list(updates.keys())}')

    def save_player_character_to_file(self, character_file_path: str):
        """
        Writes the current player character dict to the JSON file on disk.

        Called by main.py's 'savechar' command after update_player_character().
        Keeps the data/player_character.json file in sync with in-memory state.

        Parameters:
          character_file_path — Full path to the player_character.json file
        """
        with open(character_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.player_character, f, indent=2, ensure_ascii=False)

    # ══════════════════════════════════════════════════════════════════════
    # TIME ADVANCEMENT
    # ══════════════════════════════════════════════════════════════════════

    def _advance_time_for_action(self, player_input: str):
        """
        Determines how much in-game time the player's action consumes
        and advances the world clock accordingly.

        Action categories and their time costs:
          - Resting/sleeping:  config.TIME_HOURS_REST    (default 8h)
          - Travel/journeying: config.TIME_HOURS_TRAVEL  (default 4h)
          - Everything else:   config.TIME_HOURS_DEFAULT (default 1h)
        """
        lower = player_input.lower()
        if any(w in lower for w in ['rest', 'sleep', 'camp', 'make camp', 'long rest', 'short rest']):
            self.world.advance_time(config.TIME_HOURS_REST)
        elif any(w in lower for w in ['travel', 'journey', 'ride to', 'walk to', 'head to', 'go to', 'make my way']):
            self.world.advance_time(config.TIME_HOURS_TRAVEL)
        else:
            self.world.advance_time(config.TIME_HOURS_DEFAULT)

    # ══════════════════════════════════════════════════════════════════════
    # WEB SEARCH
    # ══════════════════════════════════════════════════════════════════════

    def _get_web_context(self, player_input: str) -> str:
        """
        Checks if the player's input warrants a web search and returns
        formatted results as a context string. Returns '' if not needed.
        """
        if should_search(player_input):
            results = search_web(player_input)
            if results:
                return 'Web Search Results:\n' + format_search_results(results)
        return ''

    # ══════════════════════════════════════════════════════════════════════
    # WORLD STATE PARSING
    # ══════════════════════════════════════════════════════════════════════

    def _parse_and_update_world(self, dm_response: str):
        """
        Scans the DM's response for story events and logs them to WorldState.
        Also triggers NPC extraction for character auto-saving.
        """
        lower_response = dm_response.lower()

        # Log plot events
        if any(phrase in lower_response for phrase in PLOT_TRIGGER_PHRASES):
            self.world.log_plot_event(
                event_description=dm_response[:500],
                event_type='story_beat',
                involved_entities=[self.player_character.get('id', 'player_character')]
            )

        # Auto-extract and save any newly introduced NPCs
        # This is the new addition — runs after every plot-triggering response
        self._extract_and_save_npcs(dm_response)

    # ══════════════════════════════════════════════════════════════════════
    # MAIN RESPONSE METHOD
    # ══════════════════════════════════════════════════════════════════════

    def respond(self, player_input: str) -> str:
        """
        Main entry point for each player turn.

        Full turn cycle:
          1.  Save player input to conversation history
          2.  Advance in-game time
          3.  Fetch optional web context
          4.  Build dynamic system prompt
          5.  Free SD VRAM before Ollama call
          6.  Call Ollama for DM narrative response
          7.  Extract DM text
          8.  Save DM response to history
          9.  Parse response for plot events + extract/save NPCs
          10. Increment turn counter
          11. Generate scene image (if SD is running)

        Returns the DM's narration as a plain text string.
        """
        # Reset per-turn tracking
        self.npcs_saved_this_turn = []
        self.last_image_path = None

        # ── 1: Save player input ───────────────────────────────────────────
        self.conv.add(role='user', content=player_input)

        # ── 2: Advance time ────────────────────────────────────────────────
        self._advance_time_for_action(player_input)

        # ── 3: Web context ─────────────────────────────────────────────────
        extra_context = self._get_web_context(player_input)

        # ── 4: Build system prompt ─────────────────────────────────────────
        system_prompt = self.ctx.build_system_prompt(
            player_character=self.player_character,
            current_location_id=self.current_location_id,
            extra_context=extra_context
        )

        conversation_history = self.conv.get_recent()
        full_messages = (
            [{'role': 'system', 'content': system_prompt}]
            + conversation_history
        )

        # ── 5: Free SD VRAM before calling Ollama ─────────────────────────
        # Ensures the LLM has the full GPU available.
        unload_for_llm()

        # ── 6: Call Ollama ─────────────────────────────────────────────────
        raw_response = ollama.chat(
            model=config.MODEL_NAME,
            messages=full_messages,
            options={
                'num_ctx':     config.CONTEXT_WINDOW,
                'temperature': config.TEMPERATURE,
                'num_predict': config.MAX_TOKENS_PER_RESPONSE,
                'top_p':       config.TOP_P,
            }
        )

        # ── 7: Extract DM text ─────────────────────────────────────────────
        dm_response = raw_response['message']['content']

        # ── 8: Save to history ─────────────────────────────────────────────
        self.conv.add(role='assistant', content=dm_response)

        # ── 9: Parse for world updates + extract/save NPCs ─────────────────
        self._parse_and_update_world(dm_response)

        # ── 10: Increment turn counter ─────────────────────────────────────
        self.turn_count += 1

        # ── 11: Generate scene image ───────────────────────────────────────
        self.last_image_path = generate_image(
            dm_response=dm_response,
            in_game_date=self.world.get_current_date_str(),
            turn_count=self.turn_count
        )

        return dm_response

    # ══════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ══════════════════════════════════════════════════════════════════════

    def get_session_info(self) -> dict:
        """Returns a summary of the current session state."""
        return {
            'session_id':    self.conv.session_id,
            'turn_count':    self.turn_count,
            'current_date':  self.world.get_current_date_str(),
            'model':         config.MODEL_NAME,
            'context_window': config.CONTEXT_WINDOW,
        }

    def manually_update_location(self, location_id: str):
        """Manually sets the player's current location ID."""
        self.current_location_id = location_id

    def add_npc(self, character_data: dict) -> str:
        """
        Manually adds or updates an NPC in the world database.
        Also registers the NPC in the relationship graph.
        Returns the NPC's unique ID.
        """
        npc_id = self.world.save_character(character_data)
        if not self.graph.entity_exists(npc_id):
            self.graph.add_entity(
                entity_id=npc_id,
                entity_type='character',
                name=character_data.get('name', 'Unknown NPC')
            )
        return npc_id

    def list_saved_characters(self) -> list:
        """
        Returns all characters currently saved in the world database.
        Used by main.py to display the character roster.
        """
        from memory.world_state import CHARACTERS
        return self.world._get_all_entities(CHARACTERS)

    def generate_portrait_for_character(self, character_id: str) -> str | None:
        """
        Generates a portrait image for a character by their exact ID.
        Returns the saved portrait file path, or None if failed.
        """
        character_data = self.world.get_character(character_id)
        if not character_data:
            print(f'  Character not found: {character_id}')
            return None
        return generate_character_portrait(
            character_data=character_data,
            in_game_date=self.world.get_current_date_str()
        )

    def set_relationship(self, from_id: str, to_id: str,
                         rel_type: str, sentiment: float, notes: str = ''):
        """Sets a relationship between two entities in the graph."""
        self.graph.set_relationship(
            from_id=from_id,
            to_id=to_id,
            rel_type=rel_type,
            sentiment=sentiment,
            notes=notes,
            current_date=self.world.get_current_date_str()
        )
