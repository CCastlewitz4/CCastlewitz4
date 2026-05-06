# homebrew_generator.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: AI-powered homebrew content generator.
#
# Generates balanced, lore-consistent homebrew:
#   - Classes   (with subclasses, features, hit die, proficiencies)
#   - Races     (with ASI, traits, speeds, languages, special abilities)
#   - NPCs      (fully fleshed characters for each session)
#
# HOW IT WORKS:
#   Uses Ollama (the local LLM) to generate structured JSON, then parses
#   and validates that JSON into dicts compatible with character_rules.py
#   and the character creation wizard in main.py.
#
# USAGE:
#   From main.py:
#     from homebrew_generator import HombrewGenerator
#     hbg = HomebrewGenerator()
#     race  = hbg.generate_race(concept="A race of living coral people from the deep sea")
#     cls   = hbg.generate_class(concept="A holy chef who channels divinity through cooking")
#     npc   = hbg.generate_npc(role="city guard captain", location="Ironhaven City")
#
#   In-game commands (handled in main.py):
#     homebrew race   → prompts for concept, generates, shows, optionally saves
#     homebrew class  → same for class
#     homebrew npc    → generates a session-ready NPC
#     homebrew list   → shows all saved homebrew content
#
# SAVED TO:
#   data/homebrew/races.json
#   data/homebrew/classes.json
#   data/homebrew/npcs.json
#
# LOCATION: dnd_ai_dm/homebrew_generator.py
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import re
import time

import config

# ── Storage paths ──────────────────────────────────────────────────────────
HOMEBREW_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'homebrew')
RACES_FILE      = os.path.join(HOMEBREW_DIR, 'races.json')
CLASSES_FILE    = os.path.join(HOMEBREW_DIR, 'classes.json')
NPCS_FILE       = os.path.join(HOMEBREW_DIR, 'npcs.json')
SUBCLASSES_FILE = os.path.join(HOMEBREW_DIR, 'subclasses.json')


