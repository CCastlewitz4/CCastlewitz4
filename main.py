# main.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: The entry point for the DnD AI DM system. Run this file to start
#          a DnD session. It handles player character setup, session management,
#          and the main interactive game loop.
#
# HOW TO RUN:
#   In PyCharm: Right-click main.py → Run 'main'
#   In terminal: cd dnd_ai_dm && python main.py
#
# CONTROLS:
#   - Type your action and press Enter to take a turn
#   - Type 'status'  → Show current in-game date and session info
#   - Type 'world'   → Show recent plot events
#   - Type 'rels'    → Show your character's current relationships
#   - Type 'save'    → Force-save (auto-saves already happen every turn)
#   - Type 'quit'    → Exit and save the session
#
# LOCATION: dnd_ai_dm/main.py
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import config
import systems as sys_defs
import character_rules
import world_builder
import spell_feature_picker
import character_sheet_generator
from agent.dm_agent import DMAgent

# rich Console: provides styled terminal output (colors, panels, etc.)
console = Console()

# CHARACTER_FILE is now set dynamically by config.set_active_system()
# after the player selects a game system at startup.
# It points to data/<system_id>/player_character.json
def get_character_file() -> str:
    return config.CHARACTER_FILE


# ── Race and Class Options ────────────────────────────────────────────────
# Displayed as numbered menus during character creation.
# You can add more options to either list freely.

RACES = [
    'Human', 'Elf', 'High Elf', 'Wood Elf', 'Dark Elf (Drow)',
    'Dwarf', 'Hill Dwarf', 'Mountain Dwarf',
    'Halfling', 'Lightfoot Halfling', 'Stout Halfling',
    'Gnome', 'Rock Gnome', 'Forest Gnome',
    'Half-Elf', 'Half-Orc', 'Tiefling', 'Dragonborn',
    'Aasimar', 'Genasi', 'Goliath', 'Tabaxi', 'Kenku', 'Lizardfolk',
    'Other (type your own)',
]

CLASSES = [
    'Barbarian', 'Bard', 'Cleric', 'Druid', 'Fighter',
    'Monk', 'Paladin', 'Ranger', 'Rogue', 'Sorcerer',
    'Warlock', 'Wizard', 'Artificer', 'Blood Hunter',
    'Other (type your own)',
]

ALIGNMENTS = [
    'Lawful Good', 'Neutral Good', 'Chaotic Good',
    'Lawful Neutral', 'True Neutral', 'Chaotic Neutral',
    'Lawful Evil', 'Neutral Evil', 'Chaotic Evil',
]


def _prompt_choice(prompt: str, options: list, allow_custom: bool = False) -> str:
    """
    Displays a numbered menu and returns the player's chosen option.

    Parameters:
      prompt       — The question to display above the menu
      options      — List of string options to number and display
      allow_custom — If True, the last option triggers a free-text prompt
                     so the player can type anything not on the list

    Returns the chosen string (either from the list or typed by the player).
    """
    console.print(f'\n[bold cyan]{prompt}[/bold cyan]')
    for i, opt in enumerate(options, 1):
        console.print(f'  [dim]{i:2}.[/dim] {opt}')

    while True:
        raw = console.input('[bold white]  Choose (number): [/bold white]').strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                chosen = options[idx]
                # If the last option is "Other", prompt for free text
                if allow_custom and 'other' in chosen.lower():
                    return console.input('  Type your choice: ').strip()
                return chosen
        console.print('  [red]Please enter a valid number.[/red]')


def _prompt_text(prompt: str, default: str = '', required: bool = True) -> str:
    """
    Prompts the player for free-form text input.

    Parameters:
      prompt   — The question to display
      default  — Value returned if the player presses Enter without typing
      required — If True, keeps asking until the player types something

    Returns the entered text string.
    """
    suffix = f' [dim](default: {default})[/dim]' if default else ''
    console.print(f'\n[bold cyan]{prompt}[/bold cyan]{suffix}')

    while True:
        value = console.input('[bold white]  → [/bold white]').strip()
        if value:
            return value
        if default:
            return default
        if not required:
            return ''
        console.print('  [red]This field is required. Please enter a value.[/red]')


def _prompt_ability_scores() -> dict:
    """
    Walks the player through entering their six D&D ability scores.
    Accepts any integer between 1 and 30. Defaults to 10 if skipped.

    Each score is explained briefly so new players understand what it does.
    Returns a dict with keys STR, DEX, CON, INT, WIS, CHA.
    """
    console.print('\n[bold cyan]Ability Scores[/bold cyan]')
    console.print('[dim]Enter each score (1-30). Press Enter to use default of 10.[/dim]')
    console.print('[dim]Standard array: 15, 14, 13, 12, 10, 8  |  Point buy average: 8-15[/dim]\n')

    score_info = [
        ('STR', 'Strength',     'Physical power, melee attacks, carrying capacity'),
        ('DEX', 'Dexterity',    'Agility, ranged attacks, stealth, armor class'),
        ('CON', 'Constitution', 'Endurance, hit points, concentration'),
        ('INT', 'Intelligence', 'Memory, reasoning, wizard spells, investigation'),
        ('WIS', 'Wisdom',       'Perception, insight, cleric/druid spells'),
        ('CHA', 'Charisma',     'Persuasion, deception, sorcerer/warlock/bard spells'),
    ]

    scores = {}
    for abbrev, name, description in score_info:
        console.print(f'  [cyan]{abbrev}[/cyan] — {name}: [dim]{description}[/dim]')
        while True:
            raw = console.input(f'  {abbrev} [10]: ').strip()
            if not raw:
                scores[abbrev] = 10
                break
            if raw.isdigit() and 1 <= int(raw) <= 30:
                scores[abbrev] = int(raw)
                break
            console.print('  [red]Please enter a number between 1 and 30.[/red]')

    return scores


def _prompt_hp(char_class: str) -> dict:
    """
    Asks the player for their starting hit points.
    Provides class-based suggestions so new players know reasonable values.

    Returns a dict with 'current' and 'maximum' keys.
    """
    # Suggested starting HP by class (max hit die + CON modifier of 1 for simplicity)
    hp_suggestions = {
        'Barbarian': 12, 'Fighter': 10, 'Paladin': 10, 'Ranger': 10,
        'Bard': 8, 'Cleric': 8, 'Druid': 8, 'Monk': 8, 'Rogue': 8, 'Warlock': 8,
        'Artificer': 8, 'Blood Hunter': 10,
        'Sorcerer': 6, 'Wizard': 6,
    }
    suggestion = hp_suggestions.get(char_class, 8)

    console.print(f'\n[bold cyan]Starting Hit Points[/bold cyan]')
    console.print(f'  [dim]Suggested for {char_class}: {suggestion} HP[/dim]')
    console.print(f'  [dim]At level 1 this is your max hit die + CON modifier.[/dim]')

    while True:
        raw = console.input(f'  Starting HP [{suggestion}]: ').strip()
        if not raw:
            return {'current': suggestion, 'maximum': suggestion}
        if raw.isdigit() and int(raw) > 0:
            hp = int(raw)
            return {'current': hp, 'maximum': hp}
        console.print('  [red]Please enter a positive number.[/red]')



def _pick_subclass(char_class: str, system_id: str = 'dnd_5e') -> str:
    """
    Displays a numbered table of available subclasses for the chosen class,
    with source book and description from the wiki cache. Player picks by
    number or types a custom subclass name. Returns the subclass string.
    """
    from rich.table import Table

    # Only D&D 5e has the full subclass table — PF2e and Starfinder use free text
    if system_id != 'dnd_5e':
        return _prompt_text('Subclass / Archetype (optional):', required=False)

    # Normalize class key (strip parenthetical notes)
    class_key = char_class.split('(')[0].strip()

    # Load subclasses — tries wiki cache, falls back to registry names
    try:
        import wiki_scraper
        subclasses = wiki_scraper.get_subclasses(class_key)
    except Exception:
        subclasses = []

    if not subclasses:
        # No data at all — fall back to plain text input
        return _prompt_text('Subclass / Archetype (optional):', required=False)

    console.print()
    console.print(Panel(
        f'[bold cyan]Choose your {class_key} Subclass[/bold cyan]\n'
        f'[dim]Level 1: Cleric, Sorcerer, Warlock  ·  Level 2: Druid, Fighter\n'
        f'Level 3: all others (Paladin, Ranger, Bard, Rogue, Wizard, etc.)\n'
        f'You can skip now and decide later.[/dim]',
        border_style='cyan',
    ))

    # Build table
    tbl = Table(show_header=True, header_style='bold cyan',
                border_style='dim', expand=False, padding=(0, 1))
    tbl.add_column('#',         style='dim',        width=3,  justify='right')
    tbl.add_column('Subclass',  style='bold white',  min_width=22)
    tbl.add_column('Source',    style='dim yellow',  min_width=28)
    tbl.add_column('Description', style='white',     min_width=40, max_width=62)

    for i, sc in enumerate(subclasses, 1):
        desc = sc.get('desc', '')
        # Truncate description for display
        if len(desc) > 120:
            desc = desc[:117] + '...'
        tbl.add_row(
            str(i),
            sc.get('name', ''),
            sc.get('source', ''),
            desc or '[dim](no description cached)[/dim]',
        )

    console.print(tbl)
    console.print(
        f'\n[dim]Enter a number (1-{len(subclasses)}), type a custom name, or press Enter to skip.[/dim]'
    )

    while True:
        raw = console.input('[bold white]  → [/bold white]').strip()
        if not raw:
            return ''   # player skipped
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(subclasses):
                chosen = subclasses[idx]['name']
                console.print(f'  [green]✓ {chosen}[/green]')
                return chosen
            console.print(f'  [red]Please enter a number between 1 and {len(subclasses)}.[/red]')
        else:
            # Accept any free text as a custom subclass name
            console.print(f'  [green]✓ Custom: {raw}[/green]')
            return raw


