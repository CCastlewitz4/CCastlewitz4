# spell_scraper.py  —  Open5e API VERSION
# ─────────────────────────────────────────────────────────────────────────────
# Fetches D&D 5e spell data from the Open5e REST API (api.open5e.com).
#
# WHY THIS INSTEAD OF WIKIDOT SCRAPING:
#   dnd5e.wikidot.com renders its spell list pages via JavaScript after the
#   initial HTML load, so requests + BeautifulSoup only ever see an empty
#   skeleton — no spells. The Open5e API is a purpose-built free JSON API
#   that returns everything in clean structured responses, no parsing needed.
#
# API DETAILS:
#   Base URL : https://api.open5e.com/v1/spells/
#   Free      — no API key, no account required
#   Paginated — each page returns up to 500 results with a 'next' URL
#   We fetch from multiple document slugs to maximise spell coverage:
#     wotc-srd = official 5e SRD (~300 core spells)
#     a5e      = Level Up: Advanced 5e (fills in most remaining PHB spells)
#     tce      = Tasha's Cauldron of Everything
#     xgte     = Xanathar's Guide to Everything
#
# PALADIN / RANGER NOTE:
#   Open5e under-tags these classes — many PHB spells are only tagged as
#   cleric/druid in the API. After the API fetch we merge in hardcoded
#   PALADIN_SPELL_LIST and RANGER_SPELL_LIST, pulling full spell details
#   (school, desc, etc.) from the API pool where available.
#
# CACHE FORMAT  (data/wiki_cache/spells_cache.json):
#   {
#     "Wizard":   { "0": [spell_dict, ...], "1": [...], ... },
#     "Cleric":   { ... },
#     ...
#   }
#   Each spell_dict: name, level, school, casting_time, range, components,
#   duration, concentration, ritual, desc, higher_levels, source, spell_lists
#
# USAGE:
#   python spell_scraper.py --fetch           # fetch from API + cache
#   python spell_scraper.py --fetch --force   # force full re-fetch
#   python spell_scraper.py                   # test with cached data
#
# REQUIRES: pip install requests
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import re
import time

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR  = os.path.join(BASE_DIR, "data", "wiki_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "spells_cache.json")

API_BASE  = "https://api.open5e.com/v1/spells/"
API_SLUGS = ["wotc-srd", "a5e", "tce", "xgte"]
PAGE_SIZE = 500
DELAY     = 0.3

os.makedirs(CACHE_DIR, exist_ok=True)

# ── Class name mapping ─────────────────────────────────────────────────────
# Open5e returns lowercase class names in spell_lists[]; we map to title case.
CLASS_NAMES = {
    "bard":      "Bard",
    "cleric":    "Cleric",
    "druid":     "Druid",
    "paladin":   "Paladin",
    "ranger":    "Ranger",
    "sorcerer":  "Sorcerer",
    "warlock":   "Warlock",
    "wizard":    "Wizard",
    "artificer": "Artificer",
}

SUBCLASS_SPELL_SOURCE = {
    "Arcane Trickster": "Wizard",
    "Eldritch Knight":  "Wizard",
}

# ── Hardcoded class spell lists ────────────────────────────────────────────
# Open5e's API under-tags several classes because it only knows what's in its
# source documents (wotc-srd, a5e, etc.), and many PHB spells are tagged as
# cleric/wizard only rather than also paladin/ranger.
#
# These lists are the authoritative PHB + TCE spell lists for each class.
# Format: { spell_level_int: [spell_name, ...] }
# The names must match exactly what the Open5e API returns so we can look up
# the full spell dict (school, description, etc.) from the API data pool.
# Spells not found in the API pool get a minimal stub entry.

PALADIN_SPELL_LIST: dict[int, list[str]] = {
    1: [
        "Bless", "Command", "Compelled Duel", "Cure Wounds",
        "Detect Evil and Good", "Detect Magic", "Detect Poison and Disease",
        "Divine Favor", "Heroism", "Protection from Evil and Good",
        "Purify Food and Drink", "Searing Smite", "Shield of Faith",
        "Thunderous Smite", "Wrathful Smite",
    ],
    2: [
        "Aid", "Branding Smite", "Find Steed", "Gentle Repose",
        "Lesser Restoration", "Locate Object", "Magic Weapon",
        "Prayer of Healing", "Protection from Poison", "Warding Bond",
        "Zone of Truth",
    ],
    3: [
        "Aura of Vitality", "Blinding Smite", "Create Food and Water",
        "Crusader's Mantle", "Daylight", "Dispel Magic",
        "Elemental Weapon", "Magic Circle", "Remove Curse", "Revivify",
    ],
    4: [
        "Aura of Life", "Aura of Purity", "Banishment",
        "Death Ward", "Find Greater Steed", "Locate Creature",
        "Staggering Smite",
    ],
    5: [
        "Banishing Smite", "Circle of Power", "Destructive Wave",
        "Dispel Evil and Good", "Geas", "Holy Weapon", "Raise Dead",
        "Summon Celestial",
    ],
}

RANGER_SPELL_LIST: dict[int, list[str]] = {
    1: [
        "Alarm", "Animal Friendship", "Cure Wounds", "Detect Magic",
        "Detect Poison and Disease", "Ensnaring Strike", "Fog Cloud",
        "Goodberry", "Hail of Thorns", "Hunter's Mark", "Jump",
        "Longstrider", "Speak with Animals",
    ],
    2: [
        "Animal Messenger", "Barkskin", "Beast Sense", "Cordon of Arrows",
        "Darkvision", "Find Traps", "Gust of Wind", "Lesser Restoration",
        "Locate Animals or Plants", "Locate Object", "Magic Weapon",
        "Pass Without Trace", "Protection from Poison", "Silence",
        "Spike Growth", "Summon Beast",
    ],
    3: [
        "Conjure Animals", "Conjure Barrage", "Daylight", "Lightning Arrow",
        "Nondetection", "Plant Growth", "Protection from Energy",
        "Speak with Plants", "Water Breathing", "Water Walk", "Wind Wall",
    ],
    4: [
        "Conjure Woodland Beings", "Freedom of Movement",
        "Grasping Vine", "Locate Creature", "Stoneskin",
        "Summon Elemental",
    ],
    5: [
        "Commune with Nature", "Conjure Volley", "Steel Wind Strike",
        "Swift Quiver", "Tree Stride",
    ],
}

# School restrictions NEVER apply to cantrips (PHB rule).
SUBCLASS_RESTRICTIONS = {
    ("Rogue",   "Arcane Trickster"): {
        "source":              "Wizard",
        "schools":             ["Enchantment", "Illusion"],
        "free_picks":          2,
        "guaranteed_cantrips": ["Mage Hand"],
        "note": (
            "Wizard spells only. Leveled spells must be Enchantment or Illusion, "
            "except 2 free picks from any school. "
            "Cantrips are chosen freely. Mage Hand is always known."
        ),
    },
    ("Fighter", "Eldritch Knight"): {
        "source":              "Wizard",
        "schools":             ["Abjuration", "Evocation"],
        "free_picks":          3,
        "guaranteed_cantrips": [],
        "note": (
            "Wizard spells only. Leveled spells must be Abjuration or Evocation, "
            "except 3 free picks from any school. Cantrips are chosen freely."
        ),
    },
}

SUBCLASS_BONUS_SPELLS = {
    # Cleric Domains
    ("Cleric", "Arcana Domain"):    [
        ("1","Detect Magic"),        ("1","Magic Missile"),
        ("3","Magic Weapon"),        ("3","Nystul's Magic Aura"),
        ("5","Arcane Eye"),          ("5","Leomund's Secret Chest"),
        ("7","Planar Binding"),      ("7","Teleportation Circle"),
        ("9","Gate"),                ("9","Wish"),
    ],
    ("Cleric", "Death Domain"):     [
        ("1","False Life"),          ("1","Ray of Sickness"),
        ("3","Blindness/Deafness"),  ("3","Ray of Enfeeblement"),
        ("5","Animate Dead"),        ("5","Vampiric Touch"),
        ("7","Blight"),              ("7","Death Ward"),
        ("9","Antilife Shell"),      ("9","Cloudkill"),
    ],
    ("Cleric", "Forge Domain"):     [
        ("1","Identify"),            ("1","Searing Smite"),
        ("3","Heat Metal"),          ("3","Magic Weapon"),
        ("5","Elemental Weapon"),    ("5","Protection from Energy"),
        ("7","Fabricate"),           ("7","Wall of Fire"),
        ("9","Animate Objects"),     ("9","Creation"),
    ],
    ("Cleric", "Grave Domain"):     [
        ("1","Bane"),                ("1","False Life"),
        ("3","Gentle Repose"),       ("3","Ray of Enfeeblement"),
        ("5","Revivify"),            ("5","Vampiric Touch"),
        ("7","Blight"),              ("7","Death Ward"),
        ("9","Antilife Shell"),      ("9","Raise Dead"),
    ],
    ("Cleric", "Knowledge Domain"): [
        ("1","Command"),             ("1","Identify"),
        ("3","Augury"),              ("3","Suggestion"),
        ("5","Nondetection"),        ("5","Speak with Dead"),
        ("7","Arcane Eye"),          ("7","Confusion"),
        ("9","Legend Lore"),         ("9","Scrying"),
    ],
    ("Cleric", "Life Domain"):      [
        ("1","Bless"),               ("1","Cure Wounds"),
        ("3","Lesser Restoration"),  ("3","Spiritual Weapon"),
        ("5","Beacon of Hope"),      ("5","Revivify"),
        ("7","Death Ward"),          ("7","Guardian of Faith"),
        ("9","Mass Cure Wounds"),    ("9","Raise Dead"),
    ],
    ("Cleric", "Light Domain"):     [
        ("1","Burning Hands"),       ("1","Faerie Fire"),
        ("3","Flaming Sphere"),      ("3","Scorching Ray"),
        ("5","Daylight"),            ("5","Fireball"),
        ("7","Guardian of Faith"),   ("7","Wall of Fire"),
        ("9","Flame Strike"),        ("9","Scrying"),
    ],
    ("Cleric", "Nature Domain"):    [
        ("1","Animal Friendship"),   ("1","Speak with Animals"),
        ("3","Barkskin"),            ("3","Spike Growth"),
        ("5","Plant Growth"),        ("5","Wind Wall"),
        ("7","Dominate Beast"),      ("7","Grasping Vine"),
        ("9","Insect Plague"),       ("9","Tree Stride"),
    ],
    ("Cleric", "Order Domain"):     [
        ("1","Command"),             ("1","Heroism"),
        ("3","Hold Person"),         ("3","Zone of Truth"),
        ("5","Mass Healing Word"),   ("5","Slow"),
        ("7","Compulsion"),          ("7","Locate Creature"),
        ("9","Commune"),             ("9","Dominate Person"),
    ],
    ("Cleric", "Peace Domain"):     [
        ("1","Heroism"),             ("1","Sanctuary"),
        ("3","Aid"),                 ("3","Warding Bond"),
        ("5","Beacon of Hope"),      ("5","Sending"),
        ("7","Aura of Purity"),      ("7","Otiluke's Resilient Sphere"),
        ("9","Greater Restoration"), ("9","Rary's Telepathic Bond"),
    ],
    ("Cleric", "Tempest Domain"):   [
        ("1","Fog Cloud"),           ("1","Thunderwave"),
        ("3","Gust of Wind"),        ("3","Shatter"),
        ("5","Call Lightning"),      ("5","Sleet Storm"),
        ("7","Control Water"),       ("7","Ice Storm"),
        ("9","Destructive Wave"),    ("9","Insect Plague"),
    ],
    ("Cleric", "Trickery Domain"):  [
        ("1","Charm Person"),        ("1","Disguise Self"),
        ("3","Mirror Image"),        ("3","Pass Without Trace"),
        ("5","Blink"),               ("5","Dispel Magic"),
        ("7","Dimension Door"),      ("7","Polymorph"),
        ("9","Dominate Person"),     ("9","Modify Memory"),
    ],
    ("Cleric", "Twilight Domain"):  [
        ("1","Faerie Fire"),         ("1","Sleep"),
        ("3","Moonbeam"),            ("3","See Invisibility"),
        ("5","Aura of Vitality"),    ("5","Leomund's Tiny Hut"),
        ("7","Aura of Life"),        ("7","Greater Invisibility"),
        ("9","Circle of Power"),     ("9","Mislead"),
    ],
    ("Cleric", "War Domain"):       [
        ("1","Divine Favor"),        ("1","Shield of Faith"),
        ("3","Magic Weapon"),        ("3","Spiritual Weapon"),
        ("5","Crusader's Mantle"),   ("5","Spirit Guardians"),
        ("7","Freedom of Movement"), ("7","Stoneskin"),
        ("9","Flame Strike"),        ("9","Hold Monster"),
    ],
    # Paladin Oaths
    ("Paladin","Oath of Conquest"):     [
        ("3","Armor of Agathys"),    ("3","Command"),
        ("5","Hold Person"),         ("5","Spiritual Weapon"),
        ("9","Bestow Curse"),        ("9","Fear"),
        ("13","Dominate Beast"),     ("13","Stoneskin"),
        ("17","Cloudkill"),          ("17","Dominate Person"),
    ],
    ("Paladin","Oath of Devotion"):     [
        ("3","Protection from Evil and Good"), ("3","Sanctuary"),
        ("5","Lesser Restoration"),  ("5","Zone of Truth"),
        ("9","Beacon of Hope"),      ("9","Dispel Magic"),
        ("13","Freedom of Movement"),("13","Guardian of Faith"),
        ("17","Commune"),            ("17","Flame Strike"),
    ],
    ("Paladin","Oath of Glory"):        [
        ("3","Guiding Bolt"),        ("3","Heroism"),
        ("5","Enhance Ability"),     ("5","Magic Weapon"),
        ("9","Haste"),               ("9","Protection from Energy"),
        ("13","Compulsion"),         ("13","Freedom of Movement"),
        ("17","Legend Lore"),        ("17","Yolande's Regal Presence"),
    ],
    ("Paladin","Oath of Redemption"):   [
        ("3","Sanctuary"),           ("3","Sleep"),
        ("5","Calm Emotions"),       ("5","Hold Person"),
        ("9","Counterspell"),        ("9","Hypnotic Pattern"),
        ("13","Otiluke's Resilient Sphere"), ("13","Stoneskin"),
        ("17","Hold Monster"),       ("17","Wall of Force"),
    ],
    ("Paladin","Oath of the Ancients"): [
        ("3","Ensnaring Strike"),    ("3","Speak with Animals"),
        ("5","Moonbeam"),            ("5","Misty Step"),
        ("9","Plant Growth"),        ("9","Protection from Energy"),
        ("13","Ice Storm"),          ("13","Stoneskin"),
        ("17","Commune with Nature"),("17","Tree Stride"),
    ],
    ("Paladin","Oath of the Crown"):    [
        ("3","Command"),             ("3","Compelled Duel"),
        ("5","Warding Bond"),        ("5","Zone of Truth"),
        ("9","Aura of Vitality"),    ("9","Spirit Guardians"),
        ("13","Banishment"),         ("13","Guardian of Faith"),
        ("17","Circle of Power"),    ("17","Geas"),
    ],
    ("Paladin","Oath of the Watchers"): [
        ("3","Alarm"),               ("3","Detect Magic"),
        ("5","Moonbeam"),            ("5","See Invisibility"),
        ("9","Counterspell"),        ("9","Nondetection"),
        ("13","Aura of Purity"),     ("13","Banishment"),
        ("17","Hold Monster"),       ("17","Scrying"),
    ],
    ("Paladin","Oath of Vengeance"):    [
        ("3","Bane"),                ("3","Hunter's Mark"),
        ("5","Hold Person"),         ("5","Misty Step"),
        ("9","Haste"),               ("9","Protection from Energy"),
        ("13","Banishment"),         ("13","Dimension Door"),
        ("17","Hold Monster"),       ("17","Scrying"),
    ],
    ("Paladin","Oathbreaker"):          [
        ("3","Hellish Rebuke"),      ("3","Inflict Wounds"),
        ("5","Crown of Madness"),    ("5","Darkness"),
        ("9","Animate Dead"),        ("9","Bestow Curse"),
        ("13","Blight"),             ("13","Confusion"),
        ("17","Contagion"),          ("17","Dominate Person"),
    ],
    # Ranger Conclaves
    ("Ranger","Fey Wanderer"):    [
        ("3","Charm Person"),        ("5","Misty Step"),
        ("9","Dispel Magic"),        ("13","Dimension Door"),
        ("17","Mislead"),
    ],
    ("Ranger","Gloom Stalker"):   [
        ("3","Disguise Self"),       ("5","Rope Trick"),
        ("9","Fear"),                ("13","Greater Invisibility"),
        ("17","Seeming"),
    ],
    ("Ranger","Horizon Walker"):  [
        ("3","Protection from Evil and Good"), ("5","Misty Step"),
        ("9","Haste"),               ("13","Banishment"),
        ("17","Teleportation Circle"),
    ],
    ("Ranger","Monster Slayer"):  [
        ("3","Protection from Evil and Good"), ("5","Zone of Truth"),
        ("9","Magic Circle"),        ("13","Banishment"),
        ("17","Hold Monster"),
    ],
    # Warlock Patrons
    ("Warlock","The Archfey"):       [
        ("1","Faerie Fire"),         ("1","Sleep"),
        ("3","Calm Emotions"),       ("3","Phantasmal Force"),
        ("5","Blink"),               ("5","Plant Growth"),
        ("7","Dominate Beast"),      ("7","Greater Invisibility"),
        ("9","Dominate Person"),     ("9","Seeming"),
    ],
    ("Warlock","The Celestial"):     [
        ("1","Cure Wounds"),         ("1","Guiding Bolt"),
        ("3","Flaming Sphere"),      ("3","Lesser Restoration"),
        ("5","Daylight"),            ("5","Revivify"),
        ("7","Guardian of Faith"),   ("7","Wall of Fire"),
        ("9","Flame Strike"),        ("9","Scrying"),
    ],
    ("Warlock","The Fathomless"):    [
        ("1","Create or Destroy Water"), ("1","Thunderwave"),
        ("3","Gust of Wind"),        ("3","Silence"),
        ("5","Lightning Bolt"),      ("5","Sleet Storm"),
        ("7","Control Water"),       ("7","Summon Elemental"),
        ("9","Cone of Cold"),        ("9","Commune with Nature"),
    ],
    ("Warlock","The Fiend"):         [
        ("1","Burning Hands"),       ("1","Command"),
        ("3","Blindness/Deafness"),  ("3","Scorching Ray"),
        ("5","Fireball"),            ("5","Stinking Cloud"),
        ("7","Fire Shield"),         ("7","Wall of Fire"),
        ("9","Flame Strike"),        ("9","Hallow"),
    ],
    ("Warlock","The Genie"):         [
        ("1","Detect Evil and Good"), ("1","Primordial Ward"),
        ("3","Phantasmal Force"),    ("3","Tongues"),
        ("5","Create Food and Water"),("5","Gaseous Form"),
        ("7","Phantasmal Killer"),   ("7","Private Sanctum"),
        ("9","Creation"),            ("9","Wish"),
    ],
    ("Warlock","The Great Old One"): [
        ("1","Dissonant Whispers"),  ("1","Tasha's Hideous Laughter"),
        ("3","Detect Thoughts"),     ("3","Phantasmal Force"),
        ("5","Clairvoyance"),        ("5","Sending"),
        ("7","Dominate Beast"),      ("7","Evard's Black Tentacles"),
        ("9","Dominate Person"),     ("9","Telekinesis"),
    ],
    ("Warlock","The Hexblade"):      [
        ("1","Shield"),              ("1","Wrathful Smite"),
        ("3","Blur"),                ("3","Branding Smite"),
        ("5","Blink"),               ("5","Elemental Weapon"),
        ("7","Phantasmal Killer"),   ("7","Staggering Smite"),
        ("9","Banishing Smite"),     ("9","Cone of Cold"),
    ],
    ("Warlock","The Undead"):        [
        ("1","Bane"),                ("1","False Life"),
        ("3","Blindness/Deafness"),  ("3","Phantasmal Force"),
        ("5","Phantom Steed"),       ("5","Speak with Dead"),
        ("7","Death Ward"),          ("7","Greater Invisibility"),
        ("9","Antilife Shell"),      ("9","Cloudkill"),
    ],
    ("Warlock","The Undying"):       [
        ("1","False Life"),          ("1","Ray of Sickness"),
        ("3","Blindness/Deafness"),  ("3","Silence"),
        ("5","Feign Death"),         ("5","Speak with Dead"),
        ("7","Aura of Life"),        ("7","Death Ward"),
        ("9","Contagion"),           ("9","Legend Lore"),
    ],
    # Sorcerer Subclasses
    ("Sorcerer","Aberrant Mind"):    [
        ("1","Arms of Hadar"),       ("1","Dissonant Whispers"),
        ("3","Calm Emotions"),       ("3","Detect Thoughts"),
        ("5","Hunger of Hadar"),     ("5","Sending"),
        ("7","Evard's Black Tentacles"), ("7","Summon Aberration"),
        ("9","Modify Memory"),       ("9","Rary's Telepathic Bond"),
    ],
    ("Sorcerer","Clockwork Soul"):   [
        ("1","Alarm"),               ("1","Protection from Evil and Good"),
        ("3","Aid"),                 ("3","Lesser Restoration"),
        ("5","Dispel Magic"),        ("5","Protection from Energy"),
        ("7","Freedom of Movement"), ("7","Summon Construct"),
        ("9","Dispel Evil and Good"),("9","Wall of Force"),
    ],
}

DRUID_LAND_BONUS_SPELLS = {
    "Arctic":    {3:["Hold Person","Spike Growth"], 5:["Sleet Storm","Slow"],
                  7:["Freedom of Movement","Ice Storm"], 9:["Commune with Nature","Cone of Cold"]},
    "Coast":     {3:["Mirror Image","Misty Step"], 5:["Water Breathing","Water Walk"],
                  7:["Control Water","Freedom of Movement"], 9:["Conjure Elemental","Scrying"]},
    "Desert":    {3:["Blur","Silence"], 5:["Create Food and Water","Protection from Energy"],
                  7:["Blight","Hallucinatory Terrain"], 9:["Insect Plague","Wall of Stone"]},
    "Forest":    {3:["Barkskin","Spider Climb"], 5:["Call Lightning","Plant Growth"],
                  7:["Divination","Freedom of Movement"], 9:["Commune with Nature","Tree Stride"]},
    "Grassland": {3:["Invisibility","Pass Without Trace"], 5:["Daylight","Haste"],
                  7:["Divination","Freedom of Movement"], 9:["Dream","Insect Plague"]},
    "Mountain":  {3:["Spider Climb","Spike Growth"], 5:["Lightning Bolt","Meld into Stone"],
                  7:["Stone Shape","Stoneskin"], 9:["Passwall","Wall of Stone"]},
    "Swamp":     {3:["Darkness","Melf's Acid Arrow"], 5:["Water Walk","Stinking Cloud"],
                  7:["Freedom of Movement","Locate Creature"], 9:["Insect Plague","Scrying"]},
    "Underdark": {3:["Spider Climb","Web"], 5:["Gaseous Form","Stinking Cloud"],
                  7:["Greater Invisibility","Stone Shape"], 9:["Cloudkill","Insect Plague"]},
}

SPELL_LEVEL_ACCESS = {
    "full":  {1:[0,1], 3:[0,1,2], 5:[0,1,2,3], 7:[0,1,2,3,4], 9:[0,1,2,3,4,5],
              11:[0,1,2,3,4,5,6], 13:[0,1,2,3,4,5,6,7], 15:[0,1,2,3,4,5,6,7,8],
              17:[0,1,2,3,4,5,6,7,8,9]},
    "half":  {2:[1], 5:[1,2], 9:[1,2,3], 13:[1,2,3,4], 17:[1,2,3,4,5]},
    "third": {3:[0,1], 7:[0,1,2], 13:[0,1,2,3], 19:[0,1,2,3,4]},
    "pact":  {1:[0,1], 3:[0,1,2], 5:[0,1,2,3], 7:[0,1,2,3,4], 9:[0,1,2,3,4,5]},
}

CASTER_TYPE = {
    "Bard":     "full",  "Cleric":   "full",  "Druid":    "full",
    "Sorcerer": "full",  "Wizard":   "full",  "Artificer":"half",
    "Paladin":  "half",  "Ranger":   "half",  "Warlock":  "pact",
    "Arcane Trickster": "third",
    "Eldritch Knight":  "third",
}


# =============================================================================
# CACHE HELPERS
# =============================================================================

def _int_keys(cache: dict) -> dict:
    return {cls: {int(k): v for k, v in lvls.items()} for cls, lvls in cache.items()}

def _load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return _int_keys(json.load(f))
    except Exception:
        return {}

def _is_cache_populated() -> bool:
    """Returns True only if the cache file exists AND contains at least one spell."""
    cache = _load_cache()
    if not cache:
        return False
    return any(
        any(len(spells) > 0 for spells in lvls.values())
        for lvls in cache.values()
    )

def _accessible_levels(char_level: int, caster_type: str) -> list:
    table  = SPELL_LEVEL_ACCESS.get(caster_type, SPELL_LEVEL_ACCESS["full"])
    result = []
    for threshold in sorted(table):
        if threshold <= char_level:
            result = table[threshold]
    return result


# =============================================================================
# OPEN5E API FETCH
# =============================================================================

def _api_fetch_all_spells() -> list[dict]:
    """
    Fetches all spells from the Open5e API across all configured document slugs.
    Handles pagination automatically. Returns a flat list of raw API spell dicts.
    Deduplicates by name so the same spell from multiple sources appears once.
    """
    try:
        import requests
    except ImportError:
        print("[SpellScraper] Missing dependency: pip install requests")
        return []

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    all_spells  = []
    seen_names: set[str] = set()

    for slug in API_SLUGS:
        url      = f"{API_BASE}?limit={PAGE_SIZE}&document__slug={slug}&format=json"
        page_num = 1

        while url:
            print(f"  [{slug}] page {page_num} … ", end="", flush=True)
            try:
                r = session.get(url, timeout=30)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"✗ {e}")
                break

            results   = data.get("results", [])
            new_count = 0
            for spell in results:
                name = spell.get("name", "").strip()
                if name and name not in seen_names:
                    seen_names.add(name)
                    all_spells.append(spell)
                    new_count += 1

            print(f"✓  {len(results)} spells ({new_count} new, {len(all_spells)} total)")
            url = data.get("next")
            page_num += 1
            if url:
                time.sleep(DELAY)

    return all_spells