def _ensure_dirs():
    os.makedirs(HOMEBREW_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# OLLAMA HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _ask_ollama(prompt: str, system_prompt: str = '', max_tokens: int = 2048) -> str:
    """
    Send a prompt to the local Ollama model and return the response text.
    Returns '' on any failure so callers can handle gracefully.
    """
    try:
        import ollama
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        response = ollama.chat(
            model=config.MODEL_NAME,
            messages=messages,
            options={
                'temperature': 0.85,
                'top_p': 0.92,
                'num_predict': max_tokens,
            }
        )
        return response['message']['content']
    except Exception as e:
        print(f'[Homebrew] Ollama error: {e}')
        return ''


def _extract_json(text: str) -> dict | list | None:
    """
    Extracts and parses the first JSON object or array found in a block of text.
    Handles markdown code fences (```json ... ```) and bare JSON.
    Returns None if no valid JSON is found.
    """
    # Strip markdown code fences
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = re.sub(r'```', '', text)

    # Try the whole string first
    try:
        return json.loads(text.strip())
    except Exception:
        pass

    # Find first { ... } or [ ... ] block
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        # Walk to find matching close bracket
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:
                        break

    return None


# ─────────────────────────────────────────────────────────────────────────────
# RACE GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

_RACE_SYSTEM_PROMPT = """You are a professional D&D 5e game designer creating balanced, creative homebrew races.
You MUST respond ONLY with a valid JSON object — no prose, no explanation, no markdown outside the JSON.
The JSON must match this exact schema:

{
  "name": "Race Name",
  "description": "2-3 sentence flavour description of the race's origin and culture.",
  "asi": {"STR": 0, "DEX": 0, "CON": 0, "INT": 0, "WIS": 0, "CHA": 0},
  "traits": [
    "Trait Name: Description of the trait (1-2 sentences each).",
    "..."
  ],
  "proficiencies": ["Skill or weapon name", "..."],
  "innate_spells": ["Spell name (cantrip)", "Spell name (1/long rest)"],
  "languages": ["Common", "..."],
  "speed": 30,
  "size": "Medium",
  "darkvision": false,
  "darkvision_range": 0,
  "subrace_options": [
    {"name": "Subrace Name", "asi_bonus": {"STAT": 1}, "trait": "Extra trait description."},
    "..."
  ],
  "balance_notes": "Brief note on design intent and balance considerations.",
  "homebrew": true
}

BALANCE RULES:
- Total ASI bonus should not exceed +5 across all stats (usually +2 and +1 to two different stats).
- Maximum 3-4 meaningful racial traits (not counting language/speed/size/darkvision).
- Innate spells: cantrip only, or at most one 1/rest spell. 
- Darkvision should not exceed 120ft.
- Include 2-3 subraces if the race concept supports them.
- Keep it usable at a real table, not overpowered."""

def generate_race(concept: str, system_id: str = 'dnd_5e') -> dict | None:
    """
    Generate a homebrew race from a freeform concept description.

    Parameters:
      concept   — Player's description, e.g. "A race of living coral beings from the ocean floor"
      system_id — The active game system (affects schema used)

    Returns a race data dict compatible with DND5E_RACES in character_rules.py,
    or None if generation fails.
    """
    print(f'\n[Homebrew] Generating race: "{concept}"...')

    if system_id == 'daggerheart':
        return _generate_daggerheart_heritage(concept)

    prompt = (
        f"Design a balanced D&D 5e homebrew race based on this concept:\n\n"
        f'"{concept}"\n\n'
        f"Be creative but mechanically sound. The race should feel unique and fit a fantasy world. "
        f"Return ONLY the JSON — no other text."
    )

    raw = _ask_ollama(prompt, system_prompt=_RACE_SYSTEM_PROMPT, max_tokens=1200)
    if not raw:
        return None

    data = _extract_json(raw)
    if not isinstance(data, dict):
        print('[Homebrew] Could not parse race JSON.')
        return None

    # Validate and clean required fields
    data.setdefault('name', 'Unknown Race')
    data.setdefault('description', concept)
    data.setdefault('asi', {})
    data.setdefault('traits', [])
    data.setdefault('proficiencies', [])
    data.setdefault('innate_spells', [])
    data.setdefault('languages', ['Common'])
    data.setdefault('speed', 30)
    data.setdefault('size', 'Medium')
    data.setdefault('darkvision', False)
    data.setdefault('darkvision_range', 0)
    data.setdefault('subrace_options', [])
    data.setdefault('balance_notes', '')
    data['homebrew'] = True
    data['source_concept'] = concept
    data['generated_at'] = _now()

    return data


def _generate_daggerheart_heritage(concept: str) -> dict | None:
    """Generate a Daggerheart heritage (the equivalent of a race in that system)."""
    prompt = (
        f"Design a Daggerheart RPG homebrew Heritage based on this concept:\n\n"
        f'"{concept}"\n\n'
        f"Daggerheart heritages provide: 3 heritage features (passive abilities), "
        f"an experience (a background skill/knowledge area), and a community bonus (a small stat bonus once per session). "
        f"Return ONLY JSON with keys: name, description, features (list of strings), "
        f"experience (string), community_bonus (string), homebrew (true)."
    )
    raw = _ask_ollama(prompt, max_tokens=800)
    if not raw:
        return None
    data = _extract_json(raw)
    if not isinstance(data, dict):
        return None
    data.setdefault('name', 'Custom Heritage')
    data.setdefault('features', [])
    data.setdefault('experience', 'Choose one experience of your choice.')
    data.setdefault('community_bonus', '+1 to one action roll per session.')
    data['homebrew'] = True
    data['source_concept'] = concept
    data['generated_at'] = _now()
    return data


# ─────────────────────────────────────────────────────────────────────────────
# CLASS GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

_CLASS_SYSTEM_PROMPT = """You are a professional D&D 5e game designer creating balanced homebrew classes.
You MUST respond ONLY with valid JSON — no prose outside the JSON block.

JSON schema:

{
  "name": "Class Name",
  "description": "2-3 sentence flavour description of the class's role and fantasy.",
  "hit_die": 8,
  "primary_ability": "STR, DEX, CON, INT, WIS, or CHA",
  "saves": ["STAT", "STAT"],
  "armor": ["Light Armor", "Medium Armor", "Shields"],
  "weapons": ["Simple Weapons", "specific weapon", "..."],
  "tools": ["Tool name or 'None'"],
  "skill_count": 2,
  "skill_choices": ["Skill", "Skill", "..."],
  "spellcasting": false,
  "spellcasting_ability": "",
  "features": [
    "Feature Name: Description of the level 1 feature (2-3 sentences).",
    "..."
  ],
  "equipment": ["Starting gear item", "..."],
  "subclasses": [
    {
      "name": "Subclass Name",
      "description": "Flavour of this subclass path.",
      "level_unlocked": 3,
      "features": ["Subclass Feature: Description."]
    }
  ],
  "balance_notes": "Design intent and balance notes.",
  "homebrew": true
}

BALANCE RULES:
- Hit die: d6 (fragile casters), d8 (balanced), d10 (martial), d12 (tank).
- Saving throw proficiencies: 2 only.
- Skill count: 2-4.
- Include 2-3 level 1 class features.
- Include 3 subclasses minimum, each unlocked at level 3 (or earlier for caster-focused classes).
- Do NOT give the class every armor and weapon proficiency.
- Spellcasting classes must specify the casting ability stat."""

def generate_class(concept: str, system_id: str = 'dnd_5e') -> dict | None:
    """
    Generate a homebrew class from a freeform concept description.

    Parameters:
      concept   — e.g. "A holy chef who channels divinity through elaborate meals"
      system_id — Active game system

    Returns a class dict compatible with DND5E_CLASSES in character_rules.py,
    or None on failure.
    """
    print(f'\n[Homebrew] Generating class: "{concept}"...')

    if system_id == 'daggerheart':
        return _generate_daggerheart_class(concept)

    prompt = (
        f"Design a balanced D&D 5e homebrew class based on this concept:\n\n"
        f'"{concept}"\n\n'
        f"Create something thematically original that fills a unique niche. "
        f"Ensure it can be played alongside standard PHB classes. "
        f"Return ONLY the JSON — no other text."
    )

    raw = _ask_ollama(prompt, system_prompt=_CLASS_SYSTEM_PROMPT, max_tokens=2000)
    if not raw:
        return None

    data = _extract_json(raw)
    if not isinstance(data, dict):
        print('[Homebrew] Could not parse class JSON.')
        return None

    # Validate
    data.setdefault('name', 'Custom Class')
    data.setdefault('description', concept)
    data.setdefault('hit_die', 8)
    data.setdefault('primary_ability', 'STR')
    data.setdefault('saves', [])
    data.setdefault('armor', [])
    data.setdefault('weapons', ['Simple Weapons'])
    data.setdefault('tools', [])
    data.setdefault('skill_count', 2)
    data.setdefault('skill_choices', [])
    data.setdefault('spellcasting', False)
    data.setdefault('spellcasting_ability', '')
    data.setdefault('features', [])
    data.setdefault('equipment', [])
    data.setdefault('subclasses', [])
    data.setdefault('balance_notes', '')
    data['homebrew'] = True
    data['source_concept'] = concept
    data['generated_at'] = _now()

    return data


def _generate_daggerheart_class(concept: str) -> dict | None:
    """Generate a Daggerheart class (with domain cards, evasion, stress slots)."""
    prompt = (
        f"Design a Daggerheart RPG homebrew Class based on this concept:\n\n"
        f'"{concept}"\n\n'
        f"Daggerheart classes have: evasion (9-13), primary_trait, secondary_trait, "
        f"two domain_cards (from: Arcana, Blade, Bone, Codex, Grace, Midnight, Sage, Splendor, Valor), "
        f"hp_per_level (5-8), stress_slots (5-7), foundation_feature name, "
        f"and 2-3 features (list of strings). Return ONLY JSON."
    )
    raw = _ask_ollama(prompt, max_tokens=1000)
    if not raw:
        return None
    data = _extract_json(raw)
    if not isinstance(data, dict):
        return None
    data.setdefault('name', 'Custom Class')
    data.setdefault('evasion', 12)
    data.setdefault('primary_trait', 'Presence')
    data.setdefault('secondary_trait', 'Knowledge')
    data.setdefault('domain_cards', ['Codex', 'Grace'])
    data.setdefault('hp_per_level', 6)
    data.setdefault('stress_slots', 6)
    data.setdefault('foundation_feature', 'Custom Ability')
    data.setdefault('features', [])
    data.setdefault('starting_equipment', ['Light armor', 'Simple weapon', "Adventurer's supplies"])
    data['homebrew'] = True
    data['source_concept'] = concept
    data['generated_at'] = _now()
    return data


# ─────────────────────────────────────────────────────────────────────────────
# SUBCLASS GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_subclass(base_class: str, concept: str, system_id: str = 'dnd_5e') -> dict | None:
    """
    Generate a homebrew subclass for an existing or homebrew class.

    Parameters:
      base_class — The class this subclass belongs to (e.g. "Fighter")
      concept    — e.g. "A Fighter who draws power from lightning storms"
      system_id  — Active game system

    Returns a subclass dict with name, description, level_unlocked, features.
    """
    print(f'\n[Homebrew] Generating {base_class} subclass: "{concept}"...')

    prompt = (
        f"Design a balanced D&D 5e homebrew subclass for the {base_class} class.\n\n"
        f'Concept: "{concept}"\n\n'
        f"Return ONLY JSON with keys:\n"
        f"  name (string), description (string, 2 sentences), level_unlocked (int, usually 3),\n"
        f"  features (list of strings — 3-4 subclass-specific features with names and descriptions),\n"
        f"  balance_notes (string), homebrew (true), base_class ('{base_class}').\n\n"
        f"Features should feel thematic and powerful but not game-breaking. "
        f"Each feature should be 2-3 sentences."
    )

    raw = _ask_ollama(prompt, max_tokens=1200)
    if not raw:
        return None

    data = _extract_json(raw)
    if not isinstance(data, dict):
        return None

    data.setdefault('name', f'Custom {base_class} Subclass')
    data.setdefault('description', concept)
    data.setdefault('level_unlocked', 3)
    data.setdefault('features', [])
    data.setdefault('balance_notes', '')
    data['homebrew'] = True
    data['base_class'] = base_class
    data['source_concept'] = concept
    data['generated_at'] = _now()

    return data


# ─────────────────────────────────────────────────────────────────────────────
# NPC GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

_NPC_SYSTEM_PROMPT = """You are a Game Master's assistant generating vivid, memorable NPCs for tabletop RPGs.
Respond ONLY with valid JSON — no prose outside the JSON block.

JSON schema:

{
  "name": "Full Name",
  "race": "Race",
  "gender": "Gender / pronouns",
  "age": 35,
  "occupation": "Role or job",
  "location": "Where they are found",
  "appearance": "2-3 sentences describing distinctive physical features.",
  "personality": "2-3 sentences describing how they speak, behave, and what motivates them.",
  "secret": "One secret they hold that could become a plot hook.",
  "attitude_to_strangers": "suspicious / neutral / friendly / hostile",
  "combat_role": "non-combatant / minion / elite / boss",
  "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
  "hp": 12,
  "ac": 12,
  "notable_items": ["Item or weapon", "..."],
  "hooks": ["Story hook or side quest tied to this NPC.", "..."],
  "voice_notes": "How they sound — accent, speech pattern, verbal tic.",
  "homebrew": true
}"""

def generate_npc(
    role: str = '',
    location: str = '',
    attitude: str = '',
    combat_role: str = '',
    system_id: str = 'dnd_5e',
    extra_notes: str = ''
) -> dict | None:
    """
    Generate a fully fleshed-out NPC for the current session.

    Parameters:
      role        — e.g. "city guard captain", "shady merchant", "cult leader"
      location    — Where the NPC is found (e.g. "Ironhaven city docks")
      attitude    — "friendly", "neutral", "hostile", "suspicious" (or '' for random)
      combat_role — "non-combatant", "minion", "elite", "boss" (or '' for auto)
      system_id   — Active game system
      extra_notes — Any additional requirements

    Returns a fully populated NPC dict, or None on failure.
    """
    print(f'\n[Homebrew] Generating NPC: {role or "random"}...')

    parts = [f'Generate a memorable {system_id.replace("_", " ")} NPC']
    if role:
        parts.append(f'who is a {role}')
    if location:
        parts.append(f'found in {location}')
    if attitude:
        parts.append(f'with a {attitude} attitude toward strangers')
    if combat_role:
        parts.append(f'serving as a {combat_role} in combat')
    if extra_notes:
        parts.append(f'Additional requirements: {extra_notes}')

    prompt = ' '.join(parts) + '.\n\nReturn ONLY the JSON — no other text.'

    raw = _ask_ollama(prompt, system_prompt=_NPC_SYSTEM_PROMPT, max_tokens=1200)
    if not raw:
        return None

    data = _extract_json(raw)
    if not isinstance(data, dict):
        print('[Homebrew] Could not parse NPC JSON.')
        return None

    data.setdefault('name', 'Unknown NPC')
    data.setdefault('race', 'Human')
    data.setdefault('gender', 'they/them')
    data.setdefault('age', 30)
    data.setdefault('occupation', role or 'Unknown')
    data.setdefault('location', location or 'Unknown')
    data.setdefault('appearance', 'A nondescript individual.')
    data.setdefault('personality', 'Reserved and cautious.')
    data.setdefault('secret', 'None apparent.')
    data.setdefault('attitude_to_strangers', attitude or 'neutral')
    data.setdefault('combat_role', combat_role or 'non-combatant')
    data.setdefault('stats', {'STR':10,'DEX':10,'CON':10,'INT':10,'WIS':10,'CHA':10})
    data.setdefault('hp', 10)
    data.setdefault('ac', 11)
    data.setdefault('notable_items', [])
    data.setdefault('hooks', [])
    data.setdefault('voice_notes', 'Speaks plainly.')
    data['homebrew'] = True
    data['generated_at'] = _now()

    return data


# ─────────────────────────────────────────────────────────────────────────────
# BATCH SESSION GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_session_content(
    setting: str,
    num_npcs: int = 3,
    generate_race: bool = False,
    generate_class_: bool = False,
    system_id: str = 'dnd_5e'
) -> dict:
    """
    Generates a full suite of homebrew content for a new session.

    Parameters:
      setting        — Brief description of the session's setting/theme
      num_npcs       — How many NPCs to generate (default 3)
      generate_race  — If True, also generates one unique homebrew race for the world
      generate_class_ — If True, also generates one unique homebrew class hint
      system_id      — Active game system

    Returns a dict with keys: 'npcs', 'race' (optional), 'class' (optional)
    """
    print(f'\n[Homebrew] Generating session content for: "{setting}"')
    result: dict = {'npcs': [], 'race': None, 'class': None}

    # Generate NPCs
    roles = _infer_npc_roles(setting, num_npcs)
    for role in roles:
        npc = generate_npc(role=role, location=setting, system_id=system_id)
        if npc:
            result['npcs'].append(npc)
        time.sleep(0.2)  # Small delay between calls

    # Optionally generate a unique race/heritage for the setting
    if generate_race:
        concept = f"A race that fits naturally in a {setting} environment"
        result['race'] = generate_race(concept, system_id)

    return result


