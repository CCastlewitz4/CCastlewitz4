# wiki_scraper.py
# ─────────────────────────────────────────────────────────────────────────────
# Scrapes dnd5e.wikidot.com for live race, class, and subclass data.
#
# CONFIRMED URL STRUCTURE (verified via search results):
#   Class pages:    https://dnd5e.wikidot.com/fighter
#   Subclass pages: https://dnd5e.wikidot.com/fighter:battle-master
#                   https://dnd5e.wikidot.com/fighter:champion
#                   https://dnd5e.wikidot.com/wizard:evocation
#   Race pages:     https://dnd5e.wikidot.com/elf
#                   https://dnd5e.wikidot.com/dwarf
#
# CACHE STRATEGY:
#   First run → scrapes the wiki, saves to data/wiki_cache/dnd5e_data.json
#   All future sessions → loads from cache instantly (zero network needed)
#   Type "update wiki" in-game → forces a full fresh scrape
#
# FALLBACK:
#   If network is unavailable, libraries missing, or a page 404s — the game
#   falls back to hardcoded data in character_rules.py. Nothing ever breaks.
#
# REQUIRES: pip install requests beautifulsoup4  (added to requirements.txt)
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import re
import time

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR  = os.path.join(BASE_DIR, 'data', 'wiki_cache')
CACHE_FILE = os.path.join(CACHE_DIR, 'dnd5e_data.json')
BASE_URL   = 'https://dnd5e.wikidot.com'
DELAY      = 0.9   # seconds between requests — polite crawl rate


# ─────────────────────────────────────────────────────────────────────────────
# SUBCLASS REGISTRY
# All published + popular homebrew subclasses confirmed on the wiki.
# Format: class_name → [(display_name, url_slug, source_book), ...]
# ─────────────────────────────────────────────────────────────────────────────

