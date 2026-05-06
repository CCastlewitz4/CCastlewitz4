# world_builder.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE:
#   AI-driven world generation and character creation assistance.
#   All functions in this module call Ollama directly and are designed to
#   run BEFORE or DURING character creation, never during the main game loop.
#
# FLOW (called from campaign_setup / create_character_interactively in main.py):
#
#   1. generate_world(system, genre, seed, themes, campaign_name)
#      → AI writes full world lore: history, factions, geography, magic/tech,
#        power structures, current tensions, world secrets.
#        Returns a world_lore string saved into campaign_preferences.json.
#
#   2. offer_world_summary_for_character(world_lore, system, genre)
#      → Asks player: "Would you like a world guide to help with character
#        creation?" If yes, AI generates a focused summary covering what races
#        live here, what classes/roles exist, how society is structured, and
#        what backstory hooks fit the world.
#
#   3. offer_custom_races(world_lore, system, genre)
#      → Asks player: "Should the GM generate custom races for this world?"
#        If yes, AI generates 4-6 races with full stat blocks (ASI, traits,
#        speed, size, darkvision, languages, proficiencies). Returns list of
#        race dicts compatible with DND5E_RACES schema.
#        These are stored in prefs['generated_races'].
#
#   4. pick_race_from_world_and_standard(console, system, generated_races)
#      → Shows generated races first (labeled [World Race]), then standard
#        system races below. Player picks any. Returns chosen race name and
#        a race_data dict (for custom races) or None (for standard races).
#
#   5. generate_spell_choices(char_class, subclass, level, world_lore, system)
#      → For spellcasting classes only. AI generates a curated spell list
#        appropriate to class + subclass + level, organized by cantrips /
#        1st-level / 2nd-level / etc. Player picks from numbered menus.
#        Returns chosen spells as a list of strings.
#
# REQUIRES: pip install ollama (already in requirements.txt)
# ─────────────────────────────────────────────────────────────────────────────

import json
import re

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


# ─────────────────────────────────────────────────────────────────────────────
# SPELL METADATA  (how many cantrips / slots / spells known per class at each level)
# Used to tell the AI exactly how many spells to generate choices for.
# ─────────────────────────────────────────────────────────────────────────────