def _infer_npc_roles(setting: str, n: int) -> list[str]:
    """
    Generates a list of contextually appropriate NPC roles for a setting.
    Falls back to generic roles if setting is vague.
    """
    setting_lower = setting.lower()
    role_pools = {
        'tavern':  ['innkeeper', 'traveling merchant', 'off-duty guard', 'mysterious stranger', 'bard'],
        'dungeon': ['dungeon boss', 'trapped prisoner', 'rival adventurer', 'undead guardian', 'treasure guardian'],
        'city':    ['city guard', 'guild master', 'noble', 'beggar with secrets', 'assassin'],
        'forest':  ['druid hermit', 'forest bandit leader', 'lost traveler', 'fey emissary', 'ranger'],
        'port':    ['dockmaster', 'smuggler captain', 'ship merchant', 'sea witch', 'pirate informant'],
        'castle':  ['chamberlain', 'knight captain', 'suspicious advisor', 'royal spy', 'imprisoned noble'],
    }

    for key, roles in role_pools.items():
        if key in setting_lower:
            return roles[:n]

    return ['village elder', 'wandering merchant', 'traveling warrior', 'local troublemaker', 'wise hermit'][:n]


# ─────────────────────────────────────────────────────────────────────────────
# PERSISTENCE — SAVE / LOAD
# ─────────────────────────────────────────────────────────────────────────────

