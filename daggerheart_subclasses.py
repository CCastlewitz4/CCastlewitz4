# daggerheart_subclasses.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Subclass data for the Daggerheart RPG.
#          Since Daggerheart doesn't have a public wiki like D&D 5e,
#          subclass data is stored here from the official rulebook.
#
# SUBCLASS TERMINOLOGY IN DAGGERHEART:
#   Daggerheart calls subclasses "Specializations" or simply class paths.
#   Each class has 3 specialization paths that shape the character's
#   advanced features from level 4 onward.
#
# INTEGRATION:
#   Called by wiki_scraper.get_subclasses() when system is Daggerheart,
#   and by _pick_subclass() in main.py.
#
# LOCATION: dnd_ai_dm/daggerheart_subclasses.py
# ─────────────────────────────────────────────────────────────────────────────

# Format mirrors SUBCLASS_REGISTRY in wiki_scraper.py:
# class_name → [(display_name, description, source), ...]

DAGGERHEART_SUBCLASSES = {
    'Bard': [
        (
            'The Wordsmith',
            "You weave words like weapons, using language and story to heal, inspire, and devastate. "
            "Your Bardic Flourishes are words that cut deeper than any blade.",
            'Daggerheart Core Rulebook'
        ),
        (
            'The Performer',
            "You live for the stage and the crowd. Your performances channel raw emotion into Hope, "
            "turning every battlefield into your personal theater.",
            'Daggerheart Core Rulebook'
        ),
        (
            'The Antiquarian',
            "You collect fragments of lost history, forgotten lore, and ancient secrets. "
            "Your knowledge of the past becomes a powerful tool in the present.",
            'Daggerheart Core Rulebook'
        ),
    ],
    'Druid': [
        (
            'Warden of the Elements',
            "You draw on the raw forces of nature — fire, storm, stone, and tide — "
            "shaping them into devastating attacks and protective barriers.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Warden of Renewal',
            "Life flows through you like sap through an ancient tree. "
            "You channel nature's regenerative power to heal wounds and restore vitality.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Warden of the Predator',
            "You embody the apex hunter, adopting the instincts and forms of nature's fiercest creatures. "
            "Your Shapeshift forms are built for pursuit, takedown, and dominance.",
            'Daggerheart Core Rulebook'
        ),
    ],
    'Guardian': [
        (
            'Shining Beacon',
            "You are a rallying point on the battlefield, your presence inspiring allies and "
            "drawing enemy attention. Where you stand, the line holds.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Stalwart Defender',
            "You are an immovable wall between your allies and harm. "
            "Your mastery of armor and positioning makes you nearly impossible to bypass.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Vengeful Knight',
            "You do not merely absorb punishment — you punish those who dare threaten your allies. "
            "Every hit they land becomes fuel for your devastating counterstrikes.",
            'Daggerheart Core Rulebook'
        ),
    ],
    'Ranger': [
        (
            'Beastbound',
            "A powerful animal companion fights at your side, an extension of your will and instincts. "
            "Together, you are a devastating hunting pair.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Wayfinder',
            "You move through the world's wild places like a ghost. Terrain, weather, and distance "
            "are tools in your hands, not obstacles.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Archer',
            "Your bow is an extension of your body and your patience is infinite. "
            "At range, you are a precision instrument of inevitable death.",
            'Daggerheart Core Rulebook'
        ),
    ],
    'Rogue': [
        (
            'Syndicate Agent',
            "You operate within the hidden networks of thieves, spies, and information brokers. "
            "Your connections are your power, and knowledge is your currency.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Nightwalker',
            "Shadow is your natural home. You strike from darkness, vanish before retaliation, "
            "and turn the battlefield's chaos into your personal advantage.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Privateer',
            "Bold, daring, and utterly unpredictable — you fight with flair and improvisation. "
            "Every encounter is an opportunity to show off.",
            'Daggerheart Core Rulebook'
        ),
    ],
    'Seraph': [
        (
            'Winged Sentinel',
            "Divine wings carry you above the battlefield, granting you a god's view of combat "
            "and the ability to intervene anywhere you are needed.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Sword of Judgment',
            "You are a divine weapon given flesh. Your strikes carry divine authority, "
            "burning corruption and felling the enemies of your order.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Voice of the Divine',
            "Your words carry the weight of the heavens. You call down divine blessings, "
            "pronounce judgments, and speak the sacred rites that turn the tide of battle.",
            'Daggerheart Core Rulebook'
        ),
    ],
    'Sorcerer': [
        (
            'Primal Origin',
            "Your magic erupts from a wild, uncontrolled source within you. "
            "Wild surges are more frequent but also more powerful — you ride the chaos.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Elemental Origin',
            "You were touched by one of the primal elements at birth or during a pivotal moment. "
            "Your spells are suffused with fire, frost, lightning, or stone.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Rift Origin',
            "Something from beyond the veil reached through and left its mark on you. "
            "Your magic bends reality, tears holes in perception, and defies natural law.",
            'Daggerheart Core Rulebook'
        ),
    ],
    'Warrior': [
        (
            'Call to Arms',
            "You are a rallying force who inspires allies mid-battle. "
            "Your shouts, presence, and decisive action turn the tide of group engagements.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Hammer and Tongs',
            "Raw, relentless power is your signature. You wade in, hit hard, and keep hitting "
            "until the enemy stops moving. Simple. Effective. Devastating.",
            'Daggerheart Core Rulebook'
        ),
        (
            'Prepared for Anything',
            "You have trained for every scenario. No terrain, enemy type, or situation catches "
            "you off guard. You are always ready with exactly the right tool.",
            'Daggerheart Core Rulebook'
        ),
    ],
    'Wizard': [
        (
            'School of Excavation',
            "You plumb the depths of lost magic, recovering and repurposing forgotten spells. "
            "Your spellbook holds arcane secrets others cannot access.",
            'Daggerheart Core Rulebook'
        ),
        (
            'School of War',
            "Magic is your weapon and the battlefield is your laboratory. "
            "Your spells are optimized for destruction, range, and tactical advantage.",
            'Daggerheart Core Rulebook'
        ),
        (
            'School of Knowledge',
            "Power comes from understanding. You accumulate knowledge — magical, historical, and "
            "scientific — and transform information into devastating capability.",
            'Daggerheart Core Rulebook'
        ),
    ],
}


def get_daggerheart_subclasses(class_name: str) -> list[dict]:
    """
    Returns the list of subclass dicts for a Daggerheart class.
    Format matches wiki_scraper.get_subclasses() return format:
      [{'name': str, 'source': str, 'desc': str}, ...]

    Returns an empty list if the class is not found.
    """
    entries = DAGGERHEART_SUBCLASSES.get(class_name, [])
    return [
        {'name': name, 'desc': desc, 'source': source}
        for name, desc, source in entries
    ]


def get_daggerheart_subclass_names(class_name: str) -> list[str]:
    """Just the names — for simple menus."""
    return [sc['name'] for sc in get_daggerheart_subclasses(class_name)]


def list_all_daggerheart_classes() -> list[str]:
    """Returns all class names that have subclass entries."""
    return list(DAGGERHEART_SUBCLASSES.keys())