def _normalize_spell(raw: dict) -> dict:
    """Converts a raw Open5e API spell dict into our internal spell_dict format."""
    level      = raw.get("level_int", raw.get("spell_level", 0))
    school     = (raw.get("school") or "").strip().title()
    conc_str   = (raw.get("concentration") or "").lower()
    ritual_str = (raw.get("ritual") or "").lower()
    desc       = (raw.get("desc") or "").strip()
    desc       = re.sub(r'\n{3,}', '\n\n', desc)
    if len(desc) > 500:
        desc = desc[:500] + "…"

    return {
        "name":          raw.get("name", "").strip(),
        "level":         level,
        "school":        school,
        "source":        raw.get("document__title", raw.get("document__slug", "")),
        "casting_time":  (raw.get("casting_time") or "").strip(),
        "range":         (raw.get("range") or "").strip(),
        "components":    (raw.get("components") or "").strip(),
        "duration":      (raw.get("duration") or "").strip(),
        "concentration": (conc_str == "yes") or raw.get("requires_concentration", False),
        "ritual":        (ritual_str == "yes") or raw.get("can_be_cast_as_ritual", False),
        "desc":          desc,
        "higher_levels": (raw.get("higher_level") or "").strip(),
        "spell_lists":   [s.lower() for s in (raw.get("spell_lists") or [])],
    }