def save_race(race_data: dict):
    """Save a homebrew race to the races.json library."""
    _ensure_dirs()
    lib = _load_lib(RACES_FILE)
    name = race_data.get('name', 'Unknown Race')
    lib[name] = race_data
    _write_lib(RACES_FILE, lib)
    print(f'[Homebrew] Race "{name}" saved.')


def save_class(class_data: dict):
    """Save a homebrew class to the classes.json library."""
    _ensure_dirs()
    lib = _load_lib(CLASSES_FILE)
    name = class_data.get('name', 'Unknown Class')
    lib[name] = class_data
    _write_lib(CLASSES_FILE, lib)
    print(f'[Homebrew] Class "{name}" saved.')


def save_subclass(subclass_data: dict):
    """Save a homebrew subclass to the subclasses.json library."""
    _ensure_dirs()
    lib = _load_lib(SUBCLASSES_FILE)
    base = subclass_data.get('base_class', 'Custom')
    name = subclass_data.get('name', 'Unknown')
    key = f'{base}:{name}'
    lib[key] = subclass_data
    _write_lib(SUBCLASSES_FILE, lib)
    print(f'[Homebrew] Subclass "{name}" ({base}) saved.')


def save_npc(npc_data: dict):
    """Save a generated NPC to the npcs.json library."""
    _ensure_dirs()
    lib = _load_lib(NPCS_FILE)
    name = npc_data.get('name', 'Unknown NPC')
    # NPCs can have duplicate names — use name + timestamp as key
    key = f'{name}_{npc_data.get("generated_at", "")}'
    lib[key] = npc_data
    _write_lib(NPCS_FILE, lib)
    print(f'[Homebrew] NPC "{name}" saved.')