SUBCLASS_REGISTRY = {
    'Artificer': [
        ('Alchemist',    'artificer:alchemist',   "Tasha's Cauldron of Everything"),
        ('Armorer',      'artificer:armorer',     "Tasha's Cauldron of Everything"),
        ('Artillerist',  'artificer:artillerist', "Tasha's Cauldron of Everything"),
        ('Battle Smith', 'artificer:battle-smith',"Tasha's Cauldron of Everything"),
    ],
    'Barbarian': [
        ('Ancestral Guardian', 'barbarian:ancestral-guardian', "Xanathar's Guide to Everything"),
        ('Battlerager',        'barbarian:battlerager',        "Sword Coast Adventurer's Guide"),
        ('Beast',              'barbarian:beast',              "Tasha's Cauldron of Everything"),
        ('Berserker',          'barbarian:berserker',          "Player's Handbook"),
        ('Giant',              'barbarian:giant',              "Bigby Presents: Glory of the Giants"),
        ('Storm Herald',       'barbarian:storm-herald',       "Xanathar's Guide to Everything"),
        ('Totem Warrior',      'barbarian:totem-warrior',      "Player's Handbook"),
        ('Wild Magic',         'barbarian:wild-magic',         "Tasha's Cauldron of Everything"),
        ('Zealot',             'barbarian:zealot',             "Xanathar's Guide to Everything"),
    ],
    'Bard': [
        ('College of Creation',  'bard:creation',  "Tasha's Cauldron of Everything"),
        ('College of Eloquence', 'bard:eloquence', "Tasha's Cauldron of Everything"),
        ('College of Glamour',   'bard:glamour',   "Xanathar's Guide to Everything"),
        ('College of Lore',      'bard:lore',      "Player's Handbook"),
        ('College of Spirits',   'bard:spirits',   "Van Richten's Guide to Ravenloft"),
        ('College of Swords',    'bard:swords',    "Xanathar's Guide to Everything"),
        ('College of Valor',     'bard:valor',     "Player's Handbook"),
        ('College of Whispers',  'bard:whispers',  "Xanathar's Guide to Everything"),
    ],
    'Cleric': [
        ('Arcana Domain',    'cleric:arcana',    "Sword Coast Adventurer's Guide"),
        ('Death Domain',     'cleric:death',     "Player's Handbook"),
        ('Forge Domain',     'cleric:forge',     "Xanathar's Guide to Everything"),
        ('Grave Domain',     'cleric:grave',     "Xanathar's Guide to Everything"),
        ('Knowledge Domain', 'cleric:knowledge', "Player's Handbook"),
        ('Life Domain',      'cleric:life',      "Player's Handbook"),
        ('Light Domain',     'cleric:light',     "Player's Handbook"),
        ('Nature Domain',    'cleric:nature',    "Player's Handbook"),
        ('Order Domain',     'cleric:order',     "Tasha's Cauldron of Everything"),
        ('Peace Domain',     'cleric:peace',     "Tasha's Cauldron of Everything"),
        ('Tempest Domain',   'cleric:tempest',   "Player's Handbook"),
        ('Trickery Domain',  'cleric:trickery',  "Player's Handbook"),
        ('Twilight Domain',  'cleric:twilight',  "Tasha's Cauldron of Everything"),
        ('War Domain',       'cleric:war',       "Player's Handbook"),
    ],
    'Druid': [
        ('Circle of Dreams',   'druid:dreams',   "Xanathar's Guide to Everything"),
        ('Circle of Land',     'druid:land',     "Player's Handbook"),
        ('Circle of Moon',     'druid:moon',     "Player's Handbook"),
        ('Circle of Shepherd', 'druid:shepherd', "Xanathar's Guide to Everything"),
        ('Circle of Spores',   'druid:spores',   "Tasha's Cauldron of Everything"),
        ('Circle of Stars',    'druid:stars',    "Tasha's Cauldron of Everything"),
        ('Circle of Wildfire', 'druid:wildfire', "Tasha's Cauldron of Everything"),
    ],
    'Fighter': [
        ('Arcane Archer',        'fighter:arcane-archer',        "Xanathar's Guide to Everything"),
        ('Battle Master',        'fighter:battle-master',        "Player's Handbook"),
        ('Cavalier',             'fighter:cavalier',             "Xanathar's Guide to Everything"),
        ('Champion',             'fighter:champion',             "Player's Handbook"),
        ('Echo Knight',          'fighter:echo-knight',          "Explorer's Guide to Wildemount"),
        ('Eldritch Knight',      'fighter:eldritch-knight',      "Player's Handbook"),
        ('Gunslinger',           'fighter:gunslinger',           "Homebrew (Matt Mercer)"),
        ('Psi Warrior',          'fighter:psi-warrior',          "Tasha's Cauldron of Everything"),
        ('Purple Dragon Knight', 'fighter:purple-dragon-knight', "Sword Coast Adventurer's Guide"),
        ('Rune Knight',          'fighter:rune-knight',          "Tasha's Cauldron of Everything"),
        ('Samurai',              'fighter:samurai',              "Xanathar's Guide to Everything"),
    ],
    'Monk': [
        ('Astral Self',    'monk:astral-self',    "Tasha's Cauldron of Everything"),
        ('Drunken Master', 'monk:drunken-master', "Xanathar's Guide to Everything"),
        ('Four Elements',  'monk:four-elements',  "Player's Handbook"),
        ('Kensei',         'monk:kensei',         "Xanathar's Guide to Everything"),
        ('Long Death',     'monk:long-death',     "Sword Coast Adventurer's Guide"),
        ('Mercy',          'monk:mercy',          "Tasha's Cauldron of Everything"),
        ('Open Hand',      'monk:open-hand',      "Player's Handbook"),
        ('Shadow',         'monk:shadow',         "Player's Handbook"),
        ('Sun Soul',       'monk:sun-soul',       "Xanathar's Guide to Everything"),
    ],
    'Paladin': [
        ('Oath of Conquest',     'paladin:conquest',    "Xanathar's Guide to Everything"),
        ('Oath of Devotion',     'paladin:devotion',    "Player's Handbook"),
        ('Oath of Glory',        'paladin:glory',       "Tasha's Cauldron of Everything"),
        ('Oath of Redemption',   'paladin:redemption',  "Xanathar's Guide to Everything"),
        ('Oath of the Ancients', 'paladin:ancients',    "Player's Handbook"),
        ('Oath of the Crown',    'paladin:crown',       "Sword Coast Adventurer's Guide"),
        ('Oath of the Watchers', 'paladin:watchers',    "Tasha's Cauldron of Everything"),
        ('Oath of Vengeance',    'paladin:vengeance',   "Player's Handbook"),
        ('Oathbreaker',          'paladin:oathbreaker', "Dungeon Master's Guide"),
    ],
    'Ranger': [
        ('Beast Master',   'ranger:beast-master',   "Player's Handbook"),
        ('Drakewarden',    'ranger:drakewarden',    "Fizban's Treasury of Dragons"),
        ('Fey Wanderer',   'ranger:fey-wanderer',   "Tasha's Cauldron of Everything"),
        ('Gloom Stalker',  'ranger:gloom-stalker',  "Xanathar's Guide to Everything"),
        ('Horizon Walker', 'ranger:horizon-walker', "Xanathar's Guide to Everything"),
        ('Hunter',         'ranger:hunter',         "Player's Handbook"),
        ('Monster Slayer', 'ranger:monster-slayer', "Xanathar's Guide to Everything"),
        ('Swarmkeeper',    'ranger:swarmkeeper',    "Tasha's Cauldron of Everything"),
    ],
    'Rogue': [
        ('Arcane Trickster', 'rogue:arcane-trickster', "Player's Handbook"),
        ('Assassin',         'rogue:assassin',          "Player's Handbook"),
        ('Inquisitive',      'rogue:inquisitive',       "Xanathar's Guide to Everything"),
        ('Mastermind',       'rogue:mastermind',        "Xanathar's Guide to Everything"),
        ('Phantom',          'rogue:phantom',           "Tasha's Cauldron of Everything"),
        ('Scout',            'rogue:scout',             "Xanathar's Guide to Everything"),
        ('Soulknife',        'rogue:soulknife',         "Tasha's Cauldron of Everything"),
        ('Swashbuckler',     'rogue:swashbuckler',      "Xanathar's Guide to Everything"),
        ('Thief',            'rogue:thief',             "Player's Handbook"),
    ],
    'Sorcerer': [
        ('Aberrant Mind',     'sorcerer:aberrant-mind',  "Tasha's Cauldron of Everything"),
        ('Clockwork Soul',    'sorcerer:clockwork-soul', "Tasha's Cauldron of Everything"),
        ('Divine Soul',       'sorcerer:divine-soul',    "Xanathar's Guide to Everything"),
        ('Draconic Bloodline','sorcerer:draconic',       "Player's Handbook"),
        ('Lunar Sorcery',     'sorcerer:lunar-sorcery',  "Dragonlance: Shadow of the Dragon Queen"),
        ('Shadow Magic',      'sorcerer:shadow',         "Xanathar's Guide to Everything"),
        ('Storm Sorcery',     'sorcerer:storm',          "Xanathar's Guide to Everything"),
        ('Wild Magic',        'sorcerer:wild-magic',     "Player's Handbook"),
    ],
    'Warlock': [
        ('The Archfey',       'warlock:archfey',        "Player's Handbook"),
        ('The Celestial',     'warlock:celestial',      "Xanathar's Guide to Everything"),
        ('The Fathomless',    'warlock:fathomless',     "Tasha's Cauldron of Everything"),
        ('The Fiend',         'warlock:fiend',          "Player's Handbook"),
        ('The Genie',         'warlock:genie',          "Tasha's Cauldron of Everything"),
        ('The Great Old One', 'warlock:great-old-one',  "Player's Handbook"),
        ('The Hexblade',      'warlock:hexblade',       "Xanathar's Guide to Everything"),
        ('The Undead',        'warlock:undead',         "Van Richten's Guide to Ravenloft"),
        ('The Undying',       'warlock:undying',        "Sword Coast Adventurer's Guide"),
    ],
    'Wizard': [
        ('Abjuration',       'wizard:abjuration',      "Player's Handbook"),
        ('Bladesinging',     'wizard:bladesinging',    "Tasha's Cauldron of Everything"),
        ('Chronurgy Magic',  'wizard:chronurgy',       "Explorer's Guide to Wildemount"),
        ('Conjuration',      'wizard:conjuration',     "Player's Handbook"),
        ('Divination',       'wizard:divination',      "Player's Handbook"),
        ('Enchantment',      'wizard:enchantment',     "Player's Handbook"),
        ('Evocation',        'wizard:evocation',       "Player's Handbook"),
        ('Graviturgy Magic', 'wizard:graviturgy',      "Explorer's Guide to Wildemount"),
        ('Illusion',         'wizard:illusion',        "Player's Handbook"),
        ('Necromancy',       'wizard:necromancy',      "Player's Handbook"),
        ('Order of Scribes', 'wizard:scribes',         "Tasha's Cauldron of Everything"),
        ('Transmutation',    'wizard:transmutation',   "Player's Handbook"),
        ('War Magic',        'wizard:war-magic',       "Xanathar's Guide to Everything"),
    ],
    'Blood Hunter': [
        ('Order of the Ghostslayer',  'blood-hunter:ghostslayer',  'Homebrew (Matt Mercer)'),
        ('Order of the Lycan',        'blood-hunter:lycan',        'Homebrew (Matt Mercer)'),
        ('Order of the Mutant',       'blood-hunter:mutant',       'Homebrew (Matt Mercer)'),
        ('Order of the Profane Soul', 'blood-hunter:profane-soul', 'Homebrew (Matt Mercer)'),
    ],
}