# =============================================================================
# MAIN FETCH / CACHE ORCHESTRATION
# =============================================================================

def fetch_all_spells(force: bool = False, classes: list = None) -> dict:
    """
    Fetches all spells from the Open5e API and saves to cache.
    The `classes` parameter is accepted for API compatibility but unused
    (the API returns all classes in one pass).

    Returns: {"Wizard": {0: [spell_dict,...], 1: [...]}, ...}
    """
    if not force and _is_cache_populated():
        cache = _load_cache()
        total = sum(sum(len(v) for v in lvls.values()) for lvls in cache.values())
        print(f"[SpellScraper] Cache loaded: {len(cache)} classes, {total} spells total.")
        print("  Use --force to re-fetch from API.")
        return cache

    print("[SpellScraper] Fetching spells from Open5e API …")
    print(f"  Sources: {', '.join(API_SLUGS)}\n")

    raw_spells = _api_fetch_all_spells()

    if not raw_spells:
        print("[SpellScraper] No spells returned — check connectivity.")
        return {}

    print(f"\n[SpellScraper] Processing {len(raw_spells)} unique spells …")

    # Organise by class → level
    cache: dict[str, dict[int, list]] = {name: {} for name in CLASS_NAMES.values()}
    skipped = 0

    for raw in raw_spells:
        spell = _normalize_spell(raw)
        if not spell["name"] or not spell["school"]:
            skipped += 1
            continue
        level = spell["level"]
        for cls_lower, cls_title in CLASS_NAMES.items():
            if cls_lower in spell["spell_lists"]:
                if level not in cache[cls_title]:
                    cache[cls_title][level] = []
                existing = {s["name"] for s in cache[cls_title][level]}
                if spell["name"] not in existing:
                    cache[cls_title][level].append(spell)

    # Sort alphabetically within each level
    for cls_data in cache.values():
        for level_list in cls_data.values():
            level_list.sort(key=lambda s: s["name"])

    # Drop empty classes
    cache = {cls: lvls for cls, lvls in cache.items() if lvls}

    # ── Merge hardcoded class spell lists ──────────────────────────────────
    # Some classes (especially Paladin and Ranger) are under-represented in
    # Open5e because the SRD only tags a subset of their spells. We merge in
    # the authoritative PHB spell lists here, pulling full spell data from
    # the API pool (spell_pool) when available, or creating a stub otherwise.
    #
    # spell_pool is a flat name→spell_dict lookup built from everything we
    # fetched, regardless of what class the API tagged it under.
    spell_pool: dict[str, dict] = {}
    for lvls in cache.values():
        for spells in lvls.values():
            for s in spells:
                spell_pool.setdefault(s["name"].lower(), s)

    HARDCODED_CLASS_LISTS = {
        "Paladin": PALADIN_SPELL_LIST,
        "Ranger":  RANGER_SPELL_LIST,
    }

    for cls_title, spell_by_level in HARDCODED_CLASS_LISTS.items():
        if cls_title not in cache:
            cache[cls_title] = {}
        for level, names in spell_by_level.items():
            if level not in cache[cls_title]:
                cache[cls_title][level] = []
            existing = {s["name"].lower() for s in cache[cls_title][level]}
            for name in names:
                if name.lower() in existing:
                    continue
                # Look up full spell data from pool; fall back to stub
                spell = spell_pool.get(name.lower())
                if spell:
                    # Make a copy so we don't mutate the pooled entry
                    entry = dict(spell)
                    entry["name"] = name   # preserve canonical casing
                else:
                    entry = {
                        "name": name, "level": level, "school": "",
                        "source": "PHB", "casting_time": "", "range": "",
                        "components": "", "duration": "", "concentration": False,
                        "ritual": False, "desc": "", "higher_levels": "",
                        "spell_lists": [cls_title.lower()],
                    }
                cache[cls_title][level].append(entry)
            # Re-sort after merge
            cache[cls_title][level].sort(key=lambda s: s["name"])

    # Save
    save = {cls: {str(k): v for k, v in lvls.items()} for cls, lvls in cache.items()}
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(save, f, indent=2, ensure_ascii=False)

    total = sum(sum(len(v) for v in lvls.values()) for lvls in cache.values())
    print(f"\n[SpellScraper] Saved {len(cache)} classes, {total} spells → {CACHE_FILE}")
    if skipped:
        print(f"  ({skipped} entries skipped — missing name or school)")
    print()
    for cls in sorted(cache.keys()):
        count   = sum(len(v) for v in cache[cls].values())
        max_lvl = max(cache[cls].keys())
        print(f"  {cls:14s}  {count:3d} spells  (up to L{max_lvl})")

    return cache