def create_character_interactively(system: dict = None) -> dict:
    """
    System-aware interactive character creation wizard.

    ENHANCED FLOW (v2):
      1. Display world info / lore so the player can make informed choices
      2. Race picker — shows FULL stat block (ASI, traits, proficiencies,
         speed, darkvision, languages) before confirming
      3. Class picker — shows FULL stat block (hit die, saves, armor/weapon
         proficiencies, skill choices, level-1 features) before confirming
      4. Subclass selection (D&D 5e / PF2e / Starfinder / Daggerheart)
      5. Background picker — shows skills, tools, languages, equipment, feature
      6. Skill proficiency picker — numbered list, already-proficient skills
         shown as locked-in, player chooses remaining from class pool
      7. Starting equipment chooser — OR-choices presented as numbered menus
      8. Ability scores, HP, spells, class features
      9. Confirmation with full auto-applied summary

    Parameters:
      system — The game system dict from systems.py. If None, reads from config.

    Returns a complete character dict ready to pass to DMAgent.
    """
    from character_setup import (
        pick_race_with_details,
        pick_class_with_details,
        pick_background,
        pick_skill_proficiencies,
        pick_starting_equipment,
        build_proficiency_block,
        display_world_info_for_character_creation,
        _load_homebrew_races,
    )

    if system is None:
        system = getattr(config, 'ACTIVE_SYSTEM', None)

    system_id   = system['id'] if system else 'dnd_5e'
    system_name = system['short_name'] if system else 'RPG'

    console.print()
    console.print(Panel(
        f'[bold cyan]⚔  Character Creation — {system_name}  ⚔[/bold cyan]\n\n'
        "[white]Let's build your character.[/white]\n"
        '[dim]Each step shows you the full details so you can make informed choices.\n'
        'You can review any option before committing to it.[/dim]',
        border_style='cyan'
    ))

    # ── Get system-specific options ───────────────────────────────────────
    races      = system.get('races', []) if system else []
    roles      = system.get('roles', []) if system else []
    alignments = system.get('alignments', []) if system else []
    ab_scores  = system.get('ability_scores', []) if system else []
    hp_table   = system.get('hp_by_role', {}) if system else {}

    role_label = 'Occupation' if system_id == 'call_of_cthulhu' else \
                 'Role' if system_id == 'cyberpunk_red' else 'Class'
    race_label = 'Nationality' if system_id == 'call_of_cthulhu' else \
                 'Species / Origin' if system_id == 'starfinder' else 'Race'

    # ── Step 0: Show world info for character creation ─────────────────────
    world_lore      = getattr(config, 'CAMPAIGN_PREFS_BLOCK', '')
    generated_races = getattr(config, 'GENERATED_RACES', []) or []

    if world_lore or generated_races:
        display_world_info_for_character_creation(
            console         = console,
            world_lore      = world_lore,
            generated_races = generated_races,
            system          = system,
        )

    # Load any previously saved homebrew races for the race menu
    homebrew_new   = []
    homebrew_saved = list(_load_homebrew_races().values()) if system_id in (
        'dnd_5e', 'pathfinder_2e', 'daggerheart', 'starfinder'
    ) else []

    # ── Step 1: Race Selection with full stat block display ─────────────────
    console.print(f'\n[bold white]── {race_label} ──────────────────────────────────────[/bold white]')

    if system_id in ('dnd_5e', 'pathfinder_2e', 'daggerheart', 'starfinder'):
        race, race_data = pick_race_with_details(
            console         = console,
            system_id       = system_id,
            standard_races  = [r for r in races if 'other' not in r.lower()],
            generated_races = generated_races,
            homebrew_races  = homebrew_saved + homebrew_new,
        )
    elif generated_races:
        race, race_data = world_builder.pick_race(
            console         = console,
            system_races    = [r for r in races if 'other' not in r.lower()],
            generated_races = generated_races,
        )
    elif races and races != ['Other (type your own)']:
        race = _prompt_choice(f'{race_label}:', races, allow_custom=True)
        race_data = None
    else:
        race      = _prompt_text(f'{race_label} (type freely):', required=False)
        race_data = None

    if race_data:
        config.CUSTOM_RACE_DATA = race_data

    # ── Step 2: Class / Role Selection with full stat block display ────────
    console.print(f'\n[bold white]── {role_label} ──────────────────────────────────────[/bold white]')

    if system_id in ('dnd_5e', 'pathfinder_2e', 'daggerheart', 'starfinder') and roles:
        char_class = pick_class_with_details(
            console    = console,
            system_id  = system_id,
            classes    = [r for r in roles if 'other' not in r.lower()],
            role_label = role_label,
        )
    elif roles:
        char_class = _prompt_choice(f'Choose your {role_label}:', roles, allow_custom=True)
    else:
        char_class = _prompt_text(f'{role_label}:', required=True)

    # ── Step 3: Level ─────────────────────────────────────────────────────
    # Level must come BEFORE subclass — we need to know the level to decide
    # if the class has unlocked its subclass yet.
    if system_id in ('dnd_5e', 'pathfinder_2e', 'starfinder'):
        level_raw = console.input('\n[bold cyan]Starting level[/bold cyan] [dim](1-20, default 1)[/dim]\n  → ').strip()
        level = int(level_raw) if level_raw.isdigit() and 1 <= int(level_raw) <= 20 else 1
    else:
        level = 1

    # ── Step 4: Subclass selection (only if level qualifies) ──────────────
    # D&D 5e subclass unlock levels per class (PHB):
    #   Level 1 — Cleric (Divine Domain), Sorcerer (Sorcerous Origin),
    #             Warlock (Otherworldly Patron)
    #   Level 2 — Druid (Druid Circle), Fighter (Martial Archetype)
    #   Level 3 — Barbarian (Primal Path), Bard (Bard College),
    #             Monk (Monastic Tradition), Paladin (Sacred Oath),
    #             Ranger (Ranger Conclave), Rogue (Roguish Archetype),
    #             Wizard (Arcane Tradition), Artificer (Specialist)
    DND5E_SUBCLASS_LEVELS = {
        'cleric': 1, 'sorcerer': 1, 'warlock': 1,
        'druid': 2, 'fighter': 2,
        'barbarian': 3, 'bard': 3, 'monk': 3, 'paladin': 3, 'ranger': 3,
        'rogue': 3, 'wizard': 3, 'artificer': 3,
    }
    subclass = ''
    if system_id in ('dnd_5e', 'pathfinder_2e', 'starfinder', 'daggerheart'):
        class_key = char_class.split('(')[0].strip().lower()
        unlock_level = DND5E_SUBCLASS_LEVELS.get(class_key, 3)  # default 3 if unknown
        if level >= unlock_level:
            while True:
                subclass = _pick_subclass(char_class, system_id)
                if not subclass:
                    break
                confirm_sub = console.input(
                    f'[bold white]  Confirm subclass [cyan]{subclass}[/cyan]? (y/n): [/bold white]'
                ).strip().lower()
                if confirm_sub == 'y':
                    break
        else:
            console.print(
                f'\n[dim]  Subclass unlocked at level {unlock_level} '
                f'({char_class} — you are level {level}). '
                f'Your DM will prompt you when you reach it.[/dim]'
            )

    # ── Step 5: Basic Identity ────────────────────────────────────────────
    console.print('\n[bold white]── Basic Identity ──────────────────────────────[/bold white]')

    name = _prompt_text("What is your character's name?", required=True)

    age_raw = console.input('\n[bold cyan]Age[/bold cyan] [dim](press Enter to skip)[/dim]\n  → ').strip()
    age = int(age_raw) if age_raw.isdigit() else None

    gender = _prompt_text('Gender / Pronouns (optional):', required=False)

    if alignments:
        alignment = _prompt_choice('Choose your alignment:', alignments)
    else:
        alignment = ''

    # ── Step 6: Physical Appearance ───────────────────────────────────────
    console.print('\n[bold white]── Physical Appearance ────────────────────────[/bold white]')
    console.print('[dim]This is what the DM and other characters see. Be descriptive —[/dim]')
    console.print('[dim]hair color, eye color, build, distinguishing features, typical clothing.[/dim]')

    appearance = _prompt_text('Describe your appearance:', required=True)

    # ── Step 7: Personality ───────────────────────────────────────────────
    console.print('\n[bold white]── Personality ─────────────────────────────────[/bold white]')
    console.print('[dim]How does your character behave, speak, and react to the world?[/dim]')

    personality = _prompt_text('Describe your personality and mannerisms:', required=True)

    # ── Step 8: Backstory ─────────────────────────────────────────────────
    console.print('\n[bold white]── Backstory ───────────────────────────────────[/bold white]')
    console.print('[dim]Where did you come from? What drives you? Any secrets or enemies?[/dim]')

    backstory = _prompt_text(
        'Describe your backstory (can be brief or detailed):',
        default='A traveler seeking adventure, past largely unknown.',
        required=False
    )

    # ── Step 9: Ability Scores ────────────────────────────────────────────
    if ab_scores:
        console.print('\n[bold white]── Ability Scores / Characteristics ────────────[/bold white]')
        stat_hint = system.get('stat_label', 'Stats') if system else 'Stats'
        console.print(f'[dim]{stat_hint}[/dim]')
        console.print('[dim]Enter each value. Press Enter to use 10 as default.[/dim]\n')

        abilities = {}
        for abbrev, stat_name, description in ab_scores:
            console.print(f'  [cyan]{abbrev}[/cyan] — {stat_name}: [dim]{description}[/dim]')
            while True:
                raw = console.input(f'  {abbrev} [10]: ').strip()
                if not raw:
                    abilities[abbrev] = 10
                    break
                if raw.isdigit() and 1 <= int(raw) <= 100:
                    abilities[abbrev] = int(raw)
                    break
                console.print('  [red]Please enter a number between 1 and 100.[/red]')
    else:
        console.print('\n[bold white]── Stats / Attributes ──────────────────────────[/bold white]')
        console.print('[dim]Enter as "StatName: value" pairs, comma-separated. Or press Enter to skip.[/dim]')
        raw_stats = console.input('  Stats: ').strip()
        abilities = {}
        if raw_stats:
            for part in raw_stats.split(','):
                if ':' in part:
                    k, v = part.split(':', 1)
                    k, v_str = k.strip(), v.strip()
                    abilities[k] = int(v_str) if v_str.isdigit() else v_str

    # ── Step 10: Hit Points ───────────────────────────────────────────────
    hp_label  = 'Hit Points / Stamina'
    suggestion = hp_table.get(char_class, 8) if hp_table else 8
    console.print(f'\n[bold cyan]{hp_label}[/bold cyan]')
    if suggestion:
        console.print(f'  [dim]Suggested for {char_class}: {suggestion}[/dim]')
    while True:
        raw_hp = console.input(f'  Starting HP [{suggestion}]: ').strip()
        if not raw_hp:
            hit_points = {'current': suggestion, 'maximum': suggestion}
            break
        if raw_hp.isdigit() and int(raw_hp) > 0:
            hp = int(raw_hp)
            hit_points = {'current': hp, 'maximum': hp}
            break
        console.print('  [red]Please enter a positive number.[/red]')

    # ── Step 11: Background Picker ────────────────────────────────────────
    # Only for systems that use backgrounds
    background = {}
    if system_id in ('dnd_5e', 'pathfinder_2e', 'starfinder', 'daggerheart',
                     'call_of_cthulhu', 'cyberpunk_red'):
        background = pick_background(console, system_id, char_class)

    # ── Step 12: Skill Proficiency Picker ─────────────────────────────────
    # Build list of already-proficient skills from race + background
    already_proficient = []
    if race_data:
        already_proficient += race_data.get('proficiencies', [])
    else:
        import character_rules as _cr_tmp
        race_db_attr = {'dnd_5e': 'DND5E_RACES', 'pathfinder_2e': 'PF2E_ANCESTRIES'}.get(system_id, 'DND5E_RACES')
        race_db = getattr(_cr_tmp, race_db_attr, _cr_tmp.DND5E_RACES)
        race_info = race_db.get(race, {})
        already_proficient += race_info.get('proficiencies', [])

    bg_skills = background.get('skill_proficiencies') or background.get('skills') or []
    already_proficient += [s for s in bg_skills if s not in already_proficient]

    import character_rules as _cr_skills
    system_class_db = {
        'dnd_5e':        _cr_skills.DND5E_CLASSES,
        'pathfinder_2e': _cr_skills.PF2E_CLASSES,
        'daggerheart':   _cr_skills.DAGGERHEART_CLASSES,
    }.get(system_id, _cr_skills.DND5E_CLASSES)
    class_data = system_class_db.get(char_class, {})

    chosen_skills = []
    if system_id in ('dnd_5e', 'pathfinder_2e', 'starfinder') and class_data.get('skill_choices'):
        chosen_skills = pick_skill_proficiencies(
            console           = console,
            class_data        = class_data,
            class_name        = char_class,
            already_proficient= already_proficient,
        )

    # ── Step 13: Starting Equipment Chooser ──────────────────────────────
    # Present OR-choices as numbered menus; non-OR items auto-included
    inventory = []
    bg_equipment = background.get('equipment', [])

    if system_id in ('dnd_5e', 'pathfinder_2e', 'starfinder') and class_data.get('equipment'):
        inventory = pick_starting_equipment(
            console    = console,
            class_data = class_data,
            class_name = char_class,
        )
        # Merge background equipment (always granted)
        if bg_equipment:
            console.print()
            console.print(Panel(
                '[bold cyan]Background Equipment[/bold cyan]\n'
                '[dim]The following items are granted automatically by your background:[/dim]\n\n'
                + '\n'.join(f'  [cyan]•[/cyan] {item}' for item in bg_equipment),
                border_style='dim cyan',
                padding=(0, 2),
            ))
            inventory += [item for item in bg_equipment if item not in inventory]
    else:
        # Fallback for systems without structured equipment data
        inv_str = _prompt_text(
            'Starting items:',
            default="Adventurer's pack, 10 gold pieces",
            required=False
        )
        inventory = [item.strip() for item in inv_str.split(',') if item.strip()]
        if bg_equipment:
            inventory += [item for item in bg_equipment if item not in inventory]

    # ── Step 14: System-specific extra fields ─────────────────────────────
    extra_fields = {}

    if system_id == 'call_of_cthulhu':
        pow_score = abilities.get('POW', 10)
        default_sanity = pow_score * 5
        console.print(f'\n[bold cyan]Starting Sanity[/bold cyan]')
        console.print(f'  [dim]Default = POW x 5 = {default_sanity}. Max is 99.[/dim]')
        raw_san = console.input(f'  Sanity [{default_sanity}]: ').strip()
        extra_fields['sanity'] = int(raw_san) if raw_san.isdigit() else default_sanity
        console.print('\n[bold cyan]Key Skills[/bold cyan]')
        console.print('[dim]Enter as "Skill: value%" pairs, comma-separated.[/dim]')
        raw_skills = console.input('  Skills: ').strip()
        extra_fields['skills'] = [s.strip() for s in raw_skills.split(',') if s.strip()] if raw_skills else []

    elif system_id == 'cyberpunk_red':
        emp = abilities.get('EMP', 7)
        default_humanity = emp * 10
        console.print(f'\n[bold cyan]Starting Humanity[/bold cyan]')
        raw_hum = console.input(f'  Humanity [{default_humanity}]: ').strip()
        extra_fields['humanity'] = int(raw_hum) if raw_hum.isdigit() else default_humanity
        console.print('\n[bold cyan]Installed Cyberware[/bold cyan]')
        raw_cyber = console.input('  Cyberware (comma-separated, or Enter to skip): ').strip()
        extra_fields['cyberware'] = [c.strip() for c in raw_cyber.split(',') if c.strip()] if raw_cyber else []

    elif system_id == 'starfinder':
        console.print('\n[bold cyan]Starting Resolve Points[/bold cyan]')
        raw_rp = console.input('  Resolve Points [3]: ').strip()
        extra_fields['resolve_points'] = int(raw_rp) if raw_rp.isdigit() else 3

    elif system_id in ('dnd_5e', 'pathfinder_2e', 'daggerheart'):
        # Class feature choices (Fighting Style, Metamagic, Invocations, etc.)
        chosen_features = spell_feature_picker.pick_class_features(
            console    = console,
            char_class = char_class,
            subclass   = subclass,
            level      = level,
            system_id  = system_id,
        )
        extra_fields.update(chosen_features)
        # Sync subclass from chosen_features when pick_class_features set one
        # (e.g. Rogue → Arcane Trickster, Fighter → Eldritch Knight).
        # Only overwrite if chosen_features actually contains a non-empty value.
        if chosen_features.get('subclass'):
            subclass = chosen_features['subclass']

        # Spell selection — also triggers for subclass casters (Arcane Trickster, Eldritch Knight)
        if world_builder.is_spellcaster(char_class, subclass):
            # Show subclass bonus spells BEFORE the picker so the player
            # knows what's already on their list (domain spells, AT spells, etc.)
            try:
                subclass_bonus = spell_feature_picker.get_subclass_bonus_spells(char_class, subclass, level)
            except Exception:
                subclass_bonus = []
            if subclass_bonus:
                console.print()
                console.print(Panel(
                    f'[bold cyan]✦  {subclass} — Bonus Spells[/bold cyan]\n\n'
                    '[white]These spells are automatically added to your spell list\n'
                    'by your subclass. You do not need to pick them — they are always prepared.[/white]\n\n'
                    + '\n'.join(f'  [cyan]•[/cyan] {sp}' for sp in subclass_bonus),
                    border_style='cyan',
                    padding=(0, 2),
                ))
            chosen_spells = spell_feature_picker.offer_spell_selection_method(
                console    = console,
                char_class = char_class,
                subclass   = subclass,
                level      = level,
                system_id  = system_id,
                world_lore = getattr(config, 'CAMPAIGN_PREFS_BLOCK', ''),
                system     = system,
            )
            if chosen_spells:
                extra_fields['spells'] = chosen_spells

    spells = extra_fields.pop('spells', [])
    # Merge subclass bonus spells (domain spells, AT spells, etc.) into the list
    try:
        _bonus = spell_feature_picker.get_subclass_bonus_spells(char_class, subclass, level)
        for _sp in _bonus:
            if _sp not in spells:
                spells.append(_sp)
    except Exception:
        pass

    # ── Step 15: Notes / Special Traits ──────────────────────────────────
    console.print('\n[bold white]── Notes & Special Traits ──────────────────────[/bold white]')
    console.print('[dim]Any special conditions, racial traits, class features, or story hooks?[/dim]')

    notes = _prompt_text('Notes (optional):', required=False)

    # ── Step 16: Rumors ───────────────────────────────────────────────────
    # The player enters 1-4 rumors their character has heard. Each can be
    # true or false. True rumors may surface as plot hooks in play;
    # false rumors mislead the character just as they would in the real world.
    console.print()
    console.print(Panel(
        '[bold cyan]Rumors[/bold cyan]\n\n'
        '[white]What rumors has your character heard? Enter 1 to 4 — they can be\n'
        'wild tavern gossip, half-truths, or things that could shake the world.\n'
        'You will mark each as true or false. The GM will weave true rumors\n'
        'into the campaign as plot hooks or background events.[/white]\n\n'
        '[dim]Examples:\n'
        '  • "The king\'s advisor is secretly a member of the thieves\' guild."\n'
        '  • "A dragon was spotted sleeping beneath the old mill three nights ago."\n'
        '  • "The war ended because both sides ran out of gold, not soldiers."[/dim]',
        border_style='cyan',
        padding=(0, 2),
    ))

    rumors = []
    for i in range(1, 5):
        rumor_text = console.input(
            f'  [bold white]Rumor {i}[/bold white] [dim](or Enter to finish): [/dim]'
        ).strip()
        if not rumor_text:
            break
        is_true = console.input(
            f'  [dim]Is this rumor true? (y/n): [/dim]'
        ).strip().lower() == 'y'
        rumors.append({'text': rumor_text, 'true': is_true})
        console.print(
            f'  [green]✓[/green] [dim]{"[True]" if is_true else "[False]"} {rumor_text}[/dim]'
        )
        if i < 4:
            another = console.input(
                f'  [dim]Add another rumor? (y/n): [/dim]'
            ).strip().lower()
            if another != 'y':
                break

    # ── Assemble the character dict ────────────────────────────────────────
    # Compute spell slots from SPELL_SLOTS table in world_builder so they
    # appear on the character sheet without needing the player to look them up.
    spell_slots = {}
    try:
        from world_builder import SPELL_SLOTS, _match_spell_class
        _matched = _match_spell_class(char_class, subclass)
        if _matched and _matched in SPELL_SLOTS:
            _available = sorted(SPELL_SLOTS[_matched].keys())
            _level_cap = max((l for l in _available if l <= max(level, _available[0])), default=None)
            if _level_cap:
                spell_slots = SPELL_SLOTS[_matched][_level_cap].get('slots', {})
    except Exception:
        pass

    character = {
        'id':           'player_character',
        'system_id':    system_id,
        'name':         name,
        'race':         race,
        'class':        char_class,
        'subclass':     subclass,
        'level':        level,
        'age':          age,
        'gender':       gender,
        'alignment':    alignment,
        'appearance':   appearance,
        'personality':  personality,
        'backstory':    backstory,
        'abilities':    abilities,
        'hit_points':   hit_points,
        'inventory':    inventory,
        'spells':       spells,
        'spell_slots':  spell_slots,
        'rumors':       rumors,
        'background':   background.get('name', ''),
        'notes':        notes,
        'starting_location_id': None,
    }
    character.update(extra_fields)

    # ── Auto-apply racial and class mechanics ──────────────────────────────
    auto_data = character_rules.apply_race_and_class(
        system_id  = system_id,
        race       = race,
        char_class = char_class,
        abilities  = character['abilities'],
        level      = level,
    )
    if auto_data:
        if 'abilities' in auto_data:
            character['abilities'] = auto_data.pop('abilities')
        character.update(auto_data)

    # ── Build and store full proficiency block ─────────────────────────────
    if system_id in ('dnd_5e', 'pathfinder_2e', 'starfinder'):
        racial_profs = []
        if race_data:
            racial_profs = race_data.get('proficiencies', [])
        else:
            import character_rules as _cr_p
            rdb = getattr(_cr_p, 'DND5E_RACES', {})
            racial_profs = rdb.get(race, {}).get('proficiencies', [])

        prof_block = build_proficiency_block(
            racial_proficiencies = racial_profs,
            background           = background,
            chosen_skills        = chosen_skills,
            class_data           = class_data,
        )
        character.update(prof_block)

    # ── Confirmation Panel ─────────────────────────────────────────────────
    if abilities:
        stat_items = [f'{k} {v}' for k, v in list(abilities.items())[:6]]
        stat_line  = '  '.join(stat_items)
    else:
        stat_line = 'No stats defined'

    auto_summary = character_rules.format_auto_applied_summary(
        auto_data if auto_data else {}, system_id
    )

    # Proficiency summary for confirmation
    all_skills = character.get('all_skill_proficiencies', chosen_skills + already_proficient)
    prof_lines = []
    if all_skills:
        prof_lines.append(f'[cyan]Skills:[/cyan] {", ".join(all_skills[:8])}' +
                          ('...' if len(all_skills) > 8 else ''))
    if character.get('armor_proficiencies'):
        prof_lines.append(f'[cyan]Armor:[/cyan] {", ".join(character["armor_proficiencies"][:4])}')
    if character.get('saving_throw_proficiencies'):
        prof_lines.append(f'[cyan]Saving Throws:[/cyan] {", ".join(character["saving_throw_proficiencies"])}')

    console.print()
    console.print(Panel(
        f'[bold white]{name}[/bold white]\n'
        f'[cyan]{race} {char_class}[/cyan]'
        + (f' ({subclass})' if subclass else '')
        + (f' — Level {level}' if level > 1 else '') + '\n'
        + (f'[dim]Alignment: {alignment}[/dim]\n' if alignment else '')
        + (f'[dim]Background: {background.get("name", "")}[/dim]\n' if background.get('name') else '')
        + f'\n[white]{appearance[:120]}[/white]\n\n'
        f'HP: [green]{hit_points["current"]} / {hit_points["maximum"]}[/green]  |  '
        f'{stat_line}'
        + (f'\n\n[bold cyan]── Proficiencies ──[/bold cyan]\n' + '\n'.join(prof_lines) if prof_lines else '')
        + (f'\n\n[bold cyan]── Spell Slots ──[/bold cyan]\n' +
           '  '.join(f'[cyan]Level {lvl}:[/cyan] {cnt}' for lvl, cnt in sorted(spell_slots.items()))
           if spell_slots else '')
        + (f'\n\n[bold cyan]── Rumors Heard ──[/bold cyan]\n' +
           '\n'.join(
               f'  [{"green" if r["true"] else "dim"}]{"[TRUE]" if r["true"] else "[FALSE]"}[/{"green" if r["true"] else "dim"}] {r["text"]}'
               for r in rumors
           ) if rumors else '')
        + (f'\n\n[bold cyan]── Auto-Applied ──[/bold cyan]\n{auto_summary}' if auto_summary else ''),
        title=f'[bold green]Your {system_name} Character[/bold green]',
        border_style='green'
    ))

    if inventory:
        console.print(Panel(
            '\n'.join(f'  [cyan]•[/cyan] {item}' for item in inventory),
            title='[bold green]🎒 Starting Inventory[/bold green]',
            border_style='green',
            padding=(0, 2),
        ))

    confirm = console.input('\n[bold white]Begin your adventure with this character? (y/n): [/bold white]').strip().lower()
    if confirm != 'y':
        console.print('[yellow]Starting over...[/yellow]')
        return create_character_interactively(system)

    # ── Display character sheet ───────────────────────────────────────────
    console.print()
    character_sheet_generator.print_sheet_to_console(character, console)
    console.print(
        '\n[dim]Type [bold]sheet[/bold] at any time during play to view this again.[/dim]'
    )

    return character

