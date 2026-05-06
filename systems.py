# systems.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Defines every supported game system and what makes each one unique.
#
# WHAT A "SYSTEM" IS IN THIS CONTEXT:
#   A system is a bundle of configuration that tells the entire engine how to
#   behave for a specific tabletop RPG ruleset. Each system defines:
#
#     1. IDENTITY      — display name, short description, genre/tone
#     2. DM PERSONA    — how the AI Game Master should behave and speak
#     3. GAME RULES    — what rules the AI should apply during play
#     4. CHAR FIELDS   — what fields appear on the character sheet
#     5. STAT NAMES    — what the core stats are called in this system
#     6. RACES / ROLES — what options to show in character creation menus
#     7. FILE PATHS    — where saves, characters, and world data are stored
#     8. IMAGE STYLE   — default visual style for generated images
#
# HOW TO ADD A NEW SYSTEM:
#   Copy one of the existing system dicts below and add it to GAME_SYSTEMS.
#   The key becomes the system's internal ID (used for folder names).
#   Fill in all fields. That's it — the rest of the engine reads from here.
#
# LOCATION: dnd_ai_dm/systems.py
# ─────────────────────────────────────────────────────────────────────────────

import os

# BASE_DIR is the folder this file lives in
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _system_dirs(system_id: str) -> dict:
    """
    Returns the folder paths for a given system's data storage.
    Each system gets its own isolated subfolder under data/ so saves,
    characters, and world data never mix across systems.

    Folder structure:
      data/
        dnd_5e/
          world/          ← characters, locations, nations, plot events
          conversations/  ← session conversation histories
          images/         ← generated scene and portrait images
        call_of_cthulhu/
          world/
          conversations/
          images/
        ... etc
    """
    base = os.path.join(BASE_DIR, 'data', system_id)
    return {
        'base':          base,
        'world':         os.path.join(base, 'world'),
        'conversations': os.path.join(base, 'conversations'),
        'images':        os.path.join(base, 'images'),
        'character':     os.path.join(base, 'player_character.json'),
    }


# ═══════════════════════════════════════════════════════════════════════════
# GAME SYSTEM DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