# Format: class → { level → {'cantrips': N, 'spells_known': N, 'slot_levels': [1,1,...] } }
# slot_levels = list of spell slot levels available (e.g. [1,1] means two 1st-level slots)
SPELL_SLOTS = {
    'Bard': {
        1:  {'cantrips': 2, 'spells_known': 4,  'slots': {1: 2}},
        2:  {'cantrips': 2, 'spells_known': 5,  'slots': {1: 3}},
        3:  {'cantrips': 2, 'spells_known': 6,  'slots': {1: 4, 2: 2}},
        4:  {'cantrips': 3, 'spells_known': 7,  'slots': {1: 4, 2: 3}},
        5:  {'cantrips': 3, 'spells_known': 8,  'slots': {1: 4, 2: 3, 3: 2}},
        6:  {'cantrips': 3, 'spells_known': 9,  'slots': {1: 4, 2: 3, 3: 3}},
        7:  {'cantrips': 3, 'spells_known': 10, 'slots': {1: 4, 2: 3, 3: 3, 4: 1}},
        8:  {'cantrips': 3, 'spells_known': 11, 'slots': {1: 4, 2: 3, 3: 3, 4: 2}},
        9:  {'cantrips': 3, 'spells_known': 12, 'slots': {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}},
        10: {'cantrips': 4, 'spells_known': 14, 'slots': {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}},
    },
    'Sorcerer': {
        1:  {'cantrips': 4, 'spells_known': 2,  'slots': {1: 2}},
        2:  {'cantrips': 4, 'spells_known': 3,  'slots': {1: 3}},
        3:  {'cantrips': 4, 'spells_known': 4,  'slots': {1: 4, 2: 2}},
        4:  {'cantrips': 5, 'spells_known': 5,  'slots': {1: 4, 2: 3}},
        5:  {'cantrips': 5, 'spells_known': 6,  'slots': {1: 4, 2: 3, 3: 2}},
        6:  {'cantrips': 5, 'spells_known': 7,  'slots': {1: 4, 2: 3, 3: 3}},
        7:  {'cantrips': 5, 'spells_known': 8,  'slots': {1: 4, 2: 3, 3: 3, 4: 1}},
        8:  {'cantrips': 5, 'spells_known': 9,  'slots': {1: 4, 2: 3, 3: 3, 4: 2}},
        9:  {'cantrips': 5, 'spells_known': 10, 'slots': {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}},
        10: {'cantrips': 6, 'spells_known': 11, 'slots': {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}},
    },
    'Warlock': {
        1:  {'cantrips': 2, 'spells_known': 2,  'slots': {1: 1}},
        2:  {'cantrips': 2, 'spells_known': 3,  'slots': {1: 2}},
        3:  {'cantrips': 2, 'spells_known': 4,  'slots': {2: 2}},
        4:  {'cantrips': 3, 'spells_known': 5,  'slots': {2: 2}},
        5:  {'cantrips': 3, 'spells_known': 6,  'slots': {3: 2}},
        6:  {'cantrips': 3, 'spells_known': 7,  'slots': {3: 2}},
        7:  {'cantrips': 3, 'spells_known': 8,  'slots': {4: 2}},
        8:  {'cantrips': 3, 'spells_known': 9,  'slots': {4: 2}},
        9:  {'cantrips': 3, 'spells_known': 10, 'slots': {5: 2}},
        10: {'cantrips': 4, 'spells_known': 10, 'slots': {5: 2}},
    },
    'Wizard': {
        1:  {'cantrips': 3, 'spells_known': 6,  'slots': {1: 2}},   # spells_known = spellbook
        2:  {'cantrips': 3, 'spells_known': 8,  'slots': {1: 3}},
        3:  {'cantrips': 3, 'spells_known': 10, 'slots': {1: 4, 2: 2}},
        4:  {'cantrips': 4, 'spells_known': 12, 'slots': {1: 4, 2: 3}},
        5:  {'cantrips': 4, 'spells_known': 14, 'slots': {1: 4, 2: 3, 3: 2}},
        6:  {'cantrips': 4, 'spells_known': 16, 'slots': {1: 4, 2: 3, 3: 3}},
        7:  {'cantrips': 4, 'spells_known': 18, 'slots': {1: 4, 2: 3, 3: 3, 4: 1}},
        8:  {'cantrips': 4, 'spells_known': 20, 'slots': {1: 4, 2: 3, 3: 3, 4: 2}},
        9:  {'cantrips': 4, 'spells_known': 22, 'slots': {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}},
        10: {'cantrips': 5, 'spells_known': 24, 'slots': {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}},
    },
    'Cleric': {
        1:  {'cantrips': 3, 'spells_known': None, 'slots': {1: 2}},  # prepared = WIS+level
        2:  {'cantrips': 3, 'spells_known': None, 'slots': {1: 3}},
        3:  {'cantrips': 3, 'spells_known': None, 'slots': {1: 4, 2: 2}},
        4:  {'cantrips': 4, 'spells_known': None, 'slots': {1: 4, 2: 3}},
        5:  {'cantrips': 4, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 2}},
        6:  {'cantrips': 4, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 3}},
        7:  {'cantrips': 4, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 3, 4: 1}},
        8:  {'cantrips': 4, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 3, 4: 2}},
        9:  {'cantrips': 4, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}},
        10: {'cantrips': 5, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}},
    },
    'Druid': {
        1:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 2}},
        2:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 3}},
        3:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 4, 2: 2}},
        4:  {'cantrips': 3, 'spells_known': None, 'slots': {1: 4, 2: 3}},
        5:  {'cantrips': 3, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 2}},
        6:  {'cantrips': 3, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 3}},
        7:  {'cantrips': 3, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 3, 4: 1}},
        8:  {'cantrips': 3, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 3, 4: 2}},
        9:  {'cantrips': 3, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}},
        10: {'cantrips': 4, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}},
    },
    'Paladin': {
        1:  {'cantrips': 0, 'spells_known': None, 'slots': {}},
        2:  {'cantrips': 0, 'spells_known': None, 'slots': {1: 2}},
        3:  {'cantrips': 0, 'spells_known': None, 'slots': {1: 3}},
        4:  {'cantrips': 0, 'spells_known': None, 'slots': {1: 3}},
        5:  {'cantrips': 0, 'spells_known': None, 'slots': {1: 4, 2: 2}},
        6:  {'cantrips': 0, 'spells_known': None, 'slots': {1: 4, 2: 2}},
        7:  {'cantrips': 0, 'spells_known': None, 'slots': {1: 4, 2: 3}},
        8:  {'cantrips': 0, 'spells_known': None, 'slots': {1: 4, 2: 3}},
        9:  {'cantrips': 0, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 2}},
        10: {'cantrips': 0, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 2}},
    },
    'Ranger': {
        1:  {'cantrips': 0, 'spells_known': 0, 'slots': {}},
        2:  {'cantrips': 0, 'spells_known': 2, 'slots': {1: 2}},
        3:  {'cantrips': 0, 'spells_known': 3, 'slots': {1: 3}},
        4:  {'cantrips': 0, 'spells_known': 3, 'slots': {1: 3}},
        5:  {'cantrips': 0, 'spells_known': 4, 'slots': {1: 4, 2: 2}},
        6:  {'cantrips': 0, 'spells_known': 4, 'slots': {1: 4, 2: 2}},
        7:  {'cantrips': 0, 'spells_known': 5, 'slots': {1: 4, 2: 3}},
        8:  {'cantrips': 0, 'spells_known': 5, 'slots': {1: 4, 2: 3}},
        9:  {'cantrips': 0, 'spells_known': 6, 'slots': {1: 4, 2: 3, 3: 2}},
        10: {'cantrips': 0, 'spells_known': 6, 'slots': {1: 4, 2: 3, 3: 2}},
    },
    'Artificer': {
        1:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 2}},
        2:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 2}},
        3:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 3}},
        4:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 3}},
        5:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 4, 2: 2}},
        6:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 4, 2: 2}},
        7:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 4, 2: 3}},
        8:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 4, 2: 3}},
        9:  {'cantrips': 2, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 2}},
        10: {'cantrips': 2, 'spells_known': None, 'slots': {1: 4, 2: 3, 3: 2}},
    },
    'Blood Hunter': {
        1:  {'cantrips': 0, 'spells_known': 0, 'slots': {}},
    },
    # One-third casters — spells unlock at level 3
    'Arcane Trickster': {
        3:  {'cantrips': 3, 'spells_known': 3,  'slots': {1: 2}},
        4:  {'cantrips': 3, 'spells_known': 4,  'slots': {1: 3}},
        5:  {'cantrips': 3, 'spells_known': 4,  'slots': {1: 3}},
        6:  {'cantrips': 3, 'spells_known': 4,  'slots': {1: 3}},
        7:  {'cantrips': 3, 'spells_known': 5,  'slots': {1: 4, 2: 2}},
        8:  {'cantrips': 3, 'spells_known': 6,  'slots': {1: 4, 2: 2}},
        9:  {'cantrips': 3, 'spells_known': 6,  'slots': {1: 4, 2: 2}},
        10: {'cantrips': 4, 'spells_known': 7,  'slots': {1: 4, 2: 3}},
    },
    'Eldritch Knight': {
        3:  {'cantrips': 2, 'spells_known': 3,  'slots': {1: 2}},
        4:  {'cantrips': 2, 'spells_known': 4,  'slots': {1: 3}},
        5:  {'cantrips': 2, 'spells_known': 4,  'slots': {1: 3}},
        6:  {'cantrips': 2, 'spells_known': 4,  'slots': {1: 3}},
        7:  {'cantrips': 2, 'spells_known': 5,  'slots': {1: 4, 2: 2}},
        8:  {'cantrips': 2, 'spells_known': 6,  'slots': {1: 4, 2: 2}},
        9:  {'cantrips': 2, 'spells_known': 6,  'slots': {1: 4, 2: 2}},
        10: {'cantrips': 3, 'spells_known': 7,  'slots': {1: 4, 2: 3}},
    },
}

# Classes that cast spells (used to gate the spell selection step)
SPELLCASTING_CLASSES = set(SPELL_SLOTS.keys())


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL: OLLAMA HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _ask_ai(prompt: str, console: Console, spinner_msg: str,
            temperature: float = 0.85, max_tokens: int = 1200) -> str:
    """
    Call Ollama with a one-shot prompt. Shows a spinner while waiting.
    Returns the response text, or '' on failure.
    """
    import ollama
    import config as _cfg

    with console.status(f'[italic dim]{spinner_msg}[/italic dim]', spinner='dots'):
        try:
            resp = ollama.chat(
                model=_cfg.MODEL_NAME,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'num_ctx':     _cfg.CONTEXT_WINDOW,
                    'temperature': temperature,
                    'num_predict': max_tokens,
                    'top_p':       _cfg.TOP_P,
                }
            )
            return resp['message']['content'].strip()
        except Exception as e:
            console.print(f'[yellow]AI generation failed: {e}[/yellow]')
            return ''


def _parse_json_from_response(text: str) -> object:
    """Extract JSON from a response that may have markdown fences around it."""
    # Strip ```json ... ``` fences
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = re.sub(r'```', '', text)
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # Try to find the first [ or { and parse from there
        for start_char, end_char in [('[', ']'), ('{', '}')]:
            idx = text.find(start_char)
            if idx >= 0:
                try:
                    return json.loads(text[idx:text.rfind(end_char) + 1])
                except Exception:
                    pass
    return None