# Alias expected by wiki_scraper.update_spell_cache()
scrape_all_spells = fetch_all_spells


# =============================================================================
# PUBLIC LOOKUP API
# =============================================================================

def get_spells_for_class(class_name: str, spell_level: int = None) -> dict:
    cache  = _load_cache()
    source = SUBCLASS_SPELL_SOURCE.get(class_name, class_name)
    data   = cache.get(source, {})
    if spell_level is not None:
        return {spell_level: data.get(spell_level, [])}
    return data


def get_available_spells(class_name: str, char_level: int, subclass: str = None) -> dict:
    """
    Spells available at this character level.
    School filter applied to LEVELED spells only — cantrips always unrestricted.
    """
    sub_key     = (subclass or "").split("(")[0].strip()
    restriction = SUBCLASS_RESTRICTIONS.get((class_name, sub_key), {})
    source      = restriction.get("source", class_name)
    caster_type = CASTER_TYPE.get(sub_key) or CASTER_TYPE.get(class_name, "full")
    accessible  = _accessible_levels(char_level, caster_type)
    if not accessible:
        return {}
    all_spells = get_spells_for_class(source)
    if not all_spells:
        return {}
    allowed = restriction.get("schools")
    result  = {}
    for lvl in accessible:
        spells = all_spells.get(lvl, [])
        if allowed and lvl > 0:   # never filter cantrips
            spells = [s for s in spells if s.get("school", "") in allowed]
        if spells:
            result[lvl] = spells
    return result


