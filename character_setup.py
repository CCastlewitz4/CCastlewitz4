# character_setup.py
# ─────────────────────────────────────────────────────────────────────────────
# Extended character and campaign setup wizards.
#
# This module handles the four new creation steps that run BEFORE the main
# character sheet wizard in main.py:
#
#   1. WORLD BACKSTORY BUILDER  — Prompts the player to define the world's
#      lore, factions, history, and unique features before character creation.
#      Stored in campaign_preferences.json under 'world_lore'. The DM AI
#      uses this every turn to keep world details consistent.
#
#   2. CUSTOM RACE CREATOR — Lets the player define one or more homebrew
#      races with ASI, traits, speed, size, darkvision, languages, and
#      proficiencies. These are saved to data/homebrew/races.json and
#      injected into the race selection menu.
#
#   3. BACKGROUND PICKER — Scrapes dnd5e.wikidot.com/background (and uses
#      hardcoded equivalents for PF2e, CoC, Cyberpunk) to present a table
#      of official backgrounds with their skill proficiencies, tool
#      proficiencies, languages, and equipment. Player picks by number.
#      The chosen background is merged into the character sheet.
#
#   4. EQUIPMENT CHOOSER — Parses the 'OR'-separated equipment strings from
#      DND5E_CLASSES into interactive choice menus. E.g.
#      "Rapier OR shortsword" becomes a numbered prompt. Every OR-choice is
#      asked in sequence; the chosen items are returned as a flat list.
#
#   5. SKILL PROFICIENCY CHOOSER — Reads the class's skill_choices and
#      skill_count and presents an interactive numbered pick-list so the
#      player selects exactly the right number of skills.
#
# ENTRY POINTS (called from main.py):
#   run_world_backstory_builder(console, system_id) -> world_lore: str
#   run_custom_race_builder(console, system_id)     -> list[dict] of new races
#   pick_background(console, system_id, char_class) -> dict (background data)
#   pick_starting_equipment(console, class_data)    -> list[str] (chosen items)
#   pick_skill_proficiencies(console, class_data, already_proficient) -> list[str]
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import re

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


# ═══════════════════════════════════════════════════════════════════════════
# HARDCODED BACKGROUND DATA  (fallback if wiki scrape fails)
# ═══════════════════════════════════════════════════════════════════════════

