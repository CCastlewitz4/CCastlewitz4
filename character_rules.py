# character_rules.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Automatic race/ancestry/class proficiency and bonus application.
#
# After a player picks their race and class during character creation, this
# module automatically calculates and merges everything those choices grant:
#
#   RACE / ANCESTRY / HERITAGE gives:
#     - Ability score bonuses    (e.g. Elf +2 DEX +1 INT)
#     - Racial traits & features (e.g. Darkvision, Fey Ancestry)
#     - Racial proficiencies     (e.g. Elf Weapon Training)
#     - Movement speed, size, languages
#
#   CLASS gives:
#     - Saving throw proficiencies
#     - Armor + weapon proficiencies
#     - Tool proficiencies
#     - Skill choices count + available pool
#     - Starting equipment
#     - Level-1 class features
#     - Spellcasting info
#
# MAIN ENTRY POINT:
#   apply_race_and_class(system_id, race, char_class, abilities, level=1)
#   Returns a dict of auto-populated fields to merge into the character sheet.
#
# SUPPORTED SYSTEMS:
#   dnd_5e, pathfinder_2e, call_of_cthulhu, cyberpunk_red, daggerheart
# ─────────────────────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════
# D&D 5E — RACE DATA
# ═══════════════════════════════════════════════════════════════════════════