# Class main page slugs
CLASS_SLUGS = {
    'Artificer':    'artificer',
    'Barbarian':    'barbarian',
    'Bard':         'bard',
    'Cleric':       'cleric',
    'Druid':        'druid',
    'Fighter':      'fighter',
    'Monk':         'monk',
    'Paladin':      'paladin',
    'Ranger':       'ranger',
    'Rogue':        'rogue',
    'Sorcerer':     'sorcerer',
    'Warlock':      'warlock',
    'Wizard':       'wizard',
    'Blood Hunter': 'blood-hunter',
}

# Race page slugs (sub-races share a base page)
RACE_SLUGS = {
    'Human':               'human',
    'Elf':                 'elf',
    'High Elf':            'elf',
    'Wood Elf':            'elf',
    'Dark Elf (Drow)':     'elf',
    'Dwarf':               'dwarf',
    'Hill Dwarf':          'dwarf',
    'Mountain Dwarf':      'dwarf',
    'Halfling':            'halfling',
    'Lightfoot Halfling':  'halfling',
    'Stout Halfling':      'halfling',
    'Gnome':               'gnome',
    'Rock Gnome':          'gnome',
    'Forest Gnome':        'gnome',
    'Half-Elf':            'half-elf',
    'Half-Orc':            'half-orc',
    'Tiefling':            'tiefling',
    'Dragonborn':          'dragonborn',
    'Aasimar':             'aasimar',
    'Goliath':             'goliath',
    'Tabaxi':              'tabaxi',
    'Kenku':               'kenku',
    'Firbolg':             'firbolg',
    'Genasi':              'genasi',
    'Lizardfolk':          'lizardfolk',
    'Tortle':              'tortle',
}