# ═══════════════════════════════════════════════════════════════════════════
# 1. AI WORLD GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_world(
    console: Console,
    system: dict,
    genre: dict,
    world_seed: str,
    themes: str,
    campaign_name: str,
) -> str:
    """
    The GM AI generates a complete world from the player's seed concept.
    Returns a world_lore string (long-form prose) stored in campaign_preferences.json
    and injected into every DM system prompt for the rest of the campaign.

    What the AI generates:
      - World name and feel (if not seeded)
      - History: one defining event that shaped the present
      - Geography: major regions, cities, or landmarks worth knowing
      - Power structures: who rules, what factions compete
      - Magic / technology: how it works and who controls it
      - Current tensions: what crisis is brewing right now
      - Races / peoples: who lives here (used later for race generation)
      - World secret: something even most inhabitants don't know
    """
    system_name = system.get('short_name', 'Fantasy')
    genre_label  = genre.get('label', 'Adventure')

    seed_clause = f'The player has given this seed concept: "{world_seed}"' if world_seed else \
                  'The player has given no seed — invent the world entirely.'
    theme_clause = f'The campaign themes are: {themes}.' if themes else ''

    prompt = f"""You are the Game Master designing a world for a {system_name} tabletop RPG campaign
in the {genre_label} genre. Campaign name: "{campaign_name}".

{seed_clause}
{theme_clause}

Write a detailed world document that the GM will reference every turn of the campaign.
Cover ALL of the following sections with real, specific, usable details — not vague placeholders:

WORLD NAME AND FEEL
A name for this world or setting, and the atmospheric feel in 2-3 sentences.

DEFINING HISTORY
One major historical event (war, catastrophe, discovery, betrayal) that happened before the
campaign begins. Explain what it was, when it happened, and how it still shapes the present.

GEOGRAPHY
Name 2-3 distinct regions, cities, or environments that exist in this world.
Each gets one vivid sentence.

POWER STRUCTURES
Who holds power right now? Name specific factions, rulers, or organizations (not generic names —
give them real names). Explain what each one wants and who opposes them.

MAGIC OR TECHNOLOGY
How does magic (for fantasy) or technology (for sci-fi/cyberpunk/modern) work in this world?
Who controls it? Is it feared, celebrated, or regulated? Any major limitations?

CURRENT TENSION
What specific conflict, mystery, or crisis is simmering right now, just before the campaign begins?
This is what gives the world urgency.

PEOPLES AND CULTURES
What races, species, or peoples inhabit this world? Name 3-5 distinct groups with one sentence each
about their culture, appearance, and how they fit into the world. Be creative — these can be
standard fantasy races, custom ones, or anything that fits the genre.

WORLD SECRET
One thing that almost no one knows — a hidden truth about the world's history, power, or nature.
The GM will slowly reveal this through the campaign.

Write in plain prose. Be specific. Avoid generic fantasy clichés.
Do not use bullet points inside sections — write in sentences and paragraphs.
Do not add headers beyond the section names listed above."""

    lore = _ask_ai(
        prompt, console,
        'The GM is building your world...',
        temperature=0.88,
        max_tokens=1400,
    )

    if not lore:
        return f'A {genre_label} world for a {system_name} campaign. ' \
               + (f'Seed: {world_seed}.' if world_seed else '')

    return lore


# ═══════════════════════════════════════════════════════════════════════════
# 2. WORLD SUMMARY FOR CHARACTER CREATION
# ═══════════════════════════════════════════════════════════════════════════

def offer_world_summary_for_character(
    console: Console,
    world_lore: str,
    system: dict,
    genre: dict,
) -> None:
    """
    After world generation, asks the player if they want a world guide
    to help them build a character that fits the setting.

    IMPORTANT — SPOILER-FREE:
      This guide is intentionally restricted to surface-level world knowledge
      that any ordinary inhabitant would know. It must NOT reveal:
        - World secrets or hidden truths
        - Faction conspiracies or betrayals
        - Plot twists or campaign mysteries
        - The identities of villains or hidden antagonists
        - Any information the player character would not know at the start

    If yes, the AI generates a focused, spoiler-free character-creation guide:
      - What kinds of people/races live here and how society is structured
      - What classes / roles / occupations fit naturally
      - Backstory hooks grounded in common public knowledge (not secret events)
      - What a native would take for granted — common beliefs and daily life
      - Mechanical notes for class/race choices

    This is displayed and then discarded — it doesn't persist anywhere.
    The world_lore itself is what gets saved and injected into the DM prompt.
    """
    console.print()
    want = console.input(
        '[bold white]Would you like a world guide to help with character creation? (y/n): [/bold white]'
    ).strip().lower()

    if want != 'y':
        return

    system_name = system.get('short_name', 'Fantasy')
    genre_label  = genre.get('label', 'Adventure')

    prompt = f"""You are the Game Master for a {system_name} campaign in the {genre_label} genre.
A player is about to create their character and needs a brief world overview to help them
build someone who fits the setting naturally.

THE WORLD (GM reference — contains secrets you must protect):
{world_lore}

YOUR TASK:
Write a short, spoiler-free character creation guide. This is what an ordinary person
BORN IN THIS WORLD would know from daily life — common knowledge only.

STRICT RULES:
- Do NOT reveal world secrets, hidden truths, or anything marked as a secret.
- Do NOT reveal villain identities, hidden faction conspiracies, or plot twists.
- Do NOT mention anything the player character would not know at the START of the campaign.
- Only describe things a regular citizen would see, hear, and take for granted.
- Keep it brief: 2-3 sentences per section maximum.

WHO LIVES HERE
What peoples and cultures exist? Who is common vs rare? Written from a street-level view.

WHAT ROLES FIT
What jobs, classes, or roles make natural sense here?
What skills are valued in this society?

STARTING OUT — BACKSTORY HOOKS
Give 3 brief hooks tied to PUBLIC, KNOWN events or tensions — not hidden conspiracies.
Each hook should be a one-sentence reason a person might become an adventurer.

COMMON KNOWLEDGE
What does everyone in this world simply know? Daily customs, popular beliefs, obvious dangers.

Write in plain, simple prose. Be specific to this world. No spoilers. No secrets."""

    guide = _ask_ai(
        prompt, console,
        'The GM is preparing your world overview...',
        temperature=0.72,
        max_tokens=700,
    )

    if guide:
        console.print()
        console.print(Panel(
            guide,
            title='[bold cyan]🌍  World Overview — Character Creation[/bold cyan]',
            subtitle='[dim]Common knowledge — what any resident of this world would know[/dim]',
            border_style='cyan',
            padding=(1, 2),
        ))
        console.print(
            '[dim]  Note: The GM is keeping certain world secrets hidden until you discover them in play.[/dim]'
        )
        console.print()