def load_or_create_character(system: dict) -> dict:
    """
    Loads the player character for the active system from disk.
    If no character file exists for this system, launches the character creator.

    Each system stores its character in its own subfolder so characters
    never mix across systems:
      data/dnd_5e/player_character.json
      data/call_of_cthulhu/player_character.json
      data/cyberpunk_red/player_character.json

    Parameters:
      system — The active game system dict from systems.py

    Returns the complete player character dict.
    """
    char_file = config.CHARACTER_FILE  # Updated by set_active_system()

    if os.path.exists(char_file):
        with open(char_file, 'r', encoding='utf-8') as f:
            existing = json.load(f)

        char_name  = existing.get("name", "Unknown")
        char_race  = existing.get("race", "")
        char_class = existing.get("class", existing.get("occupation", ""))
        char_level = existing.get("level", 1)

        console.print()
        console.print(Panel(
            f'[bold white]Existing character found for {system["short_name"]}:[/bold white]\n\n'
            f'  [bold cyan]{char_name}[/bold cyan]\n'
            f'  [dim]{char_race} {char_class}'
            + (f' · Level {char_level}' if char_level > 1 else '') + '[/dim]\n\n'
            '[white]Would you like to continue with this character, or create a new one?[/white]\n'
            '  [dim]1[/dim]  Continue with [bold]{char_name}[/bold]\n'
            '  [dim]2[/dim]  Create a new character (overwrites the existing one)',
            border_style='cyan', padding=(0, 2),
        ).renderables if False else Panel(
            f'[bold white]Existing character found for {system["short_name"]}:[/bold white]\n\n'
            f'  [bold cyan]{char_name}[/bold cyan]\n'
            f'  [dim]{char_race} {char_class}'
            + (f'  ·  Level {char_level}' if char_level > 1 else '') + '[/dim]\n\n'
            '[white]Continue with this character or create a new one?[/white]',
            border_style='cyan', padding=(0, 2),
        ))
        console.print('  [dim]1[/dim]  Continue with [bold]' + char_name + '[/bold]')
        console.print('  [dim]2[/dim]  Create a new character [dim](overwrites existing)[/dim]')
        console.print()

        while True:
            choice = console.input('[bold white]  Choose (1 or 2): [/bold white]').strip()
            if choice == '1' or not choice:
                console.print(f'[green]Continuing as {char_name}.[/green]')
                return existing
            elif choice == '2':
                console.print('[yellow]Starting new character creation...[/yellow]')
                break
            else:
                console.print('[red]Please enter 1 or 2.[/red]')

    else:
        # No character for this system at all
        console.print(f'[yellow]No {system["short_name"]} character found. Let\'s create one![/yellow]')

    character = create_character_interactively(system)

    # Save to the system-specific path
    os.makedirs(os.path.dirname(char_file), exist_ok=True)
    with open(char_file, 'w', encoding='utf-8') as f:
        json.dump(character, f, indent=2, ensure_ascii=False)

    console.print(f'\n[green]Character saved.[/green]')
    console.print(f'[dim]File: {char_file}[/dim]')
    return character


def save_character(character: dict):
    """Saves the current character state to disk."""
    with open(config.CHARACTER_FILE, 'w', encoding='utf-8') as f:
        json.dump(character, f, indent=2, ensure_ascii=False)



# ── Genre Presets ─────────────────────────────────────────────────────────────
# Each genre modifies how the GM narrates and what it emphasizes.
# These are system-agnostic — any genre can be applied to any system.
# The 'tone' string is appended directly to the system's dm_persona.
# The 'image_style' string overrides the system's default image style.

GENRE_PRESETS = {
    # ── Tone-based genres ─────────────────────────────────────────────────
    'high_adventure': {
        'label':       'High Adventure',
        'description': 'Heroic, epic, action-packed. The stakes are always world-changing.',
        'tone': (
            "TONE — HIGH ADVENTURE:\n"
            "Narrate with energy and momentum. Set-pieces should feel cinematic and large-scale. "
            "Heroes are capable and bold. Victories feel earned and glorious. "
            "Describe action vividly — motion, impact, consequence. "
            "Keep the pace brisk. Embrace dramatic speeches, rallying moments, and decisive action."
        ),
        'image_style': 'epic fantasy, dynamic action, dramatic lighting, heroic composition, vibrant colors, 8k',
    },
    'dark_gritty': {
        'label':       'Dark & Gritty',
        'description': 'Brutal, realistic, morally grey. No one is safe. Every choice costs something.',
        'tone': (
            "TONE — DARK AND GRITTY:\n"
            "Narrate with weight and consequence. Violence has real cost — injury lingers, "
            "death is final. NPCs have selfish motivations. Moral choices are genuinely hard "
            "with no clean answers. The world is cruel and indifferent. "
            "Describe suffering, exhaustion, and moral compromise honestly. "
            "Hope exists but must be fought for. Avoid heroic clichés."
        ),
        'image_style': 'dark fantasy, gritty realism, desaturated, harsh shadows, grim atmosphere, detailed, cinematic',
    },
    'horror': {
        'label':       'Horror',
        'description': 'Dread, tension, and creeping fear. Something is very wrong.',
        'tone': (
            "TONE — HORROR:\n"
            "Build dread through atmosphere, not just monsters. Use sensory details — "
            "wrong smells, unnatural sounds, things that should not be. "
            "NPCs behave strangely. The environment feels hostile and aware. "
            "Pace slowly, let tension accumulate before releasing it. "
            "Make the players feel watched, vulnerable, and uncertain. "
            "Not everything has a rational explanation. Some things cannot be fought."
        ),
        'image_style': 'horror atmosphere, dark, unsettling, deep shadows, fog, gothic, creepy, detailed, cinematic',
    },
    'mystery': {
        'label':       'Mystery & Intrigue',
        'description': 'Clues, secrets, and hidden agendas. Truth must be uncovered piece by piece.',
        'tone': (
            "TONE — MYSTERY AND INTRIGUE:\n"
            "Every NPC has secrets and hidden motivations. Information is revealed gradually. "
            "Clues exist but must be found through active investigation — never handed freely. "
            "Red herrings and misdirection are fair. Trust no one completely. "
            "Political relationships and personal histories matter. "
            "Reward careful observation and logical deduction. "
            "Keep the player guessing but ensure the mystery is solvable."
        ),
        'image_style': 'noir atmosphere, dramatic shadows, detailed environments, mysterious, cinematic, muted tones',
    },
    'comedy': {
        'label':       'Comedy & Lighthearted',
        'description': 'Whimsical, funny, and irreverent. The world is absurd and invites laughing at it.',
        'tone': (
            "TONE — COMEDY AND LIGHTHEARTED:\n"
            "Embrace absurdity, wordplay, and comic timing. NPCs can be bumbling, pompous, "
            "or endearingly strange. Consequences exist but are rarely permanent. "
            "Set up comic situations and let them play out. "
            "Describe failures humorously rather than tragically. "
            "Subvert expectations for comedic effect. "
            "Keep energy playful — this is a world that doesn't take itself too seriously."
        ),
        'image_style': 'whimsical illustration, bright colors, cartoon style, expressive characters, playful, detailed',
    },
    'romance': {
        'label':       'Romance & Drama',
        'description': 'Character relationships and emotional arcs take center stage.',
        'tone': (
            "TONE — ROMANCE AND DRAMA:\n"
            "Focus on interpersonal dynamics, emotional tension, and character growth. "
            "NPCs have deep, layered personalities and genuine feelings for the player character. "
            "Relationships evolve through interactions — give them room to breathe. "
            "Describe body language, subtext, and unspoken feelings. "
            "Dramatic moments of vulnerability, confession, and connection are the high points. "
            "Conflict is personal and emotional as much as physical."
        ),
        'image_style': 'painterly, warm lighting, expressive faces, romantic atmosphere, detailed, soft focus, digital art',
    },
    'political': {
        'label':       'Political Intrigue',
        'description': 'Factions, power plays, and shifting alliances. Everyone wants something.',
        'tone': (
            "TONE — POLITICAL INTRIGUE:\n"
            "Every faction has goals, resources, and leverage. NPCs represent interests, "
            "not just personalities. Information is currency — who knows what matters enormously. "
            "Alliances shift when interests change. Betrayal is always possible. "
            "Describe court dynamics, factional tensions, and the weight of political decisions. "
            "Violence is a last resort — words and positioning are the primary weapons. "
            "The player's reputation and relationships directly affect what's possible."
        ),
        'image_style': 'cinematic, elegant interiors, rich costumes, dramatic lighting, detailed, painterly, political',
    },
    'survival': {
        'label':       'Survival & Exploration',
        'description': 'Resources are scarce, the environment is hostile, and every decision matters.',
        'tone': (
            "TONE — SURVIVAL AND EXPLORATION:\n"
            "Track resources — food, water, ammunition, fuel. The environment is a constant threat. "
            "Describe weather, terrain, and physical exhaustion honestly. "
            "Rest and recovery matter. Injuries accumulate. "
            "Discovery of new places and things should feel genuinely wondrous and dangerous. "
            "NPCs in the wilderness are rare and their motives worth questioning. "
            "Prepare players to make hard choices about risk vs reward."
        ),
        'image_style': 'wilderness photography, dramatic landscapes, survival, cinematic, detailed, atmospheric',
    },
    'war': {
        'label':       'War & Military',
        'description': 'Large-scale conflict, military strategy, and the cost of battle.',
        'tone': (
            "TONE — WAR AND MILITARY:\n"
            "Combat is part of something larger — sieges, campaigns, and strategic objectives. "
            "Describe the scale of conflict: troop movements, terrain, command decisions. "
            "Soldiers are human — show camaraderie, fear, and sacrifice. "
            "Victory has a price. Enemy soldiers are people too, not just obstacles. "
            "Military hierarchy and chain of command create tension and drama. "
            "The fog of war means information is incomplete and plans go wrong."
        ),
        'image_style': 'military realism, dramatic battlefield, smoke and fire, cinematic, detailed, epic scale',
    },
    'custom': {
        'label':       'Custom (type your own)',
        'description': 'Describe exactly what tone and atmosphere you want.',
        'tone':        '',  # Filled in by user input
        'image_style': '',  # Filled in by user input
    },
}