# ─────────────────────────────────────────────────────────────────────────────
# HTTP HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _fetch(slug: str):
    """
    Fetch BASE_URL/slug and return a BeautifulSoup object, or None on failure.
    Never raises — callers always fall back to hardcoded data on None.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    url = f'{BASE_URL}/{slug}'
    try:
        r = requests.get(
            url, timeout=15,
            headers={'User-Agent': 'DnD-AI-GM/1.0 (personal use, educational project)'}
        )
        if r.status_code == 200:
            return BeautifulSoup(r.text, 'html.parser')
    except Exception:
        pass
    return None


def _page_text(soup) -> str:
    """Extract plain text from the main page-content div."""
    if not soup:
        return ''
    block = soup.find(id='page-content') or soup.find(class_='page-content')
    return block.get_text(separator='\n') if block else ''


def _clean(s: str) -> str:
    """Collapse whitespace and strip [edit] links."""
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'\[.*?\]', '', s)
    return s.strip()


# ─────────────────────────────────────────────────────────────────────────────
# SUBCLASS DESCRIPTION FETCHER
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_subclass_desc(slug: str) -> str:
    """
    Fetch a subclass page and return its opening flavour paragraph (≤300 chars).
    This is the text that describes *what the subclass is* thematically.
    """
    time.sleep(DELAY)
    soup = _fetch(slug)
    if not soup:
        return ''
    block = soup.find(id='page-content') or soup.find(class_='page-content')
    if not block:
        return ''
    for p in block.find_all('p'):
        text = _clean(p.get_text())
        if len(text) > 80:
            return (text[:297] + '...') if len(text) > 300 else text
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# CLASS PAGE PARSER
# ─────────────────────────────────────────────────────────────────────────────

def _parse_class(class_name: str) -> dict:
    """
    Scrape the main class page and all its subclass pages.
    Returns a dict with: hit_die, saves, armor, weapons, tools,
    skill_count, skill_choices, features, subclasses.
    """
    slug = CLASS_SLUGS.get(class_name, class_name.lower().replace(' ', '-'))
    print(f'  {class_name}', end='', flush=True)
    time.sleep(DELAY)
    soup = _fetch(slug)
    text = _page_text(soup)

    result = {
        'hit_die': 0, 'saves': [], 'armor': [], 'weapons': [],
        'tools': [], 'skill_count': 2, 'skill_choices': [],
        'features': [], 'subclasses': [], 'source': 'wiki',
    }

    if text:
        # Hit die — "1d10 per fighter level"
        m = re.search(r'Hit Dic?e?:?\s*1d(\d+)', text, re.I)
        if m:
            result['hit_die'] = int(m.group(1))

        # Saving throws — "Saving Throws: Strength, Constitution"
        m = re.search(r'Saving Throws?:?\s*([^\n]+)', text, re.I)
        if m:
            raw = m.group(1)
            for full, abbr in [('Strength','STR'), ('Dexterity','DEX'),
                               ('Constitution','CON'), ('Intelligence','INT'),
                               ('Wisdom','WIS'), ('Charisma','CHA')]:
                if full in raw:
                    result['saves'].append(abbr)

        # Armor — "Armor: All armor, shields"
        m = re.search(r'\nArmor:?\s*([^\n]+)', text, re.I)
        if m:
            val = _clean(m.group(1))
            if val.lower() not in ('none', ''):
                result['armor'] = [x.strip() for x in val.split(',') if x.strip()]

        # Weapons — "Weapons: Simple weapons, martial weapons"
        m = re.search(r'\nWeapons?:?\s*([^\n]+)', text, re.I)
        if m:
            val = _clean(m.group(1))
            if val.lower() != 'none':
                result['weapons'] = [x.strip() for x in val.split(',') if x.strip()]

        # Tools — "Tools: None" / "Tools: Thieves' tools"
        m = re.search(r'\nTools?:?\s*([^\n]+)', text, re.I)
        if m:
            val = _clean(m.group(1))
            if val.lower() not in ('none', ''):
                result['tools'] = [x.strip() for x in val.split(',') if x.strip()]

        # Skills — "Choose two from Acrobatics, Animal Handling..."
        m = re.search(r'Choose\s+(\w+)\s+(?:skills?\s+)?from[:\s]+([^\n]+)', text, re.I)
        if m:
            word_map = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7}
            result['skill_count'] = word_map.get(m.group(1).lower(), 2)
            raw = re.sub(r'\band\b', ',', m.group(2), flags=re.I)
            skills = [s.strip().rstrip('.') for s in raw.split(',')]
            result['skill_choices'] = [s for s in skills if 3 < len(s) < 40]

    # Subclasses — fetch each one individually
    subclasses = []
    entries = SUBCLASS_REGISTRY.get(class_name, [])
    for display_name, sub_slug, source_book in entries:
        print('.', end='', flush=True)
        desc = _fetch_subclass_desc(sub_slug)
        subclasses.append({
            'name':   display_name,
            'source': source_book,
            'desc':   desc,
        })
    result['subclasses'] = subclasses

    count = len(subclasses)
    print(f'  ✓  ({count} subclass{"es" if count != 1 else ""})')
    return result


# ─────────────────────────────────────────────────────────────────────────────
# RACE PAGE PARSER
# ─────────────────────────────────────────────────────────────────────────────

def _parse_race(race_name: str) -> dict:
    """
    Scrape a race page and return ASI, traits, languages, speed, darkvision.
    Sub-races that share a page (Elf / High Elf / Wood Elf) are handled by
    searching the page for the sub-race heading before parsing.
    """
    slug = RACE_SLUGS.get(race_name, race_name.lower().replace(' ', '-'))
    print(f'  {race_name}', end='', flush=True)
    time.sleep(DELAY)
    soup = _fetch(slug)
    text = _page_text(soup)

    result = {
        'asi': {}, 'traits': [], 'proficiencies': [], 'languages': [],
        'speed': 30, 'size': 'Medium', 'darkvision': False,
        'darkvision_range': 0, 'source': 'wiki',
    }

    if not text:
        print('  (failed)')
        return result

    # For sub-races sharing a page, isolate the relevant section
    sub_section_map = {
        'High Elf':           'High Elf',
        'Wood Elf':           'Wood Elf',
        'Dark Elf (Drow)':    'Dark Elf',
        'Hill Dwarf':         'Hill Dwarf',
        'Mountain Dwarf':     'Mountain Dwarf',
        'Lightfoot Halfling': 'Lightfoot',
        'Stout Halfling':     'Stout',
        'Rock Gnome':         'Rock Gnome',
        'Forest Gnome':       'Forest Gnome',
    }
    section = text
    if race_name in sub_section_map:
        keyword = sub_section_map[race_name]
        idx = text.find(keyword)
        if idx >= 0:
            section = text[idx:]

    # Ability Score Increases
    stats = [('Strength','STR'), ('Dexterity','DEX'), ('Constitution','CON'),
             ('Intelligence','INT'), ('Wisdom','WIS'), ('Charisma','CHA')]
    for full, abbr in stats:
        m = re.search(rf'{full}\s+score\s+increases?\s+by\s+(\d+)', section, re.I)
        if m:
            result['asi'][abbr] = int(m.group(1))

    # Speed
    m = re.search(r'Speed:?\s*(\d+)\s*feet', section, re.I)
    if m:
        result['speed'] = int(m.group(1))

    # Size
    if re.search(r'\bSmall\b', section):
        result['size'] = 'Small'
    elif re.search(r'\bLarge\b', section):
        result['size'] = 'Large'

    # Darkvision
    m = re.search(r'[Dd]arkvision[^\n]*?(\d+)\s*feet', section)
    if m:
        result['darkvision'] = True
        result['darkvision_range'] = int(m.group(1))

    # Languages
    m = re.search(r'Languages?:?\s*([^\n]+)', section, re.I)
    if m:
        lang_raw = _clean(m.group(1))
        parts = re.split(r',\s*|\s+and\s+', lang_raw)
        result['languages'] = [p.strip().rstrip('.') for p in parts
                                if 2 < len(p.strip()) < 50][:6]

    # Racial traits — collect feature headings from the HTML
    if soup:
        block = soup.find(id='page-content') or soup.find(class_='page-content')
        if block:
            skip_words = {'age', 'alignment', 'size', 'speed', 'language',
                          'subrace', 'subraces', 'ability score', 'contents'}
            traits = []
            for h in block.find_all(['h2', 'h3', 'h4']):
                heading = _clean(h.get_text())
                if any(sw in heading.lower() for sw in skip_words):
                    continue
                if not 3 < len(heading) < 60:
                    continue
                nxt = h.find_next_sibling('p')
                desc = (_clean(nxt.get_text())[:200] + '...') if nxt else ''
                traits.append(f'{heading}: {desc}' if desc else heading)
            result['traits'] = traits[:12]

    print('  ✓')
    return result


# ─────────────────────────────────────────────────────────────────────────────
# FULL SCRAPE
# ─────────────────────────────────────────────────────────────────────────────

def scrape_all() -> dict:
    """
    Scrapes every class (+ all subclasses) and every race from the wiki.
    Saves to CACHE_FILE. Returns the full data dict.
    Typically takes 3-5 minutes due to polite crawl rate.
    """
    try:
        import requests       # noqa
        from bs4 import BeautifulSoup  # noqa
    except ImportError:
        print('\n  ⚠  Missing libraries: pip install requests beautifulsoup4')
        print('  Falling back to built-in data.\n')
        return {}

    os.makedirs(CACHE_DIR, exist_ok=True)

    # Estimate time
    total_pages = (
        len(CLASS_SLUGS)
        + sum(len(v) for v in SUBCLASS_REGISTRY.values())
        + len(set(RACE_SLUGS.values()))
    )
    mins = round(total_pages * DELAY / 60, 1)

    print(f'\n┌──────────────────────────────────────────────────────────────────┐')
    print(f'│  Scraping dnd5e.wikidot.com — only runs once, cached forever      │')
    print(f'│  {total_pages} pages at {DELAY}s each ≈ {mins} min                              │')
    print(f'└──────────────────────────────────────────────────────────────────┘\n')

    data = {
        'races': {}, 'classes': {}, 'backgrounds': [],
        'scraped_at': _iso_now(), 'version': 4,
    }

    print('Classes + Subclasses:')
    for class_name in CLASS_SLUGS:
        data['classes'][class_name] = _parse_class(class_name)

    print('\nRaces:')
    for race_name in RACE_SLUGS:
        data['races'][race_name] = _parse_race(race_name)

    print('\nBackgrounds:')
    data['backgrounds'] = _parse_backgrounds()

    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    total_sc = sum(len(cd['subclasses']) for cd in data['classes'].values())
    print(f'\n✓  Saved to {CACHE_FILE}')
    print(f'   {len(data["races"])} races  ·  {len(data["classes"])} classes  ·  {total_sc} subclasses  ·  {len(data["backgrounds"])} backgrounds\n')
    return data


def _iso_now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec='seconds')


# ─────────────────────────────────────────────────────────────────────────────
# CACHE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

_mem: dict | None = None   # In-memory cache after first load


def _ensure_spell_cache(silent: bool = False):
    """
    Triggers spell_scraper.scrape_all_spells() if the spell cache does not
    exist yet. Runs silently; never raises on failure so the game always works.
    """
    try:
        import spell_scraper as _ss
        if not os.path.exists(_ss.CACHE_FILE):
            if not silent:
                print('[wiki_scraper] Building spell cache (first run, takes a few minutes)...')
            _ss.scrape_all_spells()
    except Exception:
        pass  # spell_scraper unavailable or offline — game still works fine


def load_or_scrape(silent: bool = False) -> dict:
    """
    Load wiki data from cache if it exists, otherwise scrape now.
    Returns {} if scraping fails (network unavailable).
    Also triggers the spell cache build on first run (non-blocking on failure).
    """
    global _mem
    if _mem is not None:
        return _mem

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                _mem = json.load(f)
            if not silent:
                print(f'  [dim]Wiki cache loaded ({_cache_age()})[/dim]')
            # Ensure spell cache also exists (skipped silently if already built)
            _ensure_spell_cache(silent=True)
            return _mem
        except Exception:
            pass  # corrupted — fall through to scrape

    # No valid cache — scrape everything then build spell cache
    _mem = scrape_all()
    _ensure_spell_cache(silent=silent)
    return _mem


def force_refresh() -> dict:
    """Delete cache and re-scrape everything including spells.
    Called by the in-game `update wiki` command."""
    global _mem
    _mem = None
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    result = scrape_all()
    _mem = result
    # Also force-refresh the spell cache
    try:
        from spell_scraper import scrape_all_spells
        scrape_all_spells(force=True)
    except Exception:
        pass
    return result


def is_cached() -> bool:
    return os.path.exists(CACHE_FILE)


def cache_info() -> dict:
    """Return metadata about the current cache."""
    if not os.path.exists(CACHE_FILE):
        return {'exists': False}
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
        total_sc = sum(len(cd.get('subclasses', [])) for cd in d.get('classes', {}).values())
        return {
            'exists':     True,
            'scraped_at': d.get('scraped_at', 'unknown'),
            'races':      len(d.get('races', {})),
            'classes':    len(d.get('classes', {})),
            'subclasses': total_sc,
            'age':        _cache_age(),
        }
    except Exception:
        return {'exists': True, 'corrupted': True}


def _cache_age() -> str:
    try:
        import time as t
        secs = t.time() - os.path.getmtime(CACHE_FILE)
        if secs < 3600:  return f'{int(secs // 60)}m ago'
        if secs < 86400: return f'{int(secs // 3600)}h ago'
        return f'{int(secs // 86400)}d ago'
    except Exception:
        return 'unknown'


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND PAGE PARSER
# ─────────────────────────────────────────────────────────────────────────────

# Known background slugs on dnd5e.wikidot.com
BACKGROUND_SLUGS = [
    'acolyte', 'charlatan', 'criminal', 'entertainer', 'folk-hero',
    'guild-artisan', 'hermit', 'noble', 'outlander', 'sage',
    'sailor', 'soldier', 'urchin', 'anthropologist', 'archaeologist',
    'city-watch', 'clan-crafter', 'cloistered-scholar', 'courtier',
    'faction-agent', 'far-traveler', 'haunted-one', 'inheritor',
    'knight-of-the-order', 'mercenary-veteran', 'urban-bounty-hunter',
    'uthgardt-tribe-member', 'waterdhavian-noble', 'feylost',
    'witchlight-hand', 'criminal-spy', 'gladiator', 'pirate',
    'knight', 'wanderer',
]


def _parse_backgrounds() -> list:
    """
    Scrape the dnd5e.wikidot.com/background index page to get a list
    of all backgrounds, then scrape each one for skill proficiencies,
    tool proficiencies, languages, equipment, and feature.
    Falls back gracefully to [] if the network is unavailable.
    """
    print('  backgrounds index', end='', flush=True)
    time.sleep(DELAY)
    soup = _fetch('background')
    backgrounds = []

    if not soup:
        print('  (failed — using hardcoded data)')
        return []

    # Extract background links from the index page
    block = soup.find(id='page-content') or soup.find(class_='page-content')
    if not block:
        print('  (no content — using hardcoded data)')
        return []

    links = []
    for a in block.find_all('a', href=True):
        href = a['href']
        # Background links look like /background:acolyte
        m = re.match(r'^/background:(.+)$', href)
        if m:
            slug = m.group(1)
            name = _clean(a.get_text())
            if name and len(name) > 2:
                links.append((name, f'background:{slug}'))

    # De-duplicate while preserving order
    seen = set()
    unique_links = []
    for name, slug in links:
        if slug not in seen:
            seen.add(slug)
            unique_links.append((name, slug))

    if not unique_links:
        # Fall back to our known slug list
        for slug in BACKGROUND_SLUGS:
            name = slug.replace('-', ' ').title()
            unique_links.append((name, f'background:{slug}'))

    print(f'  ({len(unique_links)} found)', end='', flush=True)

    for name, slug in unique_links:
        print('.', end='', flush=True)
        bg = _parse_one_background(name, slug)
        if bg:
            backgrounds.append(bg)

    print(f'  ✓  ({len(backgrounds)} backgrounds)')
    return backgrounds


def _parse_one_background(name: str, slug: str) -> dict | None:
    """Scrape a single background page and extract its data."""
    time.sleep(DELAY)
    soup = _fetch(slug)
    if not soup:
        return None

    text = _page_text(soup)
    if not text:
        return None

    result = {
        'name':               name,
        'skill_proficiencies': [],
        'tool_proficiencies':  [],
        'languages':           0,
        'equipment':           [],
        'feature':             '',
        'feature_desc':        '',
        'desc':                '',
        'source':              'dnd5e.wikidot.com',
    }

    # Grab opening description paragraph
    block = soup.find(id='page-content') or soup.find(class_='page-content')
    if block:
        for p in block.find_all('p'):
            t = _clean(p.get_text())
            if len(t) > 60 and 'skill' not in t.lower()[:20]:
                result['desc'] = t[:300]
                break

    # Skill Proficiencies — "Skill Proficiencies: Insight, Religion"
    m = re.search(r'Skill Proficiencies?:?\s*([^\n]+)', text, re.I)
    if m:
        raw = _clean(m.group(1))
        skills = re.split(r',\s*|\s+and\s+', raw)
        result['skill_proficiencies'] = [
            s.strip().rstrip('.') for s in skills if 3 < len(s.strip()) < 40
        ][:4]

    # Tool Proficiencies
    m = re.search(r'Tool Proficiencies?:?\s*([^\n]+)', text, re.I)
    if m:
        raw = _clean(m.group(1))
        if 'none' not in raw.lower():
            tools = re.split(r',\s*|\s+and\s+', raw)
            result['tool_proficiencies'] = [
                t.strip().rstrip('.') for t in tools if 2 < len(t.strip()) < 60
            ][:4]

    # Languages
    m = re.search(r'Languages?:?\s*([^\n]+)', text, re.I)
    if m:
        raw = _clean(m.group(1)).lower()
        if 'none' not in raw:
            nums = re.findall(r'\b(one|two|three|1|2|3)\b', raw)
            word_map = {'one': 1, 'two': 2, 'three': 3, '1': 1, '2': 2, '3': 3}
            result['languages'] = word_map.get(nums[0], 1) if nums else 1

    # Equipment — grab the list following the Equipment: heading
    m = re.search(r'Equipment:?\s*([^\n]+(?:\n(?!\n)[^\n]+)*)', text, re.I)
    if m:
        raw = m.group(1)
        items = re.split(r',\s*(?:and\s+)?|;\s*', raw)
        result['equipment'] = [
            _clean(item).rstrip('.') for item in items
            if 3 < len(_clean(item)) < 80
        ][:8]

    # Feature heading and description
    if block:
        for h in block.find_all(['h2', 'h3', 'h4']):
            heading = _clean(h.get_text())
            if 'feature' in heading.lower() or 'variant' in heading.lower():
                result['feature'] = heading.replace('Feature:', '').replace('Feature', '').strip()
                nxt = h.find_next_sibling('p')
                if nxt:
                    result['feature_desc'] = _clean(nxt.get_text())[:400]
                break

    return result


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC LOOKUP HELPERS  (used by character_rules.py and main.py)
# ─────────────────────────────────────────────────────────────────────────────

def get_subclasses(class_name: str) -> list[dict]:
    """
    Return subclass list for a class.
    Each item: {'name': str, 'source': str, 'desc': str}

    Tries the wiki cache first; falls back to SUBCLASS_REGISTRY names.
    Always returns something — never returns [].
    """
    data = load_or_scrape(silent=True)
    cls  = data.get('classes', {}).get(class_name, {})
    if cls.get('subclasses'):
        return cls['subclasses']
    # Fallback: registry names, no descriptions
    return [
        {'name': name, 'source': src, 'desc': ''}
        for name, _slug, src in SUBCLASS_REGISTRY.get(class_name, [])
    ]


def get_subclass_names(class_name: str) -> list[str]:
    """Just the names — for simple menus."""
    return [sc['name'] for sc in get_subclasses(class_name)]


def get_class_data(class_name: str) -> dict:
    """Return scraped class data dict, or {} if not cached."""
    return load_or_scrape(silent=True).get('classes', {}).get(class_name, {})


def get_race_data(race_name: str) -> dict:
    """Return scraped race data dict, or {} if not cached."""
    return load_or_scrape(silent=True).get('races', {}).get(race_name, {})


def get_backgrounds() -> list:
    """
    Return the list of scraped D&D 5e backgrounds.
    Each item: {'name', 'skill_proficiencies', 'tool_proficiencies',
                'languages', 'equipment', 'feature', 'feature_desc', 'desc', 'source'}
    Falls back to [] if not cached (character_setup.py uses hardcoded fallback).
    """
    return load_or_scrape(silent=True).get('backgrounds', [])


def get_spell_list(class_name: str, char_level: int, subclass: str = None) -> dict:
    """
    Returns available spells for a class/subclass at a given character level.
    Organised as: {spell_level_int: [(name, school, desc), ...]}

    Enforces subclass school restrictions (Arcane Trickster, Eldritch Knight).
    Falls back to hardcoded DND5E_SPELLS data if the spell cache is unavailable.

    Parameters:
      class_name  — e.g. 'Rogue', 'Wizard', 'Cleric'
      char_level  — Character level 1-20
      subclass    — e.g. 'Arcane Trickster', 'Life Domain', or None
    """
    try:
        from spell_scraper import get_available_spells
        result = get_available_spells(class_name, char_level, subclass)
        if result:
            return result
    except ImportError:
        pass

    # Hardcoded fallback
    try:
        from spell_feature_picker import DND5E_SPELLS
        class_key = class_name.split('(')[0].strip()
        sub_key   = (subclass or '').split('(')[0].strip()
        lookup    = DND5E_SPELLS.get(class_key) or DND5E_SPELLS.get(sub_key, {})
        return {int(k): list(v) for k, v in lookup.items()}
    except Exception:
        return {}


def get_subclass_spell_context(class_name: str, subclass: str, char_level: int) -> str:
    """
    Returns a formatted string summarising a character's spell situation for
    injection into the DM's system prompt.

    Includes school restrictions, accessible spell levels, auto-granted bonus
    spells, and what new spells become available at the next level up.

    Parameters:
      class_name  — Character's class
      subclass    — Character's subclass (or None)
      char_level  — Current character level
    """
    try:
        from spell_scraper import build_spell_context_for_dm
        return build_spell_context_for_dm(class_name, subclass, char_level)
    except ImportError:
        pass

    # Minimal fallback
    spells = get_spell_list(class_name, char_level, subclass)
    if not spells:
        return f'{class_name} has no spell access yet at level {char_level}.'
    max_lvl = max(spells.keys())
    total   = sum(len(v) for v in spells.values())
    return (
        f'{class_name} ({subclass or "base"}) at level {char_level}: '
        f'Access to spell levels 0–{max_lvl} ({total} spells available).'
    )


def update_spell_cache(classes: list = None):
    """
    Forces a fresh spell data scrape for the specified classes (or all).
    Called by the in-game 'update wiki' command to refresh spell data.

    Parameters:
      classes — List of class names to update, e.g. ['Wizard', 'Cleric'].
                None refreshes all classes.
    """
    try:
        from spell_scraper import scrape_all_spells
        scrape_all_spells(force=True, classes=classes)
        print('[wiki_scraper] Spell cache updated successfully.')
    except ImportError:
        print('[wiki_scraper] spell_scraper module not found.')
    except Exception as e:
        print(f'[wiki_scraper] Spell cache update failed: {e}')