def get_spells_for_subclass(class_name: str, subclass: str, char_level: int) -> dict:
    """
    Main entry point for spell_feature_picker.py.
    Returns a dict with spells, bonus_spells, school_filter, guaranteed_cantrips, etc.
    """
    sub_key     = (subclass or "").split("(")[0].strip()
    restriction = SUBCLASS_RESTRICTIONS.get((class_name, sub_key), {})
    caster_type = CASTER_TYPE.get(sub_key) or CASTER_TYPE.get(class_name, "full")
    spells      = get_available_spells(class_name, char_level, subclass)

    bonus = []
    for (cls, sub), spell_list in SUBCLASS_BONUS_SPELLS.items():
        if cls == class_name and (sub == sub_key or sub in sub_key or sub_key in sub):
            for req, spell_name in spell_list:
                try:
                    if int(req) <= char_level:
                        bonus.append(spell_name)
                except (ValueError, TypeError):
                    bonus.append(spell_name)
            break

    if class_name == "Druid" and "Land" in (subclass or ""):
        m = re.search(r"\((\w+)\)", subclass or "")
        if m:
            terrain = m.group(1)
            for unlock_lvl, names in DRUID_LAND_BONUS_SPELLS.get(terrain, {}).items():
                if unlock_lvl <= char_level:
                    for nm in names:
                        if nm not in bonus:
                            bonus.append(nm)

    return {
        "spells":              spells,
        "bonus_spells":        bonus,
        "free_picks":          restriction.get("free_picks", 0),
        "school_filter":       restriction.get("schools"),
        "guaranteed_cantrips": restriction.get("guaranteed_cantrips", []),
        "note":                restriction.get("note", ""),
        "caster_type":         caster_type,
        "max_spell_lvl":       max(spells.keys()) if spells else 0,
    }


