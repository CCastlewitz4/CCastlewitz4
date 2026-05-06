# character_sheet_generator.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Generate a formatted character sheet in the terminal.
#
# ENTRY POINT:
#   print_sheet_to_console(character, console) -> None
#     Fully formatted text sheet printed directly to the terminal.
#     No extra dependencies beyond rich (already used everywhere).
#
# DEPENDENCIES:
#   REQUIRED : rich — already used throughout the project
#
# CALLED FROM:
#   main.py — 'sheet' command in the game loop + after character creation.
# ─────────────────────────────────────────────────────────────────────────────

import os
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS  (no external dependencies)
# ─────────────────────────────────────────────────────────────────────────────

def _prof_bonus(level: int) -> int:
    if level <= 4:  return 2
    if level <= 8:  return 3
    if level <= 12: return 4
    if level <= 16: return 5
    return 6


def _modifier(score: int) -> str:
    mod = (score - 10) // 2
    return f'+{mod}' if mod >= 0 else str(mod)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: CONSOLE TEXT SHEET  (only requires rich — always available)
# ─────────────────────────────────────────────────────────────────────────────

def print_sheet_to_console(character: dict, console) -> None:
    """
    Print a fully formatted character sheet to the Rich console.
    Works for all game systems. No dependencies beyond rich.
    """
    from rich.panel import Panel
    from rich.table import Table as RichTable
    from rich.rule  import Rule

    c         = character
    abilities = c.get('abilities', {})
    hp        = c.get('hit_points', {})
    level     = c.get('level', 1)
    system_id = c.get('system_id', 'custom')
    prof      = c.get('proficiency_bonus', _prof_bonus(level))

    SYSTEM_LABELS = {
        'dnd_5e':          'D&D 5e',
        'pathfinder_2e':   'Pathfinder 2e',
        'call_of_cthulhu': 'Call of Cthulhu',
        'cyberpunk_red':   'Cyberpunk Red',
        'daggerheart':     'Daggerheart',
        'starfinder':      'Starfinder',
    }

    console.print()
    console.rule('[bold magenta]CHARACTER SHEET[/bold magenta]', style='magenta')
    console.print()

    # ── HEADER ────────────────────────────────────────────────────────────────
    race_cls = f'{c.get("race", "?")} {c.get("class", "?")}'
    if c.get('subclass'):
        race_cls += f' ({c["subclass"]})'
    if level > 1:
        race_cls += f'  ·  Level {level}'

    hdr = (
        f'[bold white]{c.get("name", "Unnamed")}[/bold white]\n'
        f'[cyan]{race_cls}[/cyan]\n'
        + (f'[dim]{c["alignment"]}[/dim]\n' if c.get('alignment') else '')
        + f'[dim]{SYSTEM_LABELS.get(system_id, "Custom System")}[/dim]'
    )
    console.print(Panel(hdr, border_style='magenta', padding=(0, 2)))

    # ── ABILITY SCORES ────────────────────────────────────────────────────────
    if abilities:
        console.print()
        console.rule('[bold cyan]ABILITY SCORES[/bold cyan]', style='cyan')
        ab_tbl = RichTable(border_style='cyan', padding=(0, 2),
                           show_header=True, header_style='bold cyan')
        for stat in abilities:
            ab_tbl.add_column(stat, justify='center', min_width=6)
        ab_tbl.add_row(*[str(v) for v in abilities.values()])
        ab_tbl.add_row(*[f'[cyan]{_modifier(v)}[/cyan]' for v in abilities.values()])
        console.print(ab_tbl)

    # ── COMBAT ────────────────────────────────────────────────────────────────
    console.print()
    console.rule('[bold red]COMBAT[/bold red]', style='red')

    dex_mod  = (abilities.get('DEX', 10) - 10) // 2
    init_str = f'+{dex_mod}' if dex_mod >= 0 else str(dex_mod)
    parts = [
        f'HP: [bold red]{hp.get("current","?")} / {hp.get("maximum","?")}[/bold red]',
        f'Speed: [white]{c.get("speed", 30)} ft[/white]',
        f'Initiative: [white]{init_str}[/white]',
        f'Prof Bonus: [green]+{prof}[/green]',
    ]
    if c.get('darkvision'):   parts.append(f'Darkvision: [white]{c["darkvision"]} ft[/white]')
    if c.get('armor_class'):  parts.append(f'AC: [white]{c["armor_class"]}[/white]')
    if c.get('size'):         parts.append(f'Size: [white]{c["size"]}[/white]')
    console.print('  ' + '   ·   '.join(parts))

    # ── SAVING THROWS ─────────────────────────────────────────────────────────
    saves_prof = c.get('saving_throw_proficiencies', [])
    if saves_prof and abilities:
        console.print()
        console.rule('[bold yellow]SAVING THROWS[/bold yellow]', style='yellow')
        sv = []
        for stat, val in abilities.items():
            base  = (val - 10) // 2
            is_p  = stat in saves_prof
            bonus = base + prof if is_p else base
            sign  = f'+{bonus}' if bonus >= 0 else str(bonus)
            dot   = '[green]●[/green]' if is_p else '[dim]○[/dim]'
            sv.append(f'{dot} {stat} {sign}')
        console.print('  ' + '   '.join(sv))

    # ── SKILLS ────────────────────────────────────────────────────────────────
    class_sk = c.get('class_skill_proficiencies', [])
    bg_sk    = c.get('background_skill_proficiencies', [])
    all_sk   = set(class_sk + bg_sk)

    DND_SKILLS = [
        ('Acrobatics','DEX'), ('Animal Handling','WIS'), ('Arcana','INT'),
        ('Athletics','STR'),  ('Deception','CHA'),        ('History','INT'),
        ('Insight','WIS'),    ('Intimidation','CHA'),      ('Investigation','INT'),
        ('Medicine','WIS'),   ('Nature','INT'),             ('Perception','WIS'),
        ('Performance','CHA'),('Persuasion','CHA'),         ('Religion','INT'),
        ('Sleight of Hand','DEX'), ('Stealth','DEX'),       ('Survival','WIS'),
    ]

    if all_sk and system_id in ('dnd_5e', 'pathfinder_2e', 'starfinder'):
        console.print()
        console.rule('[bold yellow]SKILLS[/bold yellow]', style='yellow')
        sk_tbl = RichTable(border_style='dim', padding=(0, 1),
                           show_header=False, box=None)
        sk_tbl.add_column('dot',  width=3)
        sk_tbl.add_column('bon',  width=5, justify='right')
        sk_tbl.add_column('name', min_width=22)
        sk_tbl.add_column('dot2', width=3)
        sk_tbl.add_column('bon2', width=5, justify='right')
        sk_tbl.add_column('nam2', min_width=22)

        half = len(DND_SKILLS) // 2 + len(DND_SKILLS) % 2
        for i in range(half):
            sk1, ab1 = DND_SKILLS[i]
            b1 = (abilities.get(ab1, 10) - 10) // 2
            p1 = sk1 in all_sk;  b1 = b1 + prof if p1 else b1
            s1 = f'+{b1}' if b1 >= 0 else str(b1)
            d1 = '[green]●[/green]' if p1 else '[dim]○[/dim]'
            n1 = f'[white]{sk1}[/white]' if p1 else f'[dim]{sk1}[/dim]'
            if i + half < len(DND_SKILLS):
                sk2, ab2 = DND_SKILLS[i + half]
                b2 = (abilities.get(ab2, 10) - 10) // 2
                p2 = sk2 in all_sk;  b2 = b2 + prof if p2 else b2
                s2 = f'+{b2}' if b2 >= 0 else str(b2)
                d2 = '[green]●[/green]' if p2 else '[dim]○[/dim]'
                n2 = f'[white]{sk2}[/white]' if p2 else f'[dim]{sk2}[/dim]'
            else:
                d2 = s2 = n2 = ''
            sk_tbl.add_row(d1, s1, n1, d2, s2, n2)
        console.print(sk_tbl)

    elif all_sk:
        console.print()
        console.rule('[bold yellow]SKILL PROFICIENCIES[/bold yellow]', style='yellow')
        console.print('  ' + ', '.join(sorted(all_sk)))

    if system_id == 'call_of_cthulhu' and c.get('skills'):
        console.print()
        console.rule('[bold yellow]SKILLS[/bold yellow]', style='yellow')
        for sk in c['skills']:
            console.print(f'  [white]▸[/white] {sk}')

    # ── SPELLS ────────────────────────────────────────────────────────────────
    spells = c.get('spells', [])
    if spells:
        console.print()
        console.rule('[bold magenta]SPELLS & CANTRIPS[/bold magenta]', style='magenta')
        for i in range(0, len(spells), 3):
            console.print('  ' + '   '.join(f'[cyan]✦[/cyan] {sp}'
                                             for sp in spells[i:i+3]))

    # ── SPELL SLOTS ───────────────────────────────────────────────────────────
    spell_slots = c.get('spell_slots', {})
    if spell_slots:
        console.print()
        console.rule('[bold magenta]SPELL SLOTS[/bold magenta]', style='magenta')
        slot_parts = [
            f'[bold white]Level {lvl}:[/bold white] [cyan]{cnt} slot{"s" if cnt != 1 else ""}[/cyan]'
            for lvl, cnt in sorted(spell_slots.items())
            if cnt > 0
        ]
        console.print('  ' + '   '.join(slot_parts))

    # ── RUMORS ────────────────────────────────────────────────────────────────
    rumors = c.get('rumors', [])
    if rumors:
        console.print()
        console.rule('[bold yellow]RUMORS HEARD[/bold yellow]', style='yellow')
        for r in rumors:
            is_true = r.get('true', False)
            tag     = '[green][TRUE] [/green]' if is_true else '[dim][FALSE][/dim]'
            console.print(f'  {tag} {r.get("text", "")}')
        console.print(
            '  [dim]True rumors may surface as events; false rumors are just gossip.[/dim]'
        )

    # ── CLASS FEATURES ────────────────────────────────────────────────────────
    features = c.get('class_features', [])
    if features:
        console.print()
        console.rule('[bold cyan]CLASS FEATURES[/bold cyan]', style='cyan')
        for feat in features:
            parts = feat.split(':', 1)
            if len(parts) == 2:
                console.print(f'  [bold white]{parts[0].strip()}:[/bold white] '
                              f'[dim]{parts[1].strip()[:140]}[/dim]')
            else:
                console.print(f'  [white]▸[/white] {feat[:150]}')

    # ── CHOSEN CLASS OPTIONS ──────────────────────────────────────────────────
    EXTRA_LABELS = {
        'fighting_style':       'Fighting Style',
        'sorcerous_origin':     'Sorcerous Origin',
        'divine_domain':        'Divine Domain',
        'otherworldly_patron':  'Otherworldly Patron',
        'pact_boon':            'Pact Boon',
        'metamagic':            'Metamagic',
        'eldritch_invocations': 'Eldritch Invocations',
    }
    extras = {k: v for k, v in c.items() if k in EXTRA_LABELS and v}
    if extras:
        console.print()
        console.rule('[bold cyan]CHOSEN CLASS OPTIONS[/bold cyan]', style='cyan')
        for key, val in extras.items():
            val_str = ', '.join(val) if isinstance(val, list) else str(val)
            console.print(f'  [bold white]{EXTRA_LABELS[key]}:[/bold white] {val_str}')

    # ── RACIAL / HERITAGE TRAITS ───────────────────────────────────────────────
    racial = (c.get('racial_traits') or c.get('heritage_features')
              or c.get('ancestry_features') or [])
    if racial:
        console.print()
        r_lbl = {
            'daggerheart':   'HERITAGE FEATURES',
            'pathfinder_2e': 'ANCESTRY FEATURES',
        }.get(system_id, 'RACIAL TRAITS')
        console.rule(f'[bold green]{r_lbl}[/bold green]', style='green')
        for t in racial:
            parts = t.split(':', 1)
            if len(parts) == 2:
                console.print(f'  [bold white]{parts[0].strip()}:[/bold white] '
                              f'[dim]{parts[1].strip()[:140]}[/dim]')
            else:
                console.print(f'  [white]▸[/white] {t[:150]}')

    # ── PROFICIENCIES & LANGUAGES ──────────────────────────────────────────────
    prof_lines = []
    for key, label in [
        ('armor_proficiencies',  'Armor'),
        ('weapon_proficiencies', 'Weapons'),
        ('tool_proficiencies',   'Tools'),
        ('racial_proficiencies', 'Racial'),
        ('languages',            'Languages'),
    ]:
        vals = c.get(key, [])
        if vals:
            prof_lines.append(
                f'  [bold white]{label}:[/bold white] {", ".join(vals)}'
            )
    if prof_lines:
        console.print()
        console.rule('[bold green]PROFICIENCIES & LANGUAGES[/bold green]', style='green')
        for line in prof_lines:
            console.print(line)

    # ── EQUIPMENT & INVENTORY ─────────────────────────────────────────────────
    inventory = c.get('inventory', [])
    if inventory:
        console.print()
        console.rule('[bold yellow]EQUIPMENT & INVENTORY[/bold yellow]', style='yellow')
        half = len(inventory) // 2 + len(inventory) % 2
        for i in range(half):
            left  = f'[white]▸[/white] {inventory[i]}'
            right = f'[white]▸[/white] {inventory[i+half]}' \
                    if i + half < len(inventory) else ''
            console.print(f'  {left:<50} {right}' if right else f'  {left}')

    # ── BACKGROUND ────────────────────────────────────────────────────────────
    if c.get('background'):
        console.print()
        console.print(f'  [bold white]Background:[/bold white] {c["background"]}')
        if c.get('background_feature'):
            console.print(f'  [bold white]Feature:[/bold white] {c["background_feature"]}')

    # ── SYSTEM-SPECIFIC ────────────────────────────────────────────────────────
    if system_id == 'call_of_cthulhu':
        console.print()
        console.rule('[bold red]SANITY[/bold red]', style='red')
        console.print(f'  [bold white]Sanity:[/bold white] {c.get("sanity", "?")}')

    elif system_id == 'cyberpunk_red':
        console.print()
        console.rule('[bold red]ROLE & CYBERWARE[/bold red]', style='red')
        if c.get('special_ability'):
            console.print(f'  [bold white]Role Ability:[/bold white] {c["special_ability"]}')
        if c.get('humanity') is not None:
            console.print(f'  [bold white]Humanity:[/bold white] {c["humanity"]}')
        if c.get('cyberware'):
            console.print(f'  [bold white]Cyberware:[/bold white] {", ".join(c["cyberware"])}')

    elif system_id == 'daggerheart':
        console.print()
        console.rule('[bold magenta]DAGGERHEART STATS[/bold magenta]', style='magenta')
        dh = []
        for key, label in [('evasion','Evasion'), ('stress_slots','Stress Slots'),
                            ('primary_trait','Primary'), ('secondary_trait','Secondary')]:
            if c.get(key):
                dh.append(f'{label}: [white]{c[key]}[/white]')
        if dh:
            console.print('  ' + '   ·   '.join(dh))
        if c.get('domain_cards'):
            console.print(
                f'  [bold white]Domain Cards:[/bold white] {", ".join(c["domain_cards"])}'
            )

    # ── CHARACTER DETAILS ─────────────────────────────────────────────────────
    detail_parts = []
    for key, label in [
        ('appearance',  'Appearance'),
        ('personality', 'Personality'),
        ('backstory',   'Backstory'),
        ('notes',       'Notes'),
    ]:
        val = c.get(key)
        if val:
            detail_parts.append(f'[bold cyan]{label}:[/bold cyan]\n  {str(val)[:350]}')

    if detail_parts:
        console.print()
        console.rule('[bold white]CHARACTER DETAILS[/bold white]', style='white')
        console.print(Panel('\n\n'.join(detail_parts),
                            border_style='dim', padding=(0, 2)))

    # ── FOOTER ────────────────────────────────────────────────────────────────
    console.print()
    console.rule(style='dim')
    console.print(
        '[dim]  savechar — update HP/inventory/notes  ·  '
        'sheet — view again  ·  map — world map[/dim]'
    )
    console.print()