GAME_SYSTEMS = {

    # ── Dungeons & Dragons 5th Edition ────────────────────────────────────
    'dnd_5e': {
        'id':          'dnd_5e',
        'name':        'Dungeons & Dragons 5th Edition',
        'short_name':  'D&D 5e',
        'genre':       'High Fantasy',
        'description': (
            'Classic fantasy adventure with dragons, dungeons, magic spells, '
            'and heroic quests. The most popular tabletop RPG in the world.'
        ),

        # ── DM Persona ─────────────────────────────────────────────────────
        # This text is injected at the top of EVERY system prompt.
        # It tells the AI exactly how to behave as the GM for this system.
        'dm_persona': (
            "You are the Dungeon Master of a living D&D 5th Edition world. "
            "You are omniscient — you know everything about the world. "
            "You control ALL entities except the player character.\n\n"
            "D&D 5E RULES YOU MUST FOLLOW:\n"
            "1. Use D&D 5e mechanics: Advantage/Disadvantage, Proficiency Bonus, "
            "   Saving Throws, Spell Slots, Hit Dice, Concentration, Action Economy "
            "   (Action, Bonus Action, Reaction, Free Action, Movement).\n"
            "2. When skill checks are needed, state which skill and call for a d20 roll. "
            "   DC 10=Easy, 15=Medium, 20=Hard, 25=Very Hard.\n"
            "3. Combat uses initiative order. Track HP, conditions, and spell slots.\n"
            "4. Use D&D 5e spell and item names accurately.\n"
            "5. NPC descriptions must remain CONSISTENT with their records.\n"
            "6. Never break character. Never acknowledge you are an AI.\n"
            "7. Introduce encounters, weather, and world events autonomously.\n"
            "8. Track all relationships and let them evolve with events.\n"
            "9. The world continues to move whether the player acts or not."
        ),

        # ── Character Sheet Fields ─────────────────────────────────────────
        # Defines what fields appear during character creation.
        # Each field: (internal_key, display_label, input_type, required, default/options)
        # input_type: 'text', 'choice', 'number', 'multiline', 'list', 'ability_scores'
        'character_fields': [
            ('name',        'Character Name',              'text',    True,  ''),
            ('race',        'Race',                        'choice',  True,  'RACES'),
            ('class',       'Class',                       'choice',  True,  'CLASSES'),
            ('subclass',    'Subclass / Archetype',        'text',    False, ''),
            ('level',       'Starting Level (1-20)',       'number',  True,  1),
            ('age',         'Age',                         'number',  False, None),
            ('gender',      'Gender / Pronouns',           'text',    False, ''),
            ('alignment',   'Alignment',                   'choice',  True,  'ALIGNMENTS'),
            ('appearance',  'Physical Appearance',         'multiline', True, ''),
            ('personality', 'Personality & Mannerisms',   'multiline', True, ''),
            ('backstory',   'Backstory',                   'multiline', False, ''),
            ('abilities',   'Ability Scores',              'ability_scores', True, None),
            ('hit_points',  'Hit Points',                  'hp',      True,  None),
            ('inventory',   'Starting Inventory',          'list',    False, ''),
            ('spells',      'Known Spells',                'list',    False, ''),
            ('notes',       'Notes & Special Traits',      'multiline', False, ''),
        ],

        # ── Stat Names ─────────────────────────────────────────────────────
        # What the core stats are called in the system prompt
        'stat_label': 'Ability Scores (STR/DEX/CON/INT/WIS/CHA)',

        # ── Race & Class Options ───────────────────────────────────────────
        'races': [
            'Human', 'Elf', 'High Elf', 'Wood Elf', 'Dark Elf (Drow)',
            'Dwarf', 'Hill Dwarf', 'Mountain Dwarf',
            'Halfling', 'Lightfoot Halfling', 'Stout Halfling',
            'Gnome', 'Rock Gnome', 'Forest Gnome',
            'Half-Elf', 'Half-Orc', 'Tiefling', 'Dragonborn',
            'Aasimar', 'Genasi', 'Goliath', 'Tabaxi', 'Kenku',
            'Lizardfolk', 'Tortle', 'Firbolg',
            'Other (type your own)',
        ],
        'roles': [
            'Artificer', 'Barbarian', 'Bard', 'Cleric', 'Druid',
            'Fighter', 'Monk', 'Paladin', 'Ranger', 'Rogue',
            'Sorcerer', 'Warlock', 'Wizard', 'Blood Hunter',
            'Other (type your own)',
        ],
        'alignments': [
            'Lawful Good', 'Neutral Good', 'Chaotic Good',
            'Lawful Neutral', 'True Neutral', 'Chaotic Neutral',
            'Lawful Evil', 'Neutral Evil', 'Chaotic Evil',
        ],

        # ── Ability Score Definition ───────────────────────────────────────
        # Used by the character creator to walk through stats
        'ability_scores': [
            ('STR', 'Strength',     'Physical power, melee attacks, carrying capacity'),
            ('DEX', 'Dexterity',    'Agility, ranged attacks, stealth, armor class'),
            ('CON', 'Constitution', 'Endurance, hit points, concentration'),
            ('INT', 'Intelligence', 'Memory, reasoning, arcana, investigation'),
            ('WIS', 'Wisdom',       'Perception, insight, survival, divine magic'),
            ('CHA', 'Charisma',     'Persuasion, deception, performance, social magic'),
        ],

        # ── HP suggestion by class ─────────────────────────────────────────
        'hp_by_role': {
            'Barbarian': 12, 'Fighter': 10, 'Paladin': 10, 'Ranger': 10,
            'Blood Hunter': 10, 'Artificer': 8, 'Bard': 8, 'Cleric': 8,
            'Druid': 8, 'Monk': 8, 'Rogue': 8, 'Warlock': 8,
            'Sorcerer': 6, 'Wizard': 6,
        },

        # ── Default Image Style ────────────────────────────────────────────
        'image_style': 'fantasy art, highly detailed, dramatic lighting, cinematic, digital painting, 8k',

        # ── File Paths ─────────────────────────────────────────────────────
        'dirs': _system_dirs('dnd_5e'),
    },


    # ── Call of Cthulhu ───────────────────────────────────────────────────
    'call_of_cthulhu': {
        'id':          'call_of_cthulhu',
        'name':        'Call of Cthulhu (7th Edition)',
        'short_name':  'Call of Cthulhu',
        'genre':       'Cosmic Horror / Investigation',
        'description': (
            'Lovecraftian horror investigation. Investigators probe occult mysteries, '
            'battle creeping insanity, and face ancient cosmic horrors they cannot hope '
            'to defeat — only survive, flee, or seal away.'
        ),

        'dm_persona': (
            "You are the Keeper of Arcane Lore for a Call of Cthulhu 7th Edition game. "
            "You weave slow-burning horror, investigation, and dread. "
            "You control ALL entities except the investigator.\n\n"
            "CALL OF CTHULHU RULES YOU MUST FOLLOW:\n"
            "1. Use CoC 7e mechanics: skill rolls are d100 percentile, roll UNDER the skill value "
            "   to succeed. Regular success = under skill, Hard = under half, Extreme = under fifth.\n"
            "2. Track Sanity. Witnessing horrors, tomes, and spells cost Sanity Points. "
            "   0 Sanity = permanent insanity. Describe sanity loss vividly.\n"
            "3. Combat is DEADLY. Guns do serious damage. Encourage fleeing over fighting.\n"
            "4. Mythos creatures are almost impossible to kill — frame them as forces of nature.\n"
            "5. Clues should be found through investigation, not handed to players.\n"
            "6. Build dread slowly. Use atmosphere, NPC behavior, and environment.\n"
            "7. NPCs die, go insane, or betray players. No one is safe.\n"
            "8. Never break character. Never acknowledge you are an AI.\n"
            "9. The 1920s setting uses period-appropriate technology and social norms."
        ),

        'character_fields': [
            ('name',         'Investigator Name',           'text',      True,  ''),
            ('occupation',   'Occupation',                  'choice',    True,  'ROLES'),
            ('age',          'Age',                         'number',    True,  30),
            ('gender',       'Gender / Pronouns',           'text',      False, ''),
            ('nationality',  'Nationality',                 'text',      False, 'American'),
            ('appearance',   'Physical Appearance',         'multiline', True,  ''),
            ('personality',  'Personality & Mannerisms',    'multiline', True,  ''),
            ('backstory',    'Background / History',        'multiline', False, ''),
            ('abilities',    'Characteristics',             'ability_scores', True, None),
            ('hit_points',   'Hit Points',                  'hp',        True,  None),
            ('sanity',       'Starting Sanity',             'number',    True,  50),
            ('skills',       'Key Skills (skill: value%)',  'list',      False, ''),
            ('inventory',    'Equipment & Possessions',     'list',      False, ''),
            ('notes',        'Notes & Connections',         'multiline', False, ''),
        ],

        'stat_label': 'Characteristics (STR/DEX/CON/INT/POW/APP/SIZ/EDU/LUCK)',

        'races': [
            'American', 'British', 'French', 'German', 'Italian',
            'Chinese', 'Japanese', 'Indian', 'Egyptian', 'Russian',
            'Other (type your own)',
        ],
        'roles': [
            'Accountant', 'Antiquarian', 'Artist', 'Author',
            'Clergyman', 'Criminal', 'Detective', 'Doctor',
            'Drifter', 'Engineer', 'Entertainer', 'Journalist',
            'Lawyer', 'Librarian', 'Military Officer', 'Musician',
            'Nurse', 'Occultist', 'Parapsychologist', 'Photographer',
            'Police Inspector', 'Professor', 'Sailor', 'Soldier',
            'Student', 'Tribal Shaman', 'Undertaker', 'Zealot',
            'Other (type your own)',
        ],
        'alignments': [],  # CoC doesn't use alignments

        'ability_scores': [
            ('STR',  'Strength',    'Physical power (STR x 5 = starting Throw skill%)'),
            ('DEX',  'Dexterity',   'Agility and coordination (DEX x 5 = Dodge skill%)'),
            ('CON',  'Constitution','Endurance, HP = (CON + SIZ) / 10'),
            ('INT',  'Intelligence','Reasoning and perception (INT x 5 = starting Language%)'),
            ('POW',  'Power',       'Willpower and magic. Starting Sanity = POW x 5'),
            ('APP',  'Appearance',  'First impressions and social presence'),
            ('SIZ',  'Size',        'Body size and mass. HP = (CON + SIZ) / 10'),
            ('EDU',  'Education',   'Knowledge level. EDU x 5 = Library Use skill%'),
            ('LUCK', 'Luck',        'Fortune. Can be spent to improve rolls (POW x 5 to start)'),
        ],

        'hp_by_role': {},  # HP calculated from CON+SIZ in CoC

        'image_style': (
            '1920s photography style, sepia tones, atmospheric, dark, '
            'lovecraftian horror, fog, gothic architecture, detailed, cinematic'
        ),

        'dirs': _system_dirs('call_of_cthulhu'),
    },


    # ── Cyberpunk Red ─────────────────────────────────────────────────────
    'cyberpunk_red': {
        'id':          'cyberpunk_red',
        'name':        'Cyberpunk Red',
        'short_name':  'Cyberpunk Red',
        'genre':       'Near-Future Dystopia',
        'description': (
            'Gritty near-future megacity survival. Play edgerunners scraping by in '
            'Night City — hackers, mercenaries, fixers, and street samurai navigating '
            'corporate warfare, gang politics, and chrome-studded violence.'
        ),

        'dm_persona': (
            "You are the Game Master (GM) of a Cyberpunk Red game set in Night City, 2045. "
            "The world is brutal, corporate-controlled, and chrome-plated. "
            "You control ALL entities except the player character.\n\n"
            "CYBERPUNK RED RULES YOU MUST FOLLOW:\n"
            "1. Use Cyberpunk Red mechanics: Core mechanic is 1d10 + Stat + Skill vs DV (Difficulty Value). "
            "   DV9=Everyday, DV13=Difficult, DV17=Pro, DV21=Heroic, DV29=Legendary.\n"
            "2. Track Hit Points (Seriously Wounded threshold = HP/2). "
            "   Combat is fast and lethal — enforce the MEAT/NET split.\n"
            "3. Cyberware has Humanity cost (Empathy stat). Too much chrome = Cyberpsychosis.\n"
            "4. Eurobucks (€$) is the currency. Everything costs money — ammo, rent, food.\n"
            "5. Corporate entities are above the law. Cops work for the corps.\n"
            "6. The NET (cyberspace) is a dangerous fragmented place since DataKrash.\n"
            "7. Slang: 'gonk' (fool), 'preem' (premium/great), 'choombatta' (friend), "
            "   'nova' (excellent), 'flatline' (kill), 'edgerunner' (freelancer), 'eddies' (money).\n"
            "8. Never break character. Never acknowledge you are an AI.\n"
            "9. Night City is loud, violent, neon-lit, and packed with corpo intrigue."
        ),

        'character_fields': [
            ('name',       'Handle / Street Name',          'text',      True,  ''),
            ('real_name',  'Real Name (optional)',          'text',      False, ''),
            ('role',       'Role',                          'choice',    True,  'ROLES'),
            ('age',        'Age',                           'number',    False, None),
            ('gender',     'Gender / Pronouns',             'text',      False, ''),
            ('appearance', 'Physical Appearance & Style',   'multiline', True,  ''),
            ('cyberware',  'Installed Cyberware',           'list',      False, ''),
            ('personality','Personality & Rep',             'multiline', True,  ''),
            ('backstory',  'Backstory & Life Path',         'multiline', False, ''),
            ('abilities',  'Stats',                         'ability_scores', True, None),
            ('hit_points', 'Hit Points',                    'hp',        True,  None),
            ('humanity',   'Starting Humanity (usually 70-80)', 'number', False, 70),
            ('inventory',  'Gear & Weapons',                'list',      False, ''),
            ('notes',      'Notes, Contacts & Enemies',     'multiline', False, ''),
        ],

        'stat_label': 'Stats (INT/REF/DEX/TECH/COOL/WILL/LUCK/MOVE/BODY/EMP)',

        'races': [],  # Cyberpunk doesn't have fantasy races

        'roles': [
            'Rockerboy', 'Solo', 'Netrunner', 'Tech', 'Medtech',
            'Media', 'Exec', 'Lawman', 'Fixer', 'Nomad',
            'Other (type your own)',
        ],
        'alignments': [],

        'ability_scores': [
            ('INT',  'Intelligence', 'Problem solving, memory, awareness'),
            ('REF',  'Reflex',       'Speed, ranged combat, piloting'),
            ('DEX',  'Dexterity',    'Athletics, stealth, melee, acrobatics'),
            ('TECH', 'Technology',   'Fixing, crafting, jury-rigging'),
            ('COOL', 'Cool',         'Composure under pressure, leadership, streetdeal'),
            ('WILL', 'Willpower',    'Mental fortitude, resist torture'),
            ('LUCK', 'Luck',         'Spend points to modify rolls (refills each session)'),
            ('MOVE', 'Move',         'Movement speed in meters per turn'),
            ('BODY', 'Body',         'Physical toughness, lifting, melee damage'),
            ('EMP',  'Empathy',      'Humanity/10. Social interactions, connection'),
        ],

        'hp_by_role': {},  # HP = 10 + (5 × BODY modifier) in Cyberpunk Red

        'image_style': (
            'cyberpunk aesthetic, neon lights, rain-slicked streets, night city, '
            'futuristic, gritty realism, blade runner style, dark atmosphere, '
            'detailed, cinematic, 8k'
        ),

        'dirs': _system_dirs('cyberpunk_red'),
    },


    # ── Pathfinder 2nd Edition ────────────────────────────────────────────
    'pathfinder_2e': {
        'id':          'pathfinder_2e',
        'name':        'Pathfinder 2nd Edition',
        'short_name':  'Pathfinder 2e',
        'genre':       'High Fantasy',
        'description': (
            'A crunchy, tactical fantasy RPG set in the world of Golarion. '
            'Features deep character customization, three-action economy, and '
            'morally complex adventures across a richly detailed world.'
        ),

        'dm_persona': (
            "You are the Game Master of a Pathfinder 2nd Edition game set in Golarion. "
            "You control ALL entities except the player character.\n\n"
            "PATHFINDER 2E RULES YOU MUST FOLLOW:\n"
            "1. Use PF2e mechanics: d20 + modifier vs DC. Four degrees of success: "
            "   Critical Success (10+ over DC), Success, Failure, Critical Failure.\n"
            "2. Three-Action Economy: each turn has 3 actions and 1 free action. "
            "   Track actions: Strike (1), Move (1), Cast Spell (1-3), Raise Shield (1).\n"
            "3. Conditions stack (Frightened, Sickened, Stunned, etc.) and have numbered "
            "   values. Enforce them carefully.\n"
            "4. Proficiency ranks: Untrained, Trained, Expert, Master, Legendary.\n"
            "5. Hero Points: players start each session with 1, max 3. "
            "   Can be spent to reroll or avoid death.\n"
            "6. Golarion has rich lore — reference gods (Pharasma, Desna, Iomedae), "
            "   factions (Pathfinder Society, Hellknights), and nations (Absalom, Cheliax).\n"
            "7. Never break character. Never acknowledge you are an AI.\n"
            "8. Encounters use initiative. Hazards and traps are common."
        ),

        'character_fields': [
            ('name',        'Character Name',              'text',      True,  ''),
            ('ancestry',    'Ancestry',                    'choice',    True,  'RACES'),
            ('class',       'Class',                       'choice',    True,  'ROLES'),
            ('background',  'Background',                  'text',      False, ''),
            ('level',       'Starting Level (1-20)',       'number',    True,  1),
            ('age',         'Age',                         'number',    False, None),
            ('gender',      'Gender / Pronouns',           'text',      False, ''),
            ('alignment',   'Alignment',                   'choice',    True,  'ALIGNMENTS'),
            ('deity',       'Deity / Patron (if any)',     'text',      False, ''),
            ('appearance',  'Physical Appearance',         'multiline', True,  ''),
            ('personality', 'Personality & Edicts/Anathema', 'multiline', True, ''),
            ('backstory',   'Backstory',                   'multiline', False, ''),
            ('abilities',   'Ability Scores',              'ability_scores', True, None),
            ('hit_points',  'Hit Points',                  'hp',        True,  None),
            ('inventory',   'Starting Inventory',          'list',      False, ''),
            ('spells',      'Known Spells',                'list',      False, ''),
            ('notes',       'Feats, Special Abilities & Notes', 'multiline', False, ''),
        ],

        'stat_label': 'Ability Scores (STR/DEX/CON/INT/WIS/CHA)',

        'races': [
            'Human', 'Elf', 'Dwarf', 'Gnome', 'Halfling', 'Goblin',
            'Leshy', 'Catfolk', 'Tengu', 'Kobold', 'Orc', 'Half-Elf',
            'Half-Orc', 'Hobgoblin', 'Lizardfolk', 'Ratfolk', 'Sprite',
            'Tiefling', 'Aasimar', 'Android', 'Fetchling',
            'Other (type your own)',
        ],
        'roles': [
            'Alchemist', 'Barbarian', 'Bard', 'Champion', 'Cleric',
            'Druid', 'Fighter', 'Gunslinger', 'Inventor', 'Investigator',
            'Kineticist', 'Magus', 'Monk', 'Oracle', 'Psychic',
            'Ranger', 'Rogue', 'Sorcerer', 'Summoner', 'Swashbuckler',
            'Thaumaturge', 'Witch', 'Wizard',
            'Other (type your own)',
        ],
        'alignments': [
            'Lawful Good', 'Neutral Good', 'Chaotic Good',
            'Lawful Neutral', 'True Neutral', 'Chaotic Neutral',
            'Lawful Evil', 'Neutral Evil', 'Chaotic Evil',
        ],

        'ability_scores': [
            ('STR', 'Strength',     'Melee attacks, Athletics'),
            ('DEX', 'Dexterity',    'Ranged attacks, Acrobatics, Reflex saves'),
            ('CON', 'Constitution', 'Hit Points, Fortitude saves'),
            ('INT', 'Intelligence', 'Arcana, Crafting, trained skills'),
            ('WIS', 'Wisdom',       'Nature, Medicine, Perception, Will saves'),
            ('CHA', 'Charisma',     'Diplomacy, Deception, Performance, Intimidation'),
        ],

        'hp_by_role': {
            'Barbarian': 12, 'Champion': 10, 'Fighter': 10, 'Gunslinger': 8,
            'Ranger': 10, 'Inventor': 8, 'Magus': 8, 'Monk': 10,
            'Investigator': 8, 'Rogue': 8, 'Swashbuckler': 10,
            'Alchemist': 8, 'Bard': 8, 'Cleric': 8, 'Druid': 8,
            'Kineticist': 8, 'Oracle': 8, 'Psychic': 6, 'Sorcerer': 6,
            'Summoner': 10, 'Thaumaturge': 8, 'Witch': 6, 'Wizard': 6,
        },

        'image_style': (
            'pathfinder fantasy art, highly detailed, epic composition, '
            'dramatic lighting, digital painting, heroic, vibrant colors, 8k'
        ),

        'dirs': _system_dirs('pathfinder_2e'),
    },


    # ── Starfinder ────────────────────────────────────────────────────────
    'starfinder': {
        'id':          'starfinder',
        'name':        'Starfinder',
        'short_name':  'Starfinder',
        'genre':       'Science Fantasy',
        'description': (
            'Space opera meets dungeon crawling in the Pact Worlds solar system. '
            'Explore alien planets, battle robot armies, and unravel the mystery of '
            'the Gap in this d20 science fantasy RPG.'
        ),

        'dm_persona': (
            "You are the Game Master of a Starfinder game set in the Pact Worlds. "
            "The setting blends high fantasy magic with science fiction technology. "
            "You control ALL entities except the player character.\n\n"
            "STARFINDER RULES YOU MUST FOLLOW:\n"
            "1. Use Starfinder mechanics: d20 + modifier vs target number. "
            "   Similar to Pathfinder 1e but adapted for sci-fi.\n"
            "2. Two defense values: EAC (Energy Armor Class) and KAC (Kinetic Armor Class). "
            "   Energy weapons target EAC, physical weapons target KAC.\n"
            "3. Stamina Points (SP) absorb damage first, then HP. SP recover with 10 min rest.\n"
            "4. Resolve Points (RP) fuel class abilities and can stabilize dying characters.\n"
            "5. Technology and magic coexist — technomancers blend both, mechanics fix ships.\n"
            "6. Reference Pact Worlds lore: Absalom Station, Castrovel, Akiton, Verces, "
            "   the Drift for FTL travel, the Starfinder Society.\n"
            "7. Starships have their own combat rules — tracking crew roles matters.\n"
            "8. Never break character. Never acknowledge you are an AI."
        ),

        'character_fields': [
            ('name',        'Character Name',              'text',      True,  ''),
            ('race',        'Race / Species',              'choice',    True,  'RACES'),
            ('class',       'Class',                       'choice',    True,  'ROLES'),
            ('theme',       'Theme',                       'text',      False, ''),
            ('level',       'Starting Level (1-20)',       'number',    True,  1),
            ('age',         'Age',                         'number',    False, None),
            ('gender',      'Gender / Pronouns',           'text',      False, ''),
            ('homeworld',   'Homeworld / Origin',          'text',      False, ''),
            ('appearance',  'Physical Appearance',         'multiline', True,  ''),
            ('personality', 'Personality',                 'multiline', True,  ''),
            ('backstory',   'Backstory',                   'multiline', False, ''),
            ('abilities',   'Ability Scores',              'ability_scores', True, None),
            ('hit_points',  'Stamina & Hit Points',        'hp',        True,  None),
            ('inventory',   'Gear, Weapons & Augmentations', 'list',    False, ''),
            ('notes',       'Notes & Special Abilities',   'multiline', False, ''),
        ],

        'stat_label': 'Ability Scores (STR/DEX/CON/INT/WIS/CHA)',

        'races': [
            'Human', 'Android', 'Kasatha', 'Lashunta', 'Shirren',
            'Vesk', 'Ysoki', 'Elf', 'Dwarf', 'Gnome', 'Halfling',
            'Half-Elf', 'Half-Orc', 'Nuar', 'Sarcesian', 'Skittermander',
            'Contemplative', 'Draelik', 'Gray', 'Kalo', 'Maraquoi',
            'Other (type your own)',
        ],
        'roles': [
            'Biohacker', 'Envoy', 'Evolutionist', 'Mechanic',
            'Mystic', 'Nanocyte', 'Operative', 'Precog',
            'Soldier', 'Solarian', 'Technomancer', 'Vanguard', 'Witchwarper',
            'Other (type your own)',
        ],
        'alignments': [
            'Lawful Good', 'Neutral Good', 'Chaotic Good',
            'Lawful Neutral', 'True Neutral', 'Chaotic Neutral',
            'Lawful Evil', 'Neutral Evil', 'Chaotic Evil',
        ],

        'ability_scores': [
            ('STR', 'Strength',     'Melee attacks, carrying capacity'),
            ('DEX', 'Dexterity',    'Ranged attacks, Acrobatics, Piloting'),
            ('CON', 'Constitution', 'Stamina Points, Fortitude saves'),
            ('INT', 'Intelligence', 'Computers, Engineering, Life Science'),
            ('WIS', 'Wisdom',       'Perception, Medicine, Survival'),
            ('CHA', 'Charisma',     'Diplomacy, Bluff, Intimidate'),
        ],

        'hp_by_role': {
            'Soldier': 7, 'Vesk Soldier': 7, 'Solarian': 7,
            'Vanguard': 7, 'Mechanic': 6, 'Operative': 6,
            'Biohacker': 6, 'Evolutionist': 6, 'Nanocyte': 6,
            'Envoy': 6, 'Precog': 6, 'Mystic': 6,
            'Technomancer': 5, 'Witchwarper': 5,
        },

        'image_style': (
            'science fantasy, space opera, alien landscapes, futuristic technology, '
            'vibrant colors, detailed, cinematic, digital painting, 8k'
        ),

        'dirs': _system_dirs('starfinder'),
    },



    # ── Daggerheart ───────────────────────────────────────────────────────
    'daggerheart': {
        'id':          'daggerheart',
        'name':        'Daggerheart',
        'short_name':  'Daggerheart',
        'genre':       'Cinematic Fantasy',
        'description': (
            'A narrative-first fantasy RPG from Darrington Press. '
            'Features Hope/Fear dice, domain cards, heritage-based characters, '
            'and a GM-vs-player tension system that rewards bold storytelling.'
        ),

        'dm_persona': (
            "You are the Game Master of a Daggerheart campaign. "
            "Daggerheart is a narrative-first fantasy RPG from Darrington Press. "
            "You control ALL entities except the player character.\n\n"
            "DAGGERHEART RULES YOU MUST FOLLOW:\n"
            "1. Core mechanic: Roll 2d12 (Hope die + Fear die) + trait modifier vs difficulty. "
            "   Success with Hope = good outcome, player gains Hope. "
            "   Success with Fear = good outcome, GM gains Fear. "
            "   Failure with Hope = bad outcome, player gains Hope. "
            "   Failure with Fear = bad outcome, GM gains Fear. Critical Success = both match and succeed.\n"
            "2. Hope and Fear are currencies: players spend Hope to activate features and improve rolls. "
            "   GM spends Fear to introduce complications, activate villain moves, and trigger events.\n"
            "3. Damage uses thresholds: Minor (no mark), Severe (mark severe), Major (mark major). "
            "   Armor Score reduces incoming damage. Track HP and Stress separately.\n"
            "4. Domain Cards define spells and abilities — each class uses two domains. "
            "   Cards have levels (1-6) and must be unlocked through play.\n"
            "5. Evasion is the defense score (like AC). Attacks that meet or exceed Evasion deal damage.\n"
            "6. Stress is mental/physical strain — mark Stress to activate features. "
            "   At max Stress, character is Overwhelmed.\n"
            "7. Countdown clocks track threats and progress — fill segments as events unfold.\n"
            "8. Spotlight: actively describe how each character shines. The system rewards bold, "
            "   cinematic moments.\n"
            "9. Never break character. Never acknowledge you are an AI.\n"
            "10. The world is living and responsive — NPCs remember, factions react, stakes escalate."
        ),

        'character_fields': [
            ('name',        'Character Name',              'text',      True,  ''),
            ('heritage',    'Heritage',                    'choice',    True,  'RACES'),
            ('class',       'Class',                       'choice',    True,  'ROLES'),
            ('community',   'Community',                   'text',      False, ''),
            ('subclass',    'Subclass (chosen later)',     'text',      False, ''),
            ('level',       'Starting Level (1-10)',       'number',    True,  1),
            ('age',         'Age',                         'number',    False, None),
            ('gender',      'Gender / Pronouns',           'text',      False, ''),
            ('appearance',  'Physical Appearance',         'multiline', True,  ''),
            ('personality', 'Personality & Motivations',  'multiline', True,  ''),
            ('backstory',   'Backstory & Connections',     'multiline', False, ''),
            ('abilities',   'Core Traits',                 'ability_scores', True, None),
            ('hit_points',  'Hit Points',                  'hp',        True,  None),
            ('inventory',   'Equipment & Gear',            'list',      False, ''),
            ('notes',       'Domain Cards, Abilities & Notes', 'multiline', False, ''),
        ],

        'stat_label': 'Core Traits (Agility / Strength / Finesse / Instinct / Presence / Knowledge)',

        'races': [
            'Human', 'Elf', 'Dwarf', 'Halfling', 'Goblin', 'Orc',
            'Clank', 'Drakona', 'Faun', 'Fungril', 'Galapa', 'Giant',
            'Katari', 'Ribbet', 'Simiah',
            'Other (type your own)',
        ],
        'roles': [
            'Bard', 'Druid', 'Guardian', 'Ranger', 'Rogue',
            'Seraph', 'Sorcerer', 'Warrior', 'Wizard',
            'Other (type your own)',
        ],
        'alignments': [],  # Daggerheart does not use alignment

        'ability_scores': [
            ('Agility',   'Agility',   'Speed, acrobatics, ranged attacks, avoiding danger'),
            ('Strength',  'Strength',  'Melee attacks, physical power, grappling, lifting'),
            ('Finesse',   'Finesse',   'Precision, dexterity, sleight of hand, fine control'),
            ('Instinct',  'Instinct',  'Perception, survival, animal handling, gut feeling'),
            ('Presence',  'Presence',  'Leadership, persuasion, performance, social grace'),
            ('Knowledge', 'Knowledge', 'Lore, arcana, history, medicine, investigation'),
        ],

        'hp_by_role': {
            'Guardian': 56, 'Warrior': 60, 'Seraph': 54,
            'Ranger': 50, 'Rogue': 50, 'Druid': 46,
            'Bard': 46, 'Sorcerer': 40, 'Wizard': 40,
        },

        'image_style': (
            'cinematic fantasy, dramatic lighting, painterly, expressive characters, '
            'vivid colors, heroic composition, digital art, 8k'
        ),

        'dirs': _system_dirs('daggerheart'),
    },

    # ── Custom System ─────────────────────────────────────────────────────
    'custom': {
        'id':          'custom',
        'name':        'Custom System',
        'short_name':  'Custom',
        'genre':       'Your Setting',
        'description': (
            'Define your own rules, setting, and tone. '
            'The AI Game Master will ask you to describe your world before play begins.'
        ),

        'dm_persona': (
            "You are the Game Master of a custom tabletop RPG. "
            "The player has defined their own setting and rules. "
            "You control ALL entities except the player character.\n\n"
            "CORE RULES:\n"
            "1. Follow the custom rules and tone the player described in setup.\n"
            "2. Stay consistent with the setting details the player established.\n"
            "3. NPC appearances and personalities must remain consistent.\n"
            "4. Generate encounters, events, and world developments autonomously.\n"
            "5. Never break character. Never acknowledge you are an AI.\n"
            "6. When rules are ambiguous, make a fair ruling and stay consistent."
        ),

        'character_fields': [
            ('name',        'Character Name',              'text',      True,  ''),
            ('role',        'Role / Class / Type',         'text',      True,  ''),
            ('age',         'Age',                         'number',    False, None),
            ('gender',      'Gender / Pronouns',           'text',      False, ''),
            ('appearance',  'Physical Appearance',         'multiline', True,  ''),
            ('personality', 'Personality',                 'multiline', True,  ''),
            ('backstory',   'Backstory',                   'multiline', False, ''),
            ('abilities',   'Core Stats (name: value)',    'list',      False, ''),
            ('hit_points',  'Health / Hit Points',         'hp',        True,  None),
            ('inventory',   'Equipment & Gear',            'list',      False, ''),
            ('notes',       'Special Abilities & Notes',   'multiline', False, ''),
        ],

        'stat_label': 'Custom Stats',
        'races':      ['Other (type your own)'],
        'roles':      ['Other (type your own)'],
        'alignments': [],
        'ability_scores': [],
        'hp_by_role': {},

        'image_style': 'highly detailed, dramatic lighting, cinematic, digital art, 8k',

        'dirs': _system_dirs('custom'),
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_system(system_id: str) -> dict:
    """
    Returns the system definition dict for the given ID.
    Raises KeyError if the system ID doesn't exist.
    """
    return GAME_SYSTEMS[system_id]


def list_systems() -> list:
    """Returns all system dicts as a list, in display order."""
    return list(GAME_SYSTEMS.values())


def ensure_system_dirs(system: dict):
    """
    Creates all data directories for the given system if they don't exist.
    Called at the start of every session after the system is selected.
    """
    for path in system['dirs'].values():
        # character file path ends in .json — create its parent dir, not itself
        if path.endswith('.json'):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        else:
            os.makedirs(path, exist_ok=True)