def get_spell_by_name(spell_name: str, class_name: str = None) -> dict | None:
    cache  = _load_cache()
    target = spell_name.strip().lower()
    search = [class_name] if class_name else list(CLASS_NAMES.values())
    for cls in search:
        for level_spells in cache.get(cls, {}).values():
            for spell in level_spells:
                if spell.get("name", "").lower() == target:
                    return spell
    return None


# =============================================================================
# DM CONTEXT BUILDER
# =============================================================================

def build_spell_context_for_dm(class_name, subclass, char_level, known_spells=None):
    data  = get_spells_for_subclass(class_name, subclass, char_level)
    label = class_name + (f" ({subclass})" if subclass else "")
    lines = [
        f"--- SPELL ACCESS: {label} ---",
        f"Caster Type    : {data['caster_type']}",
        f"Max Spell Level: {data['max_spell_lvl'] or 'None yet'}",
    ]
    if data["school_filter"]:
        lines.append(f"School Restriction (leveled spells only): {' or '.join(data['school_filter'])}")
        if data["free_picks"]:
            lines.append(f"Free Picks: {data['free_picks']} from any school.")
    if data.get("guaranteed_cantrips"):
        lines.append(f"Guaranteed Cantrips: {', '.join(data['guaranteed_cantrips'])}")
    if data["note"]:
        lines.append(f"Rule: {data['note']}")
    if data["bonus_spells"]:
        lines.append("Bonus Spells (auto-granted):")
        for s in data["bonus_spells"]:
            lines.append(f"  * {s}")
    if known_spells:
        lines.append("Currently Known / Prepared:")
        for s in known_spells:
            lines.append(f"  * {s}")
    nxt = get_spells_for_subclass(class_name, subclass, char_level + 1)
    if nxt["max_spell_lvl"] > data["max_spell_lvl"]:
        lines.append(f"At level {char_level+1}: gains {nxt['max_spell_lvl']}th-level spells.")
    new_bonus = set(nxt["bonus_spells"]) - set(data["bonus_spells"])
    if new_bonus:
        lines.append(f"At level {char_level+1}: new bonus spells: {', '.join(new_bonus)}")
    return "\n".join(lines)