def list_homebrew() -> dict:
    """Returns a summary dict of all saved homebrew content."""
    races     = list(_load_lib(RACES_FILE).keys())
    classes   = list(_load_lib(CLASSES_FILE).keys())
    subclasses = list(_load_lib(SUBCLASSES_FILE).keys())
    npcs      = [v.get('name', k) for k, v in _load_lib(NPCS_FILE).items()]
    return {
        'races':      races,
        'classes':    classes,
        'subclasses': subclasses,
        'npcs':       npcs,
        'total':      len(races) + len(classes) + len(npcs) + len(subclasses),
    }


def get_homebrew_race(name: str) -> dict | None:
    """Retrieve a saved homebrew race by name."""
    return _load_lib(RACES_FILE).get(name)


def get_homebrew_class(name: str) -> dict | None:
    """Retrieve a saved homebrew class by name."""
    return _load_lib(CLASSES_FILE).get(name)


def get_homebrew_npc_list() -> list[dict]:
    """Return all saved NPCs as a list."""
    return list(_load_lib(NPCS_FILE).values())


def get_homebrew_race_names() -> list[str]:
    """Return names of all saved homebrew races — for adding to the character creation menu."""
    return list(_load_lib(RACES_FILE).keys())


def get_homebrew_class_names() -> list[str]:
    """Return names of all saved homebrew classes — for adding to class selection menu."""
    return list(_load_lib(CLASSES_FILE).keys())


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION HELPERS
# (Used by character_rules.py to apply homebrew race/class mechanics)
# ─────────────────────────────────────────────────────────────────────────────