def select_genre(system: dict) -> dict:
    """
    Displays genre presets and returns a genre dict containing the
    tone instructions and image style override for this session.

    Called immediately after select_game_system() in run_session().

    HOW GENRE AFFECTS THE GAME:
      The chosen genre's 'tone' string is appended to the system's dm_persona
      in config.ACTIVE_SYSTEM. Since context_builder reads dm_persona fresh
      each turn, the new tone instructions apply to every DM response
      for the rest of the session without any further changes.

      The genre's 'image_style' overrides config.ACTIVE_IMAGE_STYLE so all
      generated images reflect the visual mood of the chosen genre.

    Parameters:
      system — The selected game system dict (used for display context only)

    Returns the selected genre dict from GENRE_PRESETS.
    """
    import copy

    console.print()
    console.print(Panel(
        f'[bold cyan]Choose Your Genre[/bold cyan]\n'
        f'[dim]Playing: {system["name"]} — {system["genre"]}[/dim]\n\n'
        '[white]Genre shapes the tone, atmosphere, and narrative focus of your campaign.\n'
        'The GM will adjust how it narrates, what it emphasizes, and how scenes are described.[/white]',
        border_style='cyan'
    ))

    presets = list(GENRE_PRESETS.values())

    table = Table(border_style='cyan', show_header=True, padding=(0, 1))
    table.add_column('[dim]#[/dim]', width=3)
    table.add_column('[bold]Genre[/bold]', style='bold cyan', width=24)
    table.add_column('[bold]Description[/bold]', style='white')

    for i, genre in enumerate(presets, 1):
        table.add_row(str(i), genre['label'], genre['description'])

    console.print(table)
    console.print()

    while True:
        raw = console.input('[bold white]Choose genre (number): [/bold white]').strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(presets):
                chosen = copy.deepcopy(presets[idx])

                # Handle custom genre — ask player to describe their own tone
                if chosen['label'] == 'Custom (type your own)':
                    console.print()
                    console.print('[bold cyan]Describe your tone and atmosphere:[/bold cyan]')
                    console.print('[dim]Example: "Whimsical steampunk with dark undertones"[/dim]')
                    console.print('[dim]Example: "Slow-burn political thriller with occasional comedy"[/dim]')
                    tone_desc = console.input('  Tone: ').strip()

                    console.print('\n[bold cyan]Any specific GM instructions?[/bold cyan]')
                    console.print('[dim]Example: "Always describe weather", "NPCs speak in riddles"[/dim]')
                    extra = console.input('  Instructions (optional): ').strip()

                    console.print('\n[bold cyan]Image style keywords (optional):[/bold cyan]')
                    console.print('[dim]Example: "steampunk, brass gears, fog, warm tones"[/dim]')
                    img_style = console.input('  Image style: ').strip()

                    chosen['label']       = tone_desc[:40]
                    chosen['description'] = tone_desc
                    chosen['tone'] = (
                        f"TONE — {tone_desc.upper()}:\n"
                        f"{tone_desc}."
                        + (f"\n{extra}" if extra else "")
                    )
                    chosen['image_style'] = img_style

                # ── Apply genre to config ──────────────────────────────────
                # Append tone instructions to the system's dm_persona
                if chosen['tone']:
                    config.ACTIVE_SYSTEM = dict(config.ACTIVE_SYSTEM)
                    config.ACTIVE_SYSTEM['dm_persona'] = (
                        config.ACTIVE_SYSTEM.get('dm_persona', '') +
                        '\n\n' + chosen['tone']
                    )

                # Override image style if the genre specifies one
                if chosen.get('image_style'):
                    config.ACTIVE_IMAGE_STYLE = chosen['image_style']

                # Store genre label in config so status command can show it
                config.ACTIVE_GENRE = chosen['label']

                console.print(
                    f'\n[green]Genre selected:[/green] [bold cyan]{chosen["label"]}[/bold cyan]\n'
                    f'[dim]{chosen["description"]}[/dim]'
                )
                return chosen

        console.print('[red]Please enter a valid number.[/red]')


def select_game_system() -> dict:
    """
    Displays the game system selection menu and returns the chosen system dict.

    Called at the very start of every session BEFORE character loading.
    The selected system determines:
      - Which folder characters and saves are stored in
      - What the DM persona and rules are
      - What character sheet fields appear during creation
      - What the default image style is

    Returns the full system dict from systems.py.
    """
    all_systems = sys_defs.list_systems()

    console.print()
    console.print(Panel(
        '[bold cyan]⚔  Tabletop AI Game Master  ⚔[/bold cyan]\n'
        '[dim]Powered by Ollama + Stable Diffusion[/dim]\n\n'
        '[white]Select your game system to begin.[/white]',
        border_style='cyan'
    ))

    table = Table(border_style='cyan', show_header=True, padding=(0, 1))
    table.add_column('[dim]#[/dim]',      width=3)
    table.add_column('[bold]System[/bold]', style='bold cyan', width=22)
    table.add_column('[bold]Genre[/bold]',  style='green',      width=22)
    table.add_column('[bold]Description[/bold]', style='white')

    for i, sys in enumerate(all_systems, 1):
        table.add_row(
            str(i),
            sys['short_name'],
            sys['genre'],
            sys['description'][:70] + ('...' if len(sys['description']) > 70 else '')
        )

    console.print(table)
    console.print()

    while True:
        raw = console.input('[bold white]Choose system (number): [/bold white]').strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(all_systems):
                chosen = all_systems[idx]

                # Handle custom system — ask the player to describe their world
                if chosen['id'] == 'custom':
                    chosen = _configure_custom_system(chosen)

                # Apply to config so all modules use this system's paths and rules
                config.set_active_system(chosen)

                console.print(
                    f'\n[green]System selected:[/green] '
                    f'[bold cyan]{chosen["name"]}[/bold cyan] '
                    f'[dim]({chosen["genre"]})[/dim]'
                )
                return chosen

        console.print('[red]Please enter a valid number.[/red]')


def _configure_custom_system(base_system: dict) -> dict:
    """
    When the player picks the Custom system, prompts them to describe
    their world setting, tone, and any special rules.
    This description is injected into the DM persona so the AI knows
    how to behave in their custom world.

    Returns a modified copy of the custom system dict with the player's
    world description woven into the dm_persona field.
    """
    import copy
    system = copy.deepcopy(base_system)

    console.print()
    console.print(Panel(
        '[bold cyan]Custom System Setup[/bold cyan]\n'
        '[dim]Tell the AI Game Master about your world and rules.[/dim]',
        border_style='cyan'
    ))

    console.print('\n[bold cyan]World Setting[/bold cyan]')
    console.print('[dim]Describe the genre, time period, and overall tone.')
    console.print('[dim]Examples: "Gritty post-apocalyptic western", "Victorian steampunk mystery",[/dim]')
    console.print('[dim]"Underwater civilization", "A world where magic was just discovered"[/dim]')
    setting = console.input('  Setting: ').strip() or 'A unique fantasy world'

    console.print('\n[bold cyan]Core Rules Summary[/bold cyan]')
    console.print('[dim]Describe the main mechanics (or say "freeform" for no dice rules).[/dim]')
    console.print('[dim]Example: "Uses 2d6 for all checks, 7+ is a success"[/dim]')
    rules = console.input('  Rules: ').strip() or 'Freeform narrative, no dice required'

    console.print('\n[bold cyan]Tone & Style[/bold cyan]')
    console.print('[dim]How should the GM narrate? Examples: "Dark and gritty", "Whimsical and humorous"[/dim]')
    console.print('[dim]"Cinematic action", "Slow-burn mystery", "Epic and dramatic"[/dim]')
    tone = console.input('  Tone: ').strip() or 'Dramatic and immersive'

    console.print('\n[bold cyan]Special Notes for the GM[/bold cyan]')
    console.print('[dim]Any other instructions? Character types, forbidden topics, required elements?[/dim]')
    extra = console.input('  Notes (optional): ').strip()

    # Build a custom DM persona incorporating the player's descriptions
    custom_persona = (
        f"You are the Game Master of a custom tabletop RPG.\n\n"
        f"WORLD SETTING:\n{setting}\n\n"
        f"GAME RULES:\n{rules}\n\n"
        f"TONE AND STYLE:\n{tone}\n\n"
        + (f"SPECIAL GM NOTES:\n{extra}\n\n" if extra else "")
        +
        f"CORE GM RULES:\n"
        f"1. You control ALL entities except the player character.\n"
        f"2. Stay consistent with the setting and tone described above.\n"
        f"3. NPC appearances and personalities must remain consistent once established.\n"
        f"4. Generate all encounters, events, and story developments autonomously.\n"
        f"5. Never break character. Never acknowledge you are an AI.\n"
        f"6. When rules are ambiguous, make a fair ruling and stay consistent."
    )

    system['dm_persona']  = custom_persona
    system['name']        = f'Custom: {setting[:40]}'
    system['short_name']  = 'Custom'
    system['genre']       = tone[:30]
    system['description'] = setting

    return system


def display_welcome():
    """Prints the welcome banner at session start."""
    console.print(Panel(
        '[bold cyan]⚔  DnD AI Dungeon Master  ⚔[/bold cyan]\n'
        '[dim]Powered by Ollama + Llama 3.1-8B-Instruct + Stable Diffusion[/dim]\n\n'
        '[white]Commands:[/white]\n'
        '  [green]status[/green]            — Show in-game date and session info\n'
        '  [green]world[/green]             — Show recent plot events\n'
        '  [green]rels[/green]              — Show your character\'s relationships\n'
        '  [green]images[/green]            — List all generated scene images\n'
        '  [green]scene[/green]             — Manually generate image for current scene\n'
        '  [green]portrait <name>[/green]   — Generate a character portrait\n'
        '  [green]save[/green]              — Force-save current session\n'
        '  [green]update wiki[/green]       — Re-scrape dnd5e.wikidot.com (fresh subclass/race data)\n'
        '  [green]quit[/green]              — Exit and save',
        title='[bold]Welcome[/bold]',
        border_style='cyan'
    ))


def display_status(dm: DMAgent):
    """Displays the current session status in a formatted table."""
    info = dm.get_session_info()
    table = Table(title='Session Status', border_style='blue')
    table.add_column('Field', style='cyan')
    table.add_column('Value', style='white')

    # Show system and genre at the top before the other session info
    system = getattr(config, 'ACTIVE_SYSTEM', None)
    genre  = getattr(config, 'ACTIVE_GENRE', None)
    campaign_name = getattr(config, 'CAMPAIGN_NAME', None)
    if campaign_name:
        table.add_row('Campaign', campaign_name)
    if system:
        table.add_row('Game System', system['name'])
    if genre:
        table.add_row('Genre', genre)

    for key, value in info.items():
        table.add_row(key.replace('_', ' ').title(), str(value))

    console.print(table)


def display_plot_events(dm: DMAgent):
    """Displays the most recent plot events from the world database."""
    events = dm.world.get_recent_plot_events(n=8)
    if not events:
        console.print('[dim]No plot events recorded yet.[/dim]')
        return

    console.print('\n[bold cyan]Recent Story Events:[/bold cyan]')
    for event in events:
        date = event.get('in_game_date', '?')
        event_type = event.get('type', 'event')
        desc = event.get('description', '')[:150]
        console.print(f'  [dim][{date}][/dim] [yellow]({event_type})[/yellow] {desc}')


def display_relationships(dm: DMAgent):
    """Displays the player's current relationships."""
    player_id = dm.player_character.get('id', 'player_character')
    summary = dm.graph.summarize_for_prompt(player_id)
    console.print('\n[bold cyan]Your Relationships:[/bold cyan]')
    console.print(summary or '[dim]No relationships established yet.[/dim]')


def select_or_create_session(dm_stub_conv) -> str | None:
    """
    Shows the player a list of existing sessions and lets them choose to
    resume one or start fresh. Returns a session_id to resume, or None for new.
    """
    sessions = dm_stub_conv.list_sessions()

    if not sessions:
        return None  # No sessions exist yet — start fresh

    console.print(f'\n[cyan]Found {len(sessions)} existing session(s).[/cyan]')
    console.print('  [green]1[/green] — Resume most recent session')
    console.print('  [green]2[/green] — Start a new session')

    choice = console.input('[yellow]Choice (1 or 2): [/yellow]').strip()
    if choice == '1':
        return sorted(sessions)[-1]  # Most recent session
    return None  # New session



def _strip_world_secrets(world_lore: str) -> str:
    """
    Removes WORLD SECRET sections (and any GM-only content) from the world lore
    before displaying it to the player.

    The full lore — secrets included — is always saved to campaign_preferences.json
    and injected into the DM's system prompt every turn so the AI knows the truth.
    The player only ever sees the public-facing sections.

    The regex stops at the next blank line so it never eats content that follows
    the secret section.
    """
    import re

    pattern = re.compile(
        r'\n*(WORLD\s+SECRET|GM[\s\-]+ONLY|HIDDEN\s+TRUTH|SECRET\s+TRUTH|THE\s+REAL\s+REASON)'
        r'[^\n]*\n'            # rest of header line
        r'(?:(?!\n\n)[\s\S])*' # body up to the next blank line
        r'\n*',                # trailing newlines
        re.IGNORECASE | re.MULTILINE
    )
    return pattern.sub('\n', world_lore).strip()