DND5E_RACES = {
    'Human': {
        'asi': {'STR': 1, 'DEX': 1, 'CON': 1, 'INT': 1, 'WIS': 1, 'CHA': 1},
        'traits': [
            'Versatile: Gain one additional skill proficiency of your choice.',
            'Extra Language: Speak, read, and write one additional language.',
        ],
        'proficiencies': [],
        'languages': ['Common', 'One additional language of your choice'],
        'speed': 30, 'size': 'Medium', 'darkvision': False,
    },
    'Elf': {
        'asi': {'DEX': 2, 'INT': 1},
        'traits': [
            'Darkvision 60 ft.',
            'Keen Senses: Proficiency in the Perception skill.',
            'Fey Ancestry: Advantage on saving throws against being charmed; magic cannot put you to sleep.',
            'Trance: Elves do not sleep — instead they meditate for 4 hours per day.',
        ],
        'proficiencies': ['Perception'],
        'languages': ['Common', 'Elvish'],
        'speed': 30, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'High Elf': {
        'asi': {'DEX': 2, 'INT': 1},
        'traits': [
            'Darkvision 60 ft.',
            'Keen Senses: Proficiency in Perception.',
            'Fey Ancestry: Advantage on saves vs charm; immune to magical sleep.',
            'Trance: Meditate 4 hours instead of sleeping.',
            'Elf Weapon Training: Proficiency with longsword, shortsword, shortbow, longbow.',
            'Cantrip: Know one wizard cantrip of your choice (INT-based).',
            'Extra Language: Speak, read, and write one extra language of your choice.',
        ],
        'proficiencies': ['Perception', 'Longsword', 'Shortsword', 'Shortbow', 'Longbow'],
        'languages': ['Common', 'Elvish', 'One additional language of your choice'],
        'speed': 30, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'Wood Elf': {
        'asi': {'DEX': 2, 'WIS': 1},
        'traits': [
            'Darkvision 60 ft.',
            'Keen Senses: Proficiency in Perception.',
            'Fey Ancestry: Advantage on saves vs charm; immune to magical sleep.',
            'Trance: Meditate 4 hours instead of sleeping.',
            'Elf Weapon Training: Proficiency with longsword, shortsword, shortbow, longbow.',
            'Fleet of Foot: Base walking speed is 35 ft.',
            'Mask of the Wild: Can attempt to hide when lightly obscured by natural phenomena.',
        ],
        'proficiencies': ['Perception', 'Longsword', 'Shortsword', 'Shortbow', 'Longbow'],
        'languages': ['Common', 'Elvish'],
        'speed': 35, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'Dark Elf (Drow)': {
        'asi': {'DEX': 2, 'CHA': 1},
        'traits': [
            'Superior Darkvision 120 ft.',
            'Keen Senses: Proficiency in Perception.',
            'Fey Ancestry: Advantage on saves vs charm; immune to magical sleep.',
            'Trance: Meditate 4 hours instead of sleeping.',
            'Drow Weapon Training: Proficiency with rapiers, shortswords, and hand crossbows.',
            'Drow Magic: Dancing Lights cantrip. At 3rd level: Faerie Fire 1/long rest. At 5th: Darkness 1/long rest. CHA-based.',
            'Sunlight Sensitivity: Disadvantage on attack rolls and Perception checks in direct sunlight.',
        ],
        'proficiencies': ['Perception', 'Rapier', 'Shortsword', 'Hand Crossbow'],
        'innate_spells': ['Dancing Lights (cantrip)'],
        'languages': ['Common', 'Elvish'],
        'speed': 30, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 120,
    },
    'Dwarf': {
        'asi': {'CON': 2},
        'traits': [
            'Darkvision 60 ft.',
            'Dwarven Resilience: Advantage on saving throws against poison; resistance to poison damage.',
            'Dwarven Combat Training: Proficiency with battleaxe, handaxe, light hammer, warhammer.',
            'Tool Proficiency: Choose artisan\'s tools (smith\'s, brewer\'s, or mason\'s).',
            'Stonecunning: Double proficiency bonus on History checks related to stonework.',
        ],
        'proficiencies': ['Battleaxe', 'Handaxe', 'Light Hammer', 'Warhammer'],
        'languages': ['Common', 'Dwarvish'],
        'speed': 25, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'Hill Dwarf': {
        'asi': {'CON': 2, 'WIS': 1},
        'traits': [
            'Darkvision 60 ft.',
            'Dwarven Resilience: Advantage on saves vs poison; resistance to poison damage.',
            'Dwarven Combat Training: Proficiency with battleaxe, handaxe, light hammer, warhammer.',
            'Tool Proficiency: Choose artisan\'s tools.',
            'Stonecunning: Double proficiency on History checks about stonework.',
            'Dwarven Toughness: Maximum HP increases by 1 for every character level.',
        ],
        'proficiencies': ['Battleaxe', 'Handaxe', 'Light Hammer', 'Warhammer'],
        'languages': ['Common', 'Dwarvish'],
        'speed': 25, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'Mountain Dwarf': {
        'asi': {'CON': 2, 'STR': 2},
        'traits': [
            'Darkvision 60 ft.',
            'Dwarven Resilience: Advantage on saves vs poison; resistance to poison damage.',
            'Dwarven Combat Training: Proficiency with battleaxe, handaxe, light hammer, warhammer.',
            'Tool Proficiency: Choose artisan\'s tools.',
            'Stonecunning: Double proficiency on History checks about stonework.',
            'Dwarven Armor Training: Proficiency with light and medium armor.',
        ],
        'proficiencies': ['Battleaxe', 'Handaxe', 'Light Hammer', 'Warhammer', 'Light Armor', 'Medium Armor'],
        'languages': ['Common', 'Dwarvish'],
        'speed': 25, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'Halfling': {
        'asi': {'DEX': 2},
        'traits': [
            'Lucky: Reroll 1s on d20 attack rolls, ability checks, and saving throws; must use new result.',
            'Brave: Advantage on saving throws against being frightened.',
            'Halfling Nimbleness: Can move through the space of any creature larger than yourself.',
        ],
        'proficiencies': [],
        'languages': ['Common', 'Halfling'],
        'speed': 25, 'size': 'Small', 'darkvision': False,
    },
    'Lightfoot Halfling': {
        'asi': {'DEX': 2, 'CHA': 1},
        'traits': [
            'Lucky: Reroll 1s on d20 rolls; must use the new result.',
            'Brave: Advantage on saving throws against being frightened.',
            'Halfling Nimbleness: Move through the space of any larger creature.',
            'Naturally Stealthy: Attempt to hide behind a creature at least one size larger than you.',
        ],
        'proficiencies': [],
        'languages': ['Common', 'Halfling'],
        'speed': 25, 'size': 'Small', 'darkvision': False,
    },
    'Stout Halfling': {
        'asi': {'DEX': 2, 'CON': 1},
        'traits': [
            'Lucky: Reroll 1s on d20 rolls; must use the new result.',
            'Brave: Advantage on saving throws against being frightened.',
            'Halfling Nimbleness: Move through the space of any larger creature.',
            'Stout Resilience: Advantage on saves vs poison; resistance to poison damage.',
        ],
        'proficiencies': [],
        'languages': ['Common', 'Halfling'],
        'speed': 25, 'size': 'Small', 'darkvision': False,
    },
    'Gnome': {
        'asi': {'INT': 2},
        'traits': [
            'Darkvision 60 ft.',
            'Gnome Cunning: Advantage on all INT, WIS, and CHA saving throws against magic.',
        ],
        'proficiencies': [],
        'languages': ['Common', 'Gnomish'],
        'speed': 25, 'size': 'Small', 'darkvision': True, 'darkvision_range': 60,
    },
    'Rock Gnome': {
        'asi': {'INT': 2, 'CON': 1},
        'traits': [
            'Darkvision 60 ft.',
            'Gnome Cunning: Advantage on INT, WIS, and CHA saving throws against magic.',
            'Artificer\'s Lore: Double proficiency on History checks about magic items and tech devices.',
            'Tinker: Proficiency with tinker\'s tools. Can construct tiny clockwork devices.',
        ],
        'proficiencies': ["Tinker's Tools"],
        'languages': ['Common', 'Gnomish'],
        'speed': 25, 'size': 'Small', 'darkvision': True, 'darkvision_range': 60,
    },
    'Forest Gnome': {
        'asi': {'INT': 2, 'DEX': 1},
        'traits': [
            'Darkvision 60 ft.',
            'Gnome Cunning: Advantage on INT, WIS, and CHA saving throws against magic.',
            'Natural Illusionist: Know the Minor Illusion cantrip (INT-based).',
            'Speak with Small Beasts: Communicate simple ideas with Small or smaller beasts.',
        ],
        'proficiencies': [],
        'innate_spells': ['Minor Illusion (cantrip, INT-based)'],
        'languages': ['Common', 'Gnomish'],
        'speed': 25, 'size': 'Small', 'darkvision': True, 'darkvision_range': 60,
    },
    'Half-Elf': {
        'asi': {'CHA': 2},
        'traits': [
            'Darkvision 60 ft.',
            'Fey Ancestry: Advantage on saves vs charm; immune to magical sleep.',
            'Skill Versatility: Gain proficiency in two skills of your choice.',
            'Extra Language: Speak, read, and write one extra language.',
            'Flexible ASI: +1 to two ability scores of your choice (in addition to +2 CHA).',
        ],
        'proficiencies': ['Two skills of your choice'],
        'languages': ['Common', 'Elvish', 'One additional language of your choice'],
        'speed': 30, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'Half-Orc': {
        'asi': {'STR': 2, 'CON': 1},
        'traits': [
            'Darkvision 60 ft.',
            'Menacing: Proficiency in the Intimidation skill.',
            'Relentless Endurance: When reduced to 0 HP but not killed outright, drop to 1 HP instead (1/long rest).',
            'Savage Attacks: Critical hits with melee weapons roll one additional weapon damage die.',
        ],
        'proficiencies': ['Intimidation'],
        'languages': ['Common', 'Orc'],
        'speed': 30, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'Tiefling': {
        'asi': {'INT': 1, 'CHA': 2},
        'traits': [
            'Darkvision 60 ft.',
            'Hellish Resistance: Resistance to fire damage.',
            'Infernal Legacy: Thaumaturgy cantrip. At 3rd level: Hellish Rebuke 1/long rest. At 5th: Darkness 1/long rest. CHA-based.',
        ],
        'proficiencies': [],
        'innate_spells': ['Thaumaturgy (cantrip)'],
        'languages': ['Common', 'Infernal'],
        'speed': 30, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'Dragonborn': {
        'asi': {'STR': 2, 'CHA': 1},
        'traits': [
            'Draconic Ancestry: Choose a dragon type — determines breath weapon damage type and resistance.',
            'Breath Weapon: 15 ft cone or 30 ft line, DEX or CON save, 2d6 damage at level 1 (scales with level). 1/short or long rest.',
            'Damage Resistance: Resistance to your draconic ancestry damage type.',
        ],
        'proficiencies': [],
        'languages': ['Common', 'Draconic'],
        'speed': 30, 'size': 'Medium', 'darkvision': False,
    },
    'Aasimar': {
        'asi': {'CHA': 2},
        'traits': [
            'Darkvision 60 ft.',
            'Celestial Resistance: Resistance to necrotic and radiant damage.',
            'Healing Hands: Touch a creature to restore HP equal to your level (1/long rest).',
            'Light Bearer: Know the Light cantrip (CHA-based).',
            'Subrace: Choose Protector, Scourge, or Fallen Aasimar for additional traits.',
        ],
        'proficiencies': [],
        'innate_spells': ['Light (cantrip, CHA-based)'],
        'languages': ['Common', 'Celestial'],
        'speed': 30, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'Goliath': {
        'asi': {'STR': 2, 'CON': 1},
        'traits': [
            'Natural Athlete: Proficiency in the Athletics skill.',
            'Stone\'s Endurance: Reduce damage by 1d12 + CON modifier (1/short or long rest).',
            'Powerful Build: Count as one size larger for carrying capacity.',
            'Mountain Born: Acclimated to high altitude and cold weather.',
        ],
        'proficiencies': ['Athletics'],
        'languages': ['Common', 'Giant'],
        'speed': 30, 'size': 'Medium', 'darkvision': False,
    },
    'Tabaxi': {
        'asi': {'DEX': 2, 'CHA': 1},
        'traits': [
            'Darkvision 60 ft.',
            'Feline Agility: Double your speed for one turn (recharge by taking a turn without moving).',
            'Cat\'s Claws: Climbing speed 20 ft. Unarmed strikes deal 1d4 slashing damage.',
            'Cat\'s Talent: Proficiency in Perception and Stealth.',
        ],
        'proficiencies': ['Perception', 'Stealth'],
        'languages': ['Common', 'One additional language of your choice'],
        'speed': 30, 'size': 'Medium', 'darkvision': True, 'darkvision_range': 60,
    },
    'Kenku': {
        'asi': {'DEX': 2, 'WIS': 1},
        'traits': [
            'Expert Forgery: Duplicate handwriting and manufactured items with advantage.',
            'Kenku Training: Proficiency in two of: Acrobatics, Deception, Stealth, Sleight of Hand.',
            'Mimicry: Mimic sounds and voices heard. Insight DC 14 to detect as imitation.',
        ],
        'proficiencies': ['Acrobatics', 'Deception'],
        'languages': ['Common (understand only)', 'Auran (via mimicry only)'],
        'speed': 30, 'size': 'Medium', 'darkvision': False,
    },
    'Lizardfolk': {
        'asi': {'CON': 2, 'WIS': 1},
        'traits': [
            'Hold Breath: Hold breath for 15 minutes.',
            'Hunter\'s Lore: Proficiency in two of: Animal Handling, Nature, Perception, Stealth, Survival.',
            'Natural Armor: AC = 13 + DEX modifier when not wearing armor.',
            'Hungry Jaws: Bonus action bite (1d6+STR piercing). Gain temp HP = CON modifier on hit.',
        ],
        'proficiencies': ['Perception', 'Stealth'],
        'languages': ['Common', 'Draconic'],
        'speed': 30, 'size': 'Medium', 'darkvision': False,
    },
    'Tortle': {
        'asi': {'STR': 2, 'WIS': 1},
        'traits': [
            'Claws: Natural weapon — 1d4 slashing damage.',
            'Hold Breath: Hold breath for up to 1 hour.',
            'Natural Armor: AC = 17 when not wearing armor (DEX does not apply).',
            'Shell Defense: Withdraw into shell as an action — +4 AC, advantage on STR/CON saves.',
            'Survival Instinct: Proficiency in Survival.',
        ],
        'proficiencies': ['Survival'],
        'languages': ['Common', 'Aquan'],
        'speed': 30, 'size': 'Medium', 'darkvision': False,
    },
    'Firbolg': {
        'asi': {'WIS': 2, 'STR': 1},
        'traits': [
            'Firbolg Magic: Detect Magic and Disguise Self 1/short rest (WIS-based).',
            'Hidden Step: Bonus action — turn invisible until your next turn starts (1/short rest).',
            'Powerful Build: Count as one size larger for carrying capacity.',
            'Speech of Beast and Leaf: Communicate simple concepts with beasts and plants.',
        ],
        'proficiencies': [],
        'innate_spells': ['Detect Magic (1/short rest)', 'Disguise Self (1/short rest)'],
        'languages': ['Common', 'Elvish', 'Giant'],
        'speed': 30, 'size': 'Medium', 'darkvision': False,
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# D&D 5E — CLASS DATA
# ═══════════════════════════════════════════════════════════════════════════

DND5E_CLASSES = {
    'Barbarian': {
        'hit_die': 12,
        'saves': ['STR', 'CON'],
        'armor': ['Light Armor', 'Medium Armor', 'Shields'],
        'weapons': ['Simple Weapons', 'Martial Weapons'],
        'tools': [],
        'skill_count': 2,
        'skill_choices': ['Animal Handling', 'Athletics', 'Intimidation', 'Nature', 'Perception', 'Survival'],
        'features': [
            'Rage: Bonus action. Advantage on STR checks/saves, bonus melee damage, resistance to B/P/S damage. '
            '2 uses/long rest at level 1. Duration 1 minute.',
            'Unarmored Defense: AC = 10 + DEX modifier + CON modifier when not wearing armor.',
        ],
        'equipment': ['Greataxe OR two handaxes', "Dungeoneer's pack OR Explorer's pack", '4 javelins'],
    },
    'Bard': {
        'hit_die': 8,
        'saves': ['DEX', 'CHA'],
        'armor': ['Light Armor'],
        'weapons': ['Simple Weapons', 'Hand Crossbow', 'Longsword', 'Rapier', 'Shortsword'],
        'tools': ['Three musical instruments of your choice'],
        'skill_count': 3,
        'skill_choices': ['Any skill'],
        'features': [
            'Spellcasting (CHA-based): 2 cantrips, 4 spells known, two 1st-level slots.',
            'Bardic Inspiration: Bonus action — grant ally a d6 die to add to one roll. Uses = CHA modifier/long rest.',
        ],
        'equipment': ['Rapier OR longsword OR simple weapon', "Diplomat's pack OR Entertainer's pack",
                      'Lute OR another musical instrument', 'Leather armor', 'Dagger'],
    },
    'Cleric': {
        'hit_die': 8,
        'saves': ['WIS', 'CHA'],
        'armor': ['Light Armor', 'Medium Armor', 'Heavy Armor', 'Shields'],
        'weapons': ['Simple Weapons'],
        'tools': [],
        'skill_count': 2,
        'skill_choices': ['History', 'Insight', 'Medicine', 'Persuasion', 'Religion'],
        'features': [
            'Spellcasting (WIS-based): 3 cantrips, prepared spells = WIS modifier + level, two 1st-level slots.',
            'Divine Domain: Choose a subclass domain at level 1 (bonus spells + domain abilities).',
        ],
        'equipment': ['Mace OR warhammer', 'Scale mail OR leather armor OR chain mail',
                      'Light crossbow + 20 bolts OR simple weapon', "Priest's pack OR Explorer's pack",
                      'Holy symbol', 'Shield'],
    },
    'Druid': {
        'hit_die': 8,
        'saves': ['INT', 'WIS'],
        'armor': ['Light Armor (non-metal)', 'Medium Armor (non-metal)', 'Shields (non-metal)'],
        'weapons': ['Clubs', 'Daggers', 'Darts', 'Javelins', 'Maces', 'Quarterstaffs',
                    'Scimitars', 'Sickles', 'Slings', 'Spears'],
        'tools': ['Herbalism Kit'],
        'skill_count': 2,
        'skill_choices': ['Arcana', 'Animal Handling', 'Insight', 'Medicine', 'Nature', 'Perception', 'Religion', 'Survival'],
        'features': [
            'Spellcasting (WIS-based): 2 cantrips, prepared spells = WIS modifier + level, two 1st-level slots.',
            'Druidic: Know secret Druidic language and can leave/recognize hidden nature messages.',
        ],
        'equipment': ['Wooden shield OR simple weapon', 'Scimitar OR simple melee weapon',
                      'Leather armor', "Explorer's pack", 'Druidic focus'],
    },
    'Fighter': {
        'hit_die': 10,
        'saves': ['STR', 'CON'],
        'armor': ['All Armor', 'Shields'],
        'weapons': ['Simple Weapons', 'Martial Weapons'],
        'tools': [],
        'skill_count': 2,
        'skill_choices': ['Acrobatics', 'Animal Handling', 'Athletics', 'History', 'Insight',
                          'Intimidation', 'Perception', 'Survival'],
        'features': [
            'Fighting Style: Choose one at level 1 (Archery, Defense, Dueling, Great Weapon Fighting, Protection, Two-Weapon Fighting).',
            'Second Wind: Bonus action — regain 1d10 + Fighter level HP (1/short or long rest).',
        ],
        'equipment': ['Chain mail OR leather armor + longbow + 20 arrows',
                      'Martial weapon + shield OR two martial weapons',
                      'Light crossbow + 20 bolts OR two handaxes',
                      "Dungeoneer's pack OR Explorer's pack"],
    },
    'Monk': {
        'hit_die': 8,
        'saves': ['STR', 'DEX'],
        'armor': [],
        'weapons': ['Simple Weapons', 'Shortsword'],
        'tools': ['One artisan\'s tool or musical instrument of your choice'],
        'skill_count': 2,
        'skill_choices': ['Acrobatics', 'Athletics', 'History', 'Insight', 'Religion', 'Stealth'],
        'features': [
            'Unarmored Defense: AC = 10 + DEX modifier + WIS modifier when not wearing armor.',
            'Martial Arts: DEX for monk weapons, unarmed strike 1d4 at level 1, bonus unarmed strike after Attack action.',
        ],
        'equipment': ['Shortsword OR simple weapon', "Dungeoneer's pack OR Explorer's pack", '10 darts'],
    },
    'Paladin': {
        'hit_die': 10,
        'saves': ['WIS', 'CHA'],
        'armor': ['All Armor', 'Shields'],
        'weapons': ['Simple Weapons', 'Martial Weapons'],
        'tools': [],
        'skill_count': 2,
        'skill_choices': ['Athletics', 'Insight', 'Intimidation', 'Medicine', 'Persuasion', 'Religion'],
        'features': [
            'Divine Sense: Detect celestials, fiends, and undead within 60 ft (1 + CHA modifier uses/long rest).',
            'Lay on Hands: Healing pool = Paladin level × 5 HP. Cure disease/poison costs 5 HP from pool.',
            'Fighting Style: Choose one at level 2 (Defense, Dueling, Great Weapon Fighting, Protection).',
            'Spellcasting: Begins at level 2 — prepared spells = CHA modifier + half Paladin level, two 1st-level slots.',
            'Sacred Oath: Choose your subclass oath at level 3 (Devotion, Ancients, Vengeance, etc.).',
        ],
        'equipment': ['Martial weapon + shield OR two martial weapons',
                      'Five javelins OR simple melee weapon',
                      "Priest's pack OR Explorer's pack", 'Holy symbol', 'Chain mail'],
    },
    'Ranger': {
        'hit_die': 10,
        'saves': ['STR', 'DEX'],
        'armor': ['Light Armor', 'Medium Armor', 'Shields'],
        'weapons': ['Simple Weapons', 'Martial Weapons'],
        'tools': [],
        'skill_count': 3,
        'skill_choices': ['Animal Handling', 'Athletics', 'Insight', 'Investigation',
                          'Nature', 'Perception', 'Stealth', 'Survival'],
        'features': [
            'Favored Enemy: Choose a creature type — advantage on Survival to track them and INT recalls to recall lore.',
            'Natural Explorer: Choose a favored terrain type — several travel and navigation benefits.',
            'Fighting Style: Choose one at level 2 (Archery, Defense, Dueling, Two-Weapon Fighting).',
            'Spellcasting: Begins at level 2 — spells known = level-based table, two 1st-level slots.',
            'Ranger Archetype: Choose your subclass at level 3 (Hunter, Beast Master, Gloom Stalker, etc.).',
        ],
        'equipment': ['Scale mail OR leather armor', 'Two shortswords OR two simple melee weapons',
                      "Dungeoneer's pack OR Explorer's pack", 'Longbow and 20 arrows'],
    },
    'Rogue': {
        'hit_die': 8,
        'saves': ['DEX', 'INT'],
        'armor': ['Light Armor'],
        'weapons': ['Simple Weapons', 'Hand Crossbow', 'Longsword', 'Rapier', 'Shortsword'],
        'tools': ["Thieves' Tools"],
        'skill_count': 4,
        'skill_choices': ['Acrobatics', 'Athletics', 'Deception', 'Insight', 'Intimidation',
                          'Investigation', 'Perception', 'Performance', 'Persuasion',
                          'Sleight of Hand', 'Stealth'],
        'features': [
            'Expertise: Choose 2 proficiencies to double your proficiency bonus on those checks.',
            'Sneak Attack: Once per turn, +1d6 damage with advantage or adjacent ally. Must use finesse/ranged weapon.',
            "Thieves' Cant: Secret rogue language and code system.",
        ],
        'equipment': ['Rapier OR shortsword', 'Shortbow + 20 arrows OR shortsword',
                      "Burglar's pack OR Dungeoneer's pack", 'Leather armor', 'Two daggers', "Thieves' tools"],
    },
    'Sorcerer': {
        'hit_die': 6,
        'saves': ['CON', 'CHA'],
        'armor': [],
        'weapons': ['Daggers', 'Darts', 'Slings', 'Quarterstaffs', 'Light Crossbows'],
        'tools': [],
        'skill_count': 2,
        'skill_choices': ['Arcana', 'Deception', 'Insight', 'Intimidation', 'Persuasion', 'Religion'],
        'features': [
            'Spellcasting (CHA-based): 4 cantrips, 2 spells known, two 1st-level slots.',
            'Sorcerous Origin: Choose a subclass at level 1 (Draconic Bloodline, Wild Magic, Storm Sorcery, etc.).',
        ],
        'equipment': ['Light crossbow + 20 bolts OR simple weapon',
                      'Component pouch OR arcane focus',
                      "Dungeoneer's pack OR Explorer's pack", 'Two daggers'],
    },
    'Warlock': {
        'hit_die': 8,
        'saves': ['WIS', 'CHA'],
        'armor': ['Light Armor'],
        'weapons': ['Simple Weapons'],
        'tools': [],
        'skill_count': 2,
        'skill_choices': ['Arcana', 'Deception', 'History', 'Intimidation', 'Investigation', 'Nature', 'Religion'],
        'features': [
            'Otherworldly Patron: Choose at level 1 (Archfey, Fiend, Great Old One, etc.).',
            'Pact Magic (CHA-based): 2 cantrips, 2 spells known, ONE 1st-level slot — recharges on short rest.',
        ],
        'equipment': ['Light crossbow + 20 bolts OR simple weapon', 'Component pouch OR arcane focus',
                      "Scholar's pack OR Dungeoneer's pack", 'Leather armor', 'Simple weapon', 'Two daggers'],
    },
    'Wizard': {
        'hit_die': 6,
        'saves': ['INT', 'WIS'],
        'armor': [],
        'weapons': ['Daggers', 'Darts', 'Slings', 'Quarterstaffs', 'Light Crossbows'],
        'tools': [],
        'skill_count': 2,
        'skill_choices': ['Arcana', 'History', 'Insight', 'Investigation', 'Medicine', 'Religion'],
        'features': [
            'Spellcasting (INT-based): 3 cantrips, 6 spells in spellbook, prepared = INT modifier + level, two 1st-level slots.',
            'Arcane Recovery: Once per day, recover spell slots with combined level up to half your Wizard level.',
            'Arcane Tradition: Choose a school of magic at level 2 (Evocation, Illusion, Abjuration, etc.).',
        ],
        'equipment': ['Quarterstaff OR dagger', 'Component pouch OR arcane focus',
                      "Scholar's pack OR Explorer's pack", 'Spellbook'],
    },
    'Artificer': {
        'hit_die': 8,
        'saves': ['CON', 'INT'],
        'armor': ['Light Armor', 'Medium Armor', 'Shields'],
        'weapons': ['Simple Weapons'],
        'tools': ["Thieves' Tools", "Tinker's Tools", "One artisan's tool of your choice"],
        'skill_count': 2,
        'skill_choices': ['Arcana', 'History', 'Investigation', 'Medicine', 'Nature', 'Perception', 'Sleight of Hand'],
        'features': [
            'Spellcasting (INT-based via tools): 2 cantrips, prepared = INT modifier + half Artificer level, two 1st-level slots.',
            'Magical Tinkering: Imbue small objects with minor magical properties.',
        ],
        'equipment': ['Two simple weapons', 'Light crossbow + 20 bolts',
                      'Scale mail OR studded leather', "Thieves' tools", "Dungeoneer's pack"],
    },
    'Blood Hunter': {
        'hit_die': 10,
        'saves': ['DEX', 'INT'],
        'armor': ['Light Armor', 'Medium Armor', 'Shields'],
        'weapons': ['Simple Weapons', 'Martial Weapons'],
        'tools': ["Alchemist's Supplies"],
        'skill_count': 3,
        'skill_choices': ['Arcana', 'Athletics', 'History', 'Insight', 'Investigation', 'Religion', 'Stealth', 'Survival'],
        'features': [
            "Hunter's Bane: Advantage on Survival to track fey/fiends/undead; advantage on INT recalls about them.",
            'Blood Maledict: Curse a creature within 30 ft — disadvantage on attacks against you. '
            'Take 1d4 psychic damage to activate. Uses = proficiency bonus/long rest.',
        ],
        'equipment': ['Martial weapon + shield OR two martial weapons',
                      'Light crossbow + 20 bolts OR simple weapon',
                      "Dungeoneer's pack", 'Chain mail OR leather armor'],
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# PATHFINDER 2E — ANCESTRY DATA
# ═══════════════════════════════════════════════════════════════════════════

PF2E_ANCESTRIES = {
    'Human': {
        'hp': 8, 'speed': 25, 'size': 'Medium',
        'languages': ['Common', 'One additional language of your choice'],
        'features': [
            'Skilled: Gain trained proficiency in one additional skill.',
            'Versatile Heritage: Gain a general feat at 1st level in addition to your ancestry feat.',
        ],
        'ability_boosts': 'Two free ability boosts of your choice', 'ability_flaw': None,
    },
    'Elf': {
        'hp': 6, 'speed': 30, 'size': 'Medium',
        'languages': ['Common', 'Elven', 'One additional language per INT modifier'],
        'features': [
            'Low-Light Vision: See in dim light as if it were bright light.',
            'Elven Longevity: Immune to effects of magical aging.',
            'Elven Weapon Familiarity: Trained with longbow, composite longbow, rapier, shortbow, shortsword.',
        ],
        'ability_boosts': '+2 DEX, +2 INT, one free boost', 'ability_flaw': '-2 CON',
    },
    'Dwarf': {
        'hp': 10, 'speed': 20, 'size': 'Medium',
        'languages': ['Common', 'Dwarven', 'One additional language per INT modifier'],
        'features': [
            'Darkvision: See in darkness as if it were dim light.',
            'Clan Dagger: Receive a free clan dagger at character creation.',
            'Dwarven Weapon Familiarity: Trained with battleaxe, pick, and warhammer.',
        ],
        'ability_boosts': '+2 CON, +2 WIS, one free boost', 'ability_flaw': '-2 CHA',
    },
    'Gnome': {
        'hp': 8, 'speed': 25, 'size': 'Small',
        'languages': ['Common', 'Gnomish', 'Sylvan', 'One per INT modifier'],
        'features': [
            'Low-Light Vision.',
            'Gnome Obsession: Trained in one Lore skill of your choice at level 2.',
            'Gnome Weapon Familiarity: Trained with glaive and kukri.',
        ],
        'ability_boosts': '+2 CON, +2 CHA, one free boost', 'ability_flaw': '-2 STR',
    },
    'Halfling': {
        'hp': 6, 'speed': 25, 'size': 'Small',
        'languages': ['Common', 'Halfling', 'One per INT modifier'],
        'features': [
            'Keen Eyes: Reduce concealment penalty; bonus to spot hidden creatures.',
            "Halfling Luck: When you fail a roll, reroll and keep the higher result (1/day).",
            'Halfling Weapon Familiarity: Trained with sling, halfling sling staff, shortsword.',
        ],
        'ability_boosts': '+2 DEX, +2 WIS, one free boost', 'ability_flaw': '-2 STR',
    },
    'Goblin': {
        'hp': 6, 'speed': 25, 'size': 'Small',
        'languages': ['Common', 'Goblin'],
        'features': [
            'Darkvision.',
            'Goblin Scuttle: Reaction — Step when an ally moves adjacent to your enemy.',
            'Goblin Weapon Familiarity: Trained with dogslicer and horsechopper.',
        ],
        'ability_boosts': '+2 DEX, +2 CHA, one free boost', 'ability_flaw': '-2 WIS',
    },
    'Orc': {
        'hp': 10, 'speed': 25, 'size': 'Medium',
        'languages': ['Common', 'Orcish'],
        'features': [
            'Darkvision.',
            'Ferocity: When reduced to 0 HP, make a DC 10 flat check — on success stay at 1 HP (1/day).',
            'Orc Weapon Familiarity: Trained with falchion, greataxe, and all orc weapons.',
        ],
        'ability_boosts': '+2 STR, one free boost', 'ability_flaw': '-2 INT',
    },
}

PF2E_CLASSES = {
    'Fighter': {
        'hp_per_level': 10, 'key_ability': 'STR or DEX',
        'saves': {'Fortitude': 'Expert', 'Reflex': 'Expert', 'Will': 'Trained'},
        'skills_trained': 3,
        'features': [
            'Attack of Opportunity: Reaction when enemy within reach leaves or makes ranged attack.',
            'Shield Block: Reaction to reduce incoming damage using your shield.',
            'Weapon Mastery: Expert in all martial weapons; trained in advanced weapons.',
        ],
    },
    'Rogue': {
        'hp_per_level': 8, 'key_ability': 'DEX',
        'saves': {'Fortitude': 'Trained', 'Reflex': 'Expert', 'Will': 'Expert'},
        'skills_trained': 7,
        'features': [
            'Sneak Attack: +1d6 damage against flat-footed enemies.',
            "Rogue's Racket: Choose Ruffian, Scoundrel, or Thief — shapes key ability and bonus feature.",
            'Surprise Attack: Enemies are flat-footed to you on the first round of combat.',
        ],
    },
    'Wizard': {
        'hp_per_level': 6, 'key_ability': 'INT',
        'saves': {'Fortitude': 'Trained', 'Reflex': 'Trained', 'Will': 'Expert'},
        'skills_trained': 2,
        'features': [
            'Spellcasting (INT-based): Prepare spells daily. Spellbook starts with 10 cantrips + 5 first-level spells.',
            'Arcane School: Specialize in one school for bonus spells and powers.',
            'Arcane Thesis: Choose a thesis at level 1 defining your unique magical approach.',
        ],
    },
    'Cleric': {
        'hp_per_level': 8, 'key_ability': 'WIS',
        'saves': {'Fortitude': 'Trained', 'Reflex': 'Trained', 'Will': 'Expert'},
        'skills_trained': 2,
        'features': [
            'Spellcasting (WIS-based): 3 cantrips, 2 first-level slots per day.',
            'Divine Font: Channel Heal or Harm (1 + CHA modifier uses per day).',
            'Doctrine: Choose Cloistered Cleric or Warpriest.',
        ],
    },
    'Barbarian': {
        'hp_per_level': 12, 'key_ability': 'STR',
        'saves': {'Fortitude': 'Expert', 'Reflex': 'Trained', 'Will': 'Expert'},
        'skills_trained': 3,
        'features': [
            'Rage: Bonus 2 melee damage, temp HP = level + CON mod, cannot concentrate. 1 minute.',
            'Instinct: Choose Animal, Dragon, Fury, Giant, Spirit, or Superstition.',
        ],
    },
    'Bard': {
        'hp_per_level': 8, 'key_ability': 'CHA',
        'saves': {'Fortitude': 'Trained', 'Reflex': 'Trained', 'Will': 'Expert'},
        'skills_trained': 4,
        'features': [
            'Spellcasting (CHA-based, spontaneous): 2 cantrips + 2 first-level spells known.',
            'Muse: Choose Enigma, Maestro, or Polymath — shapes signature spell and unique ability.',
        ],
    },
    'Champion': {
        'hp_per_level': 10, 'key_ability': 'STR or DEX',
        'saves': {'Fortitude': 'Expert', 'Reflex': 'Trained', 'Will': 'Expert'},
        'skills_trained': 2,
        'features': [
            'Cause: Choose a divine cause (Paladin/Redeemer/Liberator) — shapes deity requirements and reaction.',
            'Shield Block: Reduce incoming damage using your shield as a reaction.',
            'Champion\'s Reaction: Your cause grants a unique reaction triggered by specific conditions.',
        ],
    },
    'Ranger': {
        'hp_per_level': 10, 'key_ability': 'STR or DEX',
        'saves': {'Fortitude': 'Expert', 'Reflex': 'Expert', 'Will': 'Trained'},
        'skills_trained': 4,
        'features': [
            "Hunt Prey: Single action — designate one creature. Reduce their concealment; ignore first range increment penalty.",
            "Ranger's Edge: Choose Flurry, Outwit, or Precision — shapes your bonus against hunted prey.",
        ],
    },
    'Monk': {
        'hp_per_level': 10, 'key_ability': 'STR or DEX',
        'saves': {'Fortitude': 'Expert', 'Reflex': 'Expert', 'Will': 'Expert'},
        'skills_trained': 4,
        'features': [
            'Flurry of Blows: Two-action activity — make two unarmed strikes at no multiple attack penalty.',
            'Powerful Fist: Unarmed strikes deal 1d6 damage and count as trained.',
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# CALL OF CTHULHU — OCCUPATION SKILL BONUSES
# ═══════════════════════════════════════════════════════════════════════════

COC_OCCUPATIONS = {
    'Doctor':           {'skills': ['First Aid', 'Medicine', 'Psychology', 'Persuade', 'Science (Biology)', 'Spot Hidden'], 'points': 'EDU × 4', 'credit': (30, 80)},
    'Detective':        {'skills': ['Art (Photography)', 'Disguise', 'Law', 'Library Use', 'Persuade', 'Psychology', 'Spot Hidden'], 'points': 'EDU × 2 + DEX or STR × 2', 'credit': (20, 50)},
    'Professor':        {'skills': ['Library Use', 'Other Language', 'Own Language', 'Psychology', 'Science (any)', 'Spot Hidden'], 'points': 'EDU × 4', 'credit': (20, 70)},
    'Journalist':       {'skills': ['Art (Photography)', 'History', 'Library Use', 'Own Language', 'Persuade', 'Psychology', 'Spot Hidden'], 'points': 'EDU × 4', 'credit': (9, 30)},
    'Occultist':        {'skills': ['Anthropology', 'Cthulhu Mythos', 'History', 'Library Use', 'Occult', 'Other Language', 'Spot Hidden'], 'points': 'EDU × 4', 'credit': (9, 65)},
    'Military Officer': {'skills': ['Firearms', 'Fighting', 'First Aid', 'Navigate', 'Persuade', 'Stealth'], 'points': 'EDU × 2 + STR or DEX × 2', 'credit': (20, 70)},
    'Criminal':         {'skills': ['Appraise', 'Disguise', 'Fast Talk', 'Fighting', 'Firearms', 'Locksmith', 'Stealth'], 'points': 'EDU × 2 + DEX × 2', 'credit': (5, 65)},
    'Librarian':        {'skills': ['Accounting', 'History', 'Library Use', 'Other Language', 'Own Language', 'Spot Hidden'], 'points': 'EDU × 4', 'credit': (9, 35)},
    'Artist':           {'skills': ['Art (choose spec)', 'History', 'Own Language', 'Persuade', 'Psychology', 'Spot Hidden'], 'points': 'EDU × 2 + DEX × 2', 'credit': (9, 50)},
    'Sailor':           {'skills': ['First Aid', 'Fighting', 'Mechanical Repair', 'Navigate', 'Pilot (Boat)', 'Spot Hidden', 'Swim'], 'points': 'EDU × 2 + STR × 2', 'credit': (9, 30)},
    'Antiquarian':      {'skills': ['Appraise', 'Art (any)', 'History', 'Library Use', 'Other Language', 'Spot Hidden'], 'points': 'EDU × 4', 'credit': (30, 70)},
}

COC_DEFAULT_OCCUPATION = {
    'skills': ['Library Use', 'Spot Hidden', 'Psychology', 'Persuade'],
    'points': 'EDU × 4', 'credit': (9, 50),
}


# ═══════════════════════════════════════════════════════════════════════════
# CYBERPUNK RED — ROLE SPECIAL ABILITIES
# ═══════════════════════════════════════════════════════════════════════════

CYBERPUNK_ROLES = {
    'Solo':       {'ability': 'Combat Awareness', 'desc': 'Initiative and defense bonus equal to rank. Premier combat specialists.', 'skills': ['Athletics', 'Brawling', 'Evasion', 'Firearms', 'Handgun', 'Perception', 'Shoulder Arms', 'Stealth']},
    'Netrunner':  {'ability': 'Interface', 'desc': 'Access the NET, run Programs, and perform Netrunning. Rank determines Cyberdeck tier.', 'skills': ['Athletics', 'Basic Tech', 'Cryptography', 'Electronics', 'Evasion', 'Handgun', 'Perception', 'Stealth']},
    'Tech':       {'ability': 'Maker', 'desc': 'Build, modify, and repair weapons, armor, and cyberware. Rank = item complexity ceiling.', 'skills': ['Basic Tech', 'Cybertech', 'Electronics', 'Handgun', 'Mechanic', 'Perception', 'Weaponstech']},
    'Medtech':    {'ability': 'Medicine', 'desc': 'Perform surgeries, treat critical injuries, install cyberware. Rank = procedure complexity.', 'skills': ['Basic Tech', 'Cybertech', 'First Aid', 'Human Perception', 'Perception', 'Persuasion']},
    'Rockerboy':  {'ability': 'Charismatic Impact', 'desc': 'Inspire, incite, and manipulate crowds. Rank = crowd size and emotional intensity.', 'skills': ['Athletics', 'Conversation', 'Evasion', 'Human Perception', 'Perception', 'Persuasion', 'Play Instrument']},
    'Fixer':      {'ability': 'Operator', 'desc': 'Source black market goods, manage contacts. Rank = item rarity accessible.', 'skills': ['Conversation', 'Deduction', 'Human Perception', 'Perception', 'Persuasion', 'Streetwise', 'Trading']},
    'Nomad':      {'ability': 'Moto', 'desc': 'Expert vehicle operation and clan network access. Rank = vehicle tier mastered.', 'skills': ['Animal Handling', 'Basic Tech', 'Drive Land Vehicle', 'Mechanic', 'Navigation', 'Perception', 'Shoulder Arms']},
    'Exec':       {'ability': 'Teamwork', 'desc': 'Direct allies for additional team actions per round. Rank = bonus scale.', 'skills': ['Business', 'Conversation', 'Deduction', 'Human Perception', 'Perception', 'Persuasion', 'Streetwise']},
    'Lawman':     {'ability': 'Backup', 'desc': 'Call in police backup as a team action. Rank = officer quantity and quality.', 'skills': ['Criminology', 'Deduction', 'Evasion', 'Handgun', 'Human Perception', 'Interrogation', 'Perception', 'Shoulder Arms']},
    'Media':      {'ability': 'Credibility', 'desc': 'Publish stories that change public opinion. Rank = reach and persuasive impact.', 'skills': ['Conversation', 'Deduction', 'Human Perception', 'Perception', 'Persuasion', 'Streetwise']},
}


# ═══════════════════════════════════════════════════════════════════════════
# DAGGERHEART — HERITAGE & CLASS DATA
# ═══════════════════════════════════════════════════════════════════════════

DAGGERHEART_HERITAGES = {
    'Human': {
        'features': [
            'Adaptable: Gain one additional experience at character creation.',
            'Determined: Once per long rest, reroll a failed roll and keep the higher result.',
            'Versatile: Gain proficiency in one additional skill or tool of your choice.',
        ],
        'experience': 'One additional experience of your choice',
        'community_bonus': '+1 to any one trait roll once per session.',
    },
    'Elf': {
        'features': [
            'Fey Step: Once per session, teleport up to a close distance as a free action.',
            'Elven Senses: See in dim conditions as clearly as daylight (low-light vision).',
            'Ancient Knowledge: +2 to Knowledge rolls about history, nature, or the arcane.',
        ],
        'experience': 'Choose one: [Ancient History], [Natural Lore], or [Arcane Traditions]',
        'community_bonus': '+1 to Finesse action rolls.',
    },
    'Dwarf': {
        'features': [
            'Dwarven Fortitude: +1 to your Severe damage threshold.',
            'Stonecunning: Advantage on Instinct rolls to notice unusual stonework or underground features.',
            'Weapon Familiarity: Proficiency with warhammers, handaxes, and battleaxes.',
        ],
        'experience': 'Choose one: [Stone Lore], [Ancestral Craft], or [Mountain Survival]',
        'community_bonus': '+1 to Strength rolls against being moved or knocked prone.',
    },
    'Halfling': {
        'features': [
            'Halfling Luck: When you roll a 1 on any Hope die, treat it as a 6 instead.',
            'Nimble: You can move through the space of any creature larger than yourself.',
            'Brave: Advantage on Instinct rolls against the Frightened condition.',
        ],
        'experience': 'Choose one: [Community Networks], [Cooking], or [Stealth]',
        'community_bonus': 'Once per session, reroll a single die and keep the better result.',
    },
    'Goblin': {
        'features': [
            'Nimble Escape: Once per short rest, disengage from melee as a free action.',
            'Sneak Attack: If an ally is adjacent to your target, add +1d6 to your damage.',
            'Pack Tactics: Advantage on attack rolls when an ally is within melee range of the target.',
        ],
        'experience': 'Choose one: [Scavenging], [Sabotage], or [Sneaky Tricks]',
        'community_bonus': '+1 to Finesse rolls when flanking.',
    },
    'Orc': {
        'features': [
            'Savage Strikes: When you roll maximum damage, add +1d6 to the result.',
            'Relentless: When you drop to 0 HP for the first time in a scene, drop to 1 HP instead (1/long rest).',
            'Menacing: +2 to Presence rolls to intimidate.',
        ],
        'experience': 'Choose one: [Clan Warfare], [Survival], or [Intimidation]',
        'community_bonus': '+1 to Strength rolls in combat.',
    },
    'Clank': {
        'features': [
            'Constructed Body: No need to eat, breathe, or sleep — rest 6 hours dormant for long rest benefits.',
            'Unflinching: Once per short rest, mark a Stress to reroll a Fear roll.',
            'Modular: At character creation, choose one tool proficiency permanently installed in your body.',
        ],
        'experience': 'Choose one: [Precision Mechanics], [Understanding Emotions], or [Following Protocols]',
        'community_bonus': 'Ignore one instance of the Frightened condition per session.',
    },
    'Drakona': {
        'features': [
            'Draconic Breath: Once per short rest, DEX action roll — all targets in close burst take 1d8 elemental damage.',
            'Draconic Resilience: Resistance to your breath weapon\'s damage type.',
            'Draconic Presence: +2 to Presence trait rolls.',
        ],
        'experience': 'Choose one: [Dragon Lore], [Commanding Presence], or [Ancient Languages]',
        'community_bonus': '+1 to Strength action rolls.',
    },
    'Faun': {
        'features': [
            'Sure-Footed: Advantage on Agility rolls to maintain balance or traverse difficult terrain.',
            'Charge: Moving at least close range before attacking adds +1d6 to the attack.',
            'Wild Empathy: Communicate simple emotions with natural animals.',
        ],
        'experience': 'Choose one: [Forest Navigation], [Music and Dance], or [Foraging]',
        'community_bonus': '+1 to Agility action rolls.',
    },
    'Fungril': {
        'features': [
            'Spore Cloud: Once per rest, release a confusion cloud (close range). Targets must succeed Presence or be Restrained.',
            'Network Sense: Always aware of allied Fungril within long range.',
            'Adaptive Metabolism: Advantage on rolls to resist poison.',
        ],
        'experience': 'Choose one: [Mycelial Networks], [Decay and Renewal], or [Ancient Memories]',
        'community_bonus': 'Once per session, share a memory with an ally as a free action.',
    },
    'Galapa': {
        'features': [
            'Shell Defense: Reaction — gain +2 Armor Score until start of your next turn (1/rest).',
            'Ancient Patience: Advantage on Instinct rolls to sense deception or hidden intent.',
            'Slow and Steady: Immune to difficult terrain movement penalties.',
        ],
        'experience': 'Choose one: [Ancient Wisdom], [Endurance], or [Lore Keeping]',
        'community_bonus': '+1 to Knowledge rolls.',
    },
    'Giant': {
        'features': [
            'Titanic Strength: Lift score doubled. Melee attacks deal +1 damage.',
            'Imposing Presence: Advantage on Presence rolls to intimidate smaller creatures.',
            'Endure: Once per session, ignore a Severe wound and treat it as Minor instead.',
        ],
        'experience': 'Choose one: [Giant History], [Survival], or [Physical Labor]',
        'community_bonus': '+1 to Strength rolls.',
    },
    'Katari': {
        'features': [
            "Cat's Claws: Unarmed strikes deal 1d6 damage. Can use Finesse instead of Strength.",
            'Pounce: Moving at least close distance before attacking leaves target Vulnerable on a hit.',
            'Feline Senses: Advantage on Instinct rolls to track by scent or detect movement.',
        ],
        'experience': 'Choose one: [Hunting], [Acrobatics], or [Wild Instinct]',
        'community_bonus': '+1 to Finesse rolls.',
    },
    'Ribbet': {
        'features': [
            'Leap: Triple jump distance. Leap as part of movement.',
            'Amphibious: Breathe underwater and swim at full speed.',
            'Sticky Tongue: Once per rest — grab a small object or disarm within close range (Agility vs Strength).',
        ],
        'experience': 'Choose one: [Swamp Navigation], [Ambush Tactics], or [Herbalism]',
        'community_bonus': '+1 to Agility rolls.',
    },
    'Simiah': {
        'features': [
            'Prehensile Tail: Hold an extra small object, climb without hands, or free object interaction 1/round.',
            'Arboreal Agility: Climbing speed = full movement. Advantage on Agility in trees/complex terrain.',
            'Tool Mastery: Advantage on Finesse rolls to use tools or tinker with mechanisms.',
        ],
        'experience': 'Choose one: [Engineering], [Climbing], or [Trade Craft]',
        'community_bonus': '+1 to Finesse rolls.',
    },
}

DAGGERHEART_CLASSES = {
    'Bard': {
        'evasion': 12, 'primary_trait': 'Presence', 'secondary_trait': 'Knowledge',
        'domain_cards': ['Codex', 'Grace'], 'hp_per_level': 6, 'stress_slots': 6,
        'foundation_feature': 'Bardic Flourish',
        'features': [
            'Bardic Flourish (Foundation): Mark a Stress — grant one ally a d4 Inspiration die to add to any roll before you rest.',
            'Song of Rest: During a short rest, spend Hope to restore HP to yourself or allies equal to your Proficiency Bonus.',
        ],
        'starting_equipment': ['Light armor', 'Simple weapon', 'Musical instrument', "Adventurer's supplies"],
    },
    'Druid': {
        'evasion': 12, 'primary_trait': 'Instinct', 'secondary_trait': 'Knowledge',
        'domain_cards': ['Sage', 'Midnight'], 'hp_per_level': 6, 'stress_slots': 6,
        'foundation_feature': 'Shapeshift',
        'features': [
            'Shapeshift (Foundation): Spend Hope — transform into a beast you have encountered. Gain its movement type. Lasts until damaged, action taken, or ended voluntarily.',
            'Wild Sense: Sense presence of magical creatures within long range.',
        ],
        'starting_equipment': ['Light armor', 'Staff or simple weapon', 'Druidic focus', "Adventurer's supplies"],
    },
    'Guardian': {
        'evasion': 9, 'primary_trait': 'Strength', 'secondary_trait': 'Presence',
        'domain_cards': ['Blade', 'Valor'], 'hp_per_level': 8, 'stress_slots': 5,
        'foundation_feature': 'Stalwart',
        'features': [
            'Stalwart (Foundation): Reaction when adjacent ally takes damage — mark a Stress, reduce the damage by your Proficiency Bonus.',
            'Armor Proficiency: All armor. Heavy armor reduces incoming damage by 1.',
        ],
        'starting_equipment': ['Heavy armor', 'Shield', 'Martial melee weapon', "Adventurer's supplies"],
    },
    'Ranger': {
        'evasion': 12, 'primary_trait': 'Finesse', 'secondary_trait': 'Instinct',
        'domain_cards': ['Bone', 'Sage'], 'hp_per_level': 6, 'stress_slots': 6,
        'foundation_feature': 'Mark Prey',
        'features': [
            'Mark Prey (Foundation): Spend Hope — mark a creature. Know its location within long range until next rest. +1d6 damage vs marked targets.',
            'Survivalist: Advantage on Instinct rolls to navigate, forage, or track.',
        ],
        'starting_equipment': ['Medium armor', 'Shortbow + 20 arrows', 'Shortsword or axe', "Adventurer's supplies", "Hunter's kit"],
    },
    'Rogue': {
        'evasion': 12, 'primary_trait': 'Finesse', 'secondary_trait': 'Knowledge',
        'domain_cards': ['Midnight', 'Grace'], 'hp_per_level': 6, 'stress_slots': 6,
        'foundation_feature': 'Sneak Attack',
        'features': [
            'Sneak Attack (Foundation): Once per round with advantage OR adjacent ally — add +2d6 to damage.',
            'Shadow Step: Mark a Stress to move up to close range without triggering reactions.',
        ],
        'starting_equipment': ['Light armor', 'Two daggers or shortswords', 'Shortbow + 20 arrows', "Thieves' tools", "Adventurer's supplies"],
    },
    'Seraph': {
        'evasion': 10, 'primary_trait': 'Presence', 'secondary_trait': 'Strength',
        'domain_cards': ['Valor', 'Splendor'], 'hp_per_level': 7, 'stress_slots': 5,
        'foundation_feature': 'Divine Radiance',
        'features': [
            'Divine Radiance (Foundation): Spend Hope — emit holy radiance. Undead/fiends in close range take 1d8 radiant. Allies in close range heal 1d4 HP.',
            'Lay on Hands: Touch an ally — heal them for your Proficiency Bonus HP (Presence roll). Uses = Presence modifier/long rest.',
        ],
        'starting_equipment': ['Full armor', 'Shield', 'Holy symbol', 'Warhammer or mace', "Adventurer's supplies"],
    },
    'Sorcerer': {
        'evasion': 12, 'primary_trait': 'Instinct', 'secondary_trait': 'Presence',
        'domain_cards': ['Arcana', 'Midnight'], 'hp_per_level': 5, 'stress_slots': 7,
        'foundation_feature': 'Channel Raw Power',
        'features': [
            'Channel Raw Power (Foundation): Spend Stress instead of Hope to cast spells. At 3 Stress, wild surge effects trigger.',
            'Overwhelming Force: Critical successes on spells trigger additional wild power effects.',
        ],
        'starting_equipment': ['Light armor or robes', 'Staff or wand', "Adventurer's supplies", 'Spellbook of origin'],
    },
    'Warrior': {
        'evasion': 10, 'primary_trait': 'Strength', 'secondary_trait': 'Finesse',
        'domain_cards': ['Blade', 'Bone'], 'hp_per_level': 8, 'stress_slots': 5,
        'foundation_feature': 'Brutal Strike',
        'features': [
            'Brutal Strike (Foundation): Once per round after hitting with melee — spend a Hope to add Proficiency Bonus to damage.',
            'Second Wind: Mark a Stress to recover HP equal to your Proficiency Bonus (1/short rest).',
        ],
        'starting_equipment': ['Heavy armor', 'Two martial weapons', 'Shield (optional)', "Adventurer's supplies"],
    },
    'Wizard': {
        'evasion': 12, 'primary_trait': 'Knowledge', 'secondary_trait': 'Instinct',
        'domain_cards': ['Arcana', 'Codex'], 'hp_per_level': 5, 'stress_slots': 7,
        'foundation_feature': 'Arcane Research',
        'features': [
            'Arcane Research (Foundation): During a long rest, mark a Stress to add a new spell to your spellbook from a scroll or tome you have encountered.',
            'Arcane Recovery: Once per short rest, recover one spell slot by spending Hope equal to its level.',
        ],
        'starting_equipment': ['Robes or light armor', 'Staff or arcane focus', 'Spellbook (6 spells)', "Adventurer's supplies", '5 scrolls of your choice'],
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def apply_race_and_class(system_id, race, char_class, abilities, level=1):
    """
    Given a system, race, and class, return all mechanical fields to
    automatically merge into the character sheet.

    Returns a dict — all keys match character sheet field names.

    Checks homebrew library first; falls back to built-in data.
    """
    # ── Strip [Homebrew] label if injected into menus ─────────────────────
    clean_race  = race.replace(' [Homebrew]', '').strip()
    clean_class = char_class.replace(' [Homebrew]', '').strip()

    # ── Check homebrew library first ──────────────────────────────────────
    try:
        import homebrew_generator as _hbg
        is_hb_race  = bool(_hbg.get_homebrew_race(clean_race))
        is_hb_class = bool(_hbg.get_homebrew_class(clean_class))

        if is_hb_race or is_hb_class:
            # Apply homebrew race
            race_result = _hbg.apply_homebrew_race(clean_race, abilities) if is_hb_race else {}

            # Apply homebrew class OR fall through to built-in class data
            if is_hb_class:
                class_result = _hbg.apply_homebrew_class(clean_class, level)
            else:
                # Built-in class for homebrew race
                class_result = {}
                if system_id == 'dnd_5e':
                    cls = dict(DND5E_CLASSES.get(clean_class, {}))
                    if cls:
                        class_result = {
                            'saving_throw_proficiencies': cls.get('saves', []),
                            'armor_proficiencies':        cls.get('armor', []),
                            'weapon_proficiencies':       cls.get('weapons', []),
                            'tool_proficiencies':         cls.get('tools', []),
                            'class_features':             cls.get('features', []),
                            'skill_choices_available':    cls.get('skill_choices', []),
                            'skill_choices_count':        cls.get('skill_count', 2),
                            'class_starting_equipment':   cls.get('equipment', []),
                            'proficiency_bonus':          _prof_bonus(level),
                        }

            # Merge — race_result takes precedence for stat fields, class_result for proficiencies
            merged = {**race_result, **class_result}
            notes = race_result.get('auto_applied_notes', []) + class_result.get('auto_applied_notes', [])
            if notes:
                merged['auto_applied_notes'] = notes
            return merged
    except Exception:
        pass  # homebrew module unavailable — fall through to standard logic

    # ── Standard built-in logic ───────────────────────────────────────────
    if system_id == 'dnd_5e':
        return _apply_dnd5e(race, char_class, abilities, level)
    elif system_id == 'pathfinder_2e':
        return _apply_pf2e(race, char_class, abilities, level)
    elif system_id == 'call_of_cthulhu':
        return _apply_coc(char_class)
    elif system_id == 'cyberpunk_red':
        return _apply_cyberpunk(char_class)
    elif system_id == 'daggerheart':
        return _apply_daggerheart(race, char_class)
    return {}


def _apply_dnd5e(race, char_class, abilities, level):
    result = {}
    notes = []

    # ── RACE: try wiki data first, fall back to hardcoded ─────────────────
    try:
        import wiki_scraper
        wiki_race = wiki_scraper.get_race_data(race)
    except Exception:
        wiki_race = {}

    # Hardcoded is the reliable base; wiki overlays/overrides individual fields
    race_data = dict(DND5E_RACES.get(race, {}))

    # Overlay wiki ASI if present and non-empty (wiki is authoritative)
    if wiki_race.get('asi'):
        race_data['asi'] = wiki_race['asi']
    # Overlay wiki traits if they look useful (>2 entries means real data, not parse failure)
    if len(wiki_race.get('traits', [])) > 2:
        race_data['traits'] = wiki_race['traits']
    # Always prefer wiki speed/size/darkvision when found
    if wiki_race.get('speed'):
        race_data['speed'] = wiki_race['speed']
    if wiki_race.get('size') and wiki_race['size'] != 'Medium':
        race_data['size'] = wiki_race['size']
    if wiki_race.get('darkvision'):
        race_data['darkvision'] = True
        race_data['darkvision_range'] = wiki_race.get('darkvision_range', 60)
    if len(wiki_race.get('languages', [])) > 1:
        race_data['languages'] = wiki_race['languages']

    if race_data:
        if abilities and race_data.get('asi'):
            updated = dict(abilities)
            for stat, bonus in race_data['asi'].items():
                updated[stat] = updated.get(stat, 10) + bonus
            result['abilities'] = updated
            asi_str = ', '.join(f'+{v} {k}' for k, v in race_data['asi'].items())
            notes.append(f'Racial ASI applied: {asi_str}')
        if race_data.get('traits'):
            result['racial_traits'] = race_data['traits']
        if race_data.get('proficiencies'):
            result['racial_proficiencies'] = race_data['proficiencies']
        if race_data.get('innate_spells'):
            result['innate_spells'] = race_data['innate_spells']
        result['languages'] = race_data.get('languages', ['Common'])
        result['speed']     = race_data.get('speed', 30)
        result['size']      = race_data.get('size', 'Medium')
        if race_data.get('darkvision'):
            result['darkvision'] = race_data.get('darkvision_range', 60)

    # ── CLASS: try wiki data first, fall back to hardcoded ────────────────
    class_key = char_class.split('(')[0].strip()

    try:
        import wiki_scraper
        wiki_cls = wiki_scraper.get_class_data(class_key)
    except Exception:
        wiki_cls = {}

    cls = dict(DND5E_CLASSES.get(class_key, {}))

    # Overlay wiki proficiency data when it parsed cleanly
    if wiki_cls.get('saves'):
        cls['saves']  = wiki_cls['saves']
    if wiki_cls.get('armor'):
        cls['armor']  = wiki_cls['armor']
    if wiki_cls.get('weapons'):
        cls['weapons'] = wiki_cls['weapons']
    if wiki_cls.get('tools'):
        cls['tools']   = wiki_cls['tools']
    if wiki_cls.get('skill_choices') and len(wiki_cls['skill_choices']) > 2:
        cls['skill_choices'] = wiki_cls['skill_choices']
        cls['skill_count']   = wiki_cls.get('skill_count', cls.get('skill_count', 2))

    if cls:
        result['saving_throw_proficiencies'] = cls.get('saves', [])
        result['armor_proficiencies']        = cls.get('armor', [])
        result['weapon_proficiencies']       = cls.get('weapons', [])
        result['tool_proficiencies']         = cls.get('tools', [])
        result['class_features']             = cls.get('features', [])
        result['skill_choices_available']    = cls.get('skill_choices', [])
        result['skill_choices_count']        = cls.get('skill_count', 2)
        result['class_starting_equipment']   = cls.get('equipment', [])
        result['proficiency_bonus']          = _prof_bonus(level)
        data_source = 'wiki + built-in' if wiki_cls else 'built-in'
        notes.append(f'{class_key}: proficiencies and features applied ({data_source}).')

    if notes:
        result['auto_applied_notes'] = notes
    return result


def _prof_bonus(level):
    if level <= 4:  return 2
    if level <= 8:  return 3
    if level <= 12: return 4
    if level <= 16: return 5
    return 6


def _apply_pf2e(race, char_class, abilities, level):
    result = {}
    notes = []

    anc = PF2E_ANCESTRIES.get(race, {})
    if anc:
        result['ancestry_hp']       = anc.get('hp', 8)
        result['ancestry_features'] = anc.get('features', [])
        result['languages']         = anc.get('languages', [])
        result['speed']             = anc.get('speed', 25)
        result['size']              = anc.get('size', 'Medium')
        result['ability_boosts']    = anc.get('ability_boosts', '')
        if anc.get('ability_flaw'):
            result['ability_flaw']  = anc['ability_flaw']
        notes.append(f'{race} ancestry HP, features, and languages applied.')

    cls_key = char_class.split('(')[0].strip()
    cls = PF2E_CLASSES.get(cls_key, {})
    if cls:
        result['key_ability']    = cls.get('key_ability', '')
        result['save_ranks']     = cls.get('saves', {})
        result['class_features'] = cls.get('features', [])
        result['skill_count']    = cls.get('skills_trained', 2)
        notes.append(f'{cls_key} key ability, saves, and class features applied.')

    if notes:
        result['auto_applied_notes'] = notes
    return result


def _apply_coc(occupation):
    occ = COC_OCCUPATIONS.get(occupation, COC_DEFAULT_OCCUPATION)
    return {
        'occupation_skills':       occ.get('skills', []),
        'credit_rating_range':     occ.get('credit', (9, 50)),
        'occupation_skill_points': occ.get('points', 'EDU × 4'),
        'auto_applied_notes': [
            f'Occupation skills for {occupation} listed.',
            f'Skill point budget: {occ.get("points", "EDU × 4")}. '
            f'Distribute these among your occupation skills.',
        ],
    }


def _apply_cyberpunk(role):
    r = CYBERPUNK_ROLES.get(role, {})
    if not r:
        return {}
    return {
        'special_ability':     r['ability'],
        'ability_description': r['desc'],
        'role_skill_list':     r.get('skills', []),
        'auto_applied_notes':  [
            f'Role special ability "{r["ability"]}" applied.',
            f'Role skill list populated with {len(r.get("skills", []))} skills.',
        ],
    }


def _apply_daggerheart(heritage, char_class):
    result = {}
    notes = []

    h = DAGGERHEART_HERITAGES.get(heritage, {})
    if h:
        result['heritage_features']   = h.get('features', [])
        result['heritage_experience'] = h.get('experience', '')
        result['community_bonus']     = h.get('community_bonus', '')
        notes.append(f'{heritage} heritage features applied.')

    cls_key = char_class.split('(')[0].strip()
    cls = DAGGERHEART_CLASSES.get(cls_key, {})
    if cls:
        result['evasion']              = cls.get('evasion', 12)
        result['primary_trait']        = cls.get('primary_trait', '')
        result['secondary_trait']      = cls.get('secondary_trait', '')
        result['domain_cards']         = cls.get('domain_cards', [])
        result['stress_slots']         = cls.get('stress_slots', 6)
        result['class_features']       = cls.get('features', [])
        result['class_starting_equip'] = cls.get('starting_equipment', [])
        result['foundation_feature']   = cls.get('foundation_feature', '')
        notes.append(f'{cls_key}: evasion, domain cards, traits, and features applied.')

    if notes:
        result['auto_applied_notes'] = notes
    return result


def format_auto_applied_summary(auto_data, system_id='dnd_5e'):
    """
    Formats a display string of everything auto-applied, for the
    confirmation panel shown after character creation.
    """
    if not auto_data:
        return 'No automatic bonuses for this system.'

    lines = []

    # ASI notes
    for note in auto_data.get('auto_applied_notes', []):
        lines.append(f'[green]✓[/green] {note}')

    # Racial / ancestry / heritage traits
    for key, label in [
        ('racial_traits', 'Racial Traits'),
        ('ancestry_features', 'Ancestry Features'),
        ('heritage_features', 'Heritage Features'),
    ]:
        if auto_data.get(key):
            lines.append(f'\n[cyan]{label}:[/cyan]')
            for t in auto_data[key][:4]:
                lines.append(f'  • {t[:95]}{"..." if len(t) > 95 else ""}')
            extra = len(auto_data[key]) - 4
            if extra > 0:
                lines.append(f'  [dim]...and {extra} more[/dim]')

    # Proficiencies
    for key, label in [
        ('saving_throw_proficiencies', 'Saving Throws'),
        ('armor_proficiencies', 'Armor'),
        ('weapon_proficiencies', 'Weapons'),
        ('tool_proficiencies', 'Tools'),
        ('racial_proficiencies', 'Racial Proficiencies'),
        ('occupation_skills', 'Occupation Skills'),
        ('role_skill_list', 'Role Skills'),
    ]:
        if auto_data.get(key):
            lines.append(f'[cyan]{label}:[/cyan] {", ".join(str(x) for x in auto_data[key][:6])}')

    # Languages / movement / vision
    if auto_data.get('languages'):
        lines.append(f'[cyan]Languages:[/cyan] {", ".join(auto_data["languages"])}')
    if auto_data.get('speed'):
        lines.append(f'[cyan]Speed:[/cyan] {auto_data["speed"]} ft')
    if auto_data.get('size'):
        lines.append(f'[cyan]Size:[/cyan] {auto_data["size"]}')
    if auto_data.get('darkvision'):
        lines.append(f'[cyan]Darkvision:[/cyan] {auto_data["darkvision"]} ft')
    if auto_data.get('proficiency_bonus'):
        lines.append(f'[cyan]Proficiency Bonus:[/cyan] +{auto_data["proficiency_bonus"]}')

    # Daggerheart
    if auto_data.get('evasion'):
        lines.append(f'[cyan]Evasion:[/cyan] {auto_data["evasion"]}')
    if auto_data.get('domain_cards'):
        lines.append(f'[cyan]Domain Cards:[/cyan] {", ".join(auto_data["domain_cards"])}')
    if auto_data.get('stress_slots'):
        lines.append(f'[cyan]Stress Slots:[/cyan] {auto_data["stress_slots"]}')
    if auto_data.get('foundation_feature'):
        lines.append(f'[cyan]Foundation Feature:[/cyan] {auto_data["foundation_feature"]}')

    # Class features (first 2)
    if auto_data.get('class_features'):
        lines.append('\n[cyan]Level 1 Class Features:[/cyan]')
        for f in auto_data['class_features'][:2]:
            short = f[:100] + ('...' if len(f) > 100 else '')
            lines.append(f'  • {short}')
        extra = len(auto_data['class_features']) - 2
        if extra > 0:
            lines.append(f'  [dim]...and {extra} more[/dim]')

    # Starting equipment
    for key in ('class_starting_equipment', 'class_starting_equip'):
        if auto_data.get(key):
            lines.append(f'[cyan]Starting Equipment:[/cyan] {", ".join(auto_data[key][:3])}...')
            break

    # Skill choices
    if auto_data.get('skill_choices_count') and auto_data.get('skill_choices_available'):
        pool = auto_data['skill_choices_available']
        pool_str = 'any skill' if pool == ['Any skill'] else ', '.join(pool[:5])
        lines.append(f'[cyan]Skill Choices:[/cyan] Pick {auto_data["skill_choices_count"]} from: {pool_str}')

    return '\n'.join(lines) if lines else 'Automatic data applied — see sheet for details.'
