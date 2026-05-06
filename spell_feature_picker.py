# spell_feature_picker.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Comprehensive hardcoded spell lists and class feature menus for all
#          D&D 5e classes and subclasses, plus Pathfinder 2e and Daggerheart.
#
# WHY HARDCODED INSTEAD OF AI-ONLY:
#   The AI generates creative/world-flavored spell lists (existing system).
#   This module provides the OFFICIAL SRD/PHB spell lists as a fallback and
#   alternative — every spell is real, balanced, and accurate. Players can
#   choose the official list OR the AI-generated list.
#
# WHAT THIS COVERS:
#   - All D&D 5e SRD spells organized by class + spell level
#   - Subclass-specific bonus spells (Domain spells, Expanded spell lists, etc.)
#   - Class features at level 1 that require choices (Fighting Style, Metamagic,
#     Eldritch Invocations, Pact Boon, Divine Domain, Sorcerous Origin, etc.)
#   - Pathfinder 2e cantrips and first-level spells by class
#   - Daggerheart domain card descriptions
#
# ENTRY POINTS:
#   pick_official_spells(console, char_class, subclass, level, system_id)
#     → Returns list of chosen spell name strings
#   pick_class_features(console, char_class, subclass, level, system_id)
#     → Returns dict of chosen features (fighting_style, invocations, etc.)
#   get_subclass_bonus_spells(char_class, subclass)
#     → Returns list of bonus spell strings granted by the subclass (auto-added)
#
# LOCATION: dnd_ai_dm/spell_feature_picker.py
# ─────────────────────────────────────────────────────────────────────────────

import re
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# ── spell_scraper integration ──────────────────────────────────────────────
# Attempts to load live wiki spell data with subclass school-restriction support.
# Falls back silently to the hardcoded DND5E_SPELLS dict below if unavailable.
_SPELL_SCRAPER_AVAILABLE = False
try:
    from spell_scraper import (
        get_spells_for_subclass as _scraper_get_spells,
        _is_cache_populated as _scraper_cache_ok,
    )
    # Only mark as available if the cache actually contains spell data.
    # Import succeeding doesn't mean the cache was ever populated — if the
    # cache is empty we'd silently fall back to the truncated hardcoded list
    # with no warning to the player.
    _SPELL_SCRAPER_AVAILABLE = _scraper_cache_ok()
    if not _SPELL_SCRAPER_AVAILABLE:
        print(
            "[SpellPicker] Spell cache not found or empty.\n"
            "  Run:  python setup_spells.py\n"
            "  to download the full spell list from dnd5e.wikidot.com.\n"
            "  Using hardcoded fallback list for now."
        )
except ImportError:
    pass   # Offline / spell_scraper.py not present — hardcoded lists used instead


# ═══════════════════════════════════════════════════════════════════════════
# D&D 5E OFFICIAL SPELL LISTS  (SRD + PHB core)
# Organized as: class → level → [(name, school, description), ...]
# ═══════════════════════════════════════════════════════════════════════════