# =============================================================================
# DEBUG PRINTER
# =============================================================================

def print_subclass_spell_summary(class_name, subclass, char_level):
    data  = get_spells_for_subclass(class_name, subclass, char_level)
    label = class_name + (f" ({subclass})" if subclass else "")
    print(f"\n{'='*62}")
    print(f"  {label}  —  level {char_level}  |  {data['caster_type']} caster")
    if data["school_filter"]:
        print(f"  Filter (leveled only): {data['school_filter']}   Free picks: {data['free_picks']}")
    if data.get("guaranteed_cantrips"):
        print(f"  Guaranteed Cantrips: {data['guaranteed_cantrips']}")
    print("=" * 62)
    if not data["spells"]:
        print("  (no spells — run --fetch first, or check character level)")
    else:
        for lvl in sorted(data["spells"].keys()):
            tier   = "Cantrips" if lvl == 0 else f"Level {lvl}"
            spells = data["spells"][lvl]
            print(f"\n  {tier} ({len(spells)}):")
            for s in spells[:6]:
                conc = " [C]" if s.get("concentration") else ""
                rit  = " [R]" if s.get("ritual") else ""
                print(f"    • {s['name']} [{s.get('school','?')}]{conc}{rit}")
                if s.get("desc") and not s["desc"].startswith("(see"):
                    print(f"      {s['desc'][:90]}…")
            if len(spells) > 6:
                print(f"    … +{len(spells)-6} more")
    if data["bonus_spells"]:
        print(f"\n  Bonus (auto-granted): {', '.join(data['bonus_spells'])}")


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    if "--fetch" in sys.argv:
        fetch_all_spells(force=force)
    else:
        print("Usage:  python spell_scraper.py --fetch [--force]")
        print("  --fetch   Fetch from Open5e API and save to cache")
        print("  --force   Force full re-fetch even if cache exists")
        print("\nTesting with cached data …\n")

    print_subclass_spell_summary("Rogue",   "Arcane Trickster", 3)
    print_subclass_spell_summary("Fighter", "Eldritch Knight",  3)
    print_subclass_spell_summary("Cleric",  "Life Domain",      5)
    print_subclass_spell_summary("Wizard",  "",                 5)
    print_subclass_spell_summary("Warlock", "The Fiend",        5)
    print_subclass_spell_summary("Paladin", "Oath of Devotion", 5)
    print_subclass_spell_summary("Ranger",  "Gloom Stalker",    5)