def campaign_setup(system: dict, genre: dict, is_new_session: bool) -> dict:
    """
    Interactive campaign setup wizard. Runs once at the start of a NEW session
    to gather world notes, GM preferences, content boundaries, and opening scene
    instructions. Returns a dict of preferences that gets saved to disk and
    injected into the system prompt every turn.

    Skipped entirely when RESUMING an existing session — preferences from
    the original setup are loaded from the campaign preferences file instead.

    WHY THIS IS A SEPARATE STEP FROM GENRE:
      Genre sets the broad narrative tone (horror, comedy, etc.).
      Campaign setup is for specifics: your world's name, what the GM should
      avoid, how long responses should be, what the opening scene looks like.
      These are more personal and session-specific than genre selection.

    Parameters:
      system         — Active system dict (used for display context)
      genre          — Active genre dict (used for display context)
      is_new_session — True if starting fresh, False if resuming

    Returns a preferences dict. Keys used downstream:
      'world_name'       → shown in DM prompts and status
      'world_notes'      → injected into system prompt as world background
      'gm_instructions'  → injected as hard rules for the GM to follow
      'content_limits'   → topics/content the GM must avoid
      'response_style'   → how long/detailed DM responses should be
      'opening_scene'    → where and how the story begins (new sessions only)
      'house_rules'      → any custom mechanical rules
    """
    prefs_file = os.path.join(config.WORLD_DIR, 'campaign_preferences.json')

    # ── Resuming session: load saved preferences ───────────────────────────
    if not is_new_session:
        if os.path.exists(prefs_file):
            with open(prefs_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            console.print(
                f'\n[green]Campaign preferences loaded:[/green] '
                f'[bold]{saved.get("world_name", "Unnamed World")}[/bold]'
            )
            return saved
        else:
            # Resuming but no preferences file — skip setup gracefully
            return {}

    # ── New session: run the full wizard ──────────────────────────────────
    console.print()
    console.print(Panel(
        f'[bold cyan]Campaign Setup[/bold cyan]\n'
        f'[dim]{system["short_name"]} · {genre["label"]}[/dim]\n\n'
        '[white]Set up your campaign before the adventure begins.[/white]\n'
        '[dim]Every answer is optional — press Enter to skip any field.\n'
        'These preferences are saved and reloaded each session.[/dim]',
        border_style='cyan'
    ))

    prefs = {}

    # ── World / Campaign Name ──────────────────────────────────────────────
    console.print('\n[bold white]── World & Campaign ────────────────────────────[/bold white]')

    console.print('\n[bold cyan]Campaign / World Name[/bold cyan]')
    console.print('[dim]Give your campaign a name. Used in session info and save files.[/dim]')
    console.print('[dim]Example: "The Shattered Reaches", "Night City Blues", "The Whitmore Case"[/dim]')
    world_name = console.input('  Name (or Enter to skip): ').strip()
    prefs['world_name'] = world_name or f'{system["short_name"]} Campaign'

    console.print('\n[bold cyan]World Concept[/bold cyan]')
    console.print('[dim]Give the GM a seed concept — one sentence is enough.[/dim]')
    console.print('[dim]Example: "A dying empire where magic is fading and gods have gone silent."[/dim]')
    console.print('[dim]         "A megacity run by warring corporations after society collapsed."[/dim]')
    console.print('[dim]         "A continent still scarred 200 years after a catastrophic war."[/dim]')
    world_seed = console.input('  World concept (or Enter for GM to decide entirely): ').strip()
    prefs['world_seed'] = world_seed

    console.print('\n[bold cyan]Recurring Themes[/bold cyan]')
    console.print('[dim]What themes should run through this campaign?[/dim]')
    console.print('[dim]Example: "Redemption, found family, the cost of power"[/dim]')
    console.print('[dim]         "Corporate greed, survival, identity"[/dim]')
    console.print('[dim]         "Loss, grief, what we leave behind"[/dim]')
    themes = console.input('  Themes (or Enter to skip): ').strip()
    prefs['themes'] = themes

    # ── AI generates the world ─────────────────────────────────────────
    # This runs before character creation so the world exists before
    # the player builds a character. world_lore is saved into prefs and
    # injected into every DM system prompt for the rest of the campaign.
    # After generation the player is offered a world summary and custom races.
    world_lore = world_builder.generate_world(
        console       = console,
        system        = system,
        genre         = genre,
        world_seed    = world_seed,
        themes        = themes,
        campaign_name = prefs['world_name'],
    )
    prefs['world_notes'] = world_lore

    # Show the generated world to the player — secrets stripped out.
    # The full world_lore (including WORLD SECRET) is saved to prefs and used
    # by the DM AI every turn, but the player only sees the public-facing content.
    if world_lore:
        console.print()
        console.print(Panel(
            _strip_world_secrets(world_lore),
            title=f'[bold cyan]🌍  {prefs["world_name"]}[/bold cyan]',
            subtitle='[dim]Your campaign world — generated by the GM[/dim]',
            border_style='cyan',
            padding=(1, 2),
        ))

    # Offer a character-creation-focused world summary
    world_builder.offer_world_summary_for_character(
        console    = console,
        world_lore = world_lore,
        system     = system,
        genre      = genre,
    )

    # Offer AI-generated custom races for the world
    generated_races = world_builder.offer_custom_races(
        console    = console,
        world_lore = world_lore,
        system     = system,
        genre      = genre,
    )
    prefs['generated_races'] = generated_races

    # Offer a world map
    map_output_dir = os.path.join(config.WORLD_DIR if hasattr(config, 'WORLD_DIR') else 'data')
    world_map_path = world_builder.offer_world_map(
        console       = console,
        world_lore    = world_lore,
        system        = system,
        genre         = genre,
        campaign_name = prefs.get('world_name', 'campaign'),
        output_dir    = map_output_dir,
    )
    if world_map_path:
        prefs['world_map_path'] = world_map_path

    # ── GM Style Preferences ───────────────────────────────────────────────
    console.print('\n[bold white]── GM Style ────────────────────────────────────[/bold white]')

    console.print('\n[bold cyan]Response Length[/bold cyan]')
    console.print('  [dim]1.[/dim] Brief      — Short punchy responses, fast pace')
    console.print('  [dim]2.[/dim] Balanced   — Mix of short and detailed (recommended)')
    console.print('  [dim]3.[/dim] Descriptive — Rich, detailed prose, slower pace')
    console.print('  [dim]4.[/dim] Novelistic — Full scene-setting paragraphs, literary style')
    length_choice = console.input('  Choose (1-4, or Enter for Balanced): ').strip()
    length_map = {
        '1': 'Brief — keep responses short and punchy, 2-3 sentences max per scene.',
        '2': 'Balanced — mix short action beats with occasional descriptive paragraphs.',
        '3': 'Descriptive — write rich, detailed prose. Take time to set the scene fully.',
        '4': 'Novelistic — write in a full literary style with immersive scene-setting, '
             'character interiority, and detailed description. Treat each response like a page of a novel.',
    }
    prefs['response_style'] = length_map.get(length_choice, length_map['2'])

    console.print('\n[bold cyan]NPC Depth[/bold cyan]')
    console.print('[dim]How much personality and backstory should NPCs have?[/dim]')
    console.print('  [dim]1.[/dim] Functional  — NPCs serve plot purposes, minimal backstory')
    console.print('  [dim]2.[/dim] Rounded     — NPCs have clear personalities and motivations (recommended)')
    console.print('  [dim]3.[/dim] Deep        — Every NPC has secrets, history, and complex feelings')
    npc_choice = console.input('  Choose (1-3, or Enter for Rounded): ').strip()
    npc_map = {
        '1': 'NPCs are functional — they serve their role in the plot with clear purpose but minimal backstory.',
        '2': 'NPCs are rounded characters with distinct personalities, clear motivations, and their own goals.',
        '3': 'Every NPC has hidden depths — personal history, secrets, complex feelings, and motivations that '
             'extend beyond their immediate role. Reveal these gradually through interaction.',
    }
    prefs['npc_depth'] = npc_map.get(npc_choice, npc_map['2'])

    console.print('\n[bold cyan]Pacing[/bold cyan]')
    console.print('[dim]How should time and events be handled?[/dim]')
    console.print('  [dim]1.[/dim] Action-driven  — Events happen fast, always something going on')
    console.print('  [dim]2.[/dim] Natural         — Mix of quiet moments and dramatic events (recommended)')
    console.print('  [dim]3.[/dim] Slow-burn       — Build up slowly, let tension accumulate over many turns')
    pacing_choice = console.input('  Choose (1-3, or Enter for Natural): ').strip()
    pacing_map = {
        '1': 'Keep the pace fast. Always have something happening or about to happen. Minimize downtime.',
        '2': 'Use natural pacing — quiet character moments between dramatic events. Let the story breathe.',
        '3': 'Use slow-burn pacing. Build tension gradually across many turns. Reward patience.',
    }
    prefs['pacing'] = pacing_map.get(pacing_choice, pacing_map['2'])

    console.print('\n[bold cyan]Additional GM Instructions[/bold cyan]')
    console.print('[dim]Any specific things the GM should always do or remember.[/dim]')
    console.print('[dim]Example: "Always describe the weather at the start of a new scene."[/dim]')
    console.print('[dim]         "NPCs should use period-appropriate language."[/dim]')
    console.print('[dim]         "Remind me when I forget to describe what my hands are doing."[/dim]')
    gm_instructions = console.input('  Instructions (or Enter to skip): ').strip()
    prefs['gm_instructions'] = gm_instructions

    # ── Content & Comfort ──────────────────────────────────────────────────
    console.print('\n[bold white]── Content & Comfort ───────────────────────────[/bold white]')
    console.print('[dim]Set limits on content so the GM never goes somewhere you are not comfortable with.[/dim]')

    console.print('\n[bold cyan]Topics to Avoid[/bold cyan]')
    console.print('[dim]The GM will not include these themes, events, or content types.[/dim]')
    console.print('[dim]Example: "No child harm, no sexual content, no real-world politics"[/dim]')
    console.print('[dim]         "No animal cruelty, keep gore minimal"[/dim]')
    console.print('[dim]         "No religious themes, avoid body horror"[/dim]')
    content_limits = console.input('  Avoid (or Enter to skip): ').strip()
    prefs['content_limits'] = content_limits

    console.print('\n[bold cyan]Violence Level[/bold cyan]')
    console.print('  [dim]1.[/dim] Minimal    — Conflict happens, details kept vague')
    console.print('  [dim]2.[/dim] Moderate   — Clear stakes and consequences, not gratuitous (recommended)')
    console.print('  [dim]3.[/dim] Gritty     — Realistic injury and consequence, unflinching')
    violence_choice = console.input('  Choose (1-3, or Enter for Moderate): ').strip()
    violence_map = {
        '1': 'Keep violence minimal. Conflict outcomes are described without graphic detail.',
        '2': 'Moderate violence — clear stakes and real consequences without being gratuitous.',
        '3': 'Gritty, realistic violence with unflinching consequence. Injuries are serious and lasting.',
    }
    prefs['violence_level'] = violence_map.get(violence_choice, violence_map['2'])

    # ── Opening Scene ──────────────────────────────────────────────────────
    console.print('\n[bold white]── Opening Scene ───────────────────────────────[/bold white]')
    console.print('[dim]Where does your story begin? The GM will open the campaign here.[/dim]')

    console.print('\n[bold cyan]Starting Location[/bold cyan]')
    console.print('[dim]Where is your character when the story begins?[/dim]')
    console.print('[dim]Example: "A grimy tavern on the edge of town during a storm"[/dim]')
    console.print('[dim]         "The lobby of MegaCorp headquarters, about to be fired"[/dim]')
    console.print('[dim]         "A remote lighthouse where strange lights appeared last night"[/dim]')
    starting_location = console.input('  Location (or Enter for GM to decide): ').strip()
    prefs['starting_location'] = starting_location

    console.print('\n[bold cyan]Opening Situation[/bold cyan]')
    console.print('[dim]What is happening when the story begins? What is the immediate situation?[/dim]')
    console.print('[dim]Example: "A mysterious stranger has just sat down at my table"[/dim]')
    console.print('[dim]         "I have just received a job offer I cannot refuse"[/dim]')
    console.print('[dim]         "Something has gone wrong with the experiment"[/dim]')
    opening_situation = console.input('  Opening situation (or Enter for GM to decide): ').strip()
    prefs['opening_situation'] = opening_situation

    console.print('\n[bold cyan]Campaign Hook[/bold cyan]')
    console.print('[dim]The central mystery, goal, or driving question of this campaign.[/dim]')
    console.print('[dim]Example: "Who destroyed the village and why?"[/dim]')
    console.print('[dim]         "Can I make enough money to get my crew off this rock?"[/dim]')
    console.print('[dim]         "What is the Whitmore family hiding in that estate?"[/dim]')
    campaign_hook = console.input('  Campaign hook (or Enter for GM to decide): ').strip()
    prefs['campaign_hook'] = campaign_hook

    # ── House Rules ────────────────────────────────────────────────────────
    console.print('\n[bold white]── House Rules ─────────────────────────────────[/bold white]')
    console.print('[dim]Any custom mechanical rules to apply on top of the system rules.[/dim]')
    console.print('[dim]Example: "Crits always deal maximum damage"[/dim]')
    console.print('[dim]         "Potions are a bonus action to use"[/dim]')
    console.print('[dim]         "Failing a social roll by 5+ makes the NPC hostile"[/dim]')
    house_rules = console.input('  House rules (or Enter to skip): ').strip()
    prefs['house_rules'] = house_rules

    # ── Show summary and confirm ───────────────────────────────────────────
    filled = {k: v for k, v in prefs.items() if v}
    summary_lines = []
    labels = {
        'world_name': 'Campaign',    'world_notes': 'World Notes',
        'themes': 'Themes',          'response_style': 'Response Style',
        'npc_depth': 'NPC Depth',    'pacing': 'Pacing',
        'gm_instructions': 'GM Notes', 'content_limits': 'Avoid',
        'violence_level': 'Violence', 'starting_location': 'Starts At',
        'opening_situation': 'Opening', 'campaign_hook': 'Hook',
        'house_rules': 'House Rules',
    }
    for key, val in filled.items():
        label = labels.get(key, key)
        short = val[:70] + '...' if len(val) > 70 else val
        summary_lines.append(f'[cyan]{label}:[/cyan] {short}')

    console.print()
    console.print(Panel(
        '\n'.join(summary_lines) or '[dim]No preferences set — GM has full creative freedom.[/dim]',
        title='[bold green]Campaign Preferences[/bold green]',
        border_style='green'
    ))

    confirm = console.input('\n[bold white]Start with these settings? (y/n): [/bold white]').strip().lower()
    if confirm == 'n':
        console.print('[yellow]Starting setup over...[/yellow]')
        return campaign_setup(system, genre, is_new_session)

    # ── Save to disk ───────────────────────────────────────────────────────
    # Save the genre so it can be loaded when the session is resumed
    prefs['genre'] = genre
    
    os.makedirs(config.WORLD_DIR, exist_ok=True)
    with open(prefs_file, 'w', encoding='utf-8') as f:
        json.dump(prefs, f, indent=2, ensure_ascii=False)

    console.print('[green]Campaign preferences saved.[/green]')
    return prefs


def _build_campaign_prefs_context(prefs: dict) -> str:
    """
    Converts the campaign preferences dict into a formatted block that gets
    appended to the system prompt every turn by context_builder.py.

    NOTE: This block is used in TWO ways:
      1. Injected into the DM AI's system prompt every turn — needs full lore
         INCLUDING world secrets so the AI can plot around them.
      2. Passed as 'world_lore' to display_world_info_for_character_creation
         which shows it to the player — secrets must be stripped here.

    We store the FULL lore in CAMPAIGN_PREFS_BLOCK for the DM AI.
    Stripping for player display is handled at the point of display.
    """
    if not prefs:
        return ''

    lines = ['=' * 60, 'CAMPAIGN PREFERENCES & GM INSTRUCTIONS', '=' * 60]

    if prefs.get('world_name'):
        lines.append(f'Campaign Name: {prefs["world_name"]}')

    if prefs.get('world_notes'):
        lines += ['', '--- WORLD BACKGROUND ---', prefs['world_notes']]

    if prefs.get('themes'):
        lines += ['', f'Recurring Themes: {prefs["themes"]}']

    if prefs.get('campaign_hook'):
        lines += ['', f'Central Campaign Hook: {prefs["campaign_hook"]}']

    if prefs.get('response_style'):
        lines += ['', f'Response Style: {prefs["response_style"]}']

    if prefs.get('npc_depth'):
        lines += ['', f'NPC Depth: {prefs["npc_depth"]}']

    if prefs.get('pacing'):
        lines += ['', f'Pacing: {prefs["pacing"]}']

    if prefs.get('violence_level'):
        lines += ['', f'Violence Level: {prefs["violence_level"]}']

    if prefs.get('content_limits'):
        lines += ['', f'CONTENT TO AVOID (mandatory): {prefs["content_limits"]}']

    if prefs.get('gm_instructions'):
        lines += ['', f'Additional GM Instructions: {prefs["gm_instructions"]}']

    if prefs.get('house_rules'):
        lines += ['', f'House Rules (apply these mechanically): {prefs["house_rules"]}']

    if prefs.get('starting_location'):
        lines += ['', f'Campaign Starting Location: {prefs["starting_location"]}']

    if prefs.get('opening_situation'):
        lines += ['', f'Opening Situation: {prefs["opening_situation"]}']

    return '\n'.join(lines)



def generate_world_intro(
    dm: 'DMAgent',
    system: dict,
    genre: dict,
    prefs: dict
) -> None:
    """
    Calls Ollama to generate a rich world introduction and displays it before
    the first player turn. Only runs for NEW sessions, never for resumed ones.

    WHY THIS IS SEPARATE FROM THE FIRST PLAYER TURN:
      Normally the AI only responds when the player does something. That means
      session one would open on a blank prompt with no context — the player
      would have to type blindly into an undefined world. This function fires
      automatically to give the player a "book opening" paragraph: the world,
      its history, the current moment, and where their character stands.

    WHAT IT GENERATES:
      A 3-5 paragraph narrative that covers:
        1. The world at large — what kind of place this is
        2. A key piece of recent history shaping the present moment
        3. The current state of the world right now
        4. Where the player character finds themselves and why
        5. A hook — something is about to happen

      The tone, length, and content all follow the genre, system, and
      campaign preferences that were just set up.

    HOW IT WORKS:
      We build a special one-shot prompt (not part of the conversation history)
      that asks the AI to write an opening narration. The response is displayed
      in a styled panel and then saved as the first assistant message in the
      conversation so future turns have context for it.

    Parameters:
      dm     — The initialized DMAgent (used to call Ollama and save to history)
      system — Active system dict
      genre  — Active genre dict
      prefs  — Campaign preferences from campaign_setup()
    """
    import ollama
    import config as _cfg

    campaign_name   = prefs.get('world_name', system['short_name'])
    world_notes     = prefs.get('world_notes', '')
    themes          = prefs.get('themes', '')
    hook            = prefs.get('campaign_hook', '')
    start_location  = prefs.get('starting_location', '')
    open_situation  = prefs.get('opening_situation', '')
    response_style  = prefs.get('response_style', 'Balanced')
    char            = dm.player_character
    char_name       = char.get('name', 'the player')
    char_race       = char.get('race', char.get('nationality', ''))
    char_class      = char.get('class', char.get('role', char.get('occupation', '')))
    char_appearance = char.get('appearance', '')
    char_backstory  = char.get('backstory', '')

    # Build the intro generation prompt
    intro_prompt = (
        f"You are opening a {system['short_name']} campaign called \"{campaign_name}\" "
        f"in the {genre['label']} genre.\n\n"
        f"Write an immersive opening narration for this campaign. "
        f"This is the very first thing the player reads — their entry into this world.\n\n"
        f"THE PLAYER CHARACTER:\n"
        f"  Name: {char_name}\n"
        f"  Identity: {char_race} {char_class}\n"
        + (f"  Appearance: {char_appearance}\n" if char_appearance else "")
        + (f"  Backstory: {char_backstory}\n" if char_backstory else "")
        + "\n"
        + (f"WORLD BACKGROUND:\n{world_notes}\n\n" if world_notes else "")
        + (f"CAMPAIGN THEMES:\n{themes}\n\n" if themes else "")
        + (f"CAMPAIGN HOOK:\n{hook}\n\n" if hook else "")
        + (f"STARTING LOCATION:\n{start_location}\n\n" if start_location else "")
        + (f"OPENING SITUATION:\n{open_situation}\n\n" if open_situation else "")
        +
        f"RESPONSE STYLE: {response_style}\n\n"
        f"INSTRUCTIONS FOR THIS OPENING:\n"
        f"1. Write 3-5 paragraphs of rich narrative prose — no dialogue yet, no player choices.\n"
        f"2. First paragraph: establish the world — what kind of place this is, its feel and history.\n"
        f"3. Middle paragraphs: the current state of things — what has recently changed, "
        f"   what tension is building, what forces are at work.\n"
        f"4. Final paragraph: place {char_name} specifically — where they are right now, "
        f"   what they can see/hear/smell, and a hook that makes the player want to act.\n"
        f"5. Match the {genre['label']} tone exactly throughout.\n"
        f"6. Do NOT ask the player what they do. End on atmosphere, not a question.\n"
        f"7. Write in second person (you are, you see, you hear).\n"
        f"8. Do not use headers or bullet points — pure narrative prose only."
    )

    with console.status(
        '[italic dim]The GM is setting the scene...[/italic dim]',
        spinner='dots'
    ):
        try:
            response = ollama.chat(
                model=_cfg.MODEL_NAME,
                messages=[{'role': 'user', 'content': intro_prompt}],
                options={
                    'num_ctx':     _cfg.CONTEXT_WINDOW,
                    'temperature': 0.85,   # Slightly higher for creative writing
                    'num_predict': 800,    # Long enough for 4-5 good paragraphs
                    'top_p':       _cfg.TOP_P,
                }
            )
            intro_text = response['message']['content'].strip()
        except Exception as e:
            console.print(f'[yellow]Could not generate world intro: {e}[/yellow]')
            return

    # Display in a styled opening panel
    console.print()
    console.print(Panel(
        Text(intro_text, style='white'),
        title=f'[bold cyan]{campaign_name}[/bold cyan]',
        subtitle=f'[dim]{system["short_name"]} · {genre["label"]}[/dim]',
        border_style='cyan',
        padding=(1, 2)
    ))
    console.print()

    # Save as the first assistant message in the conversation history.
    # This means future DM responses will have the opening intro as context
    # and will maintain continuity with the world that was just established.
    dm.conv.add(role='assistant', content=intro_text)

    # Also log the opening as a plot event so it appears in 'world' command
    dm.world.log_plot_event(
        event_description=f'Campaign opening: {intro_text[:300]}',
        event_type='campaign_opening',
        involved_entities=[char.get('id', 'player_character')]
    )


def run_session(
    force_system: dict = None,
    force_session: str = None,
    force_new: bool = False,
) -> None:
    """
    The main game loop. Runs until the player types 'quit'.

    Parameters (all optional — set by main_menu / _continue_game):
      force_system  — Skip system selection and use this system dict directly.
      force_session — Skip the new/resume prompt and resume this session ID.
      force_new     — Skip the new/resume prompt and always start a new session.

    Flow:
      1. Select game system (skipped if force_system)
      2. Determine new vs. resumed session (skipped if force_session/force_new)
      3. Select or load genre (new → select, resumed → load from preferences)
      4. Campaign setup — world generation, world display, race generation
      5. Load or create character
      6. Initialize DM agent
      7. World intro (new sessions only)
      8. Main game loop
    """

    # ── Step 1: Select game system ─────────────────────────────────────────
    if force_system:
        active_system = force_system
    else:
        active_system = select_game_system()

    # ── Step 2: Determine session (new or resume) ──────────────────────────
    # MUST run before genre selection so we know if we're loading or creating
    if force_session:
        session_id    = force_session
        is_new_session = False
    elif force_new:
        session_id    = None
        is_new_session = True
    else:
        from memory.conversation_store import ConversationStore
        temp_conv = ConversationStore.__new__(ConversationStore)
        temp_conv.session_id = 'temp'
        temp_conv.session_file = ''
        temp_conv.messages = []
        session_id = select_or_create_session(temp_conv)
        is_new_session = session_id is None

    # ── Step 3: Load or select genre ───────────────────────────────────────
    # For NEW sessions: ask player to choose genre
    # For RESUMED sessions: load genre from campaign preferences file
    if is_new_session:
        active_genre = select_genre(active_system)
    else:
        # Try to load saved genre from preferences
        prefs_file = os.path.join(config.WORLD_DIR, 'campaign_preferences.json')
        if os.path.exists(prefs_file):
            try:
                with open(prefs_file, 'r', encoding='utf-8') as f:
                    saved_prefs = json.load(f)
                    if 'genre' in saved_prefs and isinstance(saved_prefs['genre'], dict):
                        active_genre = saved_prefs['genre']
                        console.print(f"\n[green]✓ Genre loaded:[/green] {active_genre['label']}")
                    else:
                        # No genre in saved prefs — shouldn't happen, but fall back
                        console.print("[yellow]⚠ No saved genre found. Please select one:[/yellow]")
                        active_genre = select_genre(active_system)
            except (json.JSONDecodeError, IOError):
                # Corrupted file — ask player to choose
                console.print("[yellow]⚠ Could not read saved preferences. Please select a genre:[/yellow]")
                active_genre = select_genre(active_system)
        else:
            # Resuming but no preferences file — shouldn't happen, ask to choose
            console.print("[yellow]⚠ No campaign preferences found. Please select a genre:[/yellow]")
            active_genre = select_genre(active_system)

    # ── Step 4: Campaign setup — world + races FIRST ───────────────────────
    # CRITICAL ORDER: campaign_setup must run before load_or_create_character.
    #
    # For NEW sessions this runs the full wizard:
    #   - Asks for world name, seed, themes
    #   - AI generates the full world lore and DISPLAYS it to the player
    #   - Offers AI-generated races native to the world (player sees world first)
    #   - Asks GM style, content limits, opening scene, house rules
    #
    # For RESUMED sessions this silently loads saved preferences from disk.
    #
    # Either way, the results are stored in config BEFORE character creation
    # so that create_character_interactively() has access to:
    #   config.CAMPAIGN_PREFS_BLOCK  — world lore shown during char creation
    #   config.GENERATED_RACES       — world-native races shown in race picker
    campaign_prefs = campaign_setup(active_system, active_genre, is_new_session)

    # Store world data in config so character creation can read it
    config.CAMPAIGN_PREFS_BLOCK = _build_campaign_prefs_context(campaign_prefs)
    config.CAMPAIGN_NAME        = campaign_prefs.get('world_name', active_system['short_name'])
    config.GENERATED_RACES      = campaign_prefs.get('generated_races', [])
    config.CUSTOM_RACE_DATA     = None   # filled during character creation if a world race is chosen
    
    # Load saved image style preference if it exists
    if 'image_style' in campaign_prefs:
        config.ACTIVE_IMAGE_STYLE = campaign_prefs['image_style']
        style_name = campaign_prefs.get('image_style_name', 'Custom')
        console.print(f'[green]✓ Image style loaded:[/green] {style_name}')
    else:
        # First time — image style is default from genre/config
        config.ACTIVE_IMAGE_STYLE = getattr(config, 'ACTIVE_IMAGE_STYLE', config.SD_STYLE)

    # ── Step 5: Load or create character ──────────────────────────────────
    # NOW character creation runs — with the world and races already in config.
    # The wizard will:
    #   - Show the player the world lore (filtered, no secrets)
    #   - Show generated world races at the top of the race picker
    #   - Display full stat blocks for every race and class before confirming
    #   - Walk through background, skills, and equipment with proper menus
    character = load_or_create_character(active_system)

    # Show who the player is using
    role = character.get('class', character.get('role', character.get('occupation', '')))
    race = character.get('race', character.get('nationality', ''))
    console.print(
        f'\n[green]Playing as:[/green] '
        f'[bold]{character["name"]}[/bold] '
        f'[dim]— {race} {role}'
        + (f' (Level {character["level"]})' if character.get('level') else '')
        + '[/dim]'
    )

    # Store character name in config so ConversationStore can use it in the session ID
    config.ACTIVE_CHARACTER_NAME = character.get('name', '')

    # ── Step 6: Initialize the DM agent ───────────────────────────────────
    console.print('\n[dim]Initializing world engine...[/dim]')
    dm = DMAgent(player_character=character, session_id=session_id)

    # Show what system and genre are running
    console.print(
        f'[dim]System: {active_system["name"]}  |  '
        f'Genre: {active_genre["label"]}  |  '
        f'World time: {dm.world.get_current_date_str()}[/dim]'
    )

    if session_id:
        console.print(f'[green]Resumed session:[/green] {session_id}')
    else:
        console.print(f'[green]New {active_system["short_name"]} campaign started.[/green]')

    campaign_name = getattr(config, 'CAMPAIGN_NAME', active_system['short_name'])
    console.print('\n[dim]─────────────────────────────────────────────[/dim]')
    console.print(f'[dim]{campaign_name} · {active_genre["label"]} {active_system["short_name"]}[/dim]')
    console.print('[dim]─────────────────────────────────────────────[/dim]\n')

    # ── Step 7a: Session recap (resumed sessions only) ────────────────────
    # Shows a "Previously on…" AI-generated recap when the player resumes
    # an existing campaign. Skipped entirely for new sessions.
    if not is_new_session:
        from agent.session_recap import show_session_recap
        show_session_recap(dm, console)

    # ── Step 7: World intro (new sessions only) ────────────────────────────
    # Generates an opening narration from the AI that establishes the world,
    # its history, and where the player's character currently stands.
    # Skipped when resuming — the existing conversation history already has context.
    if is_new_session:
        generate_world_intro(dm, active_system, active_genre, campaign_prefs)
        console.print('[dim]The world awaits. Type your first action.[/dim]')
        console.print(
            '[dim]Commands: status · world · rels · map · citymap [town] · azgaar · sheet · savechar · '
            'newchar · chars · images · scene · portrait <name> · save · quit[/dim]\n'
        )

    # Tracks which map URLs have already been opened this session to avoid
    # opening duplicate browser tabs when the same command is repeated.
    _opened_map_urls: set = set()

    # ── Main Game Loop ─────────────────────────────────────────────────────
    # Define available commands for easy reference
    AVAILABLE_COMMANDS = (
        '[dim]Commands:[/dim]\n'
        '[cyan]Actions:[/cyan] [white]status[/white] · [white]recap[/white] · [white]world[/white] · [white]rels[/white] · '
        '[white]save[/white] · [white]quit[/white]\n'
        '[cyan]Maps:[/cyan] [white]map[/white] · [white]citymap [town][/white] · [white]azgaar[/white]\n'
        '[cyan]Character:[/cyan] [white]sheet[/white] · [white]portrait [name][/white] · '
        '[white]newchar[/white] · [white]chars[/white]\n'
        '[cyan]Scene:[/cyan] [white]scene[/white] · [white]images[/white] · [white]imagestyle[/white]\n'
    )
    
    while True:
        try:
            # Display commands and prompt for input
            console.print(AVAILABLE_COMMANDS)
            player_input = console.input('[bold white]You → [/bold white]').strip()
        except (KeyboardInterrupt, EOFError):
            # Handle Ctrl+C or end of input gracefully
            console.print('\n[yellow]Session interrupted.[/yellow]')
            break

        # Skip empty input

        if not player_input:
            continue

        # ── Built-in Commands ──────────────────────────────────────────────
        lower_input = player_input.lower()

        if lower_input == 'quit':
            console.print('\n[yellow]Saving and exiting...[/yellow]')
            break

        elif lower_input in ('update wiki', 'wiki update', 'refresh wiki'):
            console.print()
            console.print(Panel(
                '[bold cyan]Updating wiki data from dnd5e.wikidot.com...[/bold cyan]\n'
                '[dim]This re-scrapes all races, classes, and subclasses.\n'
                'Takes about 2-3 minutes. Game continues when done.[/dim]',
                border_style='cyan'
            ))
            try:
                wiki_scraper.force_refresh()
                info = wiki_scraper.cache_info()
                console.print(Panel(
                    f'[green]✓ Wiki data refreshed![/green]\n'
                    f'[dim]{info.get("races",0)} races · '
                    f'{info.get("classes",0)} classes · '
                    f'{info.get("subclasses",0)} subclasses[/dim]',
                    border_style='green'
                ))
            except Exception as wiki_err:
                console.print(f'[red]Update failed: {wiki_err}[/red]')
                console.print('[dim]Check your internet connection and try again.[/dim]')
            continue

        elif lower_input == 'status':
            display_status(dm)
            continue

        elif lower_input == 'recap':
            from agent.session_recap import generate_recap_on_demand
            generate_recap_on_demand(dm, console)
            continue

        elif lower_input == 'world':
            display_plot_events(dm)
            continue

        elif lower_input == 'rels':
            display_relationships(dm)
            continue

        elif lower_input in ('map', 'world map'):
            # (Re)generate the world map from the saved world lore.
            # Useful mid-campaign to see an updated map after discoveries.
            campaign_prefs = getattr(config, 'CAMPAIGN_PREFS', {})
            world_lore_text = campaign_prefs.get('world_notes', '')
            if not world_lore_text:
                console.print('[yellow]No world lore found. Run a new campaign to generate the world first.[/yellow]')
            else:
                map_path = world_builder.generate_world_map(
                    console       = console,
                    world_lore    = world_lore_text,
                    system        = active_system,
                    genre         = active_genre,
                    campaign_name = getattr(config, 'CAMPAIGN_NAME', 'campaign'),
                    output_dir    = getattr(config, 'WORLD_DIR', 'data'),
                )
                if map_path:
                    console.print(Panel(
                        f'[bold green]✓ World map saved:[/bold green]\n[cyan]{map_path}[/cyan]',
                        border_style='green', padding=(0, 2),
                    ))
                else:
                    console.print('[yellow]Map generation failed.[/yellow]')
            continue

        elif lower_input.startswith('citymap') or lower_input.startswith('city map'):
            # Open a Watabou city/town map in the browser, seeded from the location name.
            # Usage:  citymap             -> uses current location from world state
            #         citymap Ironhaven   -> generates a map for "Ironhaven"
            # Caches opened URLs this session so the same location won't open a new tab twice.
            import webbrowser, hashlib
            raw_loc = player_input[len('citymap'):].strip() if lower_input.startswith('citymap') \
                      else player_input[len('city map'):].strip()
            if not raw_loc:
                raw_loc = getattr(dm.world, 'current_location', '') or 'town'
            seed = int(hashlib.md5(raw_loc.lower().encode()).hexdigest(), 16) % 1000000
            watabou_url = (
                f'https://watabou.github.io/city-generator/'
                f'?size=5&seed={seed}&name={raw_loc.replace(" ", "+")}'
                f'&random=0&pop=0&citadel=0&greens=1&river=0&coast=0&rotate=0'
            )
            cache_key = f'citymap:{raw_loc.lower()}'
            already_open = cache_key in _opened_map_urls
            if not already_open:
                # Open in configured browser (or system default if BROWSER_CHOICE is 'default')
                if config.BROWSER_CHOICE == 'default':
                    webbrowser.open(watabou_url)
                else:
                    try:
                        webbrowser.get(config.BROWSER_CHOICE).open(watabou_url)
                    except Exception:
                        # Fallback to default if browser not found
                        webbrowser.open(watabou_url)
                _opened_map_urls.add(cache_key)
            status = '[dim](already open in browser)[/dim]' if already_open else '[white]Opening Watabou City Generator in your browser.[/white]'
            console.print(Panel(
                f'[bold cyan]City Map \u2014 {raw_loc}[/bold cyan]\n\n'
                + status + '\n'
                + f'[dim]Seed {seed} \u2014 same name always produces the same map.[/dim]\n\n'
                + f'[dim]Tip: In Watabou press E then choose PNG to save the map.[/dim]\n'
                + f'[dim cyan]{watabou_url}[/dim cyan]',
                border_style='cyan', padding=(0, 2),
            ))
            continue

        elif lower_input in ('azgaar', 'worldmap', 'world map azgaar', 'azgaar map'):
            # Open Azgaar Fantasy Map Generator in the browser, seeded from the campaign name.
            # Caches opened URLs this session so the same campaign won't open a new tab twice.
            import webbrowser, hashlib
            campaign_name = getattr(config, 'CAMPAIGN_NAME', 'campaign')
            seed = int(hashlib.md5(campaign_name.lower().encode()).hexdigest(), 16) % 1000000000
            azgaar_url = f'https://azgaar.github.io/Fantasy-Map-Generator/?seed={seed}'
            cache_key = f'azgaar:{campaign_name.lower()}'
            already_open = cache_key in _opened_map_urls
            if not already_open:
                # Open in configured browser (or system default if BROWSER_CHOICE is 'default')
                if config.BROWSER_CHOICE == 'default':
                    webbrowser.open(azgaar_url)
                else:
                    try:
                        webbrowser.get(config.BROWSER_CHOICE).open(azgaar_url)
                    except Exception:
                        # Fallback to default if browser not found
                        webbrowser.open(azgaar_url)
                _opened_map_urls.add(cache_key)
            status = '[dim](already open in browser)[/dim]' if already_open else "[white]Opening Azgaar's Fantasy Map Generator in your browser.[/white]"
            console.print(Panel(
                f'[bold cyan]World Map \u2014 {campaign_name}[/bold cyan]\n\n'
                + status + '\n'
                + f'[dim]Seed {seed} \u2014 this campaign always generates the same world.[/dim]\n\n'
                + f'[dim]Tip: Use Style -> Color Scheme to change look. Export -> PNG to save.[/dim]\n'
                + f'[dim cyan]{azgaar_url}[/dim cyan]',
                border_style='cyan', padding=(0, 2),
            ))
            continue

        elif lower_input in ('sheet', 'char', 'character sheet'):
            # Print the character sheet directly to the terminal.
            char = dm.player_character
            console.print()
            character_sheet_generator.print_sheet_to_console(char, console)
            continue

        elif lower_input == 'save':
            # Conversation is already auto-saved, but this reassures the player
            console.print('[green]Session saved.[/green]')
            continue

        elif lower_input == 'newchar':
            # Delete the current character file and run the creator again.
            # Warns the player first since this cannot be undone.
            # The world database (NPCs, locations, plot events) is NOT cleared —
            # only the player character sheet is replaced.
            console.print()
            console.print('[bold red]Warning:[/bold red] This will delete your current character sheet.')
            console.print('[dim]Your campaign world, NPCs, and story history will be kept.[/dim]')
            confirm = console.input('[bold white]Are you sure? Type YES to confirm: [/bold white]').strip()
            if confirm == 'YES':
                if os.path.exists(config.CHARACTER_FILE):
                    os.remove(config.CHARACTER_FILE)
                new_char = create_character_interactively(active_system)
                os.makedirs(os.path.dirname(config.CHARACTER_FILE), exist_ok=True)
                with open(config.CHARACTER_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_char, f, indent=2, ensure_ascii=False)
                dm.player_character = new_char
                dm.world.save_character(new_char)
                console.print('[green]New character created! Your adventure continues...[/green]')
            else:
                console.print('[dim]Cancelled.[/dim]')
            continue

        elif lower_input == 'imagestyle':
            # Display available image style presets and let the player switch.
            #
            # HOW IT WORKS:
            # config.IMAGE_STYLE_PRESETS is a dict of name -> style keyword string.
            # Choosing a preset updates config.ACTIVE_IMAGE_STYLE which is read
            # dynamically by image_generator.get_style_suffix() on every image call.
            # The change takes effect immediately on the next generated image.
            # NEW: Image style preference is now saved to campaign_preferences.json
            # so it persists between sessions!
            presets = config.IMAGE_STYLE_PRESETS
            current = getattr(config, 'ACTIVE_IMAGE_STYLE', config.SD_STYLE)

            console.print()
            console.print(Panel(
                '[bold cyan]Image Style Presets[/bold cyan]\n'
                '[dim]Choose a visual style for all generated images.\n'
                'Takes effect on the next image generation.[/dim]',
                border_style='cyan'
            ))

            # Display all presets as a numbered table
            table = Table(border_style='cyan', show_header=True)
            table.add_column('#', style='dim', width=3)
            table.add_column('Style Name', style='bold cyan', width=12)
            table.add_column('Description', style='white')
            table.add_column('Active', width=6)

            preset_names = list(presets.keys())
            for i, name in enumerate(preset_names, 1):
                keywords = presets[name]
                # Show first 60 chars of the keyword string as description
                desc = keywords[:65] + '...' if len(keywords) > 65 else keywords
                is_active = '✓' if keywords == current else ''
                table.add_row(str(i), name, desc, f'[green]{is_active}[/green]')

            console.print(table)

            choice = console.input('\n[bold white]Choose style number (or Enter to cancel): [/bold white]').strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(preset_names):
                    chosen_name = preset_names[idx]
                    config.ACTIVE_IMAGE_STYLE = presets[chosen_name]

                    # Reload LoRA for the new style if a trained one exists
                    try:
                        from agent.image_generator import reload_lora_for_style
                        reload_lora_for_style()
                    except Exception:
                        pass  # image_generator not loaded yet — will pick up on next image

                    # Save the image style preference to campaign preferences
                    prefs_file = os.path.join(config.WORLD_DIR, 'campaign_preferences.json')
                    if os.path.exists(prefs_file):
                        try:
                            with open(prefs_file, 'r', encoding='utf-8') as f:
                                prefs = json.load(f)
                            # Add the image style preference
                            prefs['image_style_name'] = chosen_name
                            prefs['image_style'] = presets[chosen_name]
                            # Save back to file
                            with open(prefs_file, 'w', encoding='utf-8') as f:
                                json.dump(prefs, f, indent=2, ensure_ascii=False)
                        except Exception as e:
                            console.print(f'[yellow]⚠ Could not save style preference: {e}[/yellow]')
                    
                    console.print(
                        f'\n[green]Image style changed to:[/green] [bold cyan]{chosen_name}[/bold cyan]\n'
                        f'[dim]{presets[chosen_name][:80]}...[/dim]\n'
                        f'[dim]This style is now saved and will persist across sessions![/dim]'
                    )
                else:
                    console.print('[yellow]Invalid selection.[/yellow]')
            else:
                console.print('[dim]Style unchanged.[/dim]')
            continue

        elif lower_input == 'chars':
            # List all characters currently saved in the world database.
            # Shows the player which NPCs the DM has introduced and saved,
            # plus the player character themselves.
            all_chars = dm.list_saved_characters()
            if not all_chars:
                console.print('[dim]No characters saved yet.[/dim]')
            else:
                table = Table(title=f'Known Characters ({len(all_chars)} total)', border_style='yellow')
                table.add_column('Name', style='bold white')
                table.add_column('Race', style='cyan')
                table.add_column('Role', style='green')
                table.add_column('Appearance', style='dim', max_width=40)
                for ch in all_chars:
                    table.add_row(
                        ch.get('name', 'Unknown'),
                        ch.get('race', '?'),
                        ch.get('occupation', ch.get('class', '?')),
                        ch.get('appearance', '')[:80]
                    )
                console.print(table)
                console.print('[dim]Use "portrait <name>" to generate any character portrait.[/dim]')
            continue

        elif lower_input == 'savechar':
            # Interactive command to update the player character sheet.
            # The player can update specific fields like HP, inventory, notes, level.
            # All other fields are preserved — only the updated fields change.
            #
            # HOW IT WORKS:
            #   We show the current values of key fields and ask for new input.
            #   Pressing Enter without typing anything skips that field (keeps current).
            #   At the end, changes are written to both the in-memory character dict
            #   and the player_character.json file on disk.
            console.print()
            console.print(Panel(
                '[bold white]Update Your Character Sheet[/bold white]\n'
                '[dim]Press Enter to keep the current value for any field.[/dim]',
                border_style='yellow'
            ))

            char = dm.player_character
            updates = {}

            # ── HP update ─────────────────────────────────────────────────
            current_hp = char.get('hit_points', {})
            current_max = current_hp.get('maximum', '?')
            current_cur = current_hp.get('current', '?')
            console.print(f'  [cyan]Current HP:[/cyan] {current_cur} / {current_max}')

            new_cur = console.input(f'  New current HP [{current_cur}]: ').strip()
            new_max = console.input(f'  New maximum HP [{current_max}]: ').strip()
            if new_cur or new_max:
                updates['hit_points'] = {
                    'current': int(new_cur) if new_cur else current_hp.get('current', 0),
                    'maximum': int(new_max) if new_max else current_hp.get('maximum', 0)
                }

            # ── Level update ───────────────────────────────────────────────
            current_level = char.get('level', 1)
            console.print(f'\n  [cyan]Current Level:[/cyan] {current_level}')
            new_level = console.input(f'  New level [{current_level}]: ').strip()
            if new_level and new_level.isdigit():
                new_level_int = int(new_level)
                updates['level'] = new_level_int

                # ── Level-up events ───────────────────────────────────────
                # Check if this level-up crosses any class milestones:
                #   1. Subclass unlock (first time reaching unlock threshold)
                #   2. New bonus/oath/domain spell grants
                #   3. New spell level access
                if new_level_int > current_level:
                    char_class_key  = char.get('class', '').split('(')[0].strip()
                    char_subclass   = char.get('subclass', '')
                    class_lower     = char_class_key.lower()

                    # Same table used at character creation
                    _SUBCLASS_LEVELS = {
                        'cleric': 1, 'sorcerer': 1, 'warlock': 1,
                        'druid': 2, 'fighter': 2,
                        'barbarian': 3, 'bard': 3, 'monk': 3, 'paladin': 3,
                        'ranger': 3, 'rogue': 3, 'wizard': 3, 'artificer': 3,
                    }
                    unlock_lvl = _SUBCLASS_LEVELS.get(class_lower, 3)

                    # ── Subclass unlock ───────────────────────────────────
                    # Prompt if they just hit the unlock threshold and don't
                    # have a subclass yet.
                    if (new_level_int >= unlock_lvl
                            and current_level < unlock_lvl
                            and not char_subclass):
                        console.print()
                        console.print(Panel(
                            f'[bold yellow]⚔  Subclass Unlocked![/bold yellow]\n\n'
                            f'[white]{char_class_key} reaches level {unlock_lvl} — '
                            f'time to choose a subclass.[/white]',
                            border_style='yellow', padding=(0, 2),
                        ))
                        picked_sub = _pick_subclass(char_class_key, system_id)
                        if picked_sub:
                            updates['subclass'] = picked_sub
                            char_subclass = picked_sub
                            console.print(
                                f'  [green]✓ Subclass set:[/green] [cyan]{picked_sub}[/cyan]'
                            )

                    # ── New bonus spells ──────────────────────────────────
                    # Show spells newly unlocked between old and new level.
                    # Uses spell_scraper if available; gracefully skips if not.
                    if char_subclass and system_id == 'dnd_5e':
                        try:
                            import spell_scraper as _ss
                            old_bonus = set(_ss.get_spells_for_subclass(
                                char_class_key, char_subclass, current_level
                            ).get('bonus_spells', []))
                            new_bonus = set(_ss.get_spells_for_subclass(
                                char_class_key, char_subclass, new_level_int
                            ).get('bonus_spells', []))
                            newly_granted = sorted(new_bonus - old_bonus)
                            if newly_granted:
                                console.print()
                                console.print(Panel(
                                    f'[bold cyan]✦  New {char_subclass} Spells '
                                    f'at Level {new_level_int}[/bold cyan]\n\n'
                                    '[white]These spells are now always prepared '
                                    '(no slot needed to prepare them):[/white]\n'
                                    + '\n'.join(
                                        f'  [cyan]•[/cyan] {sp}'
                                        for sp in newly_granted
                                    ),
                                    border_style='cyan', padding=(0, 2),
                                ))
                                # Merge into character's spell list
                                existing_spells = char.get('spells', [])
                                merged = list(existing_spells)
                                for sp in newly_granted:
                                    if sp not in merged:
                                        merged.append(sp)
                                if merged != existing_spells:
                                    updates['spells'] = merged
                        except Exception:
                            pass  # spell_scraper unavailable — skip silently

                    # ── New spell level access ────────────────────────────
                    # Inform the player if they can now cast a higher spell level.
                    if system_id == 'dnd_5e':
                        try:
                            import world_builder as _wb
                            import spell_feature_picker as _sfp
                            matched = _wb._match_spell_class(char_class_key, char_subclass)
                            if matched and matched in _wb.SPELL_SLOTS:
                                def _max_spell_lvl(lvl):
                                    slots_at = _wb.SPELL_SLOTS[matched]
                                    valid = [l for l in sorted(slots_at) if l <= lvl]
                                    if not valid:
                                        return 0
                                    return max(slots_at[valid[-1]].get('slots', {}).keys(), default=0)
                                old_max = _max_spell_lvl(current_level)
                                new_max = _max_spell_lvl(new_level_int)
                                if new_max > old_max:
                                    console.print(
                                        f'\n  [bold magenta]✨ New spell level unlocked:[/bold magenta] '
                                        f'[white]You can now cast '
                                        f'[bold]{new_max}{"st" if new_max==1 else "nd" if new_max==2 else "rd" if new_max==3 else "th"}'
                                        f'-level[/bold] spells![/white]'
                                    )
                        except Exception:
                            pass

            # ── Inventory update ───────────────────────────────────────────
            current_inv = char.get('inventory', [])
            console.print(f'\n  [cyan]Current Inventory:[/cyan]')
            for i, item in enumerate(current_inv, 1):
                console.print(f'    {i}. {item}')
            console.print('  [dim]Enter new inventory as comma-separated items,[/dim]')
            console.print('  [dim]or press Enter to keep current inventory.[/dim]')
            new_inv_str = console.input('  New inventory: ').strip()
            if new_inv_str:
                updates['inventory'] = [item.strip() for item in new_inv_str.split(',') if item.strip()]

            # ── Notes update ───────────────────────────────────────────────
            current_notes = char.get('notes', '')
            console.print(f'\n  [cyan]Current Notes:[/cyan] {current_notes}')
            new_notes = console.input(f'  New notes (or Enter to keep): ').strip()
            if new_notes:
                updates['notes'] = new_notes

            # ── Appearance update ──────────────────────────────────────────
            console.print(f'\n  [cyan]Current Appearance:[/cyan] {char.get("appearance", "")[:80]}...')
            new_appearance = console.input('  New appearance (or Enter to keep): ').strip()
            if new_appearance:
                updates['appearance'] = new_appearance

            # ── Apply and save ─────────────────────────────────────────────
            if updates:
                dm.update_player_character(updates)
                dm.save_player_character_to_file(config.CHARACTER_FILE)
                console.print()
                console.print(Panel(
                    f'[green]Character updated and saved![/green]\n'
                    f'[dim]Updated fields: {", ".join(updates.keys())}[/dim]',
                    border_style='green'
                ))
            else:
                console.print('\n[dim]No changes made.[/dim]')
            continue

        elif lower_input == 'images':
            # List all images generated in this campaign
            # Images are stored in data/images/ sorted by filename (= chronological order)
            import config as _cfg
            image_dir = _cfg.IMAGE_DIR
            if not os.path.exists(image_dir) or not os.listdir(image_dir):
                console.print('[dim]No images generated yet.[/dim]')
            else:
                imgs = sorted([f for f in os.listdir(image_dir) if f.endswith('.png')])
                console.print(f'\n[bold cyan]Generated Images ({len(imgs)} total):[/bold cyan]')
                for img in imgs[-10:]:  # Show last 10 to avoid flooding the terminal
                    console.print(f'  [cyan]{os.path.join(image_dir, img)}[/cyan]')
                if len(imgs) > 10:
                    console.print(f'  [dim]...and {len(imgs)-10} more in {image_dir}[/dim]')
            continue

        elif lower_input.startswith('portrait '):
            # Generate a portrait for a named character
            # Usage: portrait <character name>
            # Example: portrait Aldric Vane
            # Searches the world database for a character matching the name
            char_name = player_input[9:].strip()  # Everything after 'portrait '
            matches = dm.world.search_characters(char_name, n=1)
            if not matches:
                console.print(f'[yellow]No character found matching: {char_name}[/yellow]')
            else:
                char = matches[0]
                console.print(f'[dim]Generating portrait for {char.get("name")}...[/dim]')
                from agent.image_generator import generate_character_portrait
                portrait_path = generate_character_portrait(
                    character_data=char,
                    in_game_date=dm.world.get_current_date_str()
                )
                if portrait_path:
                    console.print(
                        f'[bold magenta]Portrait saved:[/bold magenta] '
                        f'[cyan]{portrait_path}[/cyan]'
                    )
                else:
                    console.print('[yellow]Portrait generation failed. Is Stable Diffusion running?[/yellow]')
            continue

        elif lower_input == 'scene':
            # Manually trigger a scene image for the current moment
            # Useful if image generation was skipped for this turn
            if dm.conv.messages:
                last_dm_response = next(
                    (m['content'] for m in reversed(dm.conv.messages) if m['role'] == 'assistant'),
                    None
                )
                if last_dm_response:
                    console.print('[dim]Generating scene image...[/dim]')
                    from agent.image_generator import generate_image, SD_ENABLED
                    if not SD_ENABLED:
                        console.print('[yellow]Image generation is disabled. Start Automatic1111 with --api flag.[/yellow]')
                    else:
                        path = generate_image(
                            dm_response=last_dm_response,
                            in_game_date=dm.world.get_current_date_str(),
                            turn_count=0  # 0 bypasses the every-N-turns throttle
                        )
                        if path:
                            console.print(f'[bold magenta]Scene image:[/bold magenta] [cyan]{path}[/cyan]')
                        else:
                            console.print('[yellow]Image generation failed. Is Stable Diffusion running?[/yellow]')
            continue

        # ── DM Turn ────────────────────────────────────────────────────────
        # Show a "thinking" spinner while the model generates a response
        with console.status('[italic dim]The DM is narrating...[/italic dim]', spinner='dots'):
            try:
                response = dm.respond(player_input)
            except Exception as e:
                # Catch errors from Ollama (model not running, OOM, etc.)
                console.print(f'[red]ERROR: {e}[/red]')
                console.print('[dim]Is Ollama running? Try: ollama serve[/dim]')
                continue

        # Display the DM's response in a styled panel
        console.print()
        console.print(Panel(
            Text(response, style='white'),
            title=f'[bold green]DM[/bold green] [dim]{dm.world.get_current_date_str()}[/dim]',
            border_style='green',
            padding=(1, 2)
        ))

        # ── Display image path if one was generated this turn ──────────────
        if dm.last_image_path:
            console.print(
                f'  [bold magenta]🎨 Scene image:[/bold magenta] '
                f'[cyan]{dm.last_image_path}[/cyan]'
            )

        # ── Display any NPCs auto-saved this turn ──────────────────────────
        # dm_agent._extract_and_save_npcs() fills npcs_saved_this_turn with
        # the names of any characters that were extracted and saved to WorldState.
        # We display them so the player knows the world database was updated.
        if dm.npcs_saved_this_turn:
            names = ', '.join(dm.npcs_saved_this_turn)
            console.print(
                f'  [bold yellow]📖 Characters saved:[/bold yellow] '
                f'[yellow]{names}[/yellow] '
                f'[dim](use "portrait <name>" to generate their image)[/dim]'
            )

        console.print()

    # ── Session End ────────────────────────────────────────────────────────
    console.print(Panel(
        f'[cyan]Campaign saved.[/cyan]\n'
        f'[dim]Campaign:   {getattr(config, "CAMPAIGN_NAME", active_system["short_name"])}[/dim]\n'
        f'[dim]System:     {active_system["name"]}[/dim]\n'
        f'[dim]Genre:      {active_genre["label"]}[/dim]\n'
        f'[dim]Character:  {character["name"]}[/dim]\n'
        f'[dim]Session ID: {dm.conv.session_id}[/dim]\n'
        f'[dim]World Time: {dm.world.get_current_date_str()}[/dim]\n'
        f'[dim]Turns:      {dm.turn_count}[/dim]',
        title='[bold]Until next time...[/bold]',
        border_style='cyan'
    ))


def _view_all_characters() -> None:
    """
    Scans every game system's character file and displays a summary of
    all characters the player has created, regardless of system.
    """
    import systems as _systems

    all_systems = _systems.list_systems()
    found = []

    for sys_dict in all_systems:
        sys_id  = sys_dict.get('id', '')
        if not sys_id:
            continue
        char_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'data', sys_id, 'player_character.json'
        )
        if os.path.exists(char_path):
            try:
                with open(char_path, 'r', encoding='utf-8') as f:
                    char = json.load(f)
                found.append((sys_dict, char))
            except Exception:
                pass

    console.print()
    if not found:
        console.print(Panel(
            '[white]No characters found yet.[/white]\n'
            '[dim]Start a New Game to create your first character.[/dim]',
            title='[bold cyan]All Characters[/bold cyan]',
            border_style='cyan',
            padding=(1, 2),
        ))
        console.input('\n[dim]Press Enter to return to the main menu → [/dim]')
        return

    console.print(Panel(
        f'[bold cyan]All Characters[/bold cyan]\n'
        f'[dim]{len(found)} character{"s" if len(found) != 1 else ""} found across all systems[/dim]',
        border_style='cyan',
    ))

    for sys_dict, char in found:
        name       = char.get('name', 'Unknown')
        race       = char.get('race', char.get('nationality', ''))
        cls        = char.get('class', char.get('role', char.get('occupation', '')))
        level      = char.get('level', '')
        subclass   = char.get('subclass', '')
        background = char.get('background', '')
        hp         = char.get('hp', char.get('hit_points', ''))
        backstory  = char.get('backstory', '')

        level_str = f'Level {level}' if level else ''
        sub_str   = f' ({subclass})' if subclass else ''
        identity  = f'{race} {cls}{sub_str} {level_str}'.strip()

        detail_lines = [f'[bold cyan]{name}[/bold cyan]  [dim]{identity}[/dim]']
        if background:
            detail_lines.append(f'[dim]Background:[/dim] {background}')
        if hp:
            detail_lines.append(f'[dim]HP:[/dim] {hp}')
        if backstory:
            preview = backstory[:160] + '...' if len(backstory) > 160 else backstory
            detail_lines.append(f'[dim]Backstory:[/dim] {preview}')

        console.print(Panel(
            '\n'.join(detail_lines),
            title=f'[dim]{sys_dict["name"]}[/dim]',
            border_style='dim cyan',
            padding=(0, 2),
        ))

    console.input('\n[dim]Press Enter to return to the main menu → [/dim]')