# ═══════════════════════════════════════════════════════════════════════════
# 3. AI CUSTOM RACE GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def offer_custom_races(
    console: Console,
    world_lore: str,
    system: dict,
    genre: dict,
) -> list:
    """
    Asks the player if they want the GM to generate custom races for this world.
    If yes, the AI generates 4-6 races grounded in the world's lore, each with:
      name, description, asi (ability score increases), traits, proficiencies,
      languages, speed, size, darkvision, darkvision_range.

    Returns a list of race dicts. Each dict has a 'world_race': True flag so
    the race picker can label them clearly.
    Returns [] if the player declines.
    """
    console.print()
    want = console.input(
        '[bold white]Should the GM generate custom races for this world? (y/n): [/bold white]'
    ).strip().lower()

    if want != 'y':
        return []

    system_name = system.get('short_name', 'Fantasy')
    genre_label  = genre.get('label', 'Adventure')

    # Strip the campaign preferences wrapper if present — only pass raw lore
    raw_lore = world_lore
    if '--- WORLD BACKGROUND ---' in world_lore:
        raw_lore = world_lore.split('--- WORLD BACKGROUND ---', 1)[-1].strip()

    prompt = f"""You are the Game Master for a {system_name} campaign in the {genre_label} genre.
Design 5 unique playable races that fit naturally into this specific world.

THE WORLD:
{raw_lore}

Each race must feel like it genuinely belongs to THIS world — tie their biology,
culture, and abilities directly to the world's history, geography, or power structures.

Return ONLY valid JSON. No explanation, no markdown, no text outside the JSON array.

Return a JSON array of exactly 5 race objects. Each object must have these exact keys:

{{
  "name": "Race Name",
  "description": "2-3 sentences about who they are, where they come from, their culture",
  "asi": {{"STR": 0, "DEX": 0, "CON": 0, "INT": 0, "WIS": 0, "CHA": 0}},
  "traits": ["Trait Name: description", "Trait Name: description", "Trait Name: description"],
  "proficiencies": ["Skill or weapon name"],
  "languages": ["Language 1", "Language 2"],
  "speed": 30,
  "size": "Medium",
  "darkvision": false,
  "darkvision_range": 0,
  "world_race": true
}}

Rules for balance:
- Total ASI bonuses across all stats must equal exactly 3 (e.g. +2 to one stat, +1 to another)
- Each race gets exactly 3 traits. At least one trait must be mechanically useful, not just flavour.
- Speed is 25, 30, or 35.
- Size is Small or Medium.
- Darkvision range is 0, 60, or 120 feet.
- No race should be strictly better than another — each has a different strength.
- Traits must be specific enough for a GM to adjudicate at the table.

Return ONLY the JSON array, starting with [ and ending with ]."""

    console.print()
    raw = _ask_ai(
        prompt, console,
        'The GM is designing races for your world...',
        temperature=0.82,
        max_tokens=2400,
    )

    if not raw:
        console.print('[yellow]Could not generate races — you can pick from standard races.[/yellow]')
        return []

    races = _parse_json_from_response(raw)

    if not isinstance(races, list) or not races:
        console.print('[yellow]Race generation returned unexpected data — using standard races.[/yellow]')
        return []

    # Validate and clean each race
    cleaned = []
    for r in races:
        if not isinstance(r, dict) or not r.get('name'):
            continue
        race = {
            'name':            str(r.get('name', 'Unknown')),
            'description':     str(r.get('description', '')),
            'asi':             {k: int(v) for k, v in r.get('asi', {}).items() if int(v) != 0},
            'traits':          [str(t) for t in r.get('traits', [])],
            'proficiencies':   [str(p) for p in r.get('proficiencies', [])],
            'languages':       [str(l) for l in r.get('languages', ['Common'])],
            'speed':           int(r.get('speed', 30)),
            'size':            str(r.get('size', 'Medium')),
            'darkvision':      bool(r.get('darkvision', False)),
            'darkvision_range': int(r.get('darkvision_range', 0)),
            'world_race':      True,
        }
        cleaned.append(race)

    if not cleaned:
        console.print('[yellow]No valid races generated — using standard races.[/yellow]')
        return []

    # Show the player what was generated
    _display_generated_races(console, cleaned)

    return cleaned


def _display_generated_races(console: Console, races: list) -> None:
    """Display the generated races in a formatted table with full details."""
    console.print()
    console.print(Panel(
        f'[bold cyan]✦  {len(races)} World Races Generated[/bold cyan]\n'
        '[dim]These races are native to your world. You will choose one during character creation.\n'
        'Standard races are also available if you prefer.[/dim]',
        border_style='cyan',
    ))

    for i, race in enumerate(races, 1):
        asi_parts = [f'+{v} {k}' for k, v in race['asi'].items() if v > 0]
        asi_str   = ', '.join(asi_parts) if asi_parts else 'No ASI'
        dv_str    = f'Darkvision {race["darkvision_range"]} ft' if race['darkvision'] else 'No darkvision'
        traits_preview = ' · '.join(
            t.split(':')[0].strip() for t in race['traits'][:3]
        )

        console.print(Panel(
            f'[white]{race["description"]}[/white]\n\n'
            f'[cyan]ASI:[/cyan] {asi_str}   '
            f'[cyan]Speed:[/cyan] {race["speed"]} ft   '
            f'[cyan]Size:[/cyan] {race["size"]}   '
            f'[cyan]{dv_str}[/cyan]\n'
            f'[cyan]Traits:[/cyan] {traits_preview}\n'
            + (f'[cyan]Languages:[/cyan] {", ".join(race["languages"])}\n' if race['languages'] else ''),
            title=f'[bold white]{i}. {race["name"]}[/bold white]',
            border_style='dim cyan',
            padding=(0, 2),
        ))

    console.print()


# ═══════════════════════════════════════════════════════════════════════════
# 4. RACE PICKER — world races + standard races combined
# ═══════════════════════════════════════════════════════════════════════════

def pick_race(
    console: Console,
    system_races: list,
    generated_races: list,
) -> tuple:
    """
    Shows generated world races (if any) followed by standard system races.
    Player picks by number.

    Returns (race_name: str, race_data: dict | None)
      race_data is the full race dict for generated races, None for standard.
    """
    console.print()
    console.print(Panel(
        '[bold cyan]Choose Your Race[/bold cyan]\n'
        + ('[dim]World races (top) were designed for this specific setting.\n'
           'Standard races (below) are also available.[/dim]'
           if generated_races else
           '[dim]Choose a race for your character.[/dim]'),
        border_style='cyan',
    ))

    # Build combined option list
    options   = []  # (display_label, race_name, race_data_or_None)

    if generated_races:
        console.print('[bold yellow]── World Races ──────────────────────────────────[/bold yellow]')
        for race in generated_races:
            asi_str = ', '.join(f'+{v} {k}' for k, v in race['asi'].items() if v > 0)
            label = f'{race["name"]}  [dim]({asi_str})[/dim]' if asi_str else race['name']
            options.append((label, race['name'], race))
        console.print()

    if system_races:
        if generated_races:
            console.print('[bold white]── Standard Races ───────────────────────────────[/bold white]')
        for r in system_races:
            if 'other' not in r.lower():
                options.append((r, r, None))

    # Always include custom entry
    options.append(('[dim]Other (type your own)[/dim]', '__custom__', None))

    # Display numbered list
    for i, (label, _name, _data) in enumerate(options, 1):
        console.print(f'  [dim]{i:2}.[/dim] {label}')

    console.print()
    while True:
        raw = console.input('[bold white]  Choose (number): [/bold white]').strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                _label, race_name, race_data = options[idx]
                if race_name == '__custom__':
                    custom = console.input('  Type your race: ').strip()
                    return custom, None
                # Show full detail for world races before confirming
                if race_data:
                    _show_race_detail(console, race_data)
                    confirm = console.input(
                        '[bold white]Play this race? (y/n): [/bold white]'
                    ).strip().lower()
                    if confirm != 'y':
                        # Re-display the list
                        for i2, (lbl2, _, __) in enumerate(options, 1):
                            console.print(f'  [dim]{i2:2}.[/dim] {lbl2}')
                        console.print()
                        continue
                console.print(f'  [green]✓ {race_name}[/green]')
                return race_name, race_data
        console.print('  [red]Please enter a valid number.[/red]')