DND5E_BACKGROUNDS = [
    {
        'name': 'Acolyte',
        'skill_proficiencies': ['Insight', 'Religion'],
        'tool_proficiencies': [],
        'languages': 2,
        'equipment': ["Holy symbol", "Prayer book or prayer wheel", "5 sticks of incense",
                      "Vestments", "Common clothes", "15 gp"],
        'feature': 'Shelter of the Faithful',
        'feature_desc': 'You and your companions can receive free healing and care at temples of your faith.',
        'desc': 'You have spent your life in the service of a temple to a specific god or pantheon.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Charlatan',
        'skill_proficiencies': ['Deception', 'Sleight of Hand'],
        'tool_proficiencies': ['Disguise Kit', "Forgery Kit"],
        'languages': 0,
        'equipment': ["Fine clothes", "Disguise kit", "Tools of the con (10 stoppered bottles, weighted dice, etc.)", "15 gp"],
        'feature': 'False Identity',
        'feature_desc': 'You have a second identity with documentation, established acquaintances, and disguises.',
        'desc': 'You have always had a way with people. You know what makes them tick.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Criminal',
        'skill_proficiencies': ['Deception', 'Stealth'],
        'tool_proficiencies': ["Thieves' Tools", 'One gaming set'],
        'languages': 0,
        'equipment': ["Crowbar", "Dark common clothes with hood", "15 gp"],
        'feature': 'Criminal Contact',
        'feature_desc': 'You have a reliable contact who acts as your liaison to a network of criminals.',
        'desc': 'You are an experienced criminal with a history of breaking the law.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Folk Hero',
        'skill_proficiencies': ['Animal Handling', 'Survival'],
        'tool_proficiencies': ["Artisan's Tools (one type)", 'Vehicles (land)'],
        'languages': 0,
        'equipment': ["Artisan's tools (one type)", "Shovel", "Iron pot", "Common clothes", "10 gp"],
        'feature': 'Rustic Hospitality',
        'feature_desc': 'Common folk will shelter and protect you. They will hide you from the law if needed.',
        'desc': 'You come from a humble social rank, but destiny marked you for greatness.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Guild Artisan',
        'skill_proficiencies': ['Insight', 'Persuasion'],
        'tool_proficiencies': ["Artisan's Tools (one type)"],
        'languages': 1,
        'equipment': ["Artisan's tools (one type)", "Letter of introduction from guild", "Traveler's clothes", "15 gp"],
        'feature': "Guild Membership",
        'feature_desc': 'Your guild provides support, lodging, and aid in legal matters.',
        'desc': 'You are a member of an artisan guild, skilled in a particular field and closely associated with a community of fellow artisans.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Hermit',
        'skill_proficiencies': ['Medicine', 'Religion'],
        'tool_proficiencies': ['Herbalism Kit'],
        'languages': 1,
        'equipment': ["Scroll case with notes", "Winter blanket", "Common clothes", "Herbalism kit", "5 gp"],
        'feature': 'Discovery',
        'feature_desc': 'Your solitude gave you access to a unique and powerful discovery.',
        'desc': 'You lived in seclusion — either in a sheltered community or entirely alone — for a formative part of your life.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Noble',
        'skill_proficiencies': ['History', 'Persuasion'],
        'tool_proficiencies': ['One gaming set'],
        'languages': 1,
        'equipment': ["Fine clothes", "Signet ring", "Scroll of pedigree", "Purse with 25 gp"],
        'feature': 'Position of Privilege',
        'feature_desc': 'People assume the best of you. You are welcome in high society and can secure audiences with nobles.',
        'desc': 'You understand wealth, power, and privilege.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Outlander',
        'skill_proficiencies': ['Athletics', 'Survival'],
        'tool_proficiencies': ['One musical instrument'],
        'languages': 1,
        'equipment': ["Staff", "Hunting trap", "Trophy from animal you killed", "Traveler's clothes", "10 gp"],
        'feature': 'Wanderer',
        'feature_desc': 'You have an excellent memory for maps and geography; can always recall the terrain and find food and water.',
        'desc': 'You grew up in the wilds, far from civilization and the comforts of town and technology.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Sage',
        'skill_proficiencies': ['Arcana', 'History'],
        'tool_proficiencies': [],
        'languages': 2,
        'equipment': ["Bottle of black ink", "Quill", "Small knife", "Letter with unanswered question", "Common clothes", "10 gp"],
        'feature': 'Researcher',
        'feature_desc': "If you don't know information, you know where to find it. You know which libraries, scholars, or sages to consult.",
        'desc': 'You spent years learning the lore of the multiverse.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Sailor',
        'skill_proficiencies': ['Athletics', 'Perception'],
        'tool_proficiencies': ["Navigator's Tools", 'Vehicles (water)'],
        'languages': 0,
        'equipment': ["Belaying pin (club)", "Silk rope (50 ft)", "Lucky charm", "Common clothes", "10 gp"],
        'feature': "Ship's Passage",
        'feature_desc': 'You can secure free passage on sailing ships for you and your party.',
        'desc': 'You sailed on a seagoing vessel for years.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Soldier',
        'skill_proficiencies': ['Athletics', 'Intimidation'],
        'tool_proficiencies': ['One gaming set', 'Vehicles (land)'],
        'languages': 0,
        'equipment': ["Insignia of rank", "Trophy from fallen enemy", "Bone dice or cards", "Common clothes", "10 gp"],
        'feature': 'Military Rank',
        'feature_desc': 'Soldiers loyal to your former military organization recognize your authority.',
        'desc': 'War has been your life for as long as you care to remember.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Urchin',
        'skill_proficiencies': ['Sleight of Hand', 'Stealth'],
        'tool_proficiencies': ['Disguise Kit', "Thieves' Tools"],
        'languages': 0,
        'equipment': ["Small knife", "Map of your home city", "Pet mouse", "Token from parents", "Common clothes", "10 gp"],
        'feature': 'City Secrets',
        'feature_desc': 'You know the secret patterns of cities. You can find passage through them twice as fast as normal.',
        'desc': 'You grew up on the streets alone, orphaned, and poor.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Entertainer',
        'skill_proficiencies': ['Acrobatics', 'Performance'],
        'tool_proficiencies': ['Disguise Kit', 'One musical instrument'],
        'languages': 0,
        'equipment': ["Musical instrument (one of your choice)", "Favor of admirer", "Costume", "15 gp"],
        'feature': "By Popular Demand",
        'feature_desc': 'You can always find a place to perform. You receive free lodging and food in exchange.',
        'desc': 'You thrive in front of an audience.',
        'source': "Player's Handbook",
    },
    {
        'name': 'Far Traveler',
        'skill_proficiencies': ['Insight', 'Perception'],
        'tool_proficiencies': ['One musical instrument or gaming set'],
        'languages': 1,
        'equipment': ["Traveler's clothes", "Musical instrument or gaming set", "Maps of homeland", "25 gp"],
        'feature': 'All Eyes on You',
        'feature_desc': 'Your exotic origin gets you noticed. Lords may invite you in; common folk are curious or suspicious.',
        'desc': 'You have come from a distant land, culture, or place that is strange to those around you.',
        'source': "Sword Coast Adventurer's Guide",
    },
    {
        'name': 'Haunted One',
        'skill_proficiencies': ['Arcana or Investigation', 'Religion or Survival'],
        'tool_proficiencies': [],
        'languages': 2,
        'equipment': ["Monster hunter's pack", "One trinket of grim origin"],
        'feature': 'Heart of Darkness',
        'feature_desc': 'Those who look into your eyes can see darkness. Commoners will help you (out of fear or pity).',
        'desc': 'You are haunted by something so terrible that you dare not speak of it.',
        'source': "Curse of Strahd",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# PF2E backgrounds (simplified — no public full wiki equivalent)
# ─────────────────────────────────────────────────────────────────────────────
PF2E_BACKGROUNDS = [
    {'name': 'Acolyte',      'skills': ['Religion', 'Scribing Lore'],       'feat': 'Student of the Canon',   'desc': 'You spent your early life in a religious institution.'},
    {'name': 'Acrobat',      'skills': ['Acrobatics', 'Circus Lore'],       'feat': 'Steady Balance',         'desc': 'You trained as an acrobat and performer.'},
    {'name': 'Animal Whisperer', 'skills': ['Nature', 'Animal Lore'],       'feat': 'Train Animal',           'desc': 'You have a deep connection with animals.'},
    {'name': 'Artisan',      'skills': ['Crafting', 'Guild Lore'],          'feat': 'Specialty Crafting',     'desc': 'You apprenticed with a craft guild.'},
    {'name': 'Artist',       'skills': ['Crafting', 'Art Lore'],            'feat': 'Specialty Crafting',     'desc': 'You learned artistic craft from a master.'},
    {'name': 'Barkeep',      'skills': ['Diplomacy', 'Alcohol Lore'],       'feat': 'Hobnobber',              'desc': 'You served drinks and learned everyone\'s secrets.'},
    {'name': 'Criminal',     'skills': ['Deception', 'Underworld Lore'],    'feat': 'Experienced Smuggler',   'desc': 'You lived outside the law.'},
    {'name': 'Entertainer',  'skills': ['Performance', 'Theater Lore'],     'feat': 'Fascinating Performance','desc': 'You were a performer of some renown.'},
    {'name': 'Farmhand',     'skills': ['Athletics', 'Farming Lore'],       'feat': 'Assurance (Athletics)',  'desc': 'You worked the land.'},
    {'name': 'Gladiator',    'skills': ['Performance', 'Gladiatorial Lore'],'feat': 'Impressive Performance', 'desc': 'You fought in arenas for crowds.'},
    {'name': 'Guard',        'skills': ['Intimidation', 'Legal Lore'],      'feat': 'Quick Coercion',         'desc': 'You served as a law enforcement officer.'},
    {'name': 'Herbalist',    'skills': ['Nature', 'Herbalism Lore'],        'feat': 'Natural Medicine',       'desc': 'You gathered and sold medicinal herbs.'},
    {'name': 'Hunter',       'skills': ['Nature', 'Tanning Lore'],          'feat': 'Monster Hunter',         'desc': 'You tracked and hunted game.'},
    {'name': 'Laborer',      'skills': ['Athletics', 'Labor Lore'],         'feat': 'Hefty Hauler',           'desc': 'You did hard physical work for a living.'},
    {'name': 'Merchant',     'skills': ['Diplomacy', 'Mercantile Lore'],    'feat': 'Bargain Hunter',         'desc': 'You bought and sold goods.'},
    {'name': 'Noble',        'skills': ['Society', 'Genealogy Lore'],       'feat': 'Courtly Graces',         'desc': 'You were born into a life of privilege.'},
    {'name': 'Nomad',        'skills': ['Survival', 'Region Lore'],         'feat': 'Assurance (Survival)',   'desc': 'You traveled continuously without a permanent home.'},
    {'name': 'Scholar',      'skills': ['Arcana', 'Academia Lore'],         'feat': 'Assurance (chosen lore)','desc': 'You spent years studying in a library or university.'},
    {'name': 'Scout',        'skills': ['Nature', 'Terrain Lore'],          'feat': 'Forager',                'desc': 'You patrolled the border between civilization and wilderness.'},
    {'name': 'Street Urchin','skills': ['Thievery', 'City Lore'],           'feat': 'Pickpocket',             'desc': 'You grew up on the city streets.'},
]

# ─────────────────────────────────────────────────────────────────────────────
# CoC Occupational backgrounds
# ─────────────────────────────────────────────────────────────────────────────
COC_BACKGROUNDS = [
    {'name': 'Antiquarian',   'skills': ['Appraise', 'History', 'Library Use', 'Spot Hidden'], 'desc': 'You collect and study antiques and relics.'},
    {'name': 'Artist',        'skills': ['Art/Craft', 'History', 'Psychology', 'Spot Hidden'], 'desc': 'You create visual art for a living.'},
    {'name': 'Author',        'skills': ['History', 'Library Use', 'Own Language', 'Psychology'], 'desc': 'You write books or journalism.'},
    {'name': 'Clergy',        'skills': ['Accounting', 'History', 'Library Use', 'Psychology', 'Persuade'], 'desc': 'You serve a religious institution.'},
    {'name': 'Criminal',      'skills': ['Charm', 'Fighting', 'Intimidate', 'Locksmith', 'Stealth'], 'desc': 'You make your living outside the law.'},
    {'name': 'Detective',     'skills': ['Art/Craft (photography)', 'Law', 'Library Use', 'Psychology', 'Spot Hidden'], 'desc': 'You investigate crimes.'},
    {'name': 'Doctor',        'skills': ['First Aid', 'Medicine', 'Other Language', 'Psychology', 'Science (Biology)'], 'desc': 'You practice medicine.'},
    {'name': 'Journalist',    'skills': ['Fast Talk', 'History', 'Library Use', 'Own Language', 'Psychology'], 'desc': 'You report news for a publication.'},
    {'name': 'Military',      'skills': ['Fighting', 'Firearms', 'Intimidate', 'Navigate', 'Survival'], 'desc': 'You served in the armed forces.'},
    {'name': 'Occultist',     'skills': ['Arcane', 'History', 'Library Use', 'Occult', 'Psychology'], 'desc': 'You study forbidden or esoteric knowledge.'},
    {'name': 'Police Officer', 'skills': ['Firearms', 'First Aid', 'Intimidate', 'Law', 'Psychology'], 'desc': 'You enforce the law.'},
    {'name': 'Professor',     'skills': ['History', 'Library Use', 'Other Language', 'Psychology'], 'desc': 'You teach at a university.'},
    {'name': 'Private Eye',   'skills': ['Fast Talk', 'Firearms', 'Library Use', 'Psychology', 'Stealth'], 'desc': 'You work as a private investigator.'},
    {'name': 'Soldier',       'skills': ['Fighting', 'Firearms', 'First Aid', 'Stealth', 'Survival'], 'desc': 'You fought on the front lines.'},
]

# ─────────────────────────────────────────────────────────────────────────────
# Cyberpunk Red lifepath backgrounds
# ─────────────────────────────────────────────────────────────────────────────
CYBERPUNK_BACKGROUNDS = [
    {'name': 'Corp Dropout',   'skills': ['Business', 'Bureaucracy'],  'desc': 'You escaped a corporate life — willingly or not.'},
    {'name': 'Street Kid',     'skills': ['Streetwise', 'Brawling'],   'desc': 'You grew up surviving in the Combat Zone.'},
    {'name': 'Nomad Born',     'skills': ['Land Vehicle', 'Survival'], 'desc': 'Your family traveled between settlements in a pack.'},
    {'name': 'Ex-Military',    'skills': ['Tactics', 'Weapons'],       'desc': 'You served in a corporate or government military.'},
    {'name': 'Techie Prodigy', 'skills': ['Electronics', 'Basic Tech'],'desc': 'You could take apart a servo motor at age six.'},
    {'name': 'Gang Member',    'skills': ['Streetwise', 'Intimidate'], 'desc': 'You ran with a crew and learned loyalty the hard way.'},
    {'name': 'Fixer Contact',  'skills': ['Trading', 'Persuasion'],    'desc': 'You grew up watching deals get made in back rooms.'},
    {'name': 'Rockerboy Crew', 'skills': ['Performance', 'Persuasion'],'desc': 'You followed a band and learned the power of music.'},
    {'name': 'Bootleg Medic',  'skills': ['First Aid', 'Pharmaceuticals'], 'desc': 'You learned medicine in a ripperdoc\'s back office.'},
]

# ─────────────────────────────────────────────────────────────────────────────
# Daggerheart Backgrounds
# ─────────────────────────────────────────────────────────────────────────────
DAGGERHEART_BACKGROUNDS = [
    {'name': 'Merchant',     'question': 'What did you sell that you regret?',      'skills': ['Trade', 'Persuasion'],   'desc': 'You bought and sold goods across the realm.'},
    {'name': 'Wanderer',     'question': 'What are you running from?',              'skills': ['Survival', 'Navigation'],'desc': 'You have always been on the move.'},
    {'name': 'Soldier',      'question': 'What order did you refuse to follow?',    'skills': ['Combat', 'Tactics'],     'desc': 'You served in an army or mercenary company.'},
    {'name': 'Scholar',      'question': 'What forbidden text did you read?',       'skills': ['Arcana', 'History'],     'desc': 'You studied in a great hall of learning.'},
    {'name': 'Farmer',       'question': 'What drove you from the land?',           'skills': ['Nature', 'Animal Care'], 'desc': 'You worked the earth before adventure called.'},
    {'name': 'Thief',        'question': 'Who did you steal from that you shouldn\'t have?', 'skills': ['Stealth', 'Deception'], 'desc': 'You made your living taking things that weren\'t yours.'},
    {'name': 'Noble',        'question': 'What scandal ruined your family?',        'skills': ['Etiquette', 'Politics'], 'desc': 'You were born to wealth and expectation.'},
    {'name': 'Sailor',       'question': 'What did you see that no one believes?',  'skills': ['Navigation', 'Athletics'],'desc': 'You worked aboard ships on open water.'},
    {'name': 'Healer',       'question': 'Who did you fail to save?',               'skills': ['Medicine', 'Empathy'],   'desc': 'You cared for the sick and wounded.'},
    {'name': 'Outcast',      'question': 'Why did your community exile you?',       'skills': ['Survival', 'Stealth'],   'desc': 'You were driven from where you belonged.'},
]


# ═══════════════════════════════════════════════════════════════════════════
# 1. WORLD BACKSTORY BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def run_world_backstory_builder(console: Console, system_id: str) -> str:
    """
    Interactive multi-step world-building prompts that run BEFORE genre setup.
    Returns a single formatted 'world_lore' string that gets saved into
    campaign_preferences.json and injected into the DM system prompt.

    The questions are system-aware: D&D/PF ask about magic, pantheons, and
    factions; Cyberpunk asks about corps and districts; CoC asks about era
    and historical events.
    """
    console.print()
    console.print(Panel(
        '[bold cyan]🌍  World Backstory Builder[/bold cyan]\n\n'
        '[white]Before the adventure begins, tell the GM about your world.[/white]\n'
        '[dim]The GM will use these details consistently throughout the campaign.\n'
        'Every question is optional — press Enter to skip any field.\n'
        'The more you share, the richer your world will feel.[/dim]',
        border_style='cyan'
    ))

    lore_parts = []

    def ask(prompt: str, hint: str = '', example: str = '') -> str:
        console.print(f'\n[bold cyan]{prompt}[/bold cyan]')
        if hint:
            console.print(f'[dim]{hint}[/dim]')
        if example:
            console.print(f'[dim]Example: "{example}"[/dim]')
        return console.input('  → ').strip()

    # ── Universal questions ────────────────────────────────────────────────
    world_name = ask(
        'What is this world called?',
        'The name of the realm, planet, or setting.',
        'Eberron · The Shattered Isles · New Chicago 2077'
    )
    if world_name:
        lore_parts.append(f'WORLD NAME: {world_name}')

    history = ask(
        'Describe a key historical event that shaped the world.',
        'A war, catastrophe, discovery, or era-defining moment.',
        'The Sundering split the continent 300 years ago. Magic became wild and unpredictable.',
    )
    if history:
        lore_parts.append(f'KEY HISTORY: {history}')

    current_state = ask(
        'What is the current state of the world right now?',
        'Who holds power? What tensions are simmering? Is there peace or conflict?',
        'Three city-states vie for control of the only remaining mana wells. War feels inevitable.',
    )
    if current_state:
        lore_parts.append(f'CURRENT STATE: {current_state}')

    # ── System-specific questions ──────────────────────────────────────────
    if system_id in ('dnd_5e', 'pathfinder_2e', 'daggerheart'):
        magic = ask(
            'How does magic work in this world?',
            'Is it common or rare? Feared or celebrated? Regulated or wild?',
            'Magic is rare and controlled by the Mage Council. Unlicensed casting is punishable by death.',
        )
        if magic:
            lore_parts.append(f'MAGIC: {magic}')

        gods = ask(
            'What gods or pantheon exist (if any)?',
            'Are they active or distant? Which faiths are dominant?',
            'The Old Gods vanished 50 years ago. Their clerics still have power but no one knows why.',
        )
        if gods:
            lore_parts.append(f'GODS AND RELIGION: {gods}')

        factions = ask(
            'Name one or two important factions or organizations.',
            'Guilds, kingdoms, cults, orders — who competes for power?',
            'The Merchant Guild controls trade. The Iron Brotherhood are a secret order of assassins.',
        )
        if factions:
            lore_parts.append(f'FACTIONS: {factions}')

        forbidden = ask(
            'Is there anything forbidden, feared, or taboo in this world?',
            'Ancient ruins, forbidden magic, dangerous locations, or social taboos.',
            'Speaking the name of the Lich-King aloud is said to draw his attention.',
        )
        if forbidden:
            lore_parts.append(f'FORBIDDEN / TABOO: {forbidden}')

    elif system_id == 'cyberpunk_red':
        corps = ask(
            'Which corporations dominate this city?',
            'Name 1-3 megacorps and what they control.',
            'Arasaka controls security. Militech sells weapons. SovOil owns the power grid.',
        )
        if corps:
            lore_parts.append(f'MEGACORPS: {corps}')

        districts = ask(
            'Describe the city districts where the story takes place.',
            'Combat zones, corporate enclaves, nomad territories.',
            'Night City\'s Watson district is cheap real estate with high body counts.',
        )
        if districts:
            lore_parts.append(f'CITY DISTRICTS: {districts}')

        tech = ask(
            'What technology defines the era?',
            'Cyberware, netrunning, AI, biotech — what is common and what is cutting edge?',
            'Full cyberware replacement is mainstream. True AI is illegal after the DataKrash.',
        )
        if tech:
            lore_parts.append(f'TECHNOLOGY: {tech}')

    elif system_id == 'call_of_cthulhu':
        era = ask(
            'What year and location does the campaign take place?',
            'CoC usually plays in the 1920s but any era works.',
            '1923, Arkham, Massachusetts.',
        )
        if era:
            lore_parts.append(f'ERA AND LOCATION: {era}')

        events = ask(
            'What local or national events are happening that the investigators know about?',
            'News headlines, local gossip, recent crimes or disappearances.',
            'A series of disappearances near Miskatonic University. The local police are baffled.',
        )
        if events:
            lore_parts.append(f'CURRENT EVENTS: {events}')

        mythos = ask(
            'What, if anything, do the investigators already know about the unnatural?',
            'Are they complete skeptics, or have they had prior exposure?',
            'One investigator had a vision during a fever last year — she never talks about it.',
        )
        if mythos:
            lore_parts.append(f'PRIOR KNOWLEDGE: {mythos}')

    # ── Universal closing question ─────────────────────────────────────────
    secrets = ask(
        'What is a secret about this world that even most inhabitants do not know?',
        'The GM will weave this into the story as a slow revelation.',
        'The "gods" are actually ancient constructs built by a vanished civilization.',
    )
    if secrets:
        lore_parts.append(f'WORLD SECRET (GM ONLY): {secrets}')

    extra = ask(
        'Anything else the GM should always know about this world?',
        'Unique laws of nature, required narrative elements, things to always mention.',
        'It always rains. The sun has not been seen in this region in forty years.',
    )
    if extra:
        lore_parts.append(f'OTHER WORLD NOTES: {extra}')

    if not lore_parts:
        return ''

    world_lore = '\n\n'.join(lore_parts)

    # Show a summary
    console.print()
    console.print(Panel(
        world_lore[:800] + ('...' if len(world_lore) > 800 else ''),
        title='[bold green]World Lore Summary[/bold green]',
        border_style='green'
    ))
    console.print('[green]World lore saved — the GM will use this throughout the campaign.[/green]')

    return world_lore


# ═══════════════════════════════════════════════════════════════════════════
# 2. CUSTOM RACE BUILDER
# ═══════════════════════════════════════════════════════════════════════════

_HOMEBREW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'homebrew')
_RACES_FILE   = os.path.join(_HOMEBREW_DIR, 'races.json')


def _load_homebrew_races() -> dict:
    if os.path.exists(_RACES_FILE):
        try:
            with open(_RACES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_homebrew_race(race: dict):
    os.makedirs(_HOMEBREW_DIR, exist_ok=True)
    existing = _load_homebrew_races()
    existing[race['name']] = race
    with open(_RACES_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def run_custom_race_builder(console: Console, system_id: str) -> list:
    """
    Asks the player if they want to define any custom races.
    Loops until the player says they are done.
    Returns a list of race dicts (same schema as DND5E_RACES).
    Also saves each race to data/homebrew/races.json.
    """
    new_races = []

    console.print()
    console.print(Panel(
        '[bold cyan]🧬  Custom Race Builder[/bold cyan]\n\n'
        '[white]Would you like to add any homebrew or custom races to this campaign?[/white]\n'
        '[dim]Custom races are saved and will appear in the race selection menu.\n'
        'You can add as many as you like, or skip entirely.[/dim]',
        border_style='cyan'
    ))

    while True:
        add = console.input('\n[bold white]Add a custom race? (y/n): [/bold white]').strip().lower()
        if add != 'y':
            break

        race = _build_one_race(console, system_id)
        if race:
            _save_homebrew_race(race)
            new_races.append(race)
            console.print(f'  [green]✓ "{race["name"]}" saved to homebrew races.[/green]')

    if new_races:
        console.print(
            f'\n[green]{len(new_races)} custom race(s) added.[/green] '
            f'[dim]They will appear in the race selection menu.[/dim]'
        )

    return new_races


def _build_one_race(console: Console, system_id: str) -> dict | None:
    """Interactively builds a single custom race dict."""
    console.print('\n[bold white]── New Custom Race ─────────────────────────────[/bold white]')

    def ask(prompt: str, example: str = '', required: bool = False) -> str:
        console.print(f'\n[bold cyan]{prompt}[/bold cyan]')
        if example:
            console.print(f'[dim]Example: {example}[/dim]')
        suffix = '' if required else ' [dim](Enter to skip)[/dim]'
        console.print(suffix)
        while True:
            val = console.input('  → ').strip()
            if val or not required:
                return val
            console.print('  [red]This field is required.[/red]')

    name = ask('Race name:', 'Sandborn · Ironvein Dwarf · Voidling', required=True)
    if not name:
        return None

    desc = ask('Brief description:', 'A people born from volcanic stone, their skin is obsidian-dark and warm to the touch.')

    # Ability Score Increases
    console.print('\n[bold cyan]Ability Score Increases[/bold cyan]')
    console.print('[dim]Enter as STAT: +N pairs, comma-separated. E.g. STR: +2, CON: +1[/dim]')
    console.print('[dim]Valid stats: STR DEX CON INT WIS CHA[/dim]')
    asi_raw = console.input('  → ').strip()
    asi = {}
    if asi_raw:
        for part in asi_raw.split(','):
            m = re.match(r'\s*(STR|DEX|CON|INT|WIS|CHA)\s*[:\+]\s*\+?(\d+)', part.strip(), re.I)
            if m:
                asi[m.group(1).upper()] = int(m.group(2))

    speed_raw = console.input('\n[bold cyan]Speed (feet)[/bold cyan] [dim](default 30)[/dim]\n  → ').strip()
    speed = int(speed_raw) if speed_raw.isdigit() else 30

    size_choice = console.input('\n[bold cyan]Size[/bold cyan] [dim](Small / Medium / Large, default Medium)[/dim]\n  → ').strip()
    size = size_choice.capitalize() if size_choice.capitalize() in ('Small', 'Medium', 'Large') else 'Medium'

    dv_raw = console.input('\n[bold cyan]Darkvision range (feet)[/bold cyan] [dim](0 = none, e.g. 60)[/dim]\n  → ').strip()
    darkvision_range = int(dv_raw) if dv_raw.isdigit() else 0
    darkvision = darkvision_range > 0

    console.print('\n[bold cyan]Racial Traits[/bold cyan]')
    console.print('[dim]Enter one trait per line. Empty line to finish.[/dim]')
    console.print('[dim]Example: Stone Resistance: Resistant to bludgeoning damage from non-magical sources.[/dim]')
    traits = []
    while True:
        t = console.input('  Trait: ').strip()
        if not t:
            break
        traits.append(t)

    console.print('\n[bold cyan]Racial Proficiencies[/bold cyan]')
    console.print('[dim]Weapons, skills, tools — comma-separated. E.g. Warhammer, Stonecutters Tools[/dim]')
    prof_raw = console.input('  → ').strip()
    proficiencies = [p.strip() for p in prof_raw.split(',') if p.strip()] if prof_raw else []

    console.print('\n[bold cyan]Languages[/bold cyan]')
    console.print('[dim]Comma-separated. E.g. Common, Terran[/dim]')
    lang_raw = console.input('  → ').strip()
    languages = [l.strip() for l in lang_raw.split(',') if l.strip()] if lang_raw else ['Common']

    race = {
        'name':            name,
        'description':     desc,
        'asi':             asi,
        'traits':          traits,
        'proficiencies':   proficiencies,
        'languages':       languages,
        'speed':           speed,
        'size':            size,
        'darkvision':      darkvision,
        'darkvision_range': darkvision_range,
        'homebrew':        True,
        'system_id':       system_id,
    }

    # Show summary
    lines = [
        f'[bold white]{name}[/bold white]',
        f'[dim]{desc}[/dim]' if desc else '',
        '',
        f'[cyan]Speed:[/cyan] {speed} ft  [cyan]Size:[/cyan] {size}  [cyan]Darkvision:[/cyan] {darkvision_range} ft' if darkvision else f'[cyan]Speed:[/cyan] {speed} ft  [cyan]Size:[/cyan] {size}',
    ]
    if asi:
        asi_str = '  '.join(f'{k} +{v}' for k, v in asi.items())
        lines.append(f'[cyan]ASI:[/cyan] {asi_str}')
    if traits:
        lines.append(f'[cyan]Traits:[/cyan] {", ".join(t.split(":")[0] for t in traits)}')
    if proficiencies:
        lines.append(f'[cyan]Proficiencies:[/cyan] {", ".join(proficiencies)}')
    if languages:
        lines.append(f'[cyan]Languages:[/cyan] {", ".join(languages)}')

    console.print()
    console.print(Panel('\n'.join(l for l in lines if l != ''), title='[bold green]New Race[/bold green]', border_style='green'))

    confirm = console.input('[bold white]Save this race? (y/n): [/bold white]').strip().lower()
    return race if confirm == 'y' else None


def get_homebrew_races_for_menu() -> list:
    """Returns list of homebrew race names with [Homebrew] label for the race menu."""
    races = _load_homebrew_races()
    return [f'{name} [Homebrew]' for name in races.keys()]


# ═══════════════════════════════════════════════════════════════════════════
# 3. BACKGROUND PICKER
# ═══════════════════════════════════════════════════════════════════════════

def pick_background(console: Console, system_id: str, char_class: str = '') -> dict:
    """
    Displays a numbered table of backgrounds appropriate for the game system.
    Player picks by number. Returns a dict containing:
      name, skill_proficiencies, tool_proficiencies, languages, equipment,
      feature, feature_desc, desc, source
    Returns {} if the player skips.
    """
    backgrounds = _get_backgrounds(system_id)

    if not backgrounds:
        return {}

    console.print()
    console.print(Panel(
        '[bold cyan]📖  Choose Your Background[/bold cyan]\n\n'
        '[white]Your background represents who you were before you became an adventurer.[/white]\n'
        '[dim]It grants skill proficiencies, tool proficiencies, languages, and bonus equipment.\n'
        'Press Enter to skip if you prefer to define your history through roleplay.[/dim]',
        border_style='cyan'
    ))

    # Try to scrape backgrounds for D&D 5e if wiki cache is available
    if system_id == 'dnd_5e':
        scraped = _try_scrape_backgrounds()
        if scraped:
            backgrounds = scraped

    _display_background_table(console, backgrounds, system_id)

    console.print(f'\n[dim]Enter a number (1-{len(backgrounds)}) or press Enter to skip.[/dim]')

    while True:
        raw = console.input('[bold white]  → [/bold white]').strip()
        if not raw:
            return {}
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(backgrounds):
                bg = backgrounds[idx]
                _display_background_detail(console, bg, system_id)
                confirm = console.input('[bold white]Choose this background? (y/n): [/bold white]').strip().lower()
                if confirm == 'y':
                    console.print(f'  [green]✓ Background: {bg["name"]}[/green]')
                    return bg
                # Else re-show the table
                _display_background_table(console, backgrounds, system_id)
                console.print(f'\n[dim]Enter a number (1-{len(backgrounds)}) or press Enter to skip.[/dim]')
            else:
                console.print(f'  [red]Please enter a number between 1 and {len(backgrounds)}.[/red]')
        else:
            console.print('  [red]Please enter a number or press Enter to skip.[/red]')


def _get_backgrounds(system_id: str) -> list:
    mapping = {
        'dnd_5e':        DND5E_BACKGROUNDS,
        'pathfinder_2e': PF2E_BACKGROUNDS,
        'call_of_cthulhu': COC_BACKGROUNDS,
        'cyberpunk_red': CYBERPUNK_BACKGROUNDS,
        'daggerheart':   DAGGERHEART_BACKGROUNDS,
        'starfinder':    DND5E_BACKGROUNDS,  # Starfinder uses similar backgrounds
    }
    return mapping.get(system_id, DND5E_BACKGROUNDS)


def _display_background_table(console: Console, backgrounds: list, system_id: str):
    tbl = Table(show_header=True, header_style='bold cyan', border_style='dim',
                expand=False, padding=(0, 1))
    tbl.add_column('#',          style='dim',        width=3,  justify='right')
    tbl.add_column('Background', style='bold white',  min_width=18)

    if system_id in ('dnd_5e', 'pathfinder_2e', 'starfinder'):
        tbl.add_column('Skill Proficiencies', style='green', min_width=28)
        tbl.add_column('Extras',              style='dim yellow', min_width=20)
        for i, bg in enumerate(backgrounds, 1):
            skills = bg.get('skill_proficiencies') or bg.get('skills') or []
            tools  = bg.get('tool_proficiencies', [])
            langs  = bg.get('languages', 0)
            extras = []
            if tools:
                extras.append(f'Tools: {", ".join(tools[:2])}')
            if langs and isinstance(langs, int) and langs > 0:
                extras.append(f'{langs} language{"s" if langs > 1 else ""}')
            elif isinstance(langs, list) and langs:
                extras.append(f'Languages: {", ".join(langs)}')
            tbl.add_row(str(i), bg['name'], ', '.join(skills), '; '.join(extras) or '—')
    else:
        tbl.add_column('Skills',      style='green', min_width=30)
        tbl.add_column('Description', style='white', min_width=32, max_width=50)
        for i, bg in enumerate(backgrounds, 1):
            skills = bg.get('skill_proficiencies') or bg.get('skills') or []
            desc   = bg.get('desc', '')[:50]
            tbl.add_row(str(i), bg['name'], ', '.join(skills) if isinstance(skills, list) else str(skills), desc)

    console.print(tbl)


def _display_background_detail(console: Console, bg: dict, system_id: str):
    """Shows full detail of a chosen background before confirmation."""
    lines = [f'[bold white]{bg["name"]}[/bold white]']
    if bg.get('desc'):
        lines.append(f'[dim]{bg["desc"]}[/dim]')
    lines.append('')

    skills = bg.get('skill_proficiencies') or bg.get('skills') or []
    if skills:
        lines.append(f'[cyan]Skill Proficiencies:[/cyan] {", ".join(skills) if isinstance(skills, list) else str(skills)}')

    tools = bg.get('tool_proficiencies', [])
    if tools:
        lines.append(f'[cyan]Tool Proficiencies:[/cyan] {", ".join(tools)}')

    langs = bg.get('languages', 0)
    if langs and isinstance(langs, int) and langs > 0:
        lines.append(f'[cyan]Bonus Languages:[/cyan] {langs}')
    elif isinstance(langs, list) and langs:
        lines.append(f'[cyan]Languages:[/cyan] {", ".join(langs)}')

    equip = bg.get('equipment', [])
    if equip:
        lines.append(f'[cyan]Starting Equipment:[/cyan] {", ".join(equip)}')

    feat = bg.get('feature') or bg.get('feat') or bg.get('question', '')
    feat_desc = bg.get('feature_desc', '')
    if feat:
        lines.append(f'\n[cyan]Feature:[/cyan] [bold]{feat}[/bold]')
    if feat_desc:
        lines.append(f'[dim]{feat_desc}[/dim]')

    source = bg.get('source', '')
    if source:
        lines.append(f'\n[dim]Source: {source}[/dim]')

    console.print()
    console.print(Panel('\n'.join(lines), title='[bold cyan]Background Detail[/bold cyan]', border_style='cyan'))


def _try_scrape_backgrounds() -> list:
    """
    Attempt to scrape the D&D 5e backgrounds list from the wiki cache.
    Falls back to hardcoded list if unavailable.
    """
    try:
        import wiki_scraper
        data = wiki_scraper.load_or_scrape(silent=True)
        scraped_bgs = data.get('backgrounds', [])
        if scraped_bgs:
            return scraped_bgs
    except Exception:
        pass
    return []


# ═══════════════════════════════════════════════════════════════════════════
# 4. EQUIPMENT CHOOSER
# ═══════════════════════════════════════════════════════════════════════════

def pick_starting_equipment(console: Console, class_data: dict, class_name: str = '') -> list:
    """
    Parses the 'equipment' list from a class data dict (from DND5E_CLASSES or
    wiki-scraped data). Any entry containing ' OR ' becomes an interactive
    numbered choice prompt. Non-OR entries are auto-included.

    Presents choices with clear numbering and confirmation.
    Returns a flat list of all chosen and auto-included equipment strings.
    """
    raw_equipment = class_data.get('equipment', [])
    if not raw_equipment:
        return []

    console.print()
    console.print(Panel(
        f'[bold cyan]🎒  Starting Equipment — {class_name}[/bold cyan]\n\n'
        '[white]Choose your starting gear. Some items have alternatives — pick the one that fits your build.[/white]\n'
        '[dim]Items without a choice are included automatically.[/dim]',
        border_style='cyan',
        padding=(0, 2),
    ))

    chosen       = []   # items where the player made an OR-choice
    auto_included = []  # items with no OR that are given automatically
    choice_number = 0

    for entry in raw_equipment:
        # Split on ' OR ' (case-insensitive) to find choice entries
        parts = re.split(r'\s+OR\s+', str(entry), flags=re.IGNORECASE)

        if len(parts) == 1:
            # No choice — auto-include
            auto_included.append(entry.strip())
        else:
            # Choice entry — ask the player
            choice_number += 1
            parts = [p.strip() for p in parts if p.strip()]

            console.print()
            console.print(
                f'[bold white]Choice {choice_number}[/bold white]  '
                f'[dim]— Select one of the following:[/dim]'
            )

            # Build a mini table for this choice
            tbl = Table(
                show_header=False, border_style='dim',
                padding=(0, 2), box=None
            )
            tbl.add_column('#', style='bold cyan', width=3)
            tbl.add_column('Option', style='white', min_width=40)

            for i, option in enumerate(parts, 1):
                tbl.add_row(str(i), option)

            console.print(tbl)

            while True:
                raw = console.input(
                    f'[bold white]  → Choose 1–{len(parts)}: [/bold white]'
                ).strip()

                if raw.isdigit():
                    idx = int(raw) - 1
                    if 0 <= idx < len(parts):
                        pick = parts[idx]
                        chosen.append(pick)
                        console.print(f'  [green]✓ {pick}[/green]')
                        break
                    console.print(f'  [red]Enter a number between 1 and {len(parts)}.[/red]')
                elif not raw:
                    # Default to first option on Enter
                    chosen.append(parts[0])
                    console.print(f'  [green]✓ {parts[0]} (default)[/green]')
                    break
                else:
                    console.print(f'  [red]Please enter a number (1–{len(parts)}).[/red]')

    # Combine chosen and auto-included into the final inventory
    all_items = chosen + auto_included

    # Display summary
    console.print()
    if auto_included:
        console.print(
            f'[cyan]Auto-included:[/cyan] '
            + ', '.join(f'[dim]{i}[/dim]' for i in auto_included)
        )

    console.print()
    console.print(Panel(
        '\n'.join(f'  [cyan]•[/cyan] {item}' for item in all_items)
        or '[dim]No equipment selected.[/dim]',
        title='[bold green]🎒 Your Starting Equipment[/bold green]',
        border_style='green',
        padding=(0, 2),
    ))

    return all_items


# ═══════════════════════════════════════════════════════════════════════════
# 5. SKILL PROFICIENCY CHOOSER
# ═══════════════════════════════════════════════════════════════════════════

def pick_skill_proficiencies(
    console: Console,
    class_data: dict,
    class_name: str = '',
    already_proficient: list = None,
) -> list:
    """
    Displays the class's available skill choices and asks the player to
    pick exactly skill_count of them. Already-proficient skills (from race
    or background) are shown as locked-in and excluded from the pick list.

    Returns a list of chosen skill names.
    """
    if already_proficient is None:
        already_proficient = []

    skill_choices = class_data.get('skill_choices', [])
    skill_count   = class_data.get('skill_count', 2)

    if not skill_choices:
        return []

    # Remove already-proficient skills from the available pool
    available = [s for s in skill_choices if s not in already_proficient]

    if not available:
        console.print('[dim]All class skills already granted by race/background.[/dim]')
        return []

    # Adjust count if we have fewer available than required
    pick_count = min(skill_count, len(available))

    console.print()
    console.print(Panel(
        f'[bold cyan]🎯  Skill Proficiencies — {class_name}[/bold cyan]\n\n'
        f'[white]Choose [bold]{pick_count}[/bold] skill proficiencies from your class list.[/white]\n'
        + (f'[dim]Already proficient (from race/background): {", ".join(already_proficient)}[/dim]\n' if already_proficient else '')
        + '[dim]Enter numbers separated by spaces or commas. E.g. "1 3 5"[/dim]',
        border_style='cyan'
    ))

    # Display the available skills
    tbl = Table(show_header=False, border_style='dim', padding=(0, 2), box=None)
    tbl.add_column('#',     style='dim',       width=4)
    tbl.add_column('Skill', style='bold white', min_width=22)
    tbl.add_column('Description', style='dim', min_width=40)

    skill_descriptions = {
        'Acrobatics':     'DEX — Tumbling, balance, gymnastics',
        'Animal Handling':'WIS — Calming, training, and reading animals',
        'Arcana':         'INT — Magic lore, spells, and planes',
        'Athletics':      'STR — Climbing, swimming, jumping',
        'Deception':      'CHA — Lying, misdirection, disguise',
        'History':        'INT — Events, legends, and knowledge of the past',
        'Insight':        'WIS — Reading people, detecting lies',
        'Intimidation':   'CHA — Threats, coercion, menace',
        'Investigation':  'INT — Searching, deducing, finding clues',
        'Medicine':       'WIS — Stabilizing dying creatures, diagnosing illness',
        'Nature':         'INT — Plants, animals, weather, terrain',
        'Perception':     'WIS — Noticing things, awareness of surroundings',
        'Performance':    'CHA — Acting, music, dancing, storytelling',
        'Persuasion':     'CHA — Honest appeals, diplomacy, negotiation',
        'Religion':       'INT — Theology, rites, deities, undead lore',
        'Sleight of Hand':'DEX — Pickpocketing, palming objects, stage magic',
        'Stealth':        'DEX — Moving silently and hiding',
        'Survival':       'WIS — Tracking, foraging, navigating wilds',
    }

    for i, skill in enumerate(available, 1):
        desc = skill_descriptions.get(skill, '')
        tbl.add_row(str(i), skill, desc)

    console.print(tbl)
    console.print(f'\n[dim]Pick exactly {pick_count} skills (enter {pick_count} numbers).[/dim]')

    chosen = []
    while True:
        raw = console.input('[bold white]  → [/bold white]').strip()
        if not raw:
            continue

        # Parse numbers — accept "1 2 3" or "1,2,3" or "1, 2, 3"
        nums = re.findall(r'\d+', raw)
        selected_indices = []
        valid = True

        for n in nums:
            idx = int(n) - 1
            if 0 <= idx < len(available):
                if idx not in selected_indices:
                    selected_indices.append(idx)
            else:
                console.print(f'  [red]{n} is out of range (1-{len(available)}).[/red]')
                valid = False
                break

        if not valid:
            continue

        if len(selected_indices) != pick_count:
            console.print(f'  [red]Please choose exactly {pick_count} skills (you chose {len(selected_indices)}).[/red]')
            continue

        chosen = [available[i] for i in selected_indices]
        break

    console.print(f'\n[green]Skill proficiencies chosen:[/green] {", ".join(chosen)}')
    return chosen


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY: Build merged proficiency list for character sheet
# ═══════════════════════════════════════════════════════════════════════════

def build_proficiency_block(
    racial_proficiencies: list,
    background: dict,
    chosen_skills: list,
    class_data: dict,
) -> dict:
    """
    Merges all proficiency sources into a clean summary dict for the character sheet.
    Returns:
      {
        'all_skill_proficiencies': list of all skill proficiencies (deduplicated),
        'tool_proficiencies':      list of tool proficiencies,
        'armor_proficiencies':     list,
        'weapon_proficiencies':    list,
        'saving_throw_proficiencies': list,
        'languages':               list,
        'expertise_available':     bool,
        'expertise_count':         int,
      }
    """
    all_skills = []

    # Racial skill proficiencies
    for p in racial_proficiencies:
        if p not in all_skills:
            all_skills.append(p)

    # Background skill proficiencies
    bg_skills = background.get('skill_proficiencies') or background.get('skills') or []
    for s in bg_skills:
        if s not in all_skills:
            all_skills.append(s)

    # Player-chosen class skills
    for s in chosen_skills:
        if s not in all_skills:
            all_skills.append(s)

    # Tool proficiencies
    tool_profs = list(class_data.get('tools', []))
    bg_tools   = background.get('tool_proficiencies', [])
    for t in bg_tools:
        if t not in tool_profs:
            tool_profs.append(t)

    # Languages from background
    bg_langs = background.get('languages', [])
    if isinstance(bg_langs, int):
        bg_langs = [f'Any language of your choice (×{bg_langs})'] if bg_langs else []

    # Rogue expertise
    expertise_available = 'Rogue' in str(class_data.get('features', '')) or any(
        'Expertise' in f for f in class_data.get('features', [])
    )

    return {
        'all_skill_proficiencies':    all_skills,
        'tool_proficiencies':          tool_profs,
        'armor_proficiencies':         class_data.get('armor', []),
        'weapon_proficiencies':        class_data.get('weapons', []),
        'saving_throw_proficiencies':  class_data.get('saves', []),
        'bonus_languages':             bg_langs,
        'expertise_available':         expertise_available,
        'expertise_count':             2 if expertise_available else 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 6. RACE DETAIL DISPLAY — show full stat block before picking
# ═══════════════════════════════════════════════════════════════════════════

def show_race_details_panel(console: Console, race_name: str, system_id: str = 'dnd_5e') -> None:
    """
    Displays a rich, formatted stat block for a race — ASI, traits,
    proficiencies, speed, size, darkvision, languages — so the player
    can make an informed choice before committing.

    Pulls from character_rules.DND5E_RACES (or PF2E_ANCESTRIES, etc.)
    Falls back to a minimal display if the race isn't in the data.
    """
    import character_rules as _cr

    system_map = {
        'dnd_5e':        ('DND5E_RACES', 'Ability Score Increases'),
        'pathfinder_2e': ('PF2E_ANCESTRIES', 'Ability Boosts'),
        'daggerheart':   ('DAGGERHEART_ANCESTRIES', 'Community Bonus'),
    }

    attr_name, asi_label = system_map.get(system_id, ('DND5E_RACES', 'Ability Score Increases'))
    race_db = getattr(_cr, attr_name, _cr.DND5E_RACES)
    data = race_db.get(race_name)

    if not data:
        console.print(f'[dim]  (No detailed stats on file for {race_name} — will be handled freeform.)[/dim]')
        return

    lines = []

    # Description
    if data.get('description'):
        lines.append(f'[dim]{data["description"]}[/dim]')
        lines.append('')

    # ASI / Ability Boosts
    asi = data.get('asi') or data.get('ability_boosts')
    if isinstance(asi, dict) and asi:
        asi_parts = [f'[bold cyan]+{v}[/bold cyan] {k}' for k, v in asi.items() if v > 0]
        if asi_parts:
            lines.append(f'[cyan]{asi_label}:[/cyan] ' + '  '.join(asi_parts))
    elif isinstance(asi, str) and asi:
        lines.append(f'[cyan]{asi_label}:[/cyan] {asi}')

    if data.get('ability_flaw'):
        lines.append(f'[red]Ability Flaw:[/red] {data["ability_flaw"]}')

    # Movement & physical traits
    speed = data.get('speed')
    size  = data.get('size')
    dv    = data.get('darkvision')
    dv_range = data.get('darkvision_range', 0) if dv else 0

    stat_parts = []
    if speed:
        stat_parts.append(f'[cyan]Speed:[/cyan] {speed} ft')
    if size:
        stat_parts.append(f'[cyan]Size:[/cyan] {size}')
    if dv and dv_range:
        stat_parts.append(f'[cyan]Darkvision:[/cyan] {dv_range} ft')
    if stat_parts:
        lines.append('  '.join(stat_parts))

    # Traits / Features
    traits = data.get('traits') or data.get('features', [])
    if traits:
        lines.append('')
        lines.append('[bold white]Traits & Features:[/bold white]')
        for t in traits:
            lines.append(f'  [cyan]▸[/cyan] {t}')

    # Proficiencies
    profs = data.get('proficiencies', [])
    if profs:
        lines.append('')
        lines.append(f'[cyan]Racial Proficiencies:[/cyan] {", ".join(profs)}')

    # Innate spells
    spells = data.get('innate_spells', [])
    if spells:
        lines.append(f'[cyan]Innate Magic:[/cyan] {", ".join(spells)}')

    # Languages
    langs = data.get('languages', [])
    if langs:
        lines.append(f'[cyan]Languages:[/cyan] {", ".join(langs)}')

    # Daggerheart community bonus
    if data.get('community_bonus'):
        lines.append(f'[cyan]Community Bonus:[/cyan] {data["community_bonus"]}')
    if data.get('experience'):
        lines.append(f'[cyan]Starting Experience:[/cyan] {data["experience"]}')

    console.print()
    console.print(Panel(
        '\n'.join(lines) or '[dim]No data available.[/dim]',
        title=f'[bold cyan]{race_name}[/bold cyan]',
        border_style='cyan',
        padding=(0, 2),
    ))


# ═══════════════════════════════════════════════════════════════════════════
# 7. CLASS DETAIL DISPLAY — show full class info before picking
# ═══════════════════════════════════════════════════════════════════════════

def show_class_details_panel(console: Console, class_name: str, system_id: str = 'dnd_5e') -> None:
    """
    Displays a complete class stat block: hit die, saving throws,
    armor/weapon proficiencies, skill choices, class features, and
    starting equipment — so the player knows exactly what they're choosing.
    """
    import character_rules as _cr

    system_map = {
        'dnd_5e':        'DND5E_CLASSES',
        'pathfinder_2e': 'PF2E_CLASSES',
        'daggerheart':   'DAGGERHEART_CLASSES',
    }

    attr_name = system_map.get(system_id, 'DND5E_CLASSES')
    class_db  = getattr(_cr, attr_name, _cr.DND5E_CLASSES)
    data = class_db.get(class_name)

    if not data:
        console.print(f'[dim]  (No detailed class data on file for {class_name}.)[/dim]')
        return

    lines = []

    # ── D&D 5e / similar ─────────────────────────────────────────────────
    if system_id in ('dnd_5e', 'starfinder'):
        hit_die = data.get('hit_die', '?')
        saves   = data.get('saves', [])
        armor   = data.get('armor', [])
        weapons = data.get('weapons', [])
        tools   = data.get('tools', [])
        skills  = data.get('skill_choices', [])
        count   = data.get('skill_count', 2)
        features = data.get('features', [])
        equip    = data.get('equipment', [])

        lines.append(f'[cyan]Hit Die:[/cyan] d{hit_die}   [cyan]Saving Throws:[/cyan] {", ".join(saves) if saves else "—"}')

        if armor:
            lines.append(f'[cyan]Armor Proficiencies:[/cyan] {", ".join(armor)}')
        if weapons:
            lines.append(f'[cyan]Weapon Proficiencies:[/cyan] {", ".join(weapons)}')
        if tools:
            lines.append(f'[cyan]Tool Proficiencies:[/cyan] {", ".join(tools)}')
        if skills:
            lines.append(f'[cyan]Skills (choose {count}):[/cyan] {", ".join(skills)}')

        if features:
            lines.append('')
            lines.append('[bold white]Level 1 Features:[/bold white]')
            for f in features:
                lines.append(f'  [cyan]▸[/cyan] {f}')

        if equip:
            lines.append('')
            lines.append('[bold white]Starting Equipment Options:[/bold white]')
            for e in equip:
                lines.append(f'  [dim]•[/dim] {e}')

    # ── Pathfinder 2e ──────────────────────────────────────────────────────
    elif system_id == 'pathfinder_2e':
        lines.append(f'[cyan]HP per Level:[/cyan] {data.get("hp_per_level", "?")}   '
                     f'[cyan]Key Ability:[/cyan] {data.get("key_ability", "?")}')
        saves = data.get('saves', {})
        if saves:
            save_str = '  '.join(f'{s}: {v}' for s, v in saves.items())
            lines.append(f'[cyan]Saves:[/cyan] {save_str}')
        lines.append(f'[cyan]Skills Trained:[/cyan] {data.get("skills_trained", "?")}')
        features = data.get('features', [])
        if features:
            lines.append('')
            lines.append('[bold white]Class Features:[/bold white]')
            for f in features:
                lines.append(f'  [cyan]▸[/cyan] {f}')

    # ── Daggerheart ────────────────────────────────────────────────────────
    elif system_id == 'daggerheart':
        lines.append(
            f'[cyan]HP per Level:[/cyan] {data.get("hp_per_level", "?")}   '
            f'[cyan]Evasion:[/cyan] {data.get("evasion", "?")}   '
            f'[cyan]Stress Slots:[/cyan] {data.get("stress_slots", "?")}'
        )
        lines.append(
            f'[cyan]Primary Trait:[/cyan] {data.get("primary_trait", "?")}   '
            f'[cyan]Secondary Trait:[/cyan] {data.get("secondary_trait", "?")}'
        )
        domains = data.get('domain_cards', [])
        if domains:
            lines.append(f'[cyan]Domain Cards:[/cyan] {", ".join(domains)}')
        features = data.get('features', [])
        if features:
            lines.append('')
            lines.append('[bold white]Foundation Features:[/bold white]')
            for f in features:
                lines.append(f'  [cyan]▸[/cyan] {f}')
        equip = data.get('starting_equipment', [])
        if equip:
            lines.append('')
            lines.append('[bold white]Starting Equipment:[/bold white]')
            for e in equip:
                lines.append(f'  [dim]•[/dim] {e}')

    console.print()
    console.print(Panel(
        '\n'.join(lines) or '[dim]No data available.[/dim]',
        title=f'[bold cyan]{class_name}[/bold cyan]',
        border_style='cyan',
        padding=(0, 2),
    ))


# ═══════════════════════════════════════════════════════════════════════════
# 8. PICK RACE WITH FULL DETAILS
# ═══════════════════════════════════════════════════════════════════════════

def pick_race_with_details(
    console: Console,
    system_id: str,
    standard_races: list,
    generated_races: list = None,
    homebrew_races: list = None,
) -> tuple:
    """
    Shows a numbered race menu. When the player selects a race, displays the
    full stat block (ASI, traits, speed, proficiencies, languages) BEFORE
    asking them to confirm. Loops until confirmed.

    Returns (race_name: str, race_data: dict | None)
      race_data is populated for generated/homebrew races, None for standard.
    """
    import character_rules as _cr

    generated_races = generated_races or []
    homebrew_races  = homebrew_races  or []

    system_map = {
        'dnd_5e':        'DND5E_RACES',
        'pathfinder_2e': 'PF2E_ANCESTRIES',
        'daggerheart':   'DAGGERHEART_ANCESTRIES',
    }
    race_db_attr = system_map.get(system_id, 'DND5E_RACES')
    race_db = getattr(_cr, race_db_attr, _cr.DND5E_RACES)

    console.print()
    console.print(Panel(
        '[bold cyan]⚔  Choose Your Race[/bold cyan]\n\n'
        '[white]Pick a race to see its full stat block — ASI bonuses, traits, proficiencies, and more.\n'
        'You can browse as many races as you like before deciding.[/white]\n'
        '[dim]World races (if any) were created for this specific setting.\n'
        'Standard races are also available regardless of the world.[/dim]',
        border_style='cyan',
    ))

    # Build combined option list: (display_label, race_name, race_data_or_None)
    options = []

    if generated_races:
        console.print('[bold yellow]── World Races (generated for this campaign) ──[/bold yellow]')
        for r in generated_races:
            asi_str = ', '.join(f'+{v} {k}' for k, v in r.get('asi', {}).items() if v > 0)
            label   = f'{r["name"]}  [dim cyan]({asi_str})[/dim cyan]' if asi_str else r['name']
            options.append((label, r['name'], r, '[World]'))

    if homebrew_races:
        console.print('[bold magenta]── Homebrew Races ──[/bold magenta]')
        for r in homebrew_races:
            options.append((f'{r["name"]} [dim](Homebrew)[/dim]', r['name'], r, '[Homebrew]'))

    if standard_races:
        if generated_races or homebrew_races:
            console.print('[bold white]── Standard Races ──[/bold white]')
        for r in standard_races:
            if 'other' not in r.lower():
                options.append((r, r, None, ''))

    options.append(('[dim]Other — type your own[/dim]', '__custom__', None, ''))

    while True:
        # Display the numbered list
        for i, (label, _name, _data, tag) in enumerate(options, 1):
            tag_str = f' [bold green]{tag}[/bold green]' if tag else ''
            console.print(f'  [dim]{i:2}.[/dim] {label}{tag_str}')

        console.print()
        raw = console.input('[bold white]  Enter number to view details (or confirm): [/bold white]').strip()

        if not raw.isdigit():
            console.print('  [red]Please enter a number.[/red]')
            continue

        idx = int(raw) - 1
        if not (0 <= idx < len(options)):
            console.print(f'  [red]Please enter 1–{len(options)}.[/red]')
            continue

        _label, race_name, race_data, _tag = options[idx]

        if race_name == '__custom__':
            custom = console.input('  Type your race: ').strip()
            if custom:
                return custom, None
            continue

        # Show the stat block
        if race_data:
            # Generated/homebrew race — use world_builder style display
            from world_builder import _show_race_detail as _wbrd
            _wbrd(console, race_data)
        else:
            # Standard race — look up from character_rules
            show_race_details_panel(console, race_name, system_id)

        confirm = console.input(
            f'\n[bold white]Play as [cyan]{race_name}[/cyan]? '
            f'(y = confirm / n = pick again / ? = see list again): [/bold white]'
        ).strip().lower()

        if confirm == 'y':
            console.print(f'  [green]✓ Race: {race_name}[/green]')
            return race_name, race_data
        elif confirm == '?':
            console.print()
        # 'n' or anything else → loop back and re-show menu


# ═══════════════════════════════════════════════════════════════════════════
# 9. PICK CLASS WITH FULL DETAILS
# ═══════════════════════════════════════════════════════════════════════════

def pick_class_with_details(
    console: Console,
    system_id: str,
    classes: list,
    role_label: str = 'Class',
) -> str:
    """
    Shows a numbered class/role menu. Selecting a class displays its FULL
    stat block (hit die, proficiencies, features, starting equipment) before
    asking for confirmation. Loops until confirmed.

    Returns the chosen class/role name string.
    """
    import character_rules as _cr

    system_map = {
        'dnd_5e':        'DND5E_CLASSES',
        'pathfinder_2e': 'PF2E_CLASSES',
        'daggerheart':   'DAGGERHEART_CLASSES',
    }
    class_db_attr = system_map.get(system_id, 'DND5E_CLASSES')
    class_db = getattr(_cr, class_db_attr, _cr.DND5E_CLASSES)

    console.print()
    console.print(Panel(
        f'[bold cyan]⚔  Choose Your {role_label}[/bold cyan]\n\n'
        '[white]Select a number to see the full class stat block — hit die, saves,\n'
        'armor, weapons, skills, and level-1 features — before you commit.[/white]\n'
        '[dim]Browse freely. You can look at as many as you like.[/dim]',
        border_style='cyan',
    ))

    # Add "Other" option if not already present
    display_classes = [c for c in classes if 'other' not in c.lower()]
    display_classes.append('Other (type your own)')

    while True:
        # Display numbered list
        for i, cls in enumerate(display_classes, 1):
            # Peek at whether we have data for quick hint
            data = class_db.get(cls, {})
            hit_die = data.get('hit_die', data.get('hp_per_level'))
            hint = f'  [dim](d{hit_die})[/dim]' if hit_die else ''
            console.print(f'  [dim]{i:2}.[/dim] {cls}{hint}')

        console.print()
        raw = console.input('[bold white]  Enter number to view details: [/bold white]').strip()

        if not raw.isdigit():
            console.print('  [red]Please enter a number.[/red]')
            continue

        idx = int(raw) - 1
        if not (0 <= idx < len(display_classes)):
            console.print(f'  [red]Please enter 1–{len(display_classes)}.[/red]')
            continue

        chosen_class = display_classes[idx]

        if 'other' in chosen_class.lower():
            custom = console.input(f'  Type your {role_label.lower()}: ').strip()
            if custom:
                return custom
            continue

        # Show the full stat block
        show_class_details_panel(console, chosen_class, system_id)

        confirm = console.input(
            f'\n[bold white]Play as a [cyan]{chosen_class}[/cyan]? '
            f'(y = confirm / n = pick again / ? = see list again): [/bold white]'
        ).strip().lower()

        if confirm == 'y':
            console.print(f'  [green]✓ {role_label}: {chosen_class}[/green]')
            return chosen_class
        elif confirm == '?':
            console.print()
        # 'n' → re-show list


# ═══════════════════════════════════════════════════════════════════════════
# 10. WORLD INFO DISPLAY FOR CHARACTER CREATION
# ═══════════════════════════════════════════════════════════════════════════

def display_world_info_for_character_creation(
    console: Console,
    world_lore: str,
    generated_races: list,
    system: dict,
) -> None:
    """
    Shows the player what they need to know about the world to make
    informed character choices, WITHOUT revealing secrets or hidden info.

    Covers:
      - What races/species exist and where they live
      - What factions/organizations the player could be part of
      - What classes/roles make sense in this world
      - What the social/political situation is at ground level
      - Any special rules about magic, tech, or society
    """
    import re

    if not world_lore:
        return

    # ── Strip ALL secret/GM-only content before showing anything ──────────
    # Stops at the next blank line so nothing after the secret block is eaten.
    SECRET_PATTERN = re.compile(
        r'\n*(WORLD\s+SECRET|GM[\s\-]+ONLY|HIDDEN\s+TRUTH|SECRET\s+TRUTH|THE\s+REAL\s+REASON)'
        r'[^\n]*\n'
        r'(?:(?!\n\n)[\s\S])*'
        r'\n*',
        re.IGNORECASE | re.MULTILINE
    )
    safe_lore = SECRET_PATTERN.sub('\n', world_lore).strip()

    # Also catch inline "KEY: value" style secrets from the backstory builder
    safe_lore = re.sub(
        r'(?im)^(WORLD\s+SECRET|GM[\s\-]+ONLY)[^\n]*\n.*?(?=\n[A-Z][A-Z\s]{3,}:|\Z)',
        '', safe_lore, flags=re.DOTALL
    ).strip()

    system_name = system.get('short_name', 'Fantasy')

    console.print()
    console.print(Panel(
        '[bold cyan]📖  World Guide — Character Creation[/bold cyan]\n\n'
        '[white]Here is what your character would know about the world they were born into.\n'
        'Secrets and hidden truths will be discovered through play.[/white]\n'
        '[dim]Use this to inform your race, class, background, and backstory choices.[/dim]',
        border_style='cyan',
        padding=(1, 2),
    ))

    # Print the cleaned lore as one block (it's already formatted prose)
    if safe_lore:
        console.print(f'[white]{safe_lore}[/white]')
        console.print()

    # Show generated races summary if available
    if generated_races:
        console.print(Panel(
            '[bold cyan]Races of This World[/bold cyan]\n\n'
            + '\n'.join(
                f'[bold white]• {r["name"]}:[/bold white] {r.get("description", "")[:120]}'
                + (f'\n  [cyan]ASI:[/cyan] {", ".join(f"+{v} {k}" for k, v in r.get("asi", {}).items() if v > 0)}'
                   f'  [cyan]Speed:[/cyan] {r.get("speed", 30)} ft  [cyan]Size:[/cyan] {r.get("size", "Medium")}'
                   if r.get('asi') else '')
                for r in generated_races
            ),
            border_style='dim cyan',
            padding=(0, 2),
        ))

    console.print('[dim]  ─────────────────────────────────────────────────────[/dim]')
    console.print('[dim]  Character creation will begin on the next screen.[/dim]')
    console.print()
    console.input('[bold white]  Press Enter when you are ready to create your character → [/bold white]')


# ═══════════════════════════════════════════════════════════════════════════
# 11. HOMEBREW RACE PROMPT (world-aware)
# ═══════════════════════════════════════════════════════════════════════════

def offer_homebrew_races_prompt(
    console: Console,
    system_id: str,
    world_lore: str = '',
) -> list:
    """
    Prompts the player to optionally create homebrew races by hand.
    Shown AFTER the world is generated and world races are offered,
    as a final option for players who want to define their own race
    using the detailed stat-builder form.

    Returns list of newly created homebrew race dicts (may be empty).
    """
    console.print()
    console.print(Panel(
        '[bold magenta]🧬  Homebrew Race Builder[/bold magenta]\n\n'
        '[white]Would you like to manually define a custom homebrew race for this campaign?[/white]\n'
        '[dim]This lets you define exact stats: ASI, traits, speed, darkvision, proficiencies, and languages.\n'
        'Homebrew races are saved permanently and will always appear in the race menu.[/dim]',
        border_style='magenta',
    ))

    if world_lore:
        console.print('[dim]  Tip: Your custom race will work best if it fits the world described above.[/dim]')
        console.print()

    answer = console.input('[bold white]Add a custom homebrew race? (y/n): [/bold white]').strip().lower()
    if answer != 'y':
        return []

    return run_custom_race_builder(console, system_id)