DND5E_SPELLS = {

    # ── BARD ─────────────────────────────────────────────────────────────────
    'Bard': {
        0: [  # Cantrips
            ('Blade Ward',       'Abjuration',   'Resistance to B/P/S damage until your next turn.'),
            ('Dancing Lights',   'Evocation',    'Create up to 4 floating lights for 1 minute.'),
            ('Friends',          'Enchantment',  'Advantage on CHA checks vs. one non-hostile creature.'),
            ('Light',            'Evocation',    'Object sheds 20-ft bright light, 20-ft dim. 1 hour.'),
            ('Mage Hand',        'Conjuration',  'Spectral hand carries up to 10 lb. 1 minute.'),
            ('Mending',          'Transmutation','Repair a single break in an object.'),
            ('Message',          'Transmutation','Whisper a message 120 ft; recipient can reply.'),
            ('Minor Illusion',   'Illusion',     'Create a sound or image for 1 minute. INT save to disbelieve.'),
            ('Prestidigitation', 'Transmutation','Minor magical tricks — clean, light/snuff, change flavor, etc.'),
            ('Thunderclap',      'Evocation',    '5-ft radius thunder burst. CON save or take 1d6 thunder.'),
            ('True Strike',      'Divination',   'Advantage on first attack roll vs. one target next turn.'),
            ('Vicious Mockery',  'Enchantment',  'WIS save or 1d4 psychic + disadvantage on next attack. 60 ft.'),
        ],
        1: [
            ('Animal Friendship',    'Enchantment',  'WIS save or beast is charmed for 24 hr. 30 ft.'),
            ('Bane',                 'Enchantment',  'Up to 3 creatures: CHA save or -1d4 to attacks/saves. Conc 1 min.'),
            ('Charm Person',         'Enchantment',  'WIS save or one humanoid charmed for 1 hr.'),
            ('Comprehend Languages', 'Divination',   'Understand any spoken/written language for 1 hr. (ritual)'),
            ('Cure Wounds',          'Evocation',    'Restore 1d8 + spellcasting modifier HP on touch.'),
            ('Detect Magic',         'Divination',   'Sense magic within 30 ft for 10 min. Conc. (ritual)'),
            ('Disguise Self',        'Illusion',     'Change your appearance for 1 hr.'),
            ("Faerie Fire",          'Evocation',    'Objects/creatures in 20-ft cube outlined. No benefit from hiding. Conc 1 min.'),
            ('Feather Fall',         'Transmutation','Up to 5 creatures fall at 60 ft/round for 1 min. Reaction.'),
            ('Healing Word',         'Evocation',    'Bonus action: restore 1d4 + mod HP. 60 ft range.'),
            ('Heroism',              'Enchantment',  'Immune to fear, gain temp HP = mod/turn. Conc 1 min.'),
            ('Identify',             'Divination',   'Learn properties of one magic item or spell. (ritual)'),
            ('Illusory Script',      'Illusion',     'Only designated creatures can read this message. 10 days. (ritual)'),
            ('Longstrider',          'Transmutation','Touch: +10 ft speed for 1 hr.'),
            ('Silent Image',         'Illusion',     '15-ft cube illusion, no sound/smell. Conc 10 min.'),
            ('Sleep',                'Enchantment',  'Creatures with fewest HP first fall unconscious. 5d8 HP pool.'),
            ('Speak with Animals',   'Divination',   'Communicate with beasts for 10 min. (ritual)'),
            ('Tasha\'s Hideous Laughter','Enchantment','WIS save or fall prone, incapacitated, laughing. Conc 1 min.'),
            ('Thunderwave',          'Evocation',    '15-ft cube: CON save or 2d8 thunder + pushed 10 ft. '),
            ('Unseen Servant',       'Conjuration',  'Invisible force performs simple tasks for 1 hr. (ritual)'),
        ],
        2: [
            ('Animal Messenger',  'Enchantment',  'Send a tiny beast as a messenger for 24 hr. (ritual)'),
            ('Blindness/Deafness','Necromancy',   'CON save or blinded or deafened (your choice). Conc 1 min.'),
            ('Calm Emotions',     'Enchantment',  'Suppress charm/fear or make indifferent. CHA save. Conc 1 min.'),
            ('Cloud of Daggers',  'Conjuration',  '5-ft cube deals 4d4 slashing each turn. Conc 1 min.'),
            ('Crown of Madness',  'Enchantment',  'CHA save or attacks nearest creature. Conc 1 min.'),
            ('Detect Thoughts',   'Divination',   'Read surface thoughts, or probe deeper. Conc 1 min.'),
            ('Enhance Ability',   'Transmutation','Grant advantage on checks for one ability score. Conc 1 hr.'),
            ('Enthrall',          'Enchantment',  'WIS save or creatures focus only on you for 1 min.'),
            ('Heat Metal',        'Transmutation','Metal object becomes scorching hot. CON or drop + 2d8 fire. Conc 1 min.'),
            ('Hold Person',       'Enchantment',  'WIS save or humanoid paralyzed. Conc 1 min.'),
            ('Invisibility',      'Illusion',     'Creature invisible until it attacks/casts. Conc 1 hr.'),
            ('Knock',             'Transmutation','Unlock a lock, door, or container. Loud boom.'),
            ('Lesser Restoration','Abjuration',   'End one disease or condition (blinded, deafened, etc.) on touch.'),
            ('Locate Animals/Plants','Divination','Know direction to nearest beast/plant of species named. Conc 1 hr.'),
            ('Locate Object',     'Divination',   'Know direction to familiar object within 1000 ft. Conc 10 min.'),
            ('Magic Mouth',       'Illusion',     'Object speaks a message when triggered. (ritual)'),
            ('Mirror Image',      'Illusion',     'Create 3 duplicates; attackers may hit a duplicate. 1 min.'),
            ('Phantasmal Force',  'Illusion',     'INT save or believe in constructed illusion. Conc 1 min.'),
            ('See Invisibility',  'Divination',   'See invisible/ethereal creatures for 1 hr.'),
            ('Shatter',           'Evocation',    '10-ft radius: CON save or 3d8 thunder. Inorganic objects auto-fail.'),
            ('Silence',           'Illusion',     '20-ft radius: no sound, no verbal components. Conc 10 min. (ritual)'),
            ('Suggestion',        'Enchantment',  'WIS save or follow one reasonable suggestion. Conc 8 hr.'),
            ('Zone of Truth',     'Enchantment',  '15-ft sphere: CHA save or cannot lie. 10 min.'),
        ],
    },

    # ── CLERIC ───────────────────────────────────────────────────────────────
    'Cleric': {
        0: [
            ('Guidance',         'Divination',   '+1d4 to one ability check before it ends. Conc 1 min.'),
            ('Light',            'Evocation',    'Object glows 20-ft bright, 20-ft dim. 1 hr.'),
            ('Mending',          'Transmutation','Repair a single break in an object.'),
            ('Resistance',       'Abjuration',   '+1d4 to one saving throw. Conc 1 min.'),
            ('Sacred Flame',     'Evocation',    'DEX save or target takes 1d8 radiant. 60 ft. No cover.'),
            ('Spare the Dying',  'Necromancy',   'Stabilize a dying creature within 5 ft. '),
            ('Thaumaturgy',      'Transmutation','Create minor magical effects (tremors, voices, fire flare, etc.)'),
            ('Toll the Dead',    'Necromancy',   'WIS save or 1d8 necrotic (1d12 if already damaged). 60 ft.'),
            ('Word of Radiance', 'Evocation',    'CON save or 1d6 radiant to all within 5 ft.'),
        ],
        1: [
            ('Bane',             'Enchantment',  'Up to 3: CHA save or -1d4 to attacks and saves. Conc 1 min.'),
            ('Bless',            'Enchantment',  'Up to 3 creatures: +1d4 to attacks and saves. Conc 1 min.'),
            ('Command',          'Enchantment',  'WIS save or follow a one-word command on next turn.'),
            ('Create/Destroy Water','Transmutation','Create 10 gallons or destroy same. 30 ft.'),
            ('Cure Wounds',      'Evocation',    'Restore 1d8 + mod HP on touch.'),
            ('Detect Evil/Good', 'Divination',   'Sense aberrations, celestials, fiends, etc. within 30 ft. Conc 10 min.'),
            ('Detect Magic',     'Divination',   'Sense magic within 30 ft for 10 min. Conc. (ritual)'),
            ('Detect Poison/Disease','Divination','Know poisonous/diseased creatures and objects. Conc 10 min. (ritual)'),
            ('Guiding Bolt',     'Evocation',    'Ranged: 4d6 radiant. Next attack on target has advantage.'),
            ('Healing Word',     'Evocation',    'Bonus action: 1d4 + mod HP. 60 ft.'),
            ('Inflict Wounds',   'Necromancy',   'Melee touch: 3d10 necrotic.'),
            ('Protection from Evil/Good','Abjuration','Protection from aberrations, celestials, etc. Conc 10 min.'),
            ('Purify Food/Drink','Transmutation','Remove poison/disease from food/drink. 10 ft. (ritual)'),
            ('Sanctuary',        'Abjuration',   'WIS save or attackers must choose new target. Conc 1 min.'),
            ('Shield of Faith',  'Abjuration',   '+2 AC to one creature. Conc 10 min.'),
        ],
        2: [
            ('Aid',              'Abjuration',   'Up to 3: +5 max and current HP for 8 hr.'),
            ('Augury',           'Divination',   'Weal/woe reading on action taken in next 30 min. (ritual)'),
            ('Blindness/Deafness','Necromancy',  'CON save or blinded or deafened. 1 min.'),
            ('Calm Emotions',    'Enchantment',  'Suppress charm/fear or make indifferent. Conc 1 min.'),
            ('Continual Flame',  'Evocation',    'Create permanent flame on object (no heat or fuel needed).'),
            ('Enhance Ability',  'Transmutation','Advantage on checks for one ability score. Conc 1 hr.'),
            ('Find Traps',       'Divination',   'Sense presence of traps within line of sight.'),
            ('Gentle Repose',    'Necromancy',   'Preserve corpse for 10 days; extends raise dead timers. (ritual)'),
            ('Hold Person',      'Enchantment',  'WIS save or humanoid paralyzed. Conc 1 min.'),
            ('Lesser Restoration','Abjuration',  'Remove one disease or blinded/deafened/paralyzed/poisoned.'),
            ('Locate Object',    'Divination',   'Direction to familiar object within 1000 ft. Conc 10 min.'),
            ('Prayer of Healing','Evocation',    'Up to 6: 2d8 + mod HP. 10 min cast time.'),
            ('Protection from Poison','Abjuration','Neutralize one poison; advantage vs. poison. 1 hr.'),
            ('Silence',          'Illusion',     '20-ft sphere: no sound, no verbal spells. Conc 10 min. (ritual)'),
            ('Spiritual Weapon', 'Evocation',    'Create weapon that attacks as bonus action. 1 min.'),
            ('Warding Bond',     'Abjuration',   'Ally gets +1 AC and saves, resistance to damage. 1 hr.'),
            ('Zone of Truth',    'Enchantment',  '15-ft sphere: CHA save or cannot lie. 10 min.'),
        ],
    },

    # ── DRUID ────────────────────────────────────────────────────────────────
    'Druid': {
        0: [
            ('Druidcraft',       'Transmutation','Minor nature effects: predict weather, make flowers bloom, etc.'),
            ('Guidance',         'Divination',   '+1d4 to one ability check before it ends. Conc 1 min.'),
            ('Infestation',      'Conjuration',  'CON save or 1d6 poison; moved 5 ft random direction. 30 ft.'),
            ('Mending',          'Transmutation','Repair a single break in an object.'),
            ('Poison Spray',     'Conjuration',  'CON save or 1d12 poison. 10 ft.'),
            ('Produce Flame',    'Conjuration',  'Harmless flame; can hurl for 1d8 fire. 30 ft. 10 min.'),
            ('Resistance',       'Abjuration',   '+1d4 to one saving throw. Conc 1 min.'),
            ('Shillelagh',       'Transmutation','Club/quarterstaff: use WIS for attacks, 1d8 damage. Conc 1 min.'),
            ('Thorn Whip',       'Transmutation','Melee ranged: 1d6 piercing, pull 10 ft. 30 ft.'),
            ('Thunderclap',      'Evocation',    'CON save or 1d6 thunder within 5 ft.'),
        ],
        1: [
            ('Animal Friendship',   'Enchantment',  'WIS save or beast charmed 24 hr.'),
            ('Charm Person',        'Enchantment',  'WIS save or humanoid charmed 1 hr.'),
            ('Create/Destroy Water','Transmutation','Create 10 gallons of water or destroy it.'),
            ('Cure Wounds',         'Evocation',    '1d8 + mod HP on touch.'),
            ('Detect Magic',        'Divination',   'Sense magic within 30 ft. Conc 10 min. (ritual)'),
            ('Detect Poison/Disease','Divination',  'Know poisonous/diseased creatures nearby. Conc 10 min. (ritual)'),
            ('Entangle',            'Conjuration',  '20-ft square: STR save or restrained. Conc 1 min.'),
            ('Faerie Fire',         'Evocation',    'Creatures outlined; no benefit from hiding. Conc 1 min.'),
            ('Fog Cloud',           'Conjuration',  '20-ft sphere of heavy obscurement. Conc 1 hr.'),
            ('Goodberry',           'Transmutation','10 berries each heal 1 HP and provide nutrition for 1 day.'),
            ('Healing Word',        'Evocation',    'Bonus action: 1d4 + mod HP. 60 ft.'),
            ('Jump',                'Transmutation','Triple jump distance for 1 min.'),
            ('Longstrider',         'Transmutation','+10 ft speed for 1 hr.'),
            ('Purify Food/Drink',   'Transmutation','Remove poison/disease from food or drink. (ritual)'),
            ('Speak with Animals',  'Divination',   'Communicate with beasts 10 min. (ritual)'),
            ('Thunderwave',         'Evocation',    '15-ft cube: CON or 2d8 thunder + pushed 10 ft.'),
        ],
        2: [
            ('Animal Messenger',  'Enchantment',  'Tiny beast delivers message in 24 hr. (ritual)'),
            ('Barkskin',          'Transmutation','Target\'s AC can\'t be below 16. Conc 1 hr.'),
            ('Beast Sense',       'Divination',   'Use a beast\'s senses. Conc 1 hr. (ritual)'),
            ('Darkvision',        'Transmutation','Grant darkvision 60 ft for 8 hr.'),
            ('Enhance Ability',   'Transmutation','Advantage on one ability checks. Conc 1 hr.'),
            ('Find Traps',        'Divination',   'Sense trap presence within line of sight.'),
            ('Flame Blade',       'Evocation',    'Fiery scimitar: 3d6 fire melee attack. Conc 10 min.'),
            ('Flaming Sphere',    'Conjuration',  '5-ft sphere deals 2d6 fire; bonus action to ram. Conc 1 min.'),
            ('Gust of Wind',      'Evocation',    '60-ft line: pushed 15 ft. Conc 1 min.'),
            ('Heat Metal',        'Transmutation','Metal scorching hot: CON or 2d8 fire + drop. Conc 1 min.'),
            ('Hold Person',       'Enchantment',  'WIS save or humanoid paralyzed. Conc 1 min.'),
            ('Lesser Restoration','Abjuration',   'Remove one condition on touch.'),
            ('Locate Animals/Plants','Divination','Direction to nearest of named species. Conc 1 hr.'),
            ('Moonbeam',          'Evocation',    '5-ft cylinder: CON or 2d10 radiant. Shapes-changers disadvantage. Conc 1 min.'),
            ('Pass Without Trace','Abjuration',   '+10 to Stealth for party, can\'t be tracked. Conc 1 hr.'),
            ('Protection from Poison','Abjuration','Neutralize one poison; advantage vs. poison. 1 hr.'),
            ('Spike Growth',      'Transmutation','20-ft radius: difficult terrain + 2d4 piercing per 5 ft moved. Conc 10 min.'),
        ],
    },

    # ── PALADIN ──────────────────────────────────────────────────────────────
    'Paladin': {
        1: [
            ('Bless',              'Enchantment',  'Up to 3: +1d4 to attack rolls and saves. Conc 1 min.'),
            ('Command',            'Enchantment',  'WIS save or follow one-word command on next turn.'),
            ('Compelled Duel',     'Enchantment',  'WIS save or must target you. Conc 1 min.'),
            ('Cure Wounds',        'Evocation',    '1d8 + mod HP on touch.'),
            ('Detect Evil/Good',   'Divination',   'Sense aberrations, celestials, fiends, etc. Conc 10 min.'),
            ('Detect Magic',       'Divination',   'Sense magic within 30 ft. Conc 10 min. (ritual)'),
            ('Detect Poison/Disease','Divination', 'Know poisonous/diseased creatures nearby. Conc 10 min. (ritual)'),
            ('Divine Favor',       'Evocation',    '+1d4 radiant to weapon attacks for 1 min. Conc. Bonus action.'),
            ('Heroism',            'Enchantment',  'Immune to fear; gain temp HP = mod each turn. Conc 1 min.'),
            ('Protection from Evil/Good','Abjuration','Protection from aberrations, celestials, fiends, etc. Conc 10 min.'),
            ('Purify Food/Drink',  'Transmutation','Remove poison/disease from food/drink. (ritual)'),
            ('Searing Smite',      'Evocation',    'Next hit: +1d6 fire; CON save or burning 1d6/turn. Conc 1 min.'),
            ('Shield of Faith',    'Abjuration',   '+2 AC. Conc 10 min. Bonus action.'),
            ('Thunderous Smite',   'Evocation',    'Next hit: +2d6 thunder; STR save or prone + pushed 10 ft. Conc 1 min.'),
            ('Wrathful Smite',     'Evocation',    'Next hit: +1d6 psychic; WIS save or frightened. Conc 1 min.'),
        ],
        2: [
            ('Aid',                'Abjuration',   'Up to 3: +5 max HP and current HP. 8 hr.'),
            ('Branding Smite',     'Evocation',    'Next hit: +2d6 radiant; visible, no invisibility. Conc 1 min.'),
            ('Find Steed',         'Conjuration',  'Summon a spirit steed (warhorse, pony, mastiff, etc.). 1 hr cast.'),
            ('Lesser Restoration', 'Abjuration',   'Remove one condition on touch.'),
            ('Locate Object',      'Divination',   'Direction to familiar object within 1000 ft. Conc 10 min.'),
            ('Magic Weapon',       'Transmutation','Nonmagical weapon becomes +1 magic weapon. Conc 1 hr.'),
            ('Protection from Poison','Abjuration','Neutralize one poison; advantage vs. poison. 1 hr.'),
            ('Zone of Truth',      'Enchantment',  '15-ft sphere: CHA save or cannot lie. 10 min.'),
        ],
    },

    # ── RANGER ───────────────────────────────────────────────────────────────
    'Ranger': {
        1: [
            ('Alarm',              'Abjuration',   'Alert you when a creature passes a warded area. 8 hr. (ritual)'),
            ('Animal Friendship',  'Enchantment',  'WIS save or beast charmed 24 hr.'),
            ('Cure Wounds',        'Evocation',    '1d8 + mod HP on touch.'),
            ('Detect Magic',       'Divination',   'Sense magic within 30 ft. Conc 10 min. (ritual)'),
            ('Detect Poison/Disease','Divination', 'Know poisonous/diseased creatures nearby. Conc 10 min. (ritual)'),
            ('Ensnaring Strike',   'Conjuration',  'Next hit: STR save or restrained 1 min. Conc.'),
            ('Fog Cloud',          'Conjuration',  '20-ft sphere of heavy obscurement. Conc 1 hr.'),
            ('Goodberry',          'Transmutation','10 berries; each heals 1 HP.'),
            ('Hail of Thorns',     'Conjuration',  'Next hit: 1d10 piercing burst, DEX save. Conc.'),
            ('Hunter\'s Mark',     'Divination',   'Mark quarry: +1d6 damage vs. it; track easily. Conc 1 hr. Bonus action.'),
            ('Jump',               'Transmutation','Triple jump distance 1 min.'),
            ('Longstrider',        'Transmutation','+10 ft speed 1 hr.'),
            ('Speak with Animals', 'Divination',   'Communicate with beasts 10 min. (ritual)'),
        ],
        2: [
            ('Animal Messenger',   'Enchantment',  'Tiny beast messenger 24 hr. (ritual)'),
            ('Barkskin',           'Transmutation','AC can\'t be below 16. Conc 1 hr.'),
            ('Cordon of Arrows',   'Transmutation','4 arrows fire at intruders within 30 ft. 8 hr.'),
            ('Darkvision',         'Transmutation','Grant darkvision 60 ft for 8 hr.'),
            ('Find Traps',         'Divination',   'Sense trap presence within line of sight.'),
            ('Lesser Restoration', 'Abjuration',   'Remove one condition on touch.'),
            ('Locate Animals/Plants','Divination', 'Direction to nearest of named species. Conc 1 hr.'),
            ('Locate Object',      'Divination',   'Direction to familiar object 1000 ft. Conc 10 min.'),
            ('Pass Without Trace', 'Abjuration',   '+10 to Stealth; can\'t be tracked. Conc 1 hr.'),
            ('Protection from Poison','Abjuration','Neutralize one poison; advantage vs. poison. 1 hr.'),
            ('Silence',            'Illusion',     '20-ft sphere: no sound. Conc 10 min. (ritual)'),
            ('Spike Growth',       'Transmutation','20-ft radius: difficult terrain + 2d4 piercing/5 ft. Conc 10 min.'),
        ],
    },

    # ── SORCERER ─────────────────────────────────────────────────────────────
    'Sorcerer': {
        0: [
            ('Acid Splash',      'Conjuration',  '1d6 acid to 1-2 adjacent targets. DEX save. 60 ft.'),
            ('Blade Ward',       'Abjuration',   'Resistance to B/P/S damage until next turn.'),
            ('Chill Touch',      'Necromancy',   '1d8 necrotic; undead have disadvantage on attacks vs. you. 120 ft.'),
            ('Dancing Lights',   'Evocation',    'Four floating lights for 1 min.'),
            ('Fire Bolt',        'Evocation',    '1d10 fire. 120 ft.'),
            ('Friends',          'Enchantment',  'Advantage on CHA checks vs. one creature. Conc 1 min.'),
            ('Light',            'Evocation',    'Object glows 20-ft bright, 20-ft dim. 1 hr.'),
            ('Mage Hand',        'Conjuration',  'Spectral hand, 10 lb. 30 ft. 1 min.'),
            ('Mending',          'Transmutation','Repair one break in an object.'),
            ('Message',          'Transmutation','Whisper 120 ft; recipient can reply.'),
            ('Minor Illusion',   'Illusion',     'Sound or image for 1 min. INT save to disbelieve.'),
            ('Poison Spray',     'Conjuration',  'CON save or 1d12 poison. 10 ft.'),
            ('Prestidigitation', 'Transmutation','Minor magical effects.'),
            ('Ray of Frost',     'Evocation',    '1d8 cold; target\'s speed -10 ft until next turn. 60 ft.'),
            ('Shocking Grasp',   'Evocation',    '1d8 lightning; no reactions until next turn. Advantage vs. metal armor.'),
            ('True Strike',      'Divination',   'Advantage on first attack next turn vs. one target.'),
        ],
        1: [
            ('Burning Hands',    'Evocation',    '15-ft cone: DEX or 3d6 fire.'),
            ('Charm Person',     'Enchantment',  'WIS save or humanoid charmed 1 hr.'),
            ('Color Spray',      'Illusion',     '6d10 HP of creatures blinded. Lowest HP first.'),
            ('Comprehend Languages','Divination','Understand any language for 1 hr. (ritual)'),
            ('Detect Magic',     'Divination',   'Sense magic 30 ft. Conc 10 min. (ritual)'),
            ('Disguise Self',    'Illusion',     'Change your appearance for 1 hr.'),
            ('Expeditious Retreat','Transmutation','Dash as bonus action. Conc 10 min.'),
            ('False Life',       'Necromancy',   'Gain 1d4+4 temp HP. 1 hr.'),
            ('Feather Fall',     'Transmutation','Up to 5 creatures fall slowly. Reaction.'),
            ('Fog Cloud',        'Conjuration',  '20-ft sphere: heavily obscured. Conc 1 hr.'),
            ('Jump',             'Transmutation','Triple jump distance 1 min.'),
            ('Mage Armor',       'Abjuration',   'AC = 13 + DEX (replaces armor). 8 hr.'),
            ('Magic Missile',    'Evocation',    '3 darts of 1d4+1 force. Auto-hit.'),
            ('Ray of Sickness',  'Necromancy',   '2d8 poison; CON save or poisoned 1 turn. 60 ft.'),
            ('Shield',           'Abjuration',   '+5 AC until next turn; immune to Magic Missile. Reaction.'),
            ('Silent Image',     'Illusion',     '15-ft cube illusion. Conc 10 min.'),
            ('Sleep',            'Enchantment',  '5d8 HP pool; targets fall unconscious. Lowest first. 20-ft circle.'),
            ('Thunderwave',      'Evocation',    '15-ft cube: CON or 2d8 thunder + pushed 10 ft.'),
        ],
        2: [
            ('Alter Self',        'Transmutation','Change appearance, grow natural weapons, or breathe water. Conc 1 hr.'),
            ('Blindness/Deafness','Necromancy',   'CON save or blinded or deafened. 1 min.'),
            ('Blur',              'Illusion',     'Attackers have disadvantage. Conc 1 min.'),
            ('Cloud of Daggers',  'Conjuration',  '5-ft cube: 4d4 slashing each turn. Conc 1 min.'),
            ('Crown of Madness',  'Enchantment',  'CHA save or attacks nearest creature. Conc 1 min.'),
            ('Darkness',          'Evocation',    '15-ft sphere of magical darkness. Conc 10 min.'),
            ('Darkvision',        'Transmutation','Grant darkvision 60 ft for 8 hr.'),
            ('Detect Thoughts',   'Divination',   'Read surface/deep thoughts. Conc 1 min.'),
            ('Enhance Ability',   'Transmutation','Advantage on one ability score checks. Conc 1 hr.'),
            ('Gust of Wind',      'Evocation',    '60-ft line: pushed 15 ft. Conc 1 min.'),
            ('Hold Person',       'Enchantment',  'WIS save or humanoid paralyzed. Conc 1 min.'),
            ('Invisibility',      'Illusion',     'Invisible until attacks/casts. Conc 1 hr.'),
            ('Knock',             'Transmutation','Unlock lock/door/container. Loud boom.'),
            ('Levitate',          'Transmutation','One creature/object floats up to 20 ft. Conc 10 min.'),
            ('Mirror Image',      'Illusion',     '3 duplicates; attackers may hit duplicate. 1 min.'),
            ('Misty Step',        'Conjuration',  'Teleport 30 ft. Bonus action.'),
            ('Scorching Ray',     'Evocation',    '3 rays: each 2d6 fire. Ranged attack. 120 ft.'),
            ('See Invisibility',  'Divination',   'See invisible and ethereal for 1 hr.'),
            ('Shatter',           'Evocation',    '10-ft radius: CON or 3d8 thunder.'),
            ('Spider Climb',      'Transmutation','Walk on walls/ceilings. Conc 1 hr.'),
            ('Suggestion',        'Enchantment',  'WIS save or follow reasonable suggestion. Conc 8 hr.'),
            ('Web',               'Conjuration',  '20-ft cube: difficult terrain + DEX save or restrained. Conc 1 hr.'),
        ],
    },

    # ── WARLOCK ──────────────────────────────────────────────────────────────
    'Warlock': {
        0: [
            ('Blade Ward',       'Abjuration',   'Resistance to B/P/S damage until next turn.'),
            ('Chill Touch',      'Necromancy',   '1d8 necrotic; undead have disadv vs. you. 120 ft.'),
            ('Eldritch Blast',   'Evocation',    '1 beam (more at higher levels): 1d10 force. 120 ft.'),
            ('Friends',          'Enchantment',  'Advantage on CHA checks vs. one creature. Conc 1 min.'),
            ('Mage Hand',        'Conjuration',  'Spectral hand, 10 lb. 30 ft. 1 min.'),
            ('Minor Illusion',   'Illusion',     'Sound or image for 1 min.'),
            ('Poison Spray',     'Conjuration',  'CON save or 1d12 poison. 10 ft.'),
            ('Prestidigitation', 'Transmutation','Minor magical effects.'),
            ('True Strike',      'Divination',   'Advantage on first attack vs. one target next turn.'),
        ],
        1: [
            ('Armor of Agathys', 'Abjuration',   '5 temp HP; attacker takes 5 cold if it hits you. 1 hr.'),
            ('Arms of Hadar',    'Conjuration',  '10-ft radius: STR save or 2d6 necrotic + no reactions.'),
            ('Charm Person',     'Enchantment',  'WIS save or charmed 1 hr.'),
            ('Comprehend Languages','Divination','Understand any language 1 hr. (ritual)'),
            ('Expeditious Retreat','Transmutation','Dash as bonus action. Conc 10 min.'),
            ('Hex',              'Enchantment',  'Bonus action: +1d6 necrotic on attacks; one ability check has disadv. Conc 1 hr.'),
            ('Hellish Rebuke',   'Evocation',    'Reaction: 2d10 fire to attacker. DEX save.'),
            ('Illusory Script',  'Illusion',     'Secret message only designated reader can see. (ritual)'),
            ('Protection from Evil/Good','Abjuration','Protection from aberrations, fiends, etc. Conc 10 min.'),
            ('Unseen Servant',   'Conjuration',  'Invisible helper for 1 hr. (ritual)'),
            ('Witch Bolt',       'Evocation',    'Arc of lightning; 1d12 lightning + 1d12/round action. Conc 1 min.'),
        ],
        2: [
            ('Cloud of Daggers',  'Conjuration',  '5-ft cube: 4d4 slashing/turn. Conc 1 min.'),
            ('Crown of Madness',  'Enchantment',  'CHA save or attacks nearest creature. Conc 1 min.'),
            ('Darkness',          'Evocation',    '15-ft sphere: magical darkness. Conc 10 min.'),
            ('Enthrall',          'Enchantment',  'WIS save or fixed on you 1 min.'),
            ('Hold Person',       'Enchantment',  'WIS save or paralyzed humanoid. Conc 1 min.'),
            ('Invisibility',      'Illusion',     'Invisible until attacks/casts. Conc 1 hr.'),
            ('Mirror Image',      'Illusion',     '3 duplicates. 1 min.'),
            ('Misty Step',        'Conjuration',  'Teleport 30 ft. Bonus action.'),
            ('Ray of Enfeeblement','Necromancy',  'CON save or halved STR damage. Conc 1 min.'),
            ('Shatter',           'Evocation',    '10-ft radius: CON or 3d8 thunder.'),
            ('Spider Climb',      'Transmutation','Walk on walls/ceilings. Conc 1 hr.'),
            ('Suggestion',        'Enchantment',  'WIS save or follow reasonable suggestion. Conc 8 hr.'),
        ],
    },

    # ── WIZARD ───────────────────────────────────────────────────────────────
    'Wizard': {
        0: [
            ('Acid Splash',      'Conjuration',  '1d6 acid to 1-2 adjacent targets. DEX save. 60 ft.'),
            ('Blade Ward',       'Abjuration',   'Resistance to B/P/S damage until next turn.'),
            ('Chill Touch',      'Necromancy',   '1d8 necrotic; undead disadv on attacks vs. you. 120 ft.'),
            ('Dancing Lights',   'Evocation',    'Four floating lights for 1 min. Conc.'),
            ('Fire Bolt',        'Evocation',    '1d10 fire. 120 ft.'),
            ('Friends',          'Enchantment',  'Advantage on CHA checks vs. one creature. Conc 1 min.'),
            ('Light',            'Evocation',    'Object glows 20-ft bright, 20-ft dim. 1 hr.'),
            ('Mage Hand',        'Conjuration',  'Spectral hand, 10 lb. 30 ft. 1 min.'),
            ('Mending',          'Transmutation','Repair one break or tear.'),
            ('Message',          'Transmutation','Whisper 120 ft; recipient replies.'),
            ('Minor Illusion',   'Illusion',     'Sound or image for 1 min.'),
            ('Poison Spray',     'Conjuration',  'CON save or 1d12 poison. 10 ft.'),
            ('Prestidigitation', 'Transmutation','Minor magical effects.'),
            ('Ray of Frost',     'Evocation',    '1d8 cold; speed -10 ft next turn. 60 ft.'),
            ('Shocking Grasp',   'Evocation',    '1d8 lightning; no reactions until next turn.'),
            ('True Strike',      'Divination',   'Advantage on first attack next turn vs. one target.'),
        ],
        1: [
            ('Absorb Elements',   'Abjuration',   'Reaction: resist incoming element; add 1d6 to next attack.'),
            ('Alarm',             'Abjuration',   'Alert you when area is entered. 8 hr. (ritual)'),
            ('Burning Hands',     'Evocation',    '15-ft cone: DEX or 3d6 fire.'),
            ('Charm Person',      'Enchantment',  'WIS save or humanoid charmed 1 hr.'),
            ('Color Spray',       'Illusion',     '6d10 HP of creatures blinded. Lowest HP first.'),
            ('Comprehend Languages','Divination', 'Understand any language 1 hr. (ritual)'),
            ('Detect Magic',      'Divination',   'Sense magic 30 ft. Conc 10 min. (ritual)'),
            ('Disguise Self',     'Illusion',     'Change appearance for 1 hr.'),
            ('Expeditious Retreat','Transmutation','Dash as bonus action. Conc 10 min.'),
            ('False Life',        'Necromancy',   'Gain 1d4+4 temp HP. 1 hr.'),
            ('Feather Fall',      'Transmutation','5 creatures fall slowly. Reaction.'),
            ('Find Familiar',     'Conjuration',  'Summon a familiar spirit. (ritual)'),
            ('Fog Cloud',         'Conjuration',  '20-ft sphere: heavily obscured. Conc 1 hr.'),
            ('Grease',            'Conjuration',  '10-ft square: DEX or prone. Difficult terrain. 1 min.'),
            ('Identify',          'Divination',   'Learn properties of one item or spell. (ritual)'),
            ('Illusory Script',   'Illusion',     'Secret message only designated reader sees. (ritual)'),
            ('Jump',              'Transmutation','Triple jump distance 1 min.'),
            ('Longstrider',       'Transmutation','+10 ft speed 1 hr.'),
            ('Mage Armor',        'Abjuration',   'AC = 13 + DEX. 8 hr.'),
            ('Magic Missile',     'Evocation',    '3 darts of 1d4+1 force. Auto-hit.'),
            ('Protection from Evil/Good','Abjuration','Protection from aberrations, fiends, etc. Conc 10 min.'),
            ('Ray of Sickness',   'Necromancy',   '2d8 poison; CON or poisoned 1 turn.'),
            ('Shield',            'Abjuration',   '+5 AC; immune to Magic Missile. Reaction.'),
            ('Silent Image',      'Illusion',     '15-ft cube illusion. Conc 10 min.'),
            ('Sleep',             'Enchantment',  '5d8 HP of creatures sleep. 20-ft radius.'),
            ('Tasha\'s Hideous Laughter','Enchantment','WIS or incapacitated, prone, laughing. Conc 1 min.'),
            ('Thunderwave',       'Evocation',    '15-ft cube: CON or 2d8 thunder + pushed 10 ft.'),
            ('Unseen Servant',    'Conjuration',  'Invisible helper for 1 hr. (ritual)'),
            ('Witch Bolt',        'Evocation',    '1d12 lightning; 1d12/round as action. Conc 1 min.'),
        ],
        2: [
            ('Alter Self',        'Transmutation','Change appearance or form. Conc 1 hr.'),
            ('Arcane Lock',       'Abjuration',   'Permanent lock on door/window/chest.'),
            ('Blindness/Deafness','Necromancy',   'CON or blinded/deafened. 1 min.'),
            ('Blur',              'Illusion',     'Attackers have disadvantage on attacks. Conc 1 min.'),
            ('Cloud of Daggers',  'Conjuration',  '5-ft cube: 4d4 slashing/turn. Conc 1 min.'),
            ('Continual Flame',   'Evocation',    'Permanent flame on object.'),
            ('Crown of Madness',  'Enchantment',  'CHA or attacks nearest. Conc 1 min.'),
            ('Darkness',          'Evocation',    '15-ft sphere of magical darkness. Conc 10 min.'),
            ('Darkvision',        'Transmutation','Grant darkvision 60 ft for 8 hr.'),
            ('Detect Thoughts',   'Divination',   'Read thoughts. Conc 1 min.'),
            ('Enlarge/Reduce',    'Transmutation','Target doubled or halved in size. Conc 1 min.'),
            ('Flaming Sphere',    'Conjuration',  '5-ft sphere: 2d6 fire; bonus action to ram. Conc 1 min.'),
            ('Gentle Repose',     'Necromancy',   'Preserve corpse 10 days. (ritual)'),
            ('Hold Person',       'Enchantment',  'WIS or humanoid paralyzed. Conc 1 min.'),
            ('Invisibility',      'Illusion',     'Invisible until attack/cast. Conc 1 hr.'),
            ('Knock',             'Transmutation','Open lock/door/container.'),
            ('Levitate',          'Transmutation','One creature/object floats 20 ft. Conc 10 min.'),
            ('Magic Mouth',       'Illusion',     'Triggered spoken message on object. (ritual)'),
            ('Magic Weapon',      'Transmutation','Nonmagical weapon becomes +1 magic. Conc 1 hr.'),
            ('Mirror Image',      'Illusion',     '3 duplicates. 1 min.'),
            ('Misty Step',        'Conjuration',  'Teleport 30 ft. Bonus action.'),
            ('Nystul\'s Magic Aura','Illusion',   'Change how a creature appears to detection spells. 24 hr.'),
            ('Phantasmal Force',  'Illusion',     'INT or believe in your illusion. Conc 1 min.'),
            ('Ray of Enfeeblement','Necromancy',  'CON or halved STR damage. Conc 1 min.'),
            ('Rope Trick',        'Transmutation','Rope leads to extradimensional space for 1 hr.'),
            ('Scorching Ray',     'Evocation',    '3 rays: 2d6 fire each. 120 ft.'),
            ('See Invisibility',  'Divination',   'See invisible and ethereal 1 hr.'),
            ('Shatter',           'Evocation',    '10-ft radius: CON or 3d8 thunder.'),
            ('Spider Climb',      'Transmutation','Walk on walls/ceilings. Conc 1 hr.'),
            ('Suggestion',        'Enchantment',  'WIS or follow reasonable suggestion. Conc 8 hr.'),
            ('Web',               'Conjuration',  '20-ft cube: difficult terrain + DEX or restrained. Conc 1 hr.'),
        ],
    },
}