def _show_race_detail(console: Console, race: dict) -> None:
    """Show full stat block for a generated race."""
    asi_str    = ', '.join(f'+{v} {k}' for k, v in race['asi'].items() if v > 0) or 'None'
    dv_str     = f'{race["darkvision_range"]} ft' if race['darkvision'] else 'None'
    traits_str = '\n'.join(f'  • {t}' for t in race['traits'])

    console.print()
    console.print(Panel(
        f'[white]{race["description"]}[/white]\n\n'
        f'[cyan]Ability Score Increases:[/cyan] {asi_str}\n'
        f'[cyan]Speed:[/cyan] {race["speed"]} ft   '
        f'[cyan]Size:[/cyan] {race["size"]}   '
        f'[cyan]Darkvision:[/cyan] {dv_str}\n'
        f'[cyan]Languages:[/cyan] {", ".join(race["languages"])}\n'
        + (f'[cyan]Proficiencies:[/cyan] {", ".join(race["proficiencies"])}\n'
           if race.get("proficiencies") else '')
        + f'\n[cyan]Traits:[/cyan]\n{traits_str}',
        title=f'[bold white]{race["name"]}[/bold white]',
        border_style='cyan',
        padding=(0, 2),
    ))
    console.print()


# ═══════════════════════════════════════════════════════════════════════════
# 5. AI SPELL SELECTION
# ═══════════════════════════════════════════════════════════════════════════

