# memory/world_state.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: The living world database. Stores every entity that exists in the
#          campaign — characters, locations, nations, and plot events — and
#          makes them searchable by meaning, not just exact keywords.
#
# !! CHROMADB-FREE VERSION — Compatible with Python 3.14 !!
#
# HOW IT WORKS (replacement approach):
#   Instead of ChromaDB, this version uses:
#
#   1. PLAIN JSON FILES for storage:
#      Every entity (character, location, nation, plot event) is stored as
#      a JSON file inside the data/world/ folder. JSON is a simple text
#      format that Python reads/writes natively with no extra libraries.
#      Each entity type gets its own subfolder:
#        data/world/characters/   <- one .json file per character
#        data/world/locations/    <- one .json file per location
#        data/world/nations/      <- one .json file per nation
#        data/world/plot_events/  <- one .json file per plot event
#
#   2. NUMPY + SENTENCE-TRANSFORMERS for semantic search:
#      When you search for "the angry blacksmith", the search text is
#      converted into a numerical vector (a list of 384 numbers) using
#      sentence-transformers. All stored entity summaries also have their
#      vectors saved. Numpy then computes cosine similarity between the
#      search vector and every stored vector, ranking results by relevance.
#      This is exactly what ChromaDB was doing internally, we just do it
#      ourselves with raw numpy, which fully supports Python 3.14.
#
#   3. VECTOR CACHE FILE:
#      To avoid re-computing vectors every search, all vectors are saved
#      to data/world/vector_cache.json on disk. When an entity is added or
#      updated, only that entity's vector is recomputed.
#
# WHY NO CHROMADB?
#   ChromaDB depends on pydantic v1 which explicitly does not support
#   Python 3.14+. This pure-Python replacement has zero such dependencies.
#
# DEPENDENCIES (all Python 3.14 compatible):
#   - sentence-transformers  (for text to vector conversion)
#   - numpy                  (for cosine similarity math)
#   Both install fine with: pip install sentence-transformers numpy
#
# LOCATION: dnd_ai_dm/memory/world_state.py
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os

# ── Path fix ──────────────────────────────────────────────────────────────
# Tells Python to also search the dnd_ai_dm/ root folder when resolving imports.
# Without this, running from inside the memory/ subfolder breaks config imports.
# os.path.abspath(__file__)             -> full path to this file
# os.path.dirname(...) once             -> the memory/ folder
# os.path.dirname(...) twice            -> the dnd_ai_dm/ root folder
# sys.path.insert(0, ...)               -> puts dnd_ai_dm/ at the front of the search list
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import uuid
from datetime import datetime
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

import config


# ── Collection type constants ──────────────────────────────────────────────
# These strings double as subfolder names under data/world/.
# Using constants instead of raw strings prevents typos from causing silent bugs.
CHARACTERS  = 'characters'
LOCATIONS   = 'locations'
NATIONS     = 'nations'
PLOT_EVENTS = 'plot_events'

# Master list used to create all subfolders on startup
ALL_COLLECTIONS = [CHARACTERS, LOCATIONS, NATIONS, PLOT_EVENTS]