def _continue_game() -> None:
    """
    Lists all game systems that have an existing session and lets the
    player pick one to resume. Hands off to run_session() once chosen.
    """
    import systems as _systems
    from memory.conversation_store import ConversationStore

    all_systems = _systems.list_systems()
    sessions_by_system = []

    for sys_dict in all_systems:
        sys_id = sys_dict.get('id', '')
        if not sys_id:
            continue
        conv_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'data', sys_id, 'conversations'
        )
        if not os.path.exists(conv_dir):
            continue
        session_files = [
            f for f in os.listdir(conv_dir)
            if f.endswith('.json') and not f.startswith('_')
        ]
        if session_files:
            sessions_by_system.append((sys_dict, sorted(session_files)))

    console.print()
    if not sessions_by_system:
        console.print(Panel(
            '[white]No saved sessions found.[/white]\n'
            '[dim]Start a New Game to begin your first campaign.[/dim]',
            title='[bold cyan]Continue Game[/bold cyan]',
            border_style='cyan',
            padding=(1, 2),
        ))
        console.input('\n[dim]Press Enter to return to the main menu → [/dim]')
        return

    # Build a flat numbered list of all sessions
    options = []
    console.print(Panel(
        '[bold cyan]Continue Game[/bold cyan]\n[dim]Choose a session to resume[/dim]',
        border_style='cyan',
    ))

    for sys_dict, session_files in sessions_by_system:
        for sf in session_files:
            session_id = sf.replace('.json', '')
            options.append((sys_dict, session_id))
            idx = len(options)
            # Try to get character name for this system
            char_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'data', sys_dict['id'], 'player_character.json'
            )
            char_name = ''
            if os.path.exists(char_path):
                try:
                    with open(char_path) as f:
                        char_name = json.load(f).get('name', '')
                except Exception:
                    pass
            char_hint = f'  [dim]Playing as {char_name}[/dim]' if char_name else ''
            console.print(
                f'  [green]{idx}[/green]  [bold white]{session_id}[/bold white]'
                f'  [dim cyan]{sys_dict["short_name"]}[/dim cyan]{char_hint}'
            )

    console.print()
    while True:
        raw = console.input('[bold white]Choose session (number) or Enter to cancel: [/bold white]').strip()
        if not raw:
            return
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                chosen_system, chosen_session = options[idx]
                # Boot directly into that system + session
                import config as _cfg
                import systems as _sys
                _sys.ensure_system_dirs(chosen_system)
                _cfg.set_active_system(chosen_system)
                run_session(
                    force_system=chosen_system,
                    force_session=chosen_session,
                )
                return
        console.print(f'[red]Please enter a number between 1 and {len(options)}.[/red]')