def generate_and_pick_spells(
    console: Console,
    char_class: str,
    subclass: str,
    level: int,
    world_lore: str,
    system: dict,
) -> list:
    """
    For spellcasting classes: generates a curated list of spell options
    appropriate to the class, subclass, and level, then lets the player
    pick from numbered menus for each tier (cantrips, 1st-level, 2nd-level, etc.)

    Returns a flat list of chosen spell name strings.
    """
    # Find the matching class key
    class_key = _match_spell_class(char_class)
    if not class_key:
        return []

    level_capped = min(level, 10)  # SPELL_SLOTS table goes to 10
    slot_info = SPELL_SLOTS.get(class_key, {}).get(level_capped)
    if not slot_info:
        return []

    num_cantrips  = slot_info['cantrips']
    spells_known  = slot_info['spells_known']
    slots         = slot_info['slots']
    max_spell_lvl = max(slots.keys()) if slots else 0

    # If no spells at this level (e.g. Paladin level 1, Ranger level 1)
    if num_cantrips == 0 and max_spell_lvl == 0:
        console.print(f'[dim]{char_class} does not have spells at level {level}.[/dim]')
        return []

    console.print()
    console.print(Panel(
        f'[bold cyan]✨  Spell Selection — {char_class}[/bold cyan]'
        + (f' ({subclass})' if subclass else '') + '\n\n'
        '[white]The GM will suggest spells that fit your class and this world.[/white]\n'
        '[dim]You will pick from the generated list. Press Enter to skip any tier.[/dim]',
        border_style='cyan',
    ))

    # Generate spell options from the AI
    spell_options = _generate_spell_options(
        console, class_key, subclass, level, max_spell_lvl,
        num_cantrips, spells_known, world_lore, system
    )

    if not spell_options:
        # Fallback: free-text entry
        console.print('[yellow]Could not generate spell list. Enter spells manually.[/yellow]')
        raw = console.input('  Known spells (comma-separated, or Enter to skip): ').strip()
        return [s.strip() for s in raw.split(',') if s.strip()] if raw else []

    # Let player pick from each tier
    chosen = []

    if num_cantrips > 0 and spell_options.get('cantrips'):
        console.print(f'\n[bold white]── Cantrips — choose {num_cantrips} ──────────────────────[/bold white]')
        picks = _pick_spells_from_list(console, spell_options['cantrips'], num_cantrips, 'cantrip')
        chosen.extend(picks)

    if spells_known is not None:
        # Fixed spells-known caster (Bard, Sorcerer, Warlock, Ranger)
        # Distribute the known spell budget across available levels
        for sp_lvl in range(1, max_spell_lvl + 1):
            key = f'level_{sp_lvl}'
            if spell_options.get(key):
                # How many to pick at this tier — roughly distribute spells_known across levels
                per_level = max(1, spells_known // max(1, max_spell_lvl))
                if sp_lvl == 1 and max_spell_lvl == 1:
                    per_level = spells_known
                label = _ordinal(sp_lvl)
                console.print(
                    f'\n[bold white]── {label}-Level Spells — choose {per_level} ──────────────────[/bold white]'
                )
                picks = _pick_spells_from_list(console, spell_options[key], per_level, f'{label}-level spell')
                chosen.extend(picks)
    else:
        # Prepared caster (Cleric, Druid, Paladin, Wizard, Artificer) —
        # player picks spells to START with prepared
        for sp_lvl in range(1, max_spell_lvl + 1):
            key = f'level_{sp_lvl}'
            if spell_options.get(key):
                num_slots = slots.get(sp_lvl, 0)
                pick_count = max(2, num_slots)  # suggest at least 2 options per level
                label = _ordinal(sp_lvl)
                console.print(
                    f'\n[bold white]── {label}-Level Spells — choose {pick_count} to prepare ──────[/bold white]'
                )
                console.print(f'[dim]You can prepare more later. Choose {pick_count} to start.[/dim]')
                picks = _pick_spells_from_list(console, spell_options[key], pick_count, f'{label}-level spell')
                chosen.extend(picks)

    if chosen:
        console.print()
        console.print(Panel(
            '[cyan]Starting spells:[/cyan]\n' + '\n'.join(f'  ✦ {s}' for s in chosen),
            title='[bold green]Spell Selection Complete[/bold green]',
            border_style='green',
        ))

    return chosen


def _generate_spell_options(
    console: Console,
    class_key: str,
    subclass: str,
    level: int,
    max_spell_level: int,
    num_cantrips: int,
    spells_known,
    world_lore: str,
    system: dict,
) -> dict:
    """
    Ask the AI to generate a curated spell option list for each tier.
    Returns dict: {'cantrips': [...], 'level_1': [...], 'level_2': [...], ...}
    Each list has 6-10 spell option dicts: {name, school, description}
    """
    system_name = system.get('short_name', 'Fantasy')

    subclass_clause = f'Their subclass is {subclass}.' if subclass else ''
    world_clause    = f'\n\nWORLD CONTEXT (flavor the spell names/descriptions to fit):\n{world_lore[:600]}' \
                      if world_lore else ''

    cantrip_section = f'- "cantrips": array of {min(num_cantrips + 4, 10)} cantrip objects' \
                      if num_cantrips > 0 else ''

    level_sections = '\n'.join(
        f'- "level_{lvl}": array of {min(7, 10)} level-{lvl} spell objects'
        for lvl in range(1, max_spell_level + 1)
    )

    prompt = f"""You are a {system_name} Game Master building a spell list for a player.

Class: {class_key}
{subclass_clause}
Character Level: {level}
Highest available spell level: {max_spell_level}
{world_clause}

Generate a curated list of thematically appropriate spells for each tier.
Include a mix of offensive, defensive, utility, and roleplay spells.
If the world has a unique flavor, subtly reflect it in the descriptions.

Return ONLY valid JSON. No explanation. No markdown.

Return a single JSON object with these keys:
{cantrip_section}
{level_sections}

Each spell object has exactly these keys:
{{"name": "Spell Name", "school": "Evocation", "description": "One sentence of what it does."}}

Return ONLY the JSON object starting with {{ and ending with }}."""

    raw = _ask_ai(
        prompt, console,
        'The GM is preparing your spell options...',
        temperature=0.75,
        max_tokens=1400,
    )

    if not raw:
        return {}

    parsed = _parse_json_from_response(raw)
    if not isinstance(parsed, dict):
        return {}

    # Validate structure
    result = {}
    for key, val in parsed.items():
        if isinstance(val, list):
            cleaned_spells = []
            for sp in val:
                if isinstance(sp, dict) and sp.get('name'):
                    cleaned_spells.append({
                        'name':        str(sp.get('name', '')),
                        'school':      str(sp.get('school', '')),
                        'description': str(sp.get('description', '')),
                    })
            if cleaned_spells:
                result[key] = cleaned_spells

    return result


def _pick_spells_from_list(
    console: Console,
    spells: list,
    count: int,
    tier_label: str,
) -> list:
    """
    Display a numbered table of spells and let the player pick `count` of them.
    Returns list of chosen spell name strings.
    """
    if not spells:
        return []

    # Display table
    tbl = Table(show_header=True, header_style='bold cyan',
                border_style='dim', padding=(0, 1))
    tbl.add_column('#',           style='dim',        width=3,  justify='right')
    tbl.add_column('Spell',       style='bold white',  min_width=22)
    tbl.add_column('School',      style='dim yellow',  min_width=14)
    tbl.add_column('Effect',      style='white',       min_width=40, max_width=62)

    for i, sp in enumerate(spells, 1):
        tbl.add_row(
            str(i),
            sp['name'],
            sp['school'],
            sp['description'],
        )

    console.print(tbl)
    console.print(
        f'[dim]Choose {count} {tier_label}{"s" if count != 1 else ""} '
        f'(enter {count} number{"s" if count != 1 else ""} separated by spaces), '
        f'or press Enter to skip.[/dim]'
    )

    chosen = []
    while True:
        raw = console.input('[bold white]  → [/bold white]').strip()
        if not raw:
            return []

        nums = re.findall(r'\d+', raw)
        selected = []
        valid    = True

        for n in nums:
            idx = int(n) - 1
            if 0 <= idx < len(spells):
                if idx not in selected:
                    selected.append(idx)
            else:
                console.print(f'  [red]{n} is out of range (1-{len(spells)}).[/red]')
                valid = False
                break

        if not valid:
            continue

        if len(selected) < count:
            # Allow picking fewer than the limit if they want
            confirm = console.input(
                f'  [yellow]You chose {len(selected)} of {count}. Continue? (y/n): [/yellow]'
            ).strip().lower()
            if confirm != 'y':
                continue

        chosen = [spells[i]['name'] for i in selected]
        for name in chosen:
            console.print(f'  [green]✓ {name}[/green]')
        return chosen


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _match_spell_class(char_class: str, subclass: str = '') -> str | None:
    """
    Fuzzy-match a class or subclass string to a key in SPELL_SLOTS.
    Checks class name first, then subclass — so Rogue + Arcane Trickster
    correctly resolves to the Arcane Trickster slot table.
    """
    for key in SPELL_SLOTS:
        if key.lower() in char_class.lower():
            return key
    if subclass:
        for key in SPELL_SLOTS:
            if key.lower() in subclass.lower():
                return key
    return None


def _ordinal(n: int) -> str:
    suffixes = {1: 'st', 2: 'nd', 3: 'rd'}
    return f'{n}{suffixes.get(n, "th")}'


def is_spellcaster(char_class: str, subclass: str = '') -> bool:
    """Returns True if this class or subclass has spells."""
    return _match_spell_class(char_class, subclass) is not None


# ═══════════════════════════════════════════════════════════════════════════
# 6. WORLD MAP GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_world_map(
    console: Console,
    world_lore: str,
    system: dict,
    genre: dict,
    campaign_name: str,
    output_dir: str = 'data',
) -> str | None:
    """
    Generates a stylized world map as a PNG image from the world lore.

    HOW IT WORKS:
      1. AI reads the world lore and extracts geography: regions, cities,
         landmarks, terrain types, and rough directional relationships.
      2. Returns a JSON layout with named locations, terrain, and borders.
      3. We render this layout as a visually styled map using matplotlib —
         no Stable Diffusion required, works even with SD offline.

    The map includes:
      - Named regions drawn as colored terrain zones
      - City/location markers with labels
      - Terrain coloring (forest=green, mountains=grey, ocean=blue, etc.)
      - A title banner with the world/campaign name
      - Compass rose
      - Legend

    Returns the path to the saved PNG, or None if generation failed.
    Called from campaign_setup() in main.py after world generation.
    """
    import json as _json
    import os as _os

    console.print()
    console.print(Panel(
        '[bold cyan]🗺  Generating World Map...[/bold cyan]\n'
        '[dim]The GM is reading the world lore and placing locations on the map.[/dim]',
        border_style='cyan', padding=(0, 2),
    ))

    # ── Step 1: Ask AI to extract geography as structured JSON ────────────────
    system_name = system.get('short_name', 'Fantasy')
    genre_label  = genre.get('label', 'Adventure')

    map_prompt = f"""You are the Game Master for a {system_name} / {genre_label} campaign.
Read the following world lore and extract its geography into a JSON map layout.

WORLD LORE:
{world_lore[:2000]}

Return ONLY a valid JSON object with this exact structure — no explanation, no markdown:
{{
  "world_name": "Name of the world or setting",
  "map_title": "Short evocative subtitle (e.g. 'The Known Realms' or 'The Shattered Empire')",
  "regions": [
    {{
      "name": "Region name",
      "terrain": "one of: plains, forest, mountains, desert, ocean, tundra, swamp, city, ruins, volcanic",
      "x": 0.0,
      "y": 0.0,
      "width": 0.0,
      "height": 0.0,
      "description": "One sentence about this region"
    }}
  ],
  "locations": [
    {{
      "name": "Location name",
      "type": "one of: capital, city, town, fortress, dungeon, ruin, port, temple, landmark",
      "x": 0.0,
      "y": 0.0,
      "description": "One sentence"
    }}
  ],
  "borders": [
    {{"from": "Region A", "to": "Region B"}}
  ]
}}

COORDINATE RULES:
- All x and y values must be between 0.0 and 1.0 (fractional position on the map).
- Region x/y is the CENTER of the region. width and height are fractions (0.1 to 0.4).
- Regions should not all overlap — spread them across the map.
- Include 3-6 regions and 4-8 locations.
- Locations must be placed at coherent positions relative to regions.
- Include at least one body of water (ocean/river) if the setting is fantasy.

Return ONLY the JSON. No other text."""

    raw_json = _ask_ai(
        map_prompt, console,
        'Mapping the world...',
        temperature=0.5,
        max_tokens=1200,
    )

    if not raw_json:
        console.print('[yellow]Could not generate map layout.[/yellow]')
        return None

    # Parse the JSON
    map_data = _parse_json_from_response(raw_json)
    if not map_data or 'regions' not in map_data:
        console.print('[yellow]Map data could not be parsed. Skipping map.[/yellow]')
        return None

    # ── Step 2: Render the map with matplotlib ────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend — no display window needed
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyBboxPatch, Circle
        import numpy as np
    except ImportError:
        console.print('[yellow]matplotlib not installed. Run: pip install matplotlib[/yellow]')
        return None

    # Terrain color palette — earthy fantasy tones
    TERRAIN_COLORS = {
        'plains':    '#c8b870',   # Warm tan
        'forest':    '#4a7c59',   # Deep green
        'mountains': '#7a6a5a',   # Rocky grey-brown
        'desert':    '#d4a853',   # Sandy gold
        'ocean':     '#2a5f8f',   # Deep sea blue
        'tundra':    '#a0b8c8',   # Icy blue-grey
        'swamp':     '#5a6e3a',   # Dark murky green
        'city':      '#8b7355',   # Urban brown
        'ruins':     '#6b5a4a',   # Crumbled stone
        'volcanic':  '#8b2500',   # Dark red-orange
    }
    TERRAIN_LABELS = {
        'plains': 'Plains', 'forest': 'Forest', 'mountains': 'Mountains',
        'desert': 'Desert', 'ocean': 'Sea / Ocean', 'tundra': 'Tundra / Ice',
        'swamp': 'Swamp', 'city': 'Settled Lands', 'ruins': 'Ruins',
        'volcanic': 'Volcanic',
    }
    LOCATION_MARKERS = {
        'capital':  ('*',  16, '#ffd700'),   # gold star
        'city':     ('o',   8, '#f0e0b0'),   # circle
        'town':     ('o',   6, '#d0c090'),   # small circle
        'village':  ('o',   5, '#b0a080'),   # small circle
        'fortress': ('^',   8, '#a09080'),   # triangle up
        'castle':   ('^',   9, '#c0b090'),   # triangle up (larger)
        'dungeon':  ('d',   7, '#c06060'),   # thin diamond
        'cave':     ('d',   6, '#a05050'),   # thin diamond (smaller)
        'ruin':     ('s',   6, '#907060'),   # square
        'ruins':    ('s',   6, '#907060'),   # square (plural alias)
        'port':     ('p',   8, '#6090c0'),   # pentagon
        'harbor':   ('p',   8, '#5080b0'),   # pentagon
        'temple':   ('P',   8, '#d0a030'),   # filled plus
        'shrine':   ('P',   6, '#b08020'),   # filled plus (smaller)
        'landmark': ('h',   8, '#80c080'),   # hexagon
        'tower':    ('H',   7, '#a0d0a0'),   # rotated hexagon
        'camp':     ('v',   6, '#c0a070'),   # triangle down
        'outpost':  ('v',   5, '#a08060'),   # triangle down (smaller)
        'mine':     ('D',   6, '#b09060'),   # diamond
        'forest':   ('h',   8, '#40a040'),   # hexagon (green)
        'mystery':  ('x',   7, '#c080c0'),   # x marker
    }

    fig_w, fig_h = 14, 10
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor='#1a1a2e')
    ax = fig.add_axes([0.02, 0.08, 0.72, 0.82])  # Main map area
    ax.set_facecolor('#0d1f3a')                    # Deep ocean background
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    # ── Draw regions ────────────────────────────────────────────────────────
    drawn_terrains = {}
    for region in map_data.get('regions', []):
        terrain = region.get('terrain', 'plains').lower()
        color   = TERRAIN_COLORS.get(terrain, '#888866')
        rx      = region.get('x', 0.5) - region.get('width', 0.2) / 2
        ry      = region.get('y', 0.5) - region.get('height', 0.2) / 2
        rw      = region.get('width', 0.2)
        rh      = region.get('height', 0.2)

        # Clamp to map bounds
        rx = max(0.01, min(0.97, rx))
        ry = max(0.01, min(0.97, ry))
        rw = min(rw, 1.0 - rx - 0.01)
        rh = min(rh, 1.0 - ry - 0.01)

        patch = FancyBboxPatch(
            (rx, ry), rw, rh,
            boxstyle='round,pad=0.01',
            facecolor=color, edgecolor='#2a2a2a',
            linewidth=0.8, alpha=0.85,
        )
        ax.add_patch(patch)

        # Region name label (small, centered)
        cx = rx + rw / 2
        cy = ry + rh / 2
        ax.text(
            cx, cy, region.get('name', ''),
            ha='center', va='center',
            fontsize=6.5, color='#ffffff99',
            fontfamily='serif', style='italic',
            alpha=0.75, wrap=True,
        )

        if terrain not in drawn_terrains:
            drawn_terrains[terrain] = mpatches.Patch(
                color=color, label=TERRAIN_LABELS.get(terrain, terrain.title())
            )

    # ── Draw location markers ────────────────────────────────────────────────
    for loc in map_data.get('locations', []):
        lx = max(0.02, min(0.98, loc.get('x', 0.5)))
        ly = max(0.02, min(0.98, loc.get('y', 0.5)))
        loc_type = loc.get('type', 'town').lower()
        marker, size, color = LOCATION_MARKERS.get(loc_type, ('o', 8, '#e0d0b0'))

        ax.plot(lx, ly, marker=marker, markersize=size, color=color,
                zorder=5, linestyle='None')

        # Location name label
        name = loc.get('name', '')
        ax.text(
            lx + 0.012, ly + 0.018, name,
            ha='left', va='bottom',
            fontsize=6, color='#f0e8d0',
            fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.1', facecolor='#00000066',
                      edgecolor='none', alpha=0.7),
            zorder=6,
        )

    # ── Compass rose (top-right corner of map) ───────────────────────────────
    cr_x, cr_y, cr_r = 0.93, 0.92, 0.04
    for angle, label in [(90, 'N'), (270, 'S'), (0, 'E'), (180, 'W')]:
        rad = np.radians(angle)
        tx = cr_x + np.cos(rad) * cr_r * 1.6
        ty = cr_y + np.sin(rad) * cr_r * 1.6
        ax.text(tx, ty, label, ha='center', va='center',
                fontsize=6.5, color='#d0c090', fontweight='bold', zorder=7)
    for angle in [90, 270, 0, 180]:
        rad = np.radians(angle)
        ax.annotate('', xy=(cr_x + np.cos(rad) * cr_r, cr_y + np.sin(rad) * cr_r),
                    xytext=(cr_x, cr_y),
                    arrowprops=dict(arrowstyle='->', color='#d0c090', lw=1.0),
                    zorder=7)

    # ── Map border ornament ───────────────────────────────────────────────────
    for spine_color in ['#8b7355', '#6b5a3a']:
        border = mpatches.FancyBboxPatch(
            (0.005, 0.005), 0.99, 0.99,
            boxstyle='round,pad=0.005',
            facecolor='none',
            edgecolor=spine_color,
            linewidth=2.5 if spine_color == '#8b7355' else 1.0,
            transform=ax.transAxes, zorder=8,
        )
        ax.add_patch(border)

    # ── Title + subtitle panel (right side) ──────────────────────────────────
    title_ax = fig.add_axes([0.76, 0.60, 0.22, 0.30])
    title_ax.set_facecolor('#16213e')
    title_ax.axis('off')

    world_title = map_data.get('world_name', campaign_name or 'The World')
    map_subtitle = map_data.get('map_title', '')

    title_ax.text(0.5, 0.85, world_title,
                  ha='center', va='center', transform=title_ax.transAxes,
                  fontsize=13, color='#f5d580', fontfamily='serif',
                  fontweight='bold', wrap=True)
    if map_subtitle:
        title_ax.text(0.5, 0.62, map_subtitle,
                      ha='center', va='center', transform=title_ax.transAxes,
                      fontsize=8.5, color='#c0a870', fontfamily='serif',
                      style='italic', wrap=True)

    # System + genre tag
    title_ax.text(0.5, 0.38, f'{system_name}  ·  {genre_label}',
                  ha='center', va='center', transform=title_ax.transAxes,
                  fontsize=7, color='#888888')

    # Decorative divider
    title_ax.axhline(0.50, color='#8b7355', linewidth=0.8, alpha=0.7)
    title_ax.axhline(0.30, color='#6b5a3a', linewidth=0.4, alpha=0.5)

    # ── Legend (bottom right) ─────────────────────────────────────────────────
    legend_ax = fig.add_axes([0.76, 0.08, 0.22, 0.50])
    legend_ax.set_facecolor('#16213e')
    legend_ax.axis('off')

    legend_ax.text(0.5, 0.97, 'LEGEND', ha='center', va='top',
                   transform=legend_ax.transAxes,
                   fontsize=7.5, color='#d0c090', fontweight='bold')

    legend_ax.axhline(0.93, color='#8b7355', linewidth=0.8, alpha=0.7)

    y_pos = 0.88
    for terrain, patch in list(drawn_terrains.items())[:7]:
        legend_ax.add_patch(mpatches.Rectangle(
            (0.05, y_pos - 0.025), 0.12, 0.05,
            facecolor=patch.get_facecolor(), transform=legend_ax.transAxes
        ))
        legend_ax.text(0.22, y_pos, patch.get_label(),
                       transform=legend_ax.transAxes,
                       fontsize=6.5, color='#c0b090', va='center')
        y_pos -= 0.085

    if y_pos > 0.2:
        legend_ax.axhline(y_pos + 0.03, color='#6b5a3a', linewidth=0.4, alpha=0.5)
        y_pos -= 0.05
        # Location types actually used
        used_types = set(loc.get('type', 'town').lower() for loc in map_data.get('locations', []))
        for lt in ['capital', 'city', 'town', 'fortress', 'dungeon', 'port', 'temple', 'ruin', 'landmark']:
            if lt in used_types and y_pos > 0.05:
                marker, size, color = LOCATION_MARKERS.get(lt, ('o', 8, '#e0d0b0'))
                legend_ax.text(0.12, y_pos, marker, ha='center', va='center',
                               transform=legend_ax.transAxes,
                               fontsize=size * 0.55, color=color)
                legend_ax.text(0.22, y_pos, lt.title(),
                               transform=legend_ax.transAxes,
                               fontsize=6.5, color='#c0b090', va='center')
                y_pos -= 0.08

    # ── Bottom caption ─────────────────────────────────────────────────────────
    fig.text(0.01, 0.02,
             f'Generated for: {campaign_name or world_title}  ·  AI Dungeon Master',
             ha='left', va='bottom', fontsize=6, color='#555555')

    # ── Save ──────────────────────────────────────────────────────────────────
    _os.makedirs(output_dir, exist_ok=True)
    safe_name = ''.join(c if c.isalnum() or c in '-_' else '_'
                        for c in (campaign_name or 'world'))
    map_path = _os.path.join(output_dir, f'{safe_name}_world_map.png')

    plt.savefig(map_path, dpi=150, bbox_inches='tight',
                facecolor='#1a1a2e', edgecolor='none')
    plt.close(fig)

    return map_path


def offer_world_map(
    console: Console,
    world_lore: str,
    system: dict,
    genre: dict,
    campaign_name: str,
    output_dir: str = 'data',
) -> str | None:
    """
    Asks the player if they want a world map, then generates one if yes.
    Called from campaign_setup() in main.py after world generation.
    Returns the map file path, or None if skipped/failed.
    """
    console.print()
    want = console.input(
        '[bold white]Would you like the GM to generate a world map? (y/n): [/bold white]'
    ).strip().lower()

    if want != 'y':
        return None

    path = generate_world_map(
        console       = console,
        world_lore    = world_lore,
        system        = system,
        genre         = genre,
        campaign_name = campaign_name,
        output_dir    = output_dir,
    )

    if path:
        console.print()
        console.print(Panel(
            f'[bold green]✓ World map generated![/bold green]\n'
            f'[cyan]{path}[/cyan]\n\n'
            '[dim]Open this PNG to see your world. '
            'Type [bold]map[/bold] during play to regenerate an updated version.[/dim]',
            border_style='green', padding=(0, 2),
        ))
    else:
        console.print('[yellow]Map generation failed. You can try again with the "map" command.[/yellow]')

    return path