class WorldState:
    """
    Manages all persistent world data for the DnD campaign.

    Storage:  One JSON file per entity, organized into subfolders by type.
    Search:   Sentence-transformer embeddings + numpy cosine similarity.
    Clock:    In-game world time tracked in a separate JSON file.

    This class is a fully compatible replacement for the ChromaDB version.
    All method names, parameters, and return types are identical so nothing
    else in the project needs to change.
    """

    def __init__(self):
        # ── Step 1: Create all storage directories ─────────────────────────
        # For each entity type, make sure its subfolder exists under data/world/.
        # exist_ok=True means no error is raised if the folder already exists.
        for collection_name in ALL_COLLECTIONS:
            folder = self._collection_folder(collection_name)
            os.makedirs(folder, exist_ok=True)

        # ── Step 2: Load the sentence embedding model ──────────────────────
        # SentenceTransformer converts any text string into a vector:
        # a list of 384 decimal numbers that represent the text's meaning.
        # The model downloads automatically on first use (~80MB) and caches locally.
        # After the first download, it loads from disk instantly.
        #
        # Why vectors?
        #   "Angry blacksmith" and "furious ironworker" are different strings
        #   but nearly identical in meaning. Vectors capture this — similar
        #   meaning = vectors that point in nearly the same direction.
        #   We use this to power semantic (meaning-based) search.
        print('[WorldState] Loading embedding model (first run downloads ~80MB)...')
        self.embedder = SentenceTransformer(config.EMBED_MODEL)
        print('[WorldState] Embedding model ready.')

        # ── Step 3: Load the vector cache ─────────────────────────────────
        # The vector cache is a dict: { "entity_id": [0.12, -0.34, ...], ... }
        # Stored as data/world/vector_cache.json.
        #
        # Why cache?
        #   Computing a vector takes ~50ms. If we have 200 saved characters
        #   and searched every turn without caching, that's 10 seconds per turn
        #   just on vector math. Caching means we compute once on save, then
        #   reuse the stored result for every future search.
        self._cache_path = os.path.join(config.WORLD_DIR, 'vector_cache.json')
        self._vector_cache: dict = self._load_vector_cache()

        # ── Step 4: Load entity summary text cache ─────────────────────────
        # Maps "collection::entity_id" -> the plain-text summary string.
        # We need the summary text to know which entity a given vector belongs to,
        # and to know which collection each entity is part of during searches.
        self._summary_cache: dict = {}
        self._load_all_summaries()

        # ── Step 5: Load the world clock ──────────────────────────────────
        # Tracks in-game time. Stored as data/world/world_clock.json.
        self._clock_path = os.path.join(config.WORLD_DIR, 'world_clock.json')
        self.clock = self._load_clock()

    # ── Internal Path Helpers ──────────────────────────────────────────────

    def _collection_folder(self, collection_name: str) -> str:
        """
        Returns the full folder path for a given entity type.

        Example:
          _collection_folder('characters')
          returns: 'C:/Users/.../dnd_ai_dm/data/world/characters'
        """
        return os.path.join(config.WORLD_DIR, collection_name)

    def _entity_path(self, collection_name: str, entity_id: str) -> str:
        """
        Returns the full file path for a specific entity's JSON file.

        Example:
          _entity_path('characters', 'abc-123')
          returns: 'C:/Users/.../dnd_ai_dm/data/world/characters/abc-123.json'
        """
        return os.path.join(self._collection_folder(collection_name), f'{entity_id}.json')

    # ── Vector Cache Methods ───────────────────────────────────────────────

    def _load_vector_cache(self) -> dict:
        """
        Reads the vector cache JSON file from disk and returns it as a dict.
        If the file doesn't exist (first run), returns an empty dict.

        The cache format is:
          { "entity-uuid-here": [0.12, -0.034, 0.567, ...384 numbers...], ... }
        """
        if os.path.exists(self._cache_path):
            with open(self._cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_vector_cache(self):
        """
        Writes the entire in-memory vector cache to disk as JSON.
        Called every time an entity is saved or updated, so the cache
        always reflects the current state of the world.
        """
        with open(self._cache_path, 'w', encoding='utf-8') as f:
            json.dump(self._vector_cache, f)

    def _load_all_summaries(self):
        """
        Scans all entity JSON files on disk and loads their 'search_summary'
        field into the in-memory _summary_cache dict.

        The summary cache serves two purposes:
          1. Tells us which collection an entity belongs to (via "type::id" key)
          2. Keeps the search loop fast by avoiding disk reads during searches

        This runs once at startup. After that, _save_entity() keeps the cache
        updated in real time as new entities are added.
        """
        self._summary_cache.clear()
        for collection_name in ALL_COLLECTIONS:
            folder = self._collection_folder(collection_name)
            if not os.path.exists(folder):
                continue
            for filename in os.listdir(folder):
                if not filename.endswith('.json'):
                    continue
                filepath = os.path.join(folder, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    entity_id = data.get('id')
                    summary = data.get('search_summary', '')
                    if entity_id and summary:
                        # Key format: "characters::abc-123"
                        # The prefix lets search filter to one collection type
                        cache_key = f'{collection_name}::{entity_id}'
                        self._summary_cache[cache_key] = summary
                except Exception:
                    pass  # Skip unreadable files without crashing

    # ── Cosine Similarity ──────────────────────────────────────────────────

    def _cosine_similarity(self, vec_a: list, vec_b: list) -> float:
        """
        Computes how similar two vectors are using cosine similarity.

        Cosine similarity measures the ANGLE between two vectors, not their
        magnitude. This is ideal for text meaning comparison because:
          - Two texts with identical meaning  -> similarity near 1.0
          - Two totally unrelated texts       -> similarity near 0.0
          - Two opposite-meaning texts        -> similarity near -1.0

        The math:
          similarity = dot_product(A, B) / (magnitude(A) * magnitude(B))

          dot_product: sum of element-wise multiplications
          magnitude:   square root of sum of squared elements

        Numpy handles both operations in highly optimized C code, making
        this thousands of times faster than a pure Python loop would be.

        Parameters:
          vec_a, vec_b — Two lists of floats (the embedding vectors)

        Returns a float between -1.0 and 1.0.
        """
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)

        dot = np.dot(a, b)
        mag_a = np.linalg.norm(a)
        mag_b = np.linalg.norm(b)

        # Avoid division by zero if either vector is all zeros
        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0

        return float(dot / (mag_a * mag_b))

    def _semantic_search(self, collection_name: str, query: str, n: int) -> list:
        """
        The core search engine. Returns the n most semantically relevant
        entities from a collection for the given query string.

        How it works step by step:
          1. Convert the query string to a vector using the embedder
          2. Loop through all entries in the summary cache that belong to
             the requested collection (identified by the "type::" prefix)
          3. For each entry, retrieve its stored vector from _vector_cache
          4. Compute cosine similarity between the query vector and stored vector
          5. Sort all results by similarity score, highest first
          6. Load and return the top n entity dicts from their JSON files

        This replaces ChromaDB's collection.query() method entirely.

        Parameters:
          collection_name — Which entity type to search
          query           — Natural language search string
          n               — Max number of results to return

        Returns a list of entity data dicts, most relevant first.
        """
        # Step 1: Encode the query into a vector
        query_vector = self.embedder.encode(query).tolist()

        # Step 2-4: Score every entity in this collection
        scored = []
        prefix = f'{collection_name}::'

        for cache_key, _summary in self._summary_cache.items():
            if not cache_key.startswith(prefix):
                continue  # Skip entities from other collections

            # Extract the entity ID from the "collection::id" key
            entity_id = cache_key[len(prefix):]

            # Skip if this entity has no cached vector (shouldn't happen normally)
            if entity_id not in self._vector_cache:
                continue

            stored_vector = self._vector_cache[entity_id]
            score = self._cosine_similarity(query_vector, stored_vector)
            scored.append((entity_id, score))

        # Step 5: Sort by score descending (most relevant first)
        scored.sort(key=lambda pair: pair[1], reverse=True)

        # Step 6: Load top n entity files from disk and return them
        results = []
        for entity_id, _score in scored[:n]:
            entity_path = self._entity_path(collection_name, entity_id)
            if os.path.exists(entity_path):
                with open(entity_path, 'r', encoding='utf-8') as f:
                    results.append(json.load(f))

        return results

    # ── Generic Entity Save / Get ──────────────────────────────────────────

    def _save_entity(self, collection_name: str, entity_id: str,
                     data: dict, text_for_embedding: str):
        """
        Saves an entity to disk and updates both caches.

        This is the central write method that replaces ChromaDB's upsert().
        Every save_character(), save_location(), etc. call ends up here.

        Steps performed:
          1. Generate a search vector from text_for_embedding
          2. Store the vector in _vector_cache and persist to disk
          3. Store the summary text in _summary_cache
          4. Add metadata fields to the entity data dict
          5. Write the full entity dict as a JSON file

        Parameters:
          collection_name    — Subfolder name ('characters', 'locations', etc.)
          entity_id          — Unique ID string for this entity
          data               — The full entity data dict to save
          text_for_embedding — Plain-text summary; this is what gets vectorized
                               and matched against during semantic searches.
                               The quality of this text directly affects search quality.
        """
        # Step 1: Compute the search vector for this entity's summary text
        vector = self.embedder.encode(text_for_embedding).tolist()

        # Step 2: Update vector cache in memory and on disk
        self._vector_cache[entity_id] = vector
        self._save_vector_cache()

        # Step 3: Update the summary cache in memory
        cache_key = f'{collection_name}::{entity_id}'
        self._summary_cache[cache_key] = text_for_embedding

        # Step 4: Embed metadata into the entity dict before saving
        # search_summary is stored inside the JSON so the cache can be
        # rebuilt from scratch at startup if needed (e.g. after corruption)
        data['search_summary'] = text_for_embedding
        data['last_updated'] = datetime.utcnow().isoformat()

        # Step 5: Write the entity dict to its JSON file on disk
        # upsert behavior: creates file if new, overwrites if exists
        entity_path = self._entity_path(collection_name, entity_id)
        with open(entity_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_entity(self, collection_name: str, entity_id: str) -> Optional[dict]:
        """
        Reads a single entity's JSON file by its exact ID and returns the dict.
        Returns None if the file doesn't exist (entity was never saved).
        """
        entity_path = self._entity_path(collection_name, entity_id)
        if not os.path.exists(entity_path):
            return None
        with open(entity_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_all_entities(self, collection_name: str) -> list:
        """
        Reads ALL entity JSON files in a collection folder and returns them
        as a list of dicts, sorted by filename (which sorts by creation order
        since filenames are UUIDs generated in time order).

        Used by get_recent_plot_events() to get all events for date sorting.
        """
        folder = self._collection_folder(collection_name)
        entities = []
        if not os.path.exists(folder):
            return entities
        for filename in sorted(os.listdir(folder)):
            if filename.endswith('.json'):
                filepath = os.path.join(folder, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        entities.append(json.load(f))
                except Exception:
                    pass  # Skip unreadable files
        return entities

    # ── World Clock ────────────────────────────────────────────────────────

    def _load_clock(self) -> dict:
        """
        Loads the in-game world clock from world_clock.json.
        If the file doesn't exist (first ever run), creates a default clock
        starting at Year 1, Month 1, Day 1, Morning and saves it to disk.

        Clock dict structure:
          {
            'year':        int  (e.g. 1, 2, 100)
            'month':       int  (1-12)
            'day':         int  (1-30)
            'time_of_day': str  (one of the seven named time blocks)
          }
        """
        if os.path.exists(self._clock_path):
            with open(self._clock_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        default_clock = {
            'year': 1,
            'month': 1,
            'day': 1,
            'time_of_day': 'morning'
        }
        self._save_clock(default_clock)
        return default_clock

    def _save_clock(self, clock: dict):
        """
        Writes the clock dict to world_clock.json.
        Called after every advance_time() call so time is never lost between
        program restarts.
        """
        with open(self._clock_path, 'w', encoding='utf-8') as f:
            json.dump(clock, f, indent=2)

    def advance_time(self, hours: int):
        """
        Moves the in-game clock forward by the given number of hours.
        Handles all rollovers: hours to time block, days to months, months to years.

        The day is divided into 7 named time blocks (each roughly 3-4 hours):
          dawn -> morning -> noon -> afternoon -> evening -> night -> midnight -> (wraps to dawn)

        The advance algorithm:
          1. Every 4 hours = 1 time block advancement
          2. Leftover hours of 2 or more = round up to next block
          3. Hours >= 24 = also advance whole day count
          4. Days > 30 = roll to next month
          5. Months > 12 = roll to next year

        Called by dm_agent.py every player turn with different values:
          1 hour  - short actions (looking around, talking, short tasks)
          4 hours - travel between locations
          8 hours - long rest / sleep
        """
        time_blocks = ['dawn', 'morning', 'noon', 'afternoon', 'evening', 'night', 'midnight']

        # Safely get current time block, defaulting to morning if somehow invalid
        current_tod = self.clock.get('time_of_day', 'morning')
        if current_tod not in time_blocks:
            current_tod = 'morning'
        current_idx = time_blocks.index(current_tod)

        # Calculate blocks to advance (4 hours per block, round up on remainder >= 2)
        blocks = hours // 4
        if (hours % 4) >= 2:
            blocks += 1

        # Advance through the circular time block list using modulo wrap
        new_idx = (current_idx + blocks) % len(time_blocks)
        self.clock['time_of_day'] = time_blocks[new_idx]

        # Advance whole days (integer division of hours by 24)
        self.clock['day'] += hours // 24

        # Roll over days to months (30-day months)
        while self.clock['day'] > 30:
            self.clock['day'] -= 30
            self.clock['month'] += 1

        # Roll over months to years (12-month years)
        while self.clock['month'] > 12:
            self.clock['month'] -= 12
            self.clock['year'] += 1

        # Save immediately so time is preserved if the program crashes
        self._save_clock(self.clock)

    def get_current_date_str(self) -> str:
        """
        Returns the current in-game date as a human-readable string.

        This is injected into every DM system prompt by context_builder.py
        so the AI always knows what time it is in the world, which affects:
          - Whether shops are open
          - What NPCs are doing (sleeping, working, carousing)
          - Lighting conditions for encounters
          - Whether certain events have triggered

        Example return value: "Year 3, Month 7, Day 14 (evening)"
        """
        c = self.clock
        return f"Year {c['year']}, Month {c['month']}, Day {c['day']} ({c['time_of_day']})"

    # ── Character Methods ──────────────────────────────────────────────────

    def save_character(self, character_data: dict) -> str:
        """
        Saves or updates a character in the world database.

        The DM agent calls this to persist any NPC the AI generates during play.
        Once saved, the character's appearance and personality stay consistent
        across all future sessions because the DM retrieves and re-injects this
        data into the prompt every turn.

        The search_summary is built from the character's most searchable traits.
        The richer the appearance and personality fields, the better semantic
        search will work when the context builder looks for nearby characters.

        Minimum required fields in character_data:
          'name'        - Character's name
          'race'        - e.g. "Human", "Elf", "Half-Orc"
          'appearance'  - Physical description (DM keeps this consistent)
          'personality' - Behavioral traits and mannerisms

        Recommended additional fields:
          'class', 'occupation', 'age', 'location', 'faction',
          'backstory', 'speech_style', 'current_mood', 'goals', 'secrets'

        Returns the character's unique ID string (UUID).
        """
        cid = character_data.get('id') or str(uuid.uuid4())
        character_data['id'] = cid

        # Build the search summary from all meaningful text fields
        # More fields = richer vector = better search accuracy
        parts = [
            f"{character_data.get('name', 'Unknown')} is a",
            character_data.get('race', ''),
            character_data.get('class', character_data.get('occupation', 'commoner')) + '.',
            character_data.get('appearance', ''),
            character_data.get('personality', ''),
            character_data.get('backstory', ''),
            character_data.get('location', ''),
        ]
        summary = ' '.join(p for p in parts if p).strip()

        self._save_entity(CHARACTERS, cid, character_data, summary)
        return cid

    def get_character(self, character_id: str) -> Optional[dict]:
        """
        Retrieves a single character by their exact unique ID.
        Returns the full character data dict, or None if not found.

        Use this when you have the specific ID (e.g. from a relationship graph lookup).
        Use search_characters() when you only know descriptive information.
        """
        return self._get_entity(CHARACTERS, character_id)

    def search_characters(self, query: str, n: int = 5) -> list:
        """
        Finds the most semantically relevant characters for a query string.

        Called by context_builder.py each turn to find NPCs near the player.
        Also used by dm_agent.py when looking up specific characters by description.

        Example queries that work well:
          "the innkeeper with the red beard"
          "characters who are hostile to the crown"
          "elven archers in the northern forest"
          "merchant who sells magic items"

        Returns up to n character dicts, most relevant first.
        Returns empty list if no characters are saved yet.
        """
        folder = self._collection_folder(CHARACTERS)
        if not os.path.exists(folder) or not os.listdir(folder):
            return []
        return self._semantic_search(CHARACTERS, query, n)

    def get_all_characters_in_location(self, location_name: str, n: int = 10) -> list:
        """
        Returns characters semantically associated with the given location name.
        The context builder calls this to populate scenes with relevant NPCs.

        Works because characters saved with a 'location' field or a description
        mentioning the location will have that information embedded in their
        search vector, making them rank highly for location-based searches.
        """
        return self.search_characters(f"located in {location_name}", n)

    # ── Location Methods ───────────────────────────────────────────────────

    def save_location(self, location_data: dict) -> str:
        """
        Saves or updates a location in the world database.

        Locations can be any named place: cities, dungeons, forests, taverns,
        crossroads, ruins, temples, caves, and so on.

        Recommended fields:
          'name'             - Location's name
          'type'             - Category: 'city', 'dungeon', 'tavern', 'forest'
          'nation'           - Nation/kingdom this location is part of
          'description'      - Sensory description for scene-setting
          'population'       - Approximate number of inhabitants
          'notable_features' - Key landmarks, points of interest
          'current_events'   - What's happening here right now (can change over time)
          'atmosphere'       - The mood and feel of the place
          'dangers'          - Known threats or hazards

        Returns the location's unique ID string.
        """
        lid = location_data.get('id') or str(uuid.uuid4())
        location_data['id'] = lid

        parts = [
            f"{location_data.get('name', 'Unknown')} is a",
            location_data.get('type', 'place'), 'in',
            location_data.get('nation', 'the world') + '.',
            location_data.get('description', ''),
            location_data.get('notable_features', ''),
            location_data.get('atmosphere', ''),
        ]
        summary = ' '.join(p for p in parts if p).strip()

        self._save_entity(LOCATIONS, lid, location_data, summary)
        return lid

    def get_location(self, location_id: str) -> Optional[dict]:
        """
        Retrieves a single location by its exact unique ID.
        Returns None if not found.
        """
        return self._get_entity(LOCATIONS, location_id)

    def search_locations(self, query: str, n: int = 5) -> list:
        """
        Semantic search across all saved locations.

        Example queries:
          "dangerous city in the northern mountains"
          "tavern or inn where travelers rest"
          "ancient ruins of a forgotten empire"

        Returns up to n location dicts, most relevant first.
        """
        folder = self._collection_folder(LOCATIONS)
        if not os.path.exists(folder) or not os.listdir(folder):
            return []
        return self._semantic_search(LOCATIONS, query, n)

    # ── Nation Methods ─────────────────────────────────────────────────────

    def save_nation(self, nation_data: dict) -> str:
        """
        Saves or updates a nation, kingdom, empire, or major political faction.

        Nations drive geopolitical plot — their relationships with each other
        (tracked in RelationshipGraph) create wars, alliances, trade disputes,
        and political intrigue that the DM weaves into the story automatically.

        Recommended fields:
          'name'              - Nation's name
          'government'        - 'monarchy', 'republic', 'theocracy', 'empire', etc.
          'current_ruler'     - Name and title of current leader
          'culture'           - Cultural values, customs, traditions
          'military_strength' - 'weak', 'moderate', 'strong', 'dominant'
          'economy'           - Main industries and relative wealth
          'description'       - General overview
          'capital_city_id'   - ID of the capital location entity
          'notable_laws'      - Unusual laws the player might encounter
          'current_conflicts' - Active wars, rebellions, or tensions

        Returns the nation's unique ID string.
        """
        nid = nation_data.get('id') or str(uuid.uuid4())
        nation_data['id'] = nid

        parts = [
            f"{nation_data.get('name', 'Unknown')} is a",
            nation_data.get('government', 'nation') + '.',
            nation_data.get('description', ''),
            nation_data.get('culture', ''),
        ]
        summary = ' '.join(p for p in parts if p).strip()

        self._save_entity(NATIONS, nid, nation_data, summary)
        return nid

    def get_nation(self, nation_id: str) -> Optional[dict]:
        """Retrieves a single nation by its exact unique ID."""
        return self._get_entity(NATIONS, nation_id)

    def search_nations(self, query: str, n: int = 3) -> list:
        """
        Semantic search across all saved nations.

        Example queries:
          "militaristic empire in the east"
          "nation with a history of dark magic"
          "trading republic near the coast"

        Returns up to n nation dicts, most relevant first.
        """
        folder = self._collection_folder(NATIONS)
        if not os.path.exists(folder) or not os.listdir(folder):
            return []
        return self._semantic_search(NATIONS, query, n)

    # ── Plot Event Methods ─────────────────────────────────────────────────

    def log_plot_event(
        self,
        event_description: str,
        event_type: str = 'general',
        involved_entities: list = None
    ) -> str:
        """
        Records a significant story moment in the world's permanent history log.

        Every important event should be logged here: battles, discoveries,
        character deaths, political shifts, quest completions, relationship
        changes, and major revelations. These events form the AI's long-term
        memory of what has happened in the story.

        How this affects the DM's responses:
          context_builder.py calls get_recent_plot_events() every turn and
          injects the last 5-6 events into the system prompt as "recent story
          events." The AI reads this and naturally references past events in
          its narration, maintaining story continuity even across sessions.

        Parameters:
          event_description  - A full sentence describing what happened.
                               Be specific: include names, locations, outcomes.
                               Good:  "The player killed guard captain Aldric Vane
                                       in the Thornwall barracks during a confrontation
                                       over the missing grain shipment."
                               Bad:   "A fight happened."

          event_type         - Category string for filtering and context:
                               'combat'              - Battles and fights
                               'discovery'           - Found items, places, secrets
                               'relationship_change' - Alliances, betrayals, romances
                               'political'           - Nation/faction events
                               'death'               - Character deaths
                               'quest_update'        - Quest progress
                               'story_beat'          - Major narrative moments
                               'world_event'         - Environmental/world changes
                               'general'             - Anything else

          involved_entities  - List of entity IDs involved in this event.
                               Stored as JSON for future filtering queries.
                               Example: [player_id, npc_id, location_id]

        Returns the unique ID of the newly created event record.
        """
        eid = str(uuid.uuid4())
        event_data = {
            'id': eid,
            'description': event_description,
            'type': event_type,
            'in_game_date': self.get_current_date_str(),
            'real_timestamp': datetime.utcnow().isoformat(),
            'involved': json.dumps(involved_entities or [])
        }
        self._save_entity(PLOT_EVENTS, eid, event_data, event_description)
        return eid

    def search_plot_events(self, query: str, n: int = 10) -> list:
        """
        Semantic search across all logged plot events.

        The DM uses this to recall story context even when the exact wording
        of past events isn't known. Semantic search means you can ask broadly
        and get relevant results.

        Example queries:
          "events involving the king"
          "battles and military conflicts"
          "anything about the thieves guild"
          "discoveries or secrets the player found"

        Returns up to n event dicts, most relevant first.
        """
        folder = self._collection_folder(PLOT_EVENTS)
        if not os.path.exists(folder) or not os.listdir(folder):
            return []
        return self._semantic_search(PLOT_EVENTS, query, n)

    def get_recent_plot_events(self, n: int = 5) -> list:
        """
        Returns the n most recently logged plot events, sorted by real timestamp.

        This is called by context_builder.py every single turn to build the
        "Recent Story Events" section of the DM's system prompt.
        The AI reads these events and uses them to maintain narrative continuity,
        reference recent happenings, and build on established story threads.

        Returns events in chronological order (oldest first, newest last),
        which is the natural reading order for "story so far" context.
        """
        all_events = self._get_all_entities(PLOT_EVENTS)
        if not all_events:
            return []

        # Sort by real_timestamp (ISO format strings sort correctly as plain strings)
        all_events.sort(key=lambda e: e.get('real_timestamp', ''))

        # Return the last n (most recent), keeping chronological order
        return all_events[-n:]

    # ── Utility Methods ────────────────────────────────────────────────────

    def get_world_summary(self) -> dict:
        """
        Returns a snapshot of everything currently in the world database.
        Useful for debugging or showing the player what the DM knows about the world.

        Returns a dict with entity counts, cache stats, and current date.
        """
        def count_entities(cname: str) -> int:
            folder = self._collection_folder(cname)
            if not os.path.exists(folder):
                return 0
            return len([f for f in os.listdir(folder) if f.endswith('.json')])

        return {
            'current_date':      self.get_current_date_str(),
            'total_characters':  count_entities(CHARACTERS),
            'total_locations':   count_entities(LOCATIONS),
            'total_nations':     count_entities(NATIONS),
            'total_plot_events': count_entities(PLOT_EVENTS),
            'vectors_cached':    len(self._vector_cache),
        }