def apply_homebrew_race(race_name: str, abilities: dict) -> dict:
    """
    Applies a saved homebrew race's bonuses to a character dict.
    Returns the same format as character_rules._apply_dnd5e() so it can be
    merged directly into the character sheet.
    """
    race_data = get_homebrew_race(race_name)
    if not race_data:
        return {}

    result = {}
    notes = []

    # Apply ASI
    if abilities and race_data.get('asi'):
        updated = dict(abilities)
        for stat, bonus in race_data['asi'].items():
            if isinstance(bonus, int) and bonus != 0:
                updated[stat] = updated.get(stat, 10) + bonus
        result['abilities'] = updated
        asi_str = ', '.join(f'+{v} {k}' for k, v in race_data['asi'].items() if isinstance(v, int) and v > 0)
        if asi_str:
            notes.append(f'Homebrew racial ASI applied: {asi_str}')

    result['racial_traits']        = race_data.get('traits', [])
    result['racial_proficiencies'] = race_data.get('proficiencies', [])
    result['innate_spells']        = race_data.get('innate_spells', [])
    result['languages']            = race_data.get('languages', ['Common'])
    result['speed']                = race_data.get('speed', 30)
    result['size']                 = race_data.get('size', 'Medium')
    if race_data.get('darkvision'):
        result['darkvision'] = race_data.get('darkvision_range', 60)

    notes.append(f'[Homebrew Race] {race_name} features applied.')
    result['auto_applied_notes'] = notes
    return result