# Artificer uses INT and prepares spells — same general lists as Wizard for selection
DND5E_SPELLS['Artificer'] = {
    0: DND5E_SPELLS['Wizard'][0][:10],  # subset
    1: [
        ('Alarm',           'Abjuration',   'Alert you when area entered. 8 hr. (ritual)'),
        ('Cure Wounds',     'Evocation',    '1d8 + mod HP on touch.'),
        ('Detect Magic',    'Divination',   'Sense magic 30 ft. Conc 10 min. (ritual)'),
        ('Disguise Self',   'Illusion',     'Change appearance for 1 hr.'),
        ('Expeditious Retreat','Transmutation','Dash as bonus action. Conc 10 min.'),
        ('Faerie Fire',     'Evocation',    'Creatures outlined. Conc 1 min.'),
        ('False Life',      'Necromancy',   '1d4+4 temp HP. 1 hr.'),
        ('Grease',          'Conjuration',  '10-ft square: DEX or prone.'),
        ('Identify',        'Divination',   'Learn item/spell properties. (ritual)'),
        ('Jump',            'Transmutation','Triple jump 1 min.'),
        ('Longstrider',     'Transmutation','+10 ft speed 1 hr.'),
        ('Purify Food/Drink','Transmutation','Remove poison/disease. (ritual)'),
        ('Sanctuary',       'Abjuration',   'WIS or must retarget. Conc 1 min.'),
        ('Thunderwave',     'Evocation',    '15-ft cube: CON or 2d8 thunder + pushed.'),
    ],
    2: [
        ('Aid',             'Abjuration',   '+5 max HP to 3 creatures. 8 hr.'),
        ('Alter Self',      'Transmutation','Change form. Conc 1 hr.'),
        ('Arcane Lock',     'Abjuration',   'Permanent lock on door/window.'),
        ('Blur',            'Illusion',     'Disadv on attacks vs. you. Conc 1 min.'),
        ('Darkvision',      'Transmutation','Grant darkvision 60 ft. 8 hr.'),
        ('Enhance Ability', 'Transmutation','Advantage on one ability. Conc 1 hr.'),
        ('Enlarge/Reduce',  'Transmutation','Double or halve target size. Conc 1 min.'),
        ('Heat Metal',      'Transmutation','Metal scorching: CON or 2d8 fire + drop. Conc 1 min.'),
        ('Invisibility',    'Illusion',     'Invisible until attack/cast. Conc 1 hr.'),
        ('Lesser Restoration','Abjuration','Remove condition on touch.'),
        ('Levitate',        'Transmutation','Float 20 ft. Conc 10 min.'),
        ('Magic Mouth',     'Illusion',     'Triggered message. (ritual)'),
        ('Magic Weapon',    'Transmutation','Weapon becomes +1 magic. Conc 1 hr.'),
        ('Rope Trick',      'Transmutation','Extradimensional rope space 1 hr.'),
        ('See Invisibility','Divination',   'See invisible/ethereal 1 hr.'),
        ('Spider Climb',    'Transmutation','Walk on walls/ceilings. Conc 1 hr.'),
        ('Web',             'Conjuration',  '20-ft cube: difficult terrain + restrained. Conc 1 hr.'),
    ],

    # ── ARCANE TRICKSTER (Rogue subclass — Enchantment/Illusion focus) ────────
    'Arcane Trickster': {
        0: [
            ('Blade Ward',       'Abjuration',   'Resistance to B/P/S damage until your next turn.'),
            ('Friends',          'Enchantment',  'Advantage on CHA checks vs. one non-hostile creature.'),
            ('Mage Hand',        'Conjuration',  'Spectral hand carries up to 10 lb. Enhanced by Mage Hand Legerdemain.'),
            ('Message',          'Transmutation','Whisper a message 120 ft; recipient can reply.'),
            ('Minor Illusion',   'Illusion',     'Create a sound or image for 1 minute. INT save to disbelieve.'),
            ('Prestidigitation', 'Transmutation','Minor magical tricks.'),
            ('True Strike',      'Divination',   'Advantage on first attack vs. target next turn.'),
        ],
        1: [
            ('Charm Person',     'Enchantment',  'WIS save or charmed 1 hr. Advantage on CHA checks vs. it.'),
            ('Color Spray',      'Illusion',     'Blinded creatures with up to 6 HP combined within 15-ft cone.'),
            ('Disguise Self',    'Illusion',     'Change appearance for 1 hr. Investigation vs. spell save to detect.'),
            ("Tasha's Hideous Laughter", 'Enchantment', 'WIS save or prone and incapacitated 1 min. Conc.'),
            ('Illusory Script',  'Illusion',     'Write secret message visible only to designated recipients. Ritual.'),
            ('Mage Armor',       'Abjuration',   'AC = 13 + DEX. Touch. 8 hr. (free pick — any school)'),
            ('Magic Missile',    'Evocation',    '3 darts, 1d4+1 force each, auto-hit. (free pick — any school)'),
            ('Silent Image',     'Illusion',     '15-ft cube illusion. Investigation vs. spell save. Conc 10 min.'),
            ('Sleep',            'Enchantment',  'Put creatures (lowest HP first) up to 5d8 HP to sleep.'),
            ('Thunderwave',      'Evocation',    '15-ft cube CON save: 2d8 thunder + pushed 10 ft. (free pick)'),
        ],
        2: [
            ('Blur',             'Illusion',     'Disadv on attacks vs. you. Conc 1 min.'),
            ('Crown of Madness', 'Enchantment',  'WIS save or charmed; attacks nearest creature. Conc 1 min.'),
            ('Hold Person',      'Enchantment',  'WIS save or paralyzed. Conc 1 min.'),
            ('Invisibility',     'Illusion',     'Invisible until attack/cast. Conc 1 hr.'),
            ('Mirror Image',     'Illusion',     '3 duplicates. Attackers must roll to hit decoys first.'),
            ('Phantasmal Force', 'Illusion',     'INT save or creature believes in illusion; 2d6 psychic/round.'),
            ('Silence',          'Illusion',     'No sound in 20-ft radius. Conc 10 min. Ritual.'),
            ('Suggestion',       'Enchantment',  'WIS save or follow one suggestion. Conc 8 hr.'),
        ],
    },

    # ── ELDRITCH KNIGHT (Fighter subclass — Abjuration/Evocation focus) ───────
    'Eldritch Knight': {
        0: [
            ('Blade Ward',       'Abjuration',   'Resistance to B/P/S damage until your next turn.'),
            ('Booming Blade',    'Evocation',    'Melee attack; if target moves, +1d8 thunder. Scales.'),
            ('Fire Bolt',        'Evocation',    'Ranged spell attack: 1d10 fire. 120 ft.'),
            ('Green-Flame Blade','Evocation',    'Melee attack; fire leaps to adjacent creature.'),
            ('Light',            'Evocation',    'Object sheds bright light 20 ft, dim 20 ft. 1 hr.'),
            ('Shocking Grasp',   'Evocation',    'Lightning melee: 1d8, target loses reaction until its next turn.'),
            ('True Strike',      'Divination',   'Advantage on first attack vs. one target next turn. (free pick)'),
        ],
        1: [
            ('Absorb Elements',  'Abjuration',   'Reaction: halve incoming elemental damage; add to next melee.'),
            ('Burning Hands',    'Evocation',    '15-ft cone: DEX save or 3d6 fire.'),
            ('Chromatic Orb',    'Evocation',    'Ranged attack: 3d8 of chosen energy type.'),
            ('Expeditious Retreat','Transmutation','Bonus action Dash. Conc 10 min. (free pick)'),
            ('Feather Fall',     'Transmutation','Slow fall for up to 5 creatures. Reaction. (free pick)'),
            ('Magic Missile',    'Evocation',    '3 darts, 1d4+1 force each, auto-hit.'),
            ('Mage Armor',       'Abjuration',   'AC = 13 + DEX. 8 hr.'),
            ('Protection from Evil/Good', 'Abjuration', 'Protect vs. aberrations/celestials/etc. Conc 10 min.'),
            ('Shield',           'Abjuration',   'Reaction: +5 AC until next turn; block Magic Missile.'),
            ('Thunderwave',      'Evocation',    '15-ft cube CON save: 2d8 thunder + pushed 10 ft.'),
            ('Witch Bolt',       'Evocation',    'Lightning tether: 1d12/round. Conc 1 min.'),
        ],
        2: [
            ('Blur',             'Illusion',     'Disadv on attacks vs. you. Conc 1 min. (free pick)'),
            ('Darkness',         'Evocation',    '15-ft radius magical darkness. Conc 10 min.'),
            ('Hold Person',      'Enchantment',  'WIS save or paralyzed. Conc 1 min. (free pick)'),
            ('Magic Weapon',     'Transmutation','Weapon becomes +1 magic. Conc 1 hr. (free pick)'),
            ('Misty Step',       'Conjuration',  'Bonus action teleport 30 ft. (free pick)'),
            ('Scorching Ray',    'Evocation',    '3 rays, ranged spell attack: 2d6 fire each.'),
            ('Shatter',          'Evocation',    '10-ft sphere CON save: 3d8 thunder. Extra damage vs. inorganic.'),
            ('Web',              'Conjuration',  '20-ft cube restrained. STR save. Conc 1 hr. (free pick)'),
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# SUBCLASS BONUS SPELLS  (auto-added, not chosen)
# ═══════════════════════════════════════════════════════════════════════════

# SUBCLASS_BONUS_SPELLS
# Format: {(class, subclass): [(min_character_level, spell_name), ...]}
#
# Spells are only granted once the character reaches the listed level.
# PHB unlock schedule:
#   Cleric domains   — 1, 3, 5, 7, 9  (one pair per spell level tier)
#   Paladin oaths    — 3, 5, 9, 13, 17 (subclass unlocks at 3, then every
#                      odd level where a new spell tier opens)
#   Ranger conclaves — 3, 5, 9, 13, 17
#   Warlock patrons  — 1, 3, 5, 7, 9  (Expanded Spells unlock with Pact Magic)
#   Sorcerer/Druid   — same pattern as Warlock / Cleric respectively
SUBCLASS_BONUS_SPELLS = {
    # ── Cleric Domains ─────────────────────────────────────────────────────
    ('Cleric', 'Life Domain'): [
        (1, 'Bless'), (1, 'Cure Wounds'),
        (3, 'Lesser Restoration'), (3, 'Spiritual Weapon'),
        (5, 'Beacon of Hope'), (5, 'Revivify'),
        (7, 'Death Ward'), (7, 'Guardian of Faith'),
        (9, 'Mass Cure Wounds'), (9, 'Raise Dead'),
    ],
    ('Cleric', 'Light Domain'): [
        (1, 'Burning Hands'), (1, 'Faerie Fire'),
        (3, 'Flaming Sphere'), (3, 'Scorching Ray'),
        (5, 'Daylight'), (5, 'Fireball'),
        (7, 'Guardian of Faith'), (7, 'Wall of Fire'),
        (9, 'Flame Strike'), (9, 'Scrying'),
    ],
    ('Cleric', 'Tempest Domain'): [
        (1, 'Fog Cloud'), (1, 'Thunderwave'),
        (3, 'Gust of Wind'), (3, 'Shatter'),
        (5, 'Call Lightning'), (5, 'Sleet Storm'),
        (7, 'Control Water'), (7, 'Ice Storm'),
        (9, 'Destructive Wave'), (9, 'Insect Plague'),
    ],
    ('Cleric', 'War Domain'): [
        (1, 'Divine Favor'), (1, 'Shield of Faith'),
        (3, 'Magic Weapon'), (3, 'Spiritual Weapon'),
        (5, "Crusader's Mantle"), (5, 'Spirit Guardians'),
        (7, 'Freedom of Movement'), (7, 'Stoneskin'),
        (9, 'Flame Strike'), (9, 'Hold Monster'),
    ],
    ('Cleric', 'Trickery Domain'): [
        (1, 'Charm Person'), (1, 'Disguise Self'),
        (3, 'Mirror Image'), (3, 'Pass Without Trace'),
        (5, 'Blink'), (5, 'Dispel Magic'),
        (7, 'Dimension Door'), (7, 'Polymorph'),
        (9, 'Dominate Person'), (9, 'Modify Memory'),
    ],
    ('Cleric', 'Knowledge Domain'): [
        (1, 'Command'), (1, 'Identify'),
        (3, 'Augury'), (3, 'Suggestion'),
        (5, 'Nondetection'), (5, 'Speak with Dead'),
        (7, 'Arcane Eye'), (7, 'Confusion'),
        (9, 'Legend Lore'), (9, 'Scrying'),
    ],
    ('Cleric', 'Nature Domain'): [
        (1, 'Animal Friendship'), (1, 'Speak with Animals'),
        (3, 'Barkskin'), (3, 'Spike Growth'),
        (5, 'Plant Growth'), (5, 'Wind Wall'),
        (7, 'Dominate Beast'), (7, 'Grasping Vine'),
        (9, 'Insect Plague'), (9, 'Tree Stride'),
    ],
    ('Cleric', 'Death Domain'): [
        (1, 'False Life'), (1, 'Ray of Sickness'),
        (3, 'Blindness/Deafness'), (3, 'Ray of Enfeeblement'),
        (5, 'Animate Dead'), (5, 'Vampiric Touch'),
        (7, 'Blight'), (7, 'Death Ward'),
        (9, 'Antilife Shell'), (9, 'Cloudkill'),
    ],
    ("Cleric", "Arcana Domain"): [
        (1, "Detect Magic"), (1, "Magic Missile"),
        (3, "Magic Weapon"), (3, "Nystul's Magic Aura"),
        (5, "Arcane Eye"), (5, "Leomund's Secret Chest"),
        (7, "Planar Binding"), (7, "Teleportation Circle"),
        (9, "Gate"), (9, "Wish"),
    ],
    ('Cleric', 'Forge Domain'): [
        (1, 'Identify'), (1, 'Searing Smite'),
        (3, 'Heat Metal'), (3, 'Magic Weapon'),
        (5, 'Elemental Weapon'), (5, 'Protection from Energy'),
        (7, 'Fabricate'), (7, 'Wall of Fire'),
        (9, 'Animate Objects'), (9, 'Creation'),
    ],
    ('Cleric', 'Grave Domain'): [
        (1, 'Bane'), (1, 'False Life'),
        (3, 'Gentle Repose'), (3, 'Ray of Enfeeblement'),
        (5, 'Revivify'), (5, 'Vampiric Touch'),
        (7, 'Blight'), (7, 'Death Ward'),
        (9, 'Antilife Shell'), (9, 'Raise Dead'),
    ],
    ('Cleric', 'Order Domain'): [
        (1, 'Command'), (1, 'Heroism'),
        (3, 'Hold Person'), (3, 'Zone of Truth'),
        (5, 'Mass Healing Word'), (5, 'Slow'),
        (7, 'Compulsion'), (7, 'Locate Creature'),
        (9, 'Commune'), (9, 'Dominate Person'),
    ],
    ('Cleric', 'Peace Domain'): [
        (1, 'Heroism'), (1, 'Sanctuary'),
        (3, 'Aid'), (3, 'Warding Bond'),
        (5, 'Beacon of Hope'), (5, 'Sending'),
        (7, 'Aura of Purity'), (7, "Otiluke's Resilient Sphere"),
        (9, 'Greater Restoration'), (9, "Rary's Telepathic Bond"),
    ],
    ('Cleric', 'Twilight Domain'): [
        (1, 'Faerie Fire'), (1, 'Sleep'),
        (3, 'Moonbeam'), (3, 'See Invisibility'),
        (5, 'Aura of Vitality'), (5, "Leomund's Tiny Hut"),
        (7, 'Aura of Life'), (7, 'Greater Invisibility'),
        (9, 'Circle of Power'), (9, 'Mislead'),
    ],
    # ── Paladin Oaths — unlock at level 3, then 5/9/13/17 ────────────────
    ('Paladin', 'Oath of Devotion'): [
        (3, 'Protection from Evil and Good'), (3, 'Sanctuary'),
        (5, 'Lesser Restoration'), (5, 'Zone of Truth'),
        (9, 'Beacon of Hope'), (9, 'Dispel Magic'),
        (13, 'Freedom of Movement'), (13, 'Guardian of Faith'),
        (17, 'Commune'), (17, 'Flame Strike'),
    ],
    ('Paladin', 'Oath of the Ancients'): [
        (3, 'Ensnaring Strike'), (3, 'Speak with Animals'),
        (5, 'Moonbeam'), (5, 'Misty Step'),
        (9, 'Plant Growth'), (9, 'Protection from Energy'),
        (13, 'Ice Storm'), (13, 'Stoneskin'),
        (17, 'Commune with Nature'), (17, 'Tree Stride'),
    ],
    ('Paladin', 'Oath of Vengeance'): [
        (3, 'Bane'), (3, "Hunter's Mark"),
        (5, 'Hold Person'), (5, 'Misty Step'),
        (9, 'Haste'), (9, 'Protection from Energy'),
        (13, 'Banishment'), (13, 'Dimension Door'),
        (17, 'Hold Monster'), (17, 'Scrying'),
    ],
    ('Paladin', 'Oath of Conquest'): [
        (3, 'Armor of Agathys'), (3, 'Command'),
        (5, 'Hold Person'), (5, 'Spiritual Weapon'),
        (9, 'Bestow Curse'), (9, 'Fear'),
        (13, 'Dominate Beast'), (13, 'Stoneskin'),
        (17, 'Cloudkill'), (17, 'Dominate Person'),
    ],
    ('Paladin', 'Oath of Glory'): [
        (3, 'Guiding Bolt'), (3, 'Heroism'),
        (5, 'Enhance Ability'), (5, 'Magic Weapon'),
        (9, 'Haste'), (9, 'Protection from Energy'),
        (13, 'Compulsion'), (13, 'Freedom of Movement'),
        (17, 'Legend Lore'), (17, "Yolande's Regal Presence"),
    ],
    ('Paladin', 'Oath of Redemption'): [
        (3, 'Sanctuary'), (3, 'Sleep'),
        (5, 'Calm Emotions'), (5, 'Hold Person'),
        (9, 'Counterspell'), (9, 'Hypnotic Pattern'),
        (13, "Otiluke's Resilient Sphere"), (13, 'Stoneskin'),
        (17, 'Hold Monster'), (17, 'Wall of Force'),
    ],
    ('Paladin', 'Oath of the Watchers'): [
        (3, 'Alarm'), (3, 'Detect Magic'),
        (5, 'Moonbeam'), (5, 'See Invisibility'),
        (9, 'Counterspell'), (9, 'Nondetection'),
        (13, 'Aura of Purity'), (13, 'Banishment'),
        (17, 'Hold Monster'), (17, 'Scrying'),
    ],
    ('Paladin', 'Oath of the Crown'): [
        (3, 'Command'), (3, 'Compelled Duel'),
        (5, 'Warding Bond'), (5, 'Zone of Truth'),
        (9, 'Aura of Vitality'), (9, 'Spirit Guardians'),
        (13, 'Banishment'), (13, 'Guardian of Faith'),
        (17, 'Circle of Power'), (17, 'Geas'),
    ],
    ('Paladin', 'Oathbreaker'): [
        (3, 'Hellish Rebuke'), (3, 'Inflict Wounds'),
        (5, 'Crown of Madness'), (5, 'Darkness'),
        (9, 'Animate Dead'), (9, 'Bestow Curse'),
        (13, 'Blight'), (13, 'Confusion'),
        (17, 'Contagion'), (17, 'Dominate Person'),
    ],
    # ── Ranger Conclaves — unlock at level 3, then 5/9/13/17 ─────────────
    ('Ranger', 'Beast Master'):  [],
    ('Ranger', 'Hunter'):        [],
    ('Ranger', 'Gloom Stalker'): [
        (3, 'Disguise Self'),
        (5, 'Rope Trick'),
        (9, 'Fear'),
        (13, 'Greater Invisibility'),
        (17, 'Seeming'),
    ],
    ('Ranger', 'Horizon Walker'): [
        (3, 'Protection from Evil and Good'),
        (5, 'Misty Step'),
        (9, 'Haste'),
        (13, 'Banishment'),
        (17, 'Teleportation Circle'),
    ],
    ('Ranger', 'Monster Slayer'): [
        (3, 'Protection from Evil and Good'),
        (5, 'Zone of Truth'),
        (9, 'Magic Circle'),
        (13, 'Banishment'),
        (17, 'Hold Monster'),
    ],
    ('Ranger', 'Fey Wanderer'): [
        (3, 'Charm Person'),
        (5, 'Misty Step'),
        (9, 'Dispel Magic'),
        (13, 'Dimension Door'),
        (17, 'Mislead'),
    ],
    # ── Warlock Patrons — unlock at level 1, then 3/5/7/9 ────────────────
    ('Warlock', 'Archfey'): [
        (1, 'Faerie Fire'), (1, 'Sleep'),
        (3, 'Calm Emotions'), (3, 'Phantasmal Force'),
        (5, 'Blink'), (5, 'Plant Growth'),
        (7, 'Dominate Beast'), (7, 'Greater Invisibility'),
        (9, 'Dominate Person'), (9, 'Seeming'),
    ],
    ('Warlock', 'The Archfey'): [
        (1, 'Faerie Fire'), (1, 'Sleep'),
        (3, 'Calm Emotions'), (3, 'Phantasmal Force'),
        (5, 'Blink'), (5, 'Plant Growth'),
        (7, 'Dominate Beast'), (7, 'Greater Invisibility'),
        (9, 'Dominate Person'), (9, 'Seeming'),
    ],
    ('Warlock', 'Fiend'): [
        (1, 'Burning Hands'), (1, 'Command'),
        (3, 'Blindness/Deafness'), (3, 'Scorching Ray'),
        (5, 'Fireball'), (5, 'Stinking Cloud'),
        (7, 'Fire Shield'), (7, 'Wall of Fire'),
        (9, 'Flame Strike'), (9, 'Hallow'),
    ],
    ('Warlock', 'The Fiend'): [
        (1, 'Burning Hands'), (1, 'Command'),
        (3, 'Blindness/Deafness'), (3, 'Scorching Ray'),
        (5, 'Fireball'), (5, 'Stinking Cloud'),
        (7, 'Fire Shield'), (7, 'Wall of Fire'),
        (9, 'Flame Strike'), (9, 'Hallow'),
    ],
    ('Warlock', 'Great Old One'): [
        (1, 'Dissonant Whispers'), (1, "Tasha's Hideous Laughter"),
        (3, 'Detect Thoughts'), (3, 'Phantasmal Force'),
        (5, 'Clairvoyance'), (5, 'Sending'),
        (7, 'Dominate Beast'), (7, "Evard's Black Tentacles"),
        (9, 'Dominate Person'), (9, 'Telekinesis'),
    ],
    ('Warlock', 'The Great Old One'): [
        (1, 'Dissonant Whispers'), (1, "Tasha's Hideous Laughter"),
        (3, 'Detect Thoughts'), (3, 'Phantasmal Force'),
        (5, 'Clairvoyance'), (5, 'Sending'),
        (7, 'Dominate Beast'), (7, "Evard's Black Tentacles"),
        (9, 'Dominate Person'), (9, 'Telekinesis'),
    ],
    ('Warlock', 'Hexblade'): [
        (1, 'Shield'), (1, 'Wrathful Smite'),
        (3, 'Blur'), (3, 'Branding Smite'),
        (5, 'Blink'), (5, 'Elemental Weapon'),
        (7, 'Phantasmal Killer'), (7, 'Staggering Smite'),
        (9, 'Banishing Smite'), (9, 'Cone of Cold'),
    ],
    ('Warlock', 'The Hexblade'): [
        (1, 'Shield'), (1, 'Wrathful Smite'),
        (3, 'Blur'), (3, 'Branding Smite'),
        (5, 'Blink'), (5, 'Elemental Weapon'),
        (7, 'Phantasmal Killer'), (7, 'Staggering Smite'),
        (9, 'Banishing Smite'), (9, 'Cone of Cold'),
    ],
    ('Warlock', 'Undead'): [
        (1, 'Bane'), (1, 'False Life'),
        (3, 'Blindness/Deafness'), (3, 'Phantasmal Force'),
        (5, 'Phantom Steed'), (5, 'Speak with Dead'),
        (7, 'Death Ward'), (7, 'Greater Invisibility'),
        (9, 'Antilife Shell'), (9, 'Cloudkill'),
    ],
    ('Warlock', 'The Undead'): [
        (1, 'Bane'), (1, 'False Life'),
        (3, 'Blindness/Deafness'), (3, 'Phantasmal Force'),
        (5, 'Phantom Steed'), (5, 'Speak with Dead'),
        (7, 'Death Ward'), (7, 'Greater Invisibility'),
        (9, 'Antilife Shell'), (9, 'Cloudkill'),
    ],
    ('Warlock', 'Celestial'): [
        (1, 'Cure Wounds'), (1, 'Guiding Bolt'),
        (3, 'Flaming Sphere'), (3, 'Lesser Restoration'),
        (5, 'Daylight'), (5, 'Revivify'),
        (7, 'Guardian of Faith'), (7, 'Wall of Fire'),
        (9, 'Flame Strike'), (9, 'Scrying'),
    ],
    ('Warlock', 'The Celestial'): [
        (1, 'Cure Wounds'), (1, 'Guiding Bolt'),
        (3, 'Flaming Sphere'), (3, 'Lesser Restoration'),
        (5, 'Daylight'), (5, 'Revivify'),
        (7, 'Guardian of Faith'), (7, 'Wall of Fire'),
        (9, 'Flame Strike'), (9, 'Scrying'),
    ],
    # ── Sorcerer Subclasses ───────────────────────────────────────────────
    ('Sorcerer', 'Aberrant Mind'): [
        (1, 'Arms of Hadar'), (1, 'Dissonant Whispers'),
        (3, 'Calm Emotions'), (3, 'Detect Thoughts'),
        (5, 'Hunger of Hadar'), (5, 'Sending'),
        (7, "Evard's Black Tentacles"), (7, 'Summon Aberration'),
        (9, 'Modify Memory'), (9, "Rary's Telepathic Bond"),
    ],
    ('Sorcerer', 'Clockwork Soul'): [
        (1, 'Alarm'), (1, 'Protection from Evil and Good'),
        (3, 'Aid'), (3, 'Lesser Restoration'),
        (5, 'Dispel Magic'), (5, 'Protection from Energy'),
        (7, 'Freedom of Movement'), (7, 'Summon Construct'),
        (9, 'Dispel Evil and Good'), (9, 'Wall of Force'),
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# CLASS FEATURES THAT REQUIRE PLAYER CHOICE AT CHARACTER CREATION
# ═══════════════════════════════════════════════════════════════════════════

FIGHTING_STYLES = [
    ('Archery',                 '+2 bonus to attack rolls with ranged weapons.'),
    ('Defense',                 '+1 to AC while wearing armor.'),
    ('Dueling',                 '+2 damage when using one-handed melee weapon with no other weapon.'),
    ('Great Weapon Fighting',   'Reroll 1s and 2s on damage dice with two-handed/versatile weapons; keep new roll.'),
    ('Protection',              'Reaction: impose disadvantage on attack vs. ally within 5 ft. Requires shield.'),
    ('Two-Weapon Fighting',     'Add ability modifier to off-hand attack damage.'),
    ('Blind Fighting',          'Blindsight 10 ft — see invisible creatures within 10 ft.'),
    ('Interception',            'Reaction: 1d10 + prof bonus reduction to ally\'s incoming damage. Requires weapon/shield.'),
    ('Superior Technique',      'Learn one maneuver (4 options); gain one Superiority Die (d6).'),
    ('Thrown Weapon Fighting',  'Draw thrown weapons as part of attack; +2 damage with thrown weapons.'),
    ('Unarmed Fighting',        'Unarmed strikes deal 1d6 (1d8 without other weapons); grappled creatures take 1d4.'),
]

PALADIN_FIGHTING_STYLES = [
    ('Blessed Warrior',  'Learn 2 cleric cantrips; they count as paladin spells for you.'),
    ('Blind Fighting',   'Blindsight 10 ft.'),
    ('Defense',          '+1 to AC while wearing armor.'),
    ('Dueling',          '+2 damage with one-handed melee weapon and no other weapon.'),
    ('Great Weapon Fighting', 'Reroll 1s and 2s on weapon damage dice.'),
    ('Interception',     'Reduce ally damage by 1d10 + prof. Reaction.'),
    ('Protection',       'Impose disadvantage on attack vs. ally within 5 ft. Requires shield.'),
]

RANGER_FIGHTING_STYLES = [
    ('Archery',          '+2 to ranged attack rolls.'),
    ('Blind Fighting',   'Blindsight 10 ft.'),
    ('Defense',          '+1 AC while wearing armor.'),
    ('Druidic Warrior',  'Learn 2 druid cantrips; they count as ranger spells.'),
    ('Dueling',          '+2 damage with one-handed melee weapon and no other weapon.'),
    ('Thrown Weapon Fighting', 'Draw thrown weapons for free; +2 damage with thrown.'),
    ('Two-Weapon Fighting',    'Add mod to off-hand attack damage.'),
]

METAMAGIC_OPTIONS = [
    ('Careful Spell',    '1 SP: Up to CHA-mod creatures automatically succeed on spell save.'),
    ('Distant Spell',    '1 SP: Double spell\'s range (or 30 ft if touch).'),
    ('Empowered Spell',  '1 SP: Reroll up to CHA-mod damage dice; must keep new result.'),
    ('Extended Spell',   '1 SP: Double spell\'s duration (max 24 hr).'),
    ('Heightened Spell', '3 SP: One target has disadvantage on first save vs. spell.'),
    ('Quickened Spell',  '2 SP: Change casting time of 1-action spell to bonus action.'),
    ('Subtle Spell',     '1 SP: Cast without verbal or somatic components.'),
    ('Twinned Spell',    '1 SP × spell level: Target a second creature with single-target spell.'),
    ('Seeking Spell',    '2 SP: Reroll a missed spell attack roll.'),
    ('Transmuted Spell', '1 SP: Change damage type to acid, cold, fire, lightning, poison, or thunder.'),
]

ELDRITCH_INVOCATIONS = [
    ('Agonizing Blast',      'Requires Eldritch Blast. Add CHA modifier to EB damage.'),
    ('Armor of Shadows',     'Cast Mage Armor on yourself at will without expending a spell slot.'),
    ('Beast Speech',         'Cast Speak with Animals at will without expending a spell slot.'),
    ('Beguiling Influence',  'Gain proficiency in Deception and Persuasion.'),
    ('Devil\'s Sight',       'See normally in darkness (magical and nonmagical) to 120 ft.'),
    ('Eldritch Mind',        'Advantage on CON saves to maintain concentration.'),
    ('Eldritch Sight',       'Cast Detect Magic at will without expending a spell slot.'),
    ('Eldritch Spear',       'Requires Eldritch Blast. Range becomes 300 ft.'),
    ('Eyes of the Rune Keeper', 'Read all writing.'),
    ('Fiendish Vigor',       'Cast False Life on yourself at will as a 1st-level spell, no slot needed.'),
    ('Gaze of Two Minds',    'Touch a willing humanoid — perceive through their senses until your next turn.'),
    ('Grasp of Hadar',       'Requires Eldritch Blast. Pull struck creature 10 ft closer.'),
    ('Lance of Lethargy',    'Requires Eldritch Blast. Struck creature\'s speed -10 ft until next turn.'),
    ('Mask of Many Faces',   'Cast Disguise Self at will, no spell slot.'),
    ('Misty Visions',        'Cast Silent Image at will, no spell slot.'),
    ('Repelling Blast',      'Requires Eldritch Blast. Push struck creature 10 ft away.'),
    ('Thief of Five Fates',  'Cast Bane once per long rest using a spell slot.'),
    ('Voice of the Chain Master', 'Requires Pact of the Chain. Communicate with familiar; perceive through it.'),
]

DIVINE_SMITE_NOTE = (
    'Divine Smite — Expend a spell slot when you hit: deal 2d8 + 1d8/slot level radiant (above 1st), '
    '+1d8 vs undead/fiends. No action required.'
)

SORCEROUS_ORIGINS = [
    ('Draconic Bloodline', 'Dragon ancestor — +1 HP/level, natural armor 13+DEX, draconic affinity spells.'),
    ('Wild Magic',         'Wild Magic Surge on spells — chaotic effects. Tides of Chaos: advantage on one roll/day.'),
    ('Storm Sorcery',      'Tempest affinity — fly 10 ft when casting, lightning/thunder resistance.'),
    ('Shadow Magic',       'Shadow origin — Darkvision 120 ft, Strength of the Grave 1/day, summon Hound of Ill Omen.'),
    ('Divine Soul',        'Divine origin — one extra cleric cantrip, healing bonus, all cleric spells available.'),
    ('Aberrant Mind',      'Psionic power — telepathy 30 ft, expanded spell list (psionic spells).'),
    ('Clockwork Soul',     'Order/Mechanus origin — cancel advantage/disadvantage, expanded spell list.'),
    ('Lunar Sorcery',      'Moon-touched — lunar embodiment phases change your expanded spell list.'),
]

OTHERWORLDLY_PATRONS = [
    ('The Archfey',      'Fey patron — charm/fear resistance, misty escape, beguiling defenses.'),
    ('The Fiend',        'Devil/demon patron — Dark One\'s Blessing (temp HP on kills), expanded fire spells.'),
    ('The Great Old One','Cosmic horror patron — telepathy, mental barrier, alien knowledge.'),
    ('The Hexblade',     'Weapon spirit patron — Hexblade\'s Curse, Hex Warrior (CHA to one weapon), medium armor.'),
    ('The Undead',       'Undead patron — Form of Dread (frighten + temp HP), undead nature spells.'),
    ('The Celestial',    'Angelic patron — healing light pool, radiant cantrips, fire/radiant damage.'),
    ('The Fathomless',   'Ocean/Kraken patron — tentacle attack, swimming speed, underwater advantage.'),
    ('The Genie',        'Elemental patron — Genie\'s vessel (refuge), expanded elemental spell list.'),
]

PACT_BOONS = [
    ('Pact of the Blade',  'Summon a magic weapon in any form. You are proficient with it. Use CHA for attacks.'),
    ('Pact of the Chain',  'Ritual: Find Familiar. Familiar can be imp, pseudodragon, quasit, or sprite.'),
    ('Pact of the Tome',   'Receive a Book of Shadows with 3 extra cantrips from any spell list.'),
    ('Pact of the Talisman','Talisman: +1d4 to ability checks that fail. Ally can wear it.'),
]

DIVINE_DOMAINS = [
    ('Arcana Domain',      'Arcane magic affinity — arcane initiate cantrips, ward vs elementals/undead.'),
    ('Death Domain',       'Undead/necrotic mastery — reaper cantrip improvement, necromancy spells, undead charm.'),
    ('Forge Domain',       'Creation and crafting — Blessing of the Forge (+1 to armor/weapon), fire affinity.'),
    ('Grave Domain',       'Life/death balance — Circle of Mortality, Eyes of the Grave, spare the dying buff.'),
    ('Knowledge Domain',   'Lore mastery — 2 extra skill proficiencies, Blessing of Knowledge (expertise).'),
    ('Life Domain',        'Healing mastery — Disciple of Life (bonus healing), heavy armor proficiency.'),
    ('Light Domain',       'Radiance/fire — Warding Flare reaction, heavy armor proficiency.'),
    ('Nature Domain',      'Nature affinity — Acolyte of Nature (druid cantrip + skill), heavy armor.'),
    ('Order Domain',       'Law enforcement — Voice of Authority (ally reaction attacks), heavy armor.'),
    ('Peace Domain',       'Harmony/protection — Emboldening Bond (bonus to rolls in range).'),
    ('Tempest Domain',     'Storm mastery — Wrath of the Storm (lightning reaction), heavy armor.'),
    ('Trickery Domain',    'Deception — Blessing of the Trickster (+stealth to ally), invoke duplicity later.'),
    ('Twilight Domain',    'Dusk and protection — Eyes of Night (60 ft darkvision sharing), heavy armor.'),
    ('War Domain',         'Battle mastery — War Priest (bonus weapon attack uses), heavy armor.'),
]

RANGER_ARCHETYPES = [
    ('Beast Master',     'Bond with an animal companion. It acts on your turn, can attack.'),
    ('Hunter',           'Hunter\'s Prey at level 3: Colossus Slayer, Giant Killer, or Horde Breaker.'),
    ('Gloom Stalker',    'Darkness specialist — invisible in dim/dark, +10 ft speed first turn, Dread Ambusher.'),
    ('Fey Wanderer',     'Fey magic — Dreadful Strikes, Otherworldly Glamour (CHA add to saves).'),
    ('Horizon Walker',   'Planar traveler — Detect Portal, Planar Warrior (+1d8 force on attacks).'),
    ('Monster Slayer',   'Supernatural hunter — Hunter\'s Sense (weakness detection), Slayer\'s Prey.'),
    ('Swarmkeeper',      'Swarm of spirits — Gathered Swarm (push/pull/ride with swarm).'),
]

ROGUE_ARCHETYPES = [
    ('Thief',              'Fast Hands (bonus-action item use), Second-Story Work (climb speed), use magic items.'),
    ('Assassin',           'Infiltration Expertise (false identities), Assassinate (auto-crit on surprised foes).'),
    ('Arcane Trickster',   'Spellcasting (Enchantment/Illusion), Mage Hand Legerdemain (enhanced hand).'),
    ('Inquisitive',        'Ear for Deceit, Eye for Detail (Investigate as bonus action), Insightful Fighting.'),
    ('Mastermind',         'Misdirection, Master of Tactics (Help as bonus action from 30 ft).'),
    ('Scout',              'Skirmisher (reaction move), Survivalist (Nature + Survival expertise).'),
    ('Soulknife',          'Psionic blades — Psychic Blades (1d6 psychic), Psi-Bolstered Knack, Telepath.'),
    ('Swashbuckler',       'Panache, Fancy Footwork (leave melee without AoO), Rakish Audacity (sneak with no ally).'),
    ('Phantom',            'Whispers of the Dead (tool proficiency from dead), Wails from the Grave (psychic).'),
]

BARBARIAN_PATHS = [
    ('Path of the Berserker',    'Frenzy (bonus attack + exhaustion on rage end), Mindless Rage, Intimidating Presence.'),
    ('Path of the Totem Warrior','Spirit totem choice (Bear/Eagle/Elk/Tiger/Wolf) with unique powers per aspect.'),
    ('Path of the Ancestral Guardian', 'Spectral Guardians when raging — protect allies by marking foes.'),
    ('Path of the Battlerager',  'Spiked armor — bonus attack on charge, spikes deal damage on grapple.'),
    ('Path of the Storm Herald', 'Choose Storm Aura environment (Desert/Sea/Tundra) with aura effects while raging.'),
    ('Path of the Zealot',       'Divine Fury (+radiant/necrotic on first attack in rage), cannot die while raging.'),
    ('Path of the Beast',        'Bestial transformations — claws, bite, tail; make multiple natural attacks.'),
    ('Path of Wild Magic',       'Wild Surge table on rage, Bolstering Magic (bonus to rolls), unstable magic.'),
    ('Path of the Giant',        'Giant\'s Havoc (+5 ft reach, size change), Elemental Cleaver (energy-infused weapon).'),
]

MONK_TRADITIONS = [
    ('Way of the Open Hand',   'Open Hand Technique (push/prone/no-react on hit), Wholeness of Body, Tranquility.'),
    ('Way of Shadow',          'Shadow Arts (cast darkness/silence/pass without trace), Shadow Step teleport.'),
    ('Way of the Four Elements','Elemental disciplines (shape fire/earth/wind/water with ki).'),
    ('Way of the Astral Self', 'Summon astral arms (reach attacks), astral visage, full astral form.'),
    ('Way of the Drunken Master','Drunken Technique (+10 ft move on Flurry), Tipsy Sway (redirect attacks).'),
    ('Way of the Kensei',      'Kensei weapons (extra types), Kensei\'s Shot (+1d4 ranged), Magic Kensei Weapons.'),
    ('Way of the Mercy',       'Implements of Mercy (healer mask), Hand of Healing, Hand of Harm.'),
    ('Way of the Sun Soul',    'Radiant Sun Bolt (radiant ranged), Searing Arc Strike, Searing Sunburst.'),
    ('Way of the Long Death',  'Touch of Death (temp HP on kill), Hour of Reaping (frighten all nearby).'),
]

DRUID_CIRCLES = [
    ('Circle of the Land',     'Bonus spells by terrain type, Natural Recovery (regain slots on short rest).'),
    ('Circle of the Moon',     'Combat Wild Shape (use as bonus action), improved beast forms, elemental forms.'),
    ('Circle of Dreams',       'Balm of the Summer Court (healing pool), Hearth of Moonlight and Shadow (camp aura).'),
    ('Circle of the Shepherd', 'Spirit Totem (bonus to summons), summon spirit guardians.'),
    ('Circle of Spores',       'Halo of Spores (necrotic reaction), Symbiotic Entity (transformed wildshape).'),
    ('Circle of Stars',        'Star Map, Starry Form (three constellation forms), Cosmic Omen.'),
    ('Circle of Wildfire',     'Wildfire Spirit (summon fire elemental), Enhanced Bond (+1d8 to fire spells).'),
    ('Circle of the Sea',      'Wrath of the Sea (aura of storm damage), Aquatic Affinity.'),
]

WIZARD_SCHOOLS = [
    ('School of Abjuration',   'Arcane Ward (HP buffer from abjuration spells), Projected Ward (transfer to ally).'),
    ('School of Conjuration',  'Minor Conjuration (create 3-cubic-ft object), Focused Conjuration (conc can\'t break).'),
    ('School of Divination',   'Portent (roll 2 d20s at dawn; use them to replace rolls).'),
    ('School of Enchantment',  'Hypnotic Gaze (incapacitate nearby creature as action), Instinctive Charm.'),
    ('School of Evocation',    'Sculpt Spells (choose creatures to auto-succeed on evocation saves), Potent Cantrip.'),
    ('School of Illusion',     'Improved Minor Illusion (sound AND image), Malleable Illusions (change illusions).'),
    ('School of Necromancy',   'Grim Harvest (HP when spells kill), Undead Thralls (animate dead improvements).'),
    ('School of Transmutation','Minor Alchemy (change material type), Transmuter\'s Stone (passive bonus).'),
    ('Bladesinging',           'Bladesong (bonus AC+speed, INT to concentration, extra attack). Requires elf/half-elf.'),
    ('Order of Scribes',       'Awakened Spellbook (substitute damage types, cast without components), Manifest Mind.'),
    ('Chronurgy Magic',        'Chronal Shift (alter rolls near you), Temporal Awareness (+INT to initiative).'),
    ('Graviturgy Magic',       'Adjust Density (speed/AC tradeoff), Gravity Well (repositioning on hit).'),
    ('War Magic',              'Arcane Deflection (reaction +2 AC/+4 saves), Tactical Wit (+INT to initiative).'),
]

BARD_COLLEGES = [
    ('College of Lore',       'Bonus Proficiencies (3 skills), Cutting Words (subtract 1d6 from enemy roll).'),
    ('College of Valor',      'Bonus Proficiencies (medium armor, shields, martial weapons), Combat Inspiration.'),
    ('College of Glamour',    'Mantle of Inspiration (temp HP to allies), Enthralling Performance.'),
    ('College of Swords',     'Bonus Proficiencies (medium armor, scimitars), Blade Flourish maneuvers.'),
    ('College of Whispers',   'Psychic Blades (extra psychic damage), Words of Terror.'),
    ('College of Creation',   'Note of Potential, Performance of Creation (create object).'),
    ('College of Eloquence',  'Silver Tongue (min 10 on Persuasion/Deception), Unsettling Words.'),
    ('College of Spirits',    'Spiritual Focus (bonus to spells), Tales from Beyond (d6 table effects).'),
]

ARTIFICER_SPECIALIZATIONS = [
    ('Alchemist',       'Experimental Elixir (random beneficial effects each long rest), bonus healing spells.'),
    ('Armorer',         'Arcane Armor (battle/guardian suit), armor model modifications.'),
    ('Artillerist',     'Eldritch Cannon (force ballista/flamethrower/protector turret).'),
    ('Battle Smith',    'Battle Ready (INT for weapon attacks), Steel Defender (mechanical construct companion).'),
]

# ═══════════════════════════════════════════════════════════════════════════
# PICK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _display_and_pick(console, title, options, count, allow_skip=False):
    """
    Generic numbered picker. options = list of (name, desc) tuples.
    Returns list of chosen name strings.
    """
    console.print()
    console.print(Panel(
        f'[bold cyan]{title}[/bold cyan]\n'
        + (f'[dim]Choose {count}.[/dim]' if count else '[dim]Choose any number.[/dim]'),
        border_style='cyan', padding=(0, 2),
    ))

    tbl = Table(show_header=False, border_style='dim', padding=(0, 1), box=None)
    tbl.add_column('#',    style='bold cyan',  width=3)
    tbl.add_column('Name', style='bold white',  min_width=26)
    tbl.add_column('Description', style='white', min_width=48, max_width=68)

    for i, (name, desc) in enumerate(options, 1):
        tbl.add_row(str(i), name, desc)

    console.print(tbl)

    if count == 1:
        console.print(f'[dim]Enter a number (1–{len(options)}).[/dim]')
    else:
        console.print(f'[dim]Enter {count} numbers separated by spaces (e.g. "1 4"). '
                      + ('Or press Enter to skip.' if allow_skip else '') + '[/dim]')

    while True:
        raw = console.input('[bold white]  → [/bold white]').strip()

        if not raw and allow_skip:
            return []

        nums = re.findall(r'\d+', raw)
        if not nums:
            console.print('[red]Please enter valid numbers.[/red]')
            continue

        selected = []
        valid = True
        for n in nums:
            idx = int(n) - 1
            if 0 <= idx < len(options):
                if idx not in selected:
                    selected.append(idx)
            else:
                console.print(f'[red]{n} is out of range.[/red]')
                valid = False
                break

        if not valid:
            continue

        if count and len(selected) != count:
            console.print(f'[red]Please choose exactly {count} (you chose {len(selected)}).[/red]')
            continue

        chosen = [options[i][0] for i in selected]
        for name in chosen:
            console.print(f'  [green]✓ {name}[/green]')
        return chosen


def _display_spells_and_pick(console, spells, count, tier_label):
    """
    spells = list of (name, school, description) tuples.
    Returns list of chosen spell name strings.
    """
    if not spells:
        return []

    console.print()
    tbl = Table(show_header=True, header_style='bold cyan', border_style='dim', padding=(0, 1))
    tbl.add_column('#',       style='dim',        width=3)
    tbl.add_column('Spell',   style='bold white',  min_width=22)
    tbl.add_column('School',  style='dim yellow',  min_width=14)
    tbl.add_column('Effect',  style='white',       min_width=46, max_width=66)

    for i, entry in enumerate(spells, 1):
        # Scraper entries are dicts: {"name":..,"school":..,"desc":..,"casting_time":..}
        # Hardcoded entries are tuples: (name, school, desc)
        if isinstance(entry, dict):
            name   = entry.get("name", "")
            school = entry.get("school", "")
            desc   = entry.get("desc", "")
            # Show casting time / range / duration as a dim note if present
            parts  = [p for p in (
                entry.get("casting_time", ""),
                entry.get("range", ""),
                entry.get("duration", ""),
            ) if p]
            if parts:
                desc = desc + "  [dim]" + " | ".join(parts) + "[/dim]"
        else:
            # Legacy tuple/list format (name, school, desc[, ...])
            name   = entry[0]
            school = entry[1]
            desc   = entry[2]
        tbl.add_row(str(i), name, school, desc)

    console.print(tbl)

    if count == 1:
        console.print(f'[dim]Choose 1 {tier_label}. Enter to skip.[/dim]')
    else:
        console.print(f'[dim]Choose {count} {tier_label}s. Enter numbers separated by spaces, or Enter to skip.[/dim]')

    while True:
        raw = console.input('[bold white]  → [/bold white]').strip()
        if not raw:
            return []

        nums = re.findall(r'\d+', raw)
        selected = []
        valid = True
        for n in nums:
            idx = int(n) - 1
            if 0 <= idx < len(spells):
                if idx not in selected:
                    selected.append(idx)
            else:
                console.print(f'[red]{n} out of range.[/red]')
                valid = False
                break

        if not valid:
            continue

        if len(selected) < count:
            confirm = console.input(
                f'[yellow]You chose {len(selected)} of {count}. Keep? (y/n): [/yellow]'
            ).strip().lower()
            if confirm != 'y':
                continue

        chosen = [
            spells[i]["name"] if isinstance(spells[i], dict) else spells[i][0]
            for i in selected
        ]
        for name in chosen:
            console.print(f'  [green]✓ {name}[/green]')
        return chosen


def get_subclass_bonus_spells(
    char_class: str,
    subclass:   str,
    level:      int = 20,
) -> list:
    """
    Returns the list of bonus spells auto-granted by a subclass at or below
    the given character level.

    SUBCLASS_BONUS_SPELLS entries are lists of (min_level, spell_name) tuples.
    Only spells whose min_level <= level are returned, so a Paladin at level 3
    only sees their first two oath spells, not the entire list.

    Parameters
    ----------
    char_class : str   e.g. 'Paladin'
    subclass   : str   e.g. 'Oath of Devotion' (empty string → no subclass → [])
    level      : int   Character level (default 20 = return everything, for
                       backwards-compat callers that don't pass level)
    """
    # Guard: no subclass means no bonus spells — avoids empty-string partial match
    sub_key = (subclass or '').split('(')[0].strip()
    if not sub_key:
        return []

    class_key = char_class.split('(')[0].strip()

    # Try exact match first, then partial-match
    matched_entry = None
    for (cls, sub), spell_list in SUBCLASS_BONUS_SPELLS.items():
        if cls == class_key and (sub == sub_key or sub in sub_key or sub_key in sub):
            matched_entry = spell_list
            break

    if matched_entry is None:
        return []

    # matched_entry is [(min_level, spell_name), ...]
    # Filter to spells unlocked at or below the character's current level
    result = []
    for item in matched_entry:
        if isinstance(item, tuple):
            min_lvl, spell_name = item
            if min_lvl <= level:
                result.append(spell_name)
        else:
            # Legacy flat string (shouldn't happen, but handle gracefully)
            result.append(item)
    return result


def pick_official_spells(
    console: Console,
    char_class: str,
    subclass: str,
    level: int,
    system_id: str = 'dnd_5e',
) -> list:
    """
    Presents the official spell list for a class (or subclass, for AT/EK)
    and lets the player pick cantrips + leveled spells for their level.

    spell_scraper-aware:
      - Uses live wiki data from spells_cache.json when available.
      - Enforces subclass school restrictions:
          Arcane Trickster  → free cantrips; Ench/Illusion wizard leveled spells
                              + 2 free any-school picks; Mage Hand always known
          Eldritch Knight   → free cantrips; Abj/Evoc wizard leveled spells
                              + 3 free any-school picks
          Cleric domains    → Full cleric list + auto domain bonus spells
          Paladin oaths     → Full paladin list + auto oath bonus spells
          Warlock patrons   → Full warlock list + expanded patron spell list
      - Falls back to hardcoded DND5E_SPELLS dict if spell_scraper unavailable.

    char_class may be the resolved spell_list_key (e.g. 'Arcane Trickster')
    passed directly from offer_spell_selection_method.
    """
    class_key = char_class.split('(')[0].strip()
    sub_key   = (subclass or '').split('(')[0].strip()

    if system_id not in ('dnd_5e', 'pathfinder_2e', 'starfinder', 'daggerheart'):
        return []

    # ── Resolve spell data and restriction metadata ───────────────────────
    spell_data_by_level = None
    school_filter       = None
    free_picks_left     = 0
    subclass_note       = ''
    guaranteed_cantrips = []   # e.g. ['Mage Hand'] for Arcane Trickster (PHB p.98)

    if _SPELL_SCRAPER_AVAILABLE:
        try:
            # Pass the TRUE class name so SUBCLASS_RESTRICTIONS resolves correctly.
            # e.g. class_key="Rogue", sub_key="Arcane Trickster"
            sc_data = _scraper_get_spells(class_key, sub_key, level)
            if sc_data.get('spells'):
                spell_data_by_level = sc_data['spells']
                school_filter       = sc_data.get('school_filter')
                free_picks_left     = sc_data.get('free_picks', 0)
                subclass_note       = sc_data.get('note', '')
                guaranteed_cantrips = sc_data.get('guaranteed_cantrips', [])
        except Exception as e:
            print(f"[SpellPicker] Scraper error in pick_official_spells: {e}")

    # Fallback: hardcoded DND5E_SPELLS
    if not spell_data_by_level:
        # AT / EK have their own entry in DND5E_SPELLS; try sub_key first,
        # then class_key.
        lookup_key = class_key
        if not DND5E_SPELLS.get(class_key) and sub_key:
            if DND5E_SPELLS.get(sub_key):
                lookup_key = sub_key
        raw = DND5E_SPELLS.get(lookup_key)
        if not raw:
            return []
        spell_data_by_level = {int(k): list(v) for k, v in raw.items()}

    if not spell_data_by_level:
        return []

    # ── Slot / count info from world_builder ─────────────────────────────
    from world_builder import SPELL_SLOTS, _match_spell_class
    matched_key = _match_spell_class(class_key, sub_key)
    if not matched_key:
        return []

    available_levels = sorted(SPELL_SLOTS.get(matched_key, {}).keys())
    if not available_levels:
        return []
    valid         = [l for l in available_levels if l <= level]
    level_cap     = valid[-1] if valid else available_levels[0]
    slot_info     = SPELL_SLOTS[matched_key][level_cap]
    num_cantrips  = slot_info.get('cantrips', 0)
    spells_known  = slot_info.get('spells_known')
    slots         = slot_info.get('slots', {})
    max_spell_lvl = max(slots.keys()) if slots else 0

    if num_cantrips == 0 and max_spell_lvl == 0:
        console.print(f'[dim]{class_key} has no spells at level {level}.[/dim]')
        return []

    # ── Header panel ─────────────────────────────────────────────────────
    restriction_note = ''
    if school_filter:
        restriction_note = (
            f'\n[yellow]School Restriction (leveled spells only):[/yellow] [white]'
            f'{" or ".join(school_filter)} spells only[/white]'
        )
        if free_picks_left:
            restriction_note += (
                f'\n[yellow]Free picks:[/yellow] [white]{free_picks_left} leveled spell(s) '
                f'from any school[/white]'
            )
        restriction_note += '\n[dim]Cantrips: freely chosen from full list (no school restriction).[/dim]'
    if guaranteed_cantrips:
        restriction_note += (
            f'\n[bold green]Guaranteed:[/bold green] [white]'
            f'{", ".join(guaranteed_cantrips)} (always known, counts toward cantrip total)[/white]'
        )
    if subclass_note:
        restriction_note += f'\n[dim]{subclass_note}[/dim]'

    console.print()
    console.print(Panel(
        f'[bold cyan]✨  Spell Selection — {class_key}[/bold cyan]'
        + (f' ({sub_key})' if sub_key else '') + '\n\n'
        '[white]Pick from the official D&D 5e spell list for your class and level.[/white]\n'
        '[dim]Subclass bonus spells are shown separately and added automatically.[/dim]'
        + restriction_note,
        border_style='cyan', padding=(0, 2),
    ))

    # ── Show auto-granted bonus spells ────────────────────────────────────
    bonus_spells = get_subclass_bonus_spells(class_key, sub_key, level)
    if bonus_spells:
        console.print()
        console.print(Panel(
            '[bold yellow]✦  Subclass bonus spells — added automatically:[/bold yellow]\n'
            + '\n'.join(f'  [cyan]•[/cyan] {s}' for s in bonus_spells),
            border_style='yellow', padding=(0, 2),
        ))

    # ── Pre-pick guaranteed cantrips (e.g. Mage Hand for Arcane Trickster) ──
    # PHB rule: AT "knows the Mage Hand cantrip" — it is always known, not chosen.
    # We pre-fill it, remove it from the pick menu, and reduce the required count.
    chosen = list(guaranteed_cantrips)
    if guaranteed_cantrips:
        console.print()
        console.print(
            f'[bold green]  ✦ Guaranteed cantrips already added:[/bold green] '
            + ', '.join(f'[cyan]{c}[/cyan]' for c in guaranteed_cantrips)
        )

    # ── Inner helper: pick with optional free-pick bypass notice ─────────
    def _pick_maybe_filtered(spell_list, count, tier_label):
        """Pick spells; show free-pick reminder if AT/EK has any left."""
        nonlocal free_picks_left
        if spell_list and free_picks_left > 0 and school_filter:
            console.print(
                f'\n[bold yellow]  ⚡ FREE PICK:[/bold yellow] [white]You have '
                f'[bold]{free_picks_left}[/bold] free pick(s) remaining — these can be '
                f'ANY wizard spell, ignoring the school restriction.[/white]'
            )
        return _display_spells_and_pick(console, spell_list, count, tier_label)

    # ── Cantrips ──────────────────────────────────────────────────────────
    # Cantrips are NEVER school-restricted for AT or EK (PHB rule).
    # Subtract guaranteed cantrips already chosen from the required count.
    remaining_cantrip_picks = max(0, num_cantrips - len(guaranteed_cantrips))
    if remaining_cantrip_picks > 0 and spell_data_by_level.get(0):
        # Filter guaranteed cantrips out of the choice list so they don't appear twice
        available_cantrips = [
            s for s in spell_data_by_level[0]
            if (s.get('name') if isinstance(s, dict) else s[0]) not in guaranteed_cantrips
        ]
        console.print(
            f'\n[bold white]── Cantrips — choose {remaining_cantrip_picks} '
            f'──────────────────────────[/bold white]'
        )
        picks = _display_spells_and_pick(
            console, available_cantrips, remaining_cantrip_picks, 'cantrip'
        )
        chosen.extend(picks)

    # ── Leveled spells ────────────────────────────────────────────────────
    if spells_known is not None:
        # Fixed spells-known casters: Bard, Sorcerer, Warlock, Ranger, AT, EK
        remaining = spells_known
        for sp_lvl in range(1, max_spell_lvl + 1):
            level_spells = spell_data_by_level.get(sp_lvl, [])
            if level_spells and remaining > 0:
                per_level = max(1, remaining // max(1, max_spell_lvl - sp_lvl + 1))
                if sp_lvl == max_spell_lvl:
                    per_level = remaining
                lvl_label = _ordinal(sp_lvl)
                school_tag = (
                    f' [yellow]({"/".join(school_filter)} school)[/yellow]'
                    if school_filter else ''
                )
                console.print(
                    f'\n[bold white]── {lvl_label}-Level Spells — choose {per_level}'
                    f'{school_tag} ({remaining} remaining) ──[/bold white]'
                )
                picks = _pick_maybe_filtered(
                    level_spells, per_level, f'{lvl_label}-level spell'
                )
                chosen.extend(picks)
                remaining -= len(picks)
    else:
        # Prepared casters: Cleric, Druid, Paladin, Wizard, Artificer
        for sp_lvl in range(1, max_spell_lvl + 1):
            level_spells = spell_data_by_level.get(sp_lvl, [])
            if level_spells:
                num_slots  = slots.get(sp_lvl, 0)
                pick_count = max(1, num_slots)
                lvl_label  = _ordinal(sp_lvl)
                console.print(
                    f'\n[bold white]── {lvl_label}-Level Spells — choose {pick_count} to start prepared ──[/bold white]'
                )
                console.print(
                    '[dim]Domain/oath spells are added on top automatically.[/dim]'
                )
                picks = _display_spells_and_pick(
                    console, level_spells, pick_count, f'{lvl_label}-level spell'
                )
                chosen.extend(picks)

    # ── Merge bonus spells (domain, oath, patron, etc.) ───────────────────
    all_spells = chosen[:]
    for s in bonus_spells:
        if s not in all_spells:
            all_spells.append(s)

    if all_spells:
        console.print()
        console.print(Panel(
            '[cyan]Your spells:[/cyan]\n'
            + '\n'.join(f'  [cyan]✦[/cyan] {s}' for s in all_spells),
            title='[bold green]✨ Spell Selection Complete[/bold green]',
            border_style='green', padding=(0, 2),
        ))

    return all_spells


def pick_class_features(
    console: Console,
    char_class: str,
    subclass: str,
    level: int,
    system_id: str = 'dnd_5e',
) -> dict:
    """
    For classes with feature choices at character creation (Fighting Style,
    Metamagic, Eldritch Invocations, Divine Domain, etc.), present numbered
    menus so the player picks without typing.

    Returns a dict of chosen features:
      {
        'fighting_style':       'Archery',
        'divine_domain':        'Life Domain',
        'metamagic':            ['Quickened Spell', 'Subtle Spell'],
        'eldritch_invocations': ['Agonizing Blast', 'Devil\'s Sight'],
        'pact_boon':            'Pact of the Blade',
        'otherworldly_patron':  'The Fiend',
        'sorcerous_origin':     'Draconic Bloodline',
        'subclass':             'School of Evocation',
        ...
      }
    """
    class_key = char_class.split('(')[0].strip()
    result = {}

    if system_id not in ('dnd_5e', 'starfinder'):
        return result

    console.print()
    console.print(Panel(
        f'[bold cyan]⚔  Class Features — {class_key}[/bold cyan]'
        + (f' ({subclass})' if subclass else '') + '\n\n'
        '[white]Some class features require a choice at character creation.[/white]\n'
        '[dim]Pick from the numbered menus below.[/dim]',
        border_style='cyan', padding=(0, 2),
    ))

    # ── Fighting Style (Fighter at level 1; Paladin and Ranger at level 2) ──
    # Fighter: PHB p.72 — Fighting Style granted at 1st level.
    # Paladin: PHB p.84 — Fighting Style granted at 2nd level.
    # Ranger:  PHB p.91 — Fighting Style granted at 2nd level.
    if class_key == 'Fighter':
        picks = _display_and_pick(
            console, '⚔  Fighting Style — Choose 1', FIGHTING_STYLES, 1
        )
        if picks:
            result['fighting_style'] = picks[0]

    elif class_key == 'Paladin' and level >= 2:
        picks = _display_and_pick(
            console, '⚔  Fighting Style — Choose 1', PALADIN_FIGHTING_STYLES, 1
        )
        if picks:
            result['fighting_style'] = picks[0]

    elif class_key == 'Ranger' and level >= 2:
        picks = _display_and_pick(
            console, '⚔  Fighting Style — Choose 1', RANGER_FIGHTING_STYLES, 1
        )
        if picks:
            result['fighting_style'] = picks[0]

    # ── Barbarian: Primal Path ────────────────────────────────────────────
    if class_key == 'Barbarian' and level >= 3:
        if not subclass:
            picks = _display_and_pick(
                console, '🔥  Primal Path — Choose 1', BARBARIAN_PATHS, 1
            )
            if picks:
                result['subclass'] = picks[0]

    # ── Bard: College ─────────────────────────────────────────────────────
    elif class_key == 'Bard' and level >= 3:
        if not subclass:
            picks = _display_and_pick(
                console, '🎶  Bard College — Choose 1', BARD_COLLEGES, 1
            )
            if picks:
                result['subclass'] = picks[0]

    # ── Cleric: Divine Domain ─────────────────────────────────────────────
    elif class_key == 'Cleric':
        if not subclass:
            picks = _display_and_pick(
                console, '✝  Divine Domain — Choose 1', DIVINE_DOMAINS, 1
            )
            if picks:
                result['divine_domain'] = picks[0]
                result['subclass']      = picks[0]

    # ── Druid: Circle ────────────────────────────────────────────────────
    elif class_key == 'Druid' and level >= 2:
        if not subclass:
            picks = _display_and_pick(
                console, '🌿  Druid Circle — Choose 1', DRUID_CIRCLES, 1
            )
            if picks:
                result['subclass'] = picks[0]

    # ── Fighter: Martial Archetype ────────────────────────────────────────
    # (chosen at level 3; skip if starting at level 1 with no subclass)
    elif class_key == 'Fighter' and level >= 3 and not subclass:
        fighter_archetypes = [
            ('Battle Master',    'Superiority Dice + Combat Maneuvers (trip, disarm, feint, etc.).'),
            ('Champion',         'Improved Critical (crit on 19-20), Remarkable Athlete.'),
            ('Eldritch Knight',  'Arcane spellcasting (Abjuration/Evocation focus), War Magic.'),
            ('Psi Warrior',      'Telekinetic movement and protection, Psionic Power dice.'),
            ('Rune Knight',      'Carve runes — giant empowerment, grow large, elemental attunement.'),
            ('Echo Knight',      'Manifest echo duplicate — attack from it, teleport to it.'),
            ('Arcane Archer',    'Magical arrows (Banishing, Grasping, Seeking, Shadow, etc.).'),
            ('Cavalier',         'Mounted combat specialist — mark foes, protect mount.'),
            ('Samurai',          'Fighting Spirit (temp HP + advantage), Elegant Courtier (CHA bonus).'),
        ]
        picks = _display_and_pick(console, '⚔  Martial Archetype — Choose 1', fighter_archetypes, 1)
        if picks:
            result['subclass'] = picks[0]

    # ── Monk: Monastic Tradition ──────────────────────────────────────────
    elif class_key == 'Monk' and level >= 3:
        if not subclass:
            picks = _display_and_pick(
                console, '☯  Monastic Tradition — Choose 1', MONK_TRADITIONS, 1
            )
            if picks:
                result['subclass'] = picks[0]

    # ── Paladin: Sacred Oath ──────────────────────────────────────────────
    elif class_key == 'Paladin' and level >= 3:
        if not subclass:
            oaths = [
                ('Oath of Devotion',  'Holy warrior — Protection from Evil/Good, Sacred Weapon aura.'),
                ('Oath of the Ancients','Nature protector — Healing Radiance aura, Nature\'s Wrath.'),
                ('Oath of Vengeance', 'Divine avenger — Vow of Enmity (advantage), Misty Step, Abjure Enemy.'),
                ('Oath of Conquest',  'Tyrant lord — Conquering Presence (frighten), Hold the Line.'),
                ('Oath of Glory',     'Inspiring hero — Inspiring Smite (temp HP), Aura of Alacrity (+10 speed allies).'),
                ('Oath of Redemption','Pacifist protector — Emissary of Peace, Rebuke the Violent.'),
                ('Oath of the Watchers','Planar sentinel — Watcher\'s Will (advantage on saves), Abjure the Extraplanar.'),
                ('Oathbreaker',       'Fallen paladin — Dreadful Aspect (frighten), Channel Divinity: Control Undead.'),
            ]
            picks = _display_and_pick(console, '⚔  Sacred Oath — Choose 1', oaths, 1)
            if picks:
                result['subclass'] = picks[0]

    # ── Ranger: Archetype ────────────────────────────────────────────────
    elif class_key == 'Ranger' and level >= 3:
        if not subclass:
            picks = _display_and_pick(
                console, '🏹  Ranger Archetype — Choose 1', [(n, d) for n, d in RANGER_ARCHETYPES], 1
            )
            if picks:
                result['subclass'] = picks[0]

    # ── Rogue: Archetype ──────────────────────────────────────────────────
    elif class_key == 'Rogue' and level >= 3:
        if not subclass:
            picks = _display_and_pick(
                console, '🗡  Roguish Archetype — Choose 1', [(n, d) for n, d in ROGUE_ARCHETYPES], 1
            )
            if picks:
                result['subclass'] = picks[0]

    # ── Sorcerer: Sorcerous Origin ────────────────────────────────────────
    elif class_key == 'Sorcerer':
        if not subclass:
            picks = _display_and_pick(
                console, '✨  Sorcerous Origin — Choose 1',
                [(n, d) for n, d in SORCEROUS_ORIGINS], 1
            )
            if picks:
                result['sorcerous_origin'] = picks[0]
                result['subclass']         = picks[0]

        # Metamagic (unlocked at level 3)
        if level >= 3:
            meta_count = 2 if level < 10 else 3
            console.print(
                f'\n[bold white]── Metamagic — choose {meta_count} ──────────────────────────────[/bold white]'
            )
            picks = _display_and_pick(
                console, f'✨  Metamagic — Choose {meta_count}',
                [(n, d) for n, d in METAMAGIC_OPTIONS], meta_count
            )
            if picks:
                result['metamagic'] = picks

    # ── Warlock: Patron + Invocations ─────────────────────────────────────
    elif class_key == 'Warlock':
        if not subclass:
            picks = _display_and_pick(
                console, '🔮  Otherworldly Patron — Choose 1',
                [(n, d) for n, d in OTHERWORLDLY_PATRONS], 1
            )
            if picks:
                result['otherworldly_patron'] = picks[0]
                result['subclass']            = picks[0]

        # Pact Boon (unlocked at level 3)
        if level >= 3:
            picks = _display_and_pick(
                console, '🔮  Pact Boon — Choose 1',
                [(n, d) for n, d in PACT_BOONS], 1
            )
            if picks:
                result['pact_boon'] = picks[0]

        # Eldritch Invocations (2 at level 2, +1 every odd level)
        if level >= 2:
            inv_count = 2 + max(0, (level - 2) // 2)
            inv_count = min(inv_count, 7)
            picks = _display_and_pick(
                console,
                f'🔮  Eldritch Invocations — Choose {inv_count}',
                [(n, d) for n, d in ELDRITCH_INVOCATIONS],
                inv_count,
            )
            if picks:
                result['eldritch_invocations'] = picks

    # ── Wizard: Arcane Tradition ──────────────────────────────────────────
    # PHB p.115 — Arcane Tradition chosen at 2nd level.
    elif class_key == 'Wizard' and level >= 2:
        if not subclass:
            picks = _display_and_pick(
                console, '📚  Arcane Tradition — Choose 1',
                [(n, d) for n, d in WIZARD_SCHOOLS], 1
            )
            if picks:
                result['subclass'] = picks[0]

    # ── Artificer: Specialization ─────────────────────────────────────────
    elif class_key == 'Artificer' and level >= 3:
        if not subclass:
            picks = _display_and_pick(
                console, '⚙  Artificer Specialization — Choose 1',
                [(n, d) for n, d in ARTIFICER_SPECIALIZATIONS], 1
            )
            if picks:
                result['subclass'] = picks[0]

    # ── Summary ───────────────────────────────────────────────────────────
    if result:
        summary_lines = []
        for k, v in result.items():
            label = k.replace('_', ' ').title()
            val = ', '.join(v) if isinstance(v, list) else v
            summary_lines.append(f'  [cyan]{label}:[/cyan] {val}')

        console.print()
        console.print(Panel(
            '\n'.join(summary_lines),
            title='[bold green]Class Features Selected[/bold green]',
            border_style='green', padding=(0, 2),
        ))

    return result


def _ordinal(n: int) -> str:
    suffixes = {1: 'st', 2: 'nd', 3: 'rd'}
    return f'{n}{suffixes.get(n, "th")}'


def offer_spell_selection_method(
    console: Console,
    char_class: str,
    subclass: str,
    level: int,
    system_id: str,
    world_lore: str,
    system: dict,
) -> list:
    """
    Entry point for spell selection during character creation.

    Resolution order:
      1. spell_scraper live cache (full API data, school-filtered for AT/EK)
      2. Hardcoded DND5E_SPELLS dict (SRD fallback)
      3. AI-generated list or manual entry (homebrew / no list found)

    This order ensures AT/EK always see the full filtered wizard list from
    the API rather than the trimmed hardcoded subset.
    """
    import world_builder as _wb

    class_key = char_class.split('(')[0].strip()
    sub_key   = (subclass or '').split('(')[0].strip()

    # Non-casters skip spell selection entirely
    if not _wb.is_spellcaster(char_class, subclass):
        return []

    # ── 1. Try scraper cache first ────────────────────────────────────────
    if _SPELL_SCRAPER_AVAILABLE:
        try:
            # IMPORTANT: pass class_key (the character's true class, e.g. "Rogue"),
            # NOT sub_key. The scraper resolves AT/EK restrictions internally using
            # the (class_name, subclass) tuple in SUBCLASS_RESTRICTIONS.
            sc_data = _scraper_get_spells(class_key, sub_key, level)
            if sc_data.get('spells'):
                # Delegate to pick_official_spells which handles the full UI flow
                # including guaranteed cantrips, school filter labels, and bonus spells.
                return pick_official_spells(console, class_key, subclass, level, system_id)
        except Exception as e:
            console.print(f'[dim yellow][SpellPicker] Scraper unavailable ({e}), using hardcoded list.[/dim yellow]')

    # ── 2. Hardcoded DND5E_SPELLS fallback ───────────────────────────────
    # Resolve the dict key: AT/EK have their own entries in DND5E_SPELLS
    spell_list_key = class_key
    if not DND5E_SPELLS.get(class_key) and sub_key:
        if DND5E_SPELLS.get(sub_key):
            spell_list_key = sub_key

    if DND5E_SPELLS.get(spell_list_key):
        return pick_official_spells(console, spell_list_key, subclass, level, system_id)

    # ── 3. No official list — AI-generated or manual ──────────────────────
    console.print()
    console.print(Panel(
        f'[bold cyan]✨  Spell Selection — {class_key}[/bold cyan]\n\n'
        '[white]No official spell list found for this class.\n'
        'How would you like to pick your starting spells?[/white]',
        border_style='cyan', padding=(0, 2),
    ))
    console.print('  [dim]1.[/dim] [bold white]AI-generated list[/bold white]  '
                  '— World-flavored spells suggested by the GM')
    console.print('  [dim]2.[/dim] [bold white]Enter manually[/bold white]      '
                  '— Type spell names yourself')

    while True:
        raw = console.input('[bold white]  Choose (1 or 2): [/bold white]').strip()
        if raw == '1':
            return _wb.generate_and_pick_spells(
                console, char_class, subclass, level, world_lore, system
            )
        elif raw == '2':
            raw_text = console.input('  Spells (comma-separated): ').strip()
            return [s.strip() for s in raw_text.split(',') if s.strip()]
        else:
            console.print('[red]Please enter 1 or 2.[/red]')