def main_menu() -> None:
    """
    The top-level main menu shown when the program boots.
    Routes to: New Game, Continue Game, View Characters, or Quit.
    """
    console.print()
    console.print(Panel(
        '[bold cyan]⚔  AI Dungeon Master[/bold cyan]\n\n'
        '[white]An intelligent, adaptive tabletop RPG experience\n'
        'powered by a local AI Game Master.[/white]',
        border_style='cyan',
        padding=(1, 4),
    ))

    while True:
        console.print()
        console.print('[bold white]─────────────────────────────────[/bold white]')
        console.print('  [green]1[/green]  [bold white]New Game[/bold white]')
        console.print('      [dim]Create a new world, races, and character[/dim]')
        console.print('  [green]2[/green]  [bold white]Continue Game[/bold white]')
        console.print('      [dim]Resume a saved session[/dim]')
        console.print('  [green]3[/green]  [bold white]View Characters[/bold white]')
        console.print('      [dim]Browse all characters you have made[/dim]')
        console.print('  [green]4[/green]  [bold white]Quit[/bold white]')
        console.print('[bold white]─────────────────────────────────[/bold white]')
        console.print()

        choice = console.input('[bold white]  Choose (1-4): [/bold white]').strip()

        if choice == '1':
            run_session(force_new=True)
        elif choice == '2':
            _continue_game()
        elif choice == '3':
            _view_all_characters()
        elif choice == '4':
            console.print('\n[cyan]Farewell, adventurer.[/cyan]\n')
            break
        else:
            console.print('[red]Please enter 1, 2, 3, or 4.[/red]')


if __name__ == '__main__':
    main_menu()