def apply_homebrew_class(class_name: str, level: int = 1) -> dict:
    """
    Applies a saved homebrew class's proficiencies and features to a character.
    Returns a dict in the same format as character_rules._apply_dnd5e().
    """
    from character_rules import _prof_bonus
    cls = get_homebrew_class(class_name)
    if not cls:
        return {}

    return {
        'saving_throw_proficiencies': cls.get('saves', []),
        'armor_proficiencies':        cls.get('armor', []),
        'weapon_proficiencies':       cls.get('weapons', []),
        'tool_proficiencies':         cls.get('tools', []),
        'class_features':             cls.get('features', []),
        'skill_choices_available':    cls.get('skill_choices', []),
        'skill_choices_count':        cls.get('skill_count', 2),
        'class_starting_equipment':   cls.get('equipment', []),
        'proficiency_bonus':          _prof_bonus(level),
        'auto_applied_notes': [
            f'[Homebrew Class] {class_name} proficiencies and features applied.',
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def format_race_display(race_data: dict) -> str:
    """Format a homebrew race for Rich terminal display."""
    lines = [
        f"[bold cyan]{race_data.get('name', 'Unknown')}[/bold cyan] [dim][Homebrew Race][/dim]",
        f"[white]{race_data.get('description', '')}[/white]",
        '',
    ]

    asi = race_data.get('asi', {})
    if asi:
        asi_str = '  '.join(f'[cyan]+{v}[/cyan] {k}' for k, v in asi.items() if isinstance(v, int) and v > 0)
        lines.append(f'[bold]Ability Score Increases:[/bold] {asi_str}')

    lines.append(f'[bold]Speed:[/bold] {race_data.get("speed", 30)} ft  |  [bold]Size:[/bold] {race_data.get("size", "Medium")}')

    if race_data.get('darkvision'):
        lines.append(f'[bold]Darkvision:[/bold] {race_data.get("darkvision_range", 60)} ft')

    traits = race_data.get('traits', [])
    if traits:
        lines.append('\n[bold]Racial Traits:[/bold]')
        for t in traits:
            lines.append(f'  • {t}')

    profs = race_data.get('proficiencies', [])
    if profs:
        lines.append(f'[bold]Proficiencies:[/bold] {", ".join(profs)}')

    langs = race_data.get('languages', [])
    if langs:
        lines.append(f'[bold]Languages:[/bold] {", ".join(langs)}')

    subraces = race_data.get('subrace_options', [])
    if subraces:
        lines.append('\n[bold]Subrace Options:[/bold]')
        for sr in subraces:
            if isinstance(sr, dict):
                lines.append(f'  • [cyan]{sr.get("name", "")}[/cyan]: {sr.get("trait", "")}')

    if race_data.get('balance_notes'):
        lines.append(f'\n[dim]Balance Notes: {race_data["balance_notes"]}[/dim]')

    return '\n'.join(lines)


def format_class_display(class_data: dict) -> str:
    """Format a homebrew class for Rich terminal display."""
    lines = [
        f"[bold cyan]{class_data.get('name', 'Unknown')}[/bold cyan] [dim][Homebrew Class][/dim]",
        f"[white]{class_data.get('description', '')}[/white]",
        '',
        f"[bold]Hit Die:[/bold] d{class_data.get('hit_die', 8)}  |  "
        f"[bold]Primary Ability:[/bold] {class_data.get('primary_ability', '?')}",
        f"[bold]Saving Throws:[/bold] {', '.join(class_data.get('saves', []))}",
        f"[bold]Armor:[/bold] {', '.join(class_data.get('armor', ['None']))}",
        f"[bold]Weapons:[/bold] {', '.join(class_data.get('weapons', ['Simple Weapons']))}",
    ]

    if class_data.get('spellcasting'):
        lines.append(f"[bold]Spellcasting:[/bold] Yes ({class_data.get('spellcasting_ability', '?')}-based)")

    features = class_data.get('features', [])
    if features:
        lines.append('\n[bold]Level 1 Features:[/bold]')
        for f in features:
            lines.append(f'  • {f}')

    subclasses = class_data.get('subclasses', [])
    if subclasses:
        lines.append('\n[bold]Subclasses:[/bold]')
        for sc in subclasses:
            if isinstance(sc, dict):
                lvl = sc.get('level_unlocked', 3)
                lines.append(f'  • [cyan]{sc.get("name", "")}[/cyan] (level {lvl}): {sc.get("description", "")}')

    if class_data.get('balance_notes'):
        lines.append(f'\n[dim]Balance Notes: {class_data["balance_notes"]}[/dim]')

    return '\n'.join(lines)


def format_npc_display(npc: dict) -> str:
    """Format a generated NPC for Rich terminal display."""
    lines = [
        f"[bold cyan]{npc.get('name', 'Unknown')}[/bold cyan]"
        f" — {npc.get('race', '')} {npc.get('gender', '')} {npc.get('occupation', '')}",
        f"[dim]Location: {npc.get('location', 'Unknown')}  |  "
        f"Attitude: {npc.get('attitude_to_strangers', 'neutral')}  |  "
        f"Combat: {npc.get('combat_role', 'non-combatant')}  |  "
        f"HP: {npc.get('hp', '?')}  AC: {npc.get('ac', '?')}[/dim]",
        '',
        f"[bold]Appearance:[/bold] {npc.get('appearance', '')}",
        f"[bold]Personality:[/bold] {npc.get('personality', '')}",
        f"[bold]Voice:[/bold] {npc.get('voice_notes', '')}",
        f"[bold]Secret:[/bold] {npc.get('secret', '')}",
    ]

    hooks = npc.get('hooks', [])
    if hooks:
        lines.append('[bold]Story Hooks:[/bold]')
        for h in hooks:
            lines.append(f'  • {h}')

    items = npc.get('notable_items', [])
    if items:
        lines.append(f'[bold]Notable Items:[/bold] {", ".join(items)}')

    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _load_lib(path: str) -> dict:
    """Load a JSON library file, returning {} if it doesn't exist or is corrupt."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _write_lib(path: str, data: dict):
    """Write a dict to a JSON file."""
    _ensure_dirs()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec='seconds')
