# homebrew_commands.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: In-game terminal command handlers for homebrew content generation.
#
# These functions are called from main.py's game loop when the player types:
#   homebrew race       → Generate + optionally save a homebrew race
#   homebrew class      → Generate + optionally save a homebrew class
#   homebrew subclass   → Generate a subclass for an existing class
#   homebrew npc        → Generate a session NPC
#   homebrew session    → Generate a full suite of NPCs for a location
#   homebrew list       → Show all saved homebrew content
#   homebrew inject     → Add a saved homebrew race/class to character creation menus
#
# USAGE IN main.py:
#   from homebrew_commands import handle_homebrew_command
#   ...
#   if player_input.lower().startswith('homebrew'):
#       handle_homebrew_command(player_input, console, system_id)
#       continue
#
# LOCATION: dnd_ai_dm/homebrew_commands.py
# ─────────────────────────────────────────────────────────────────────────────

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def handle_homebrew_command(raw_input: str, console: Console, system_id: str = 'dnd_5e'):
    """
    Main dispatcher for all 'homebrew' commands.

    Parameters:
      raw_input — The full player input string (e.g. "homebrew race")
      console   — Rich Console instance for styled output
      system_id — Currently active game system ID
    """
    parts = raw_input.strip().lower().split()
    # parts[0] = 'homebrew', parts[1] = subcommand (if given)
    subcommand = parts[1] if len(parts) > 1 else 'help'

    if subcommand in ('race', 'ancestry', 'heritage'):
        _cmd_homebrew_race(console, system_id)
    elif subcommand in ('class', 'cls'):
        _cmd_homebrew_class(console, system_id)
    elif subcommand in ('subclass', 'archetype', 'specialization'):
        _cmd_homebrew_subclass(console, system_id)
    elif subcommand == 'npc':
        _cmd_homebrew_npc(console, system_id)
    elif subcommand in ('session', 'batch'):
        _cmd_homebrew_session(console, system_id)
    elif subcommand == 'list':
        _cmd_homebrew_list(console)
    elif subcommand in ('inject', 'add'):
        _cmd_homebrew_inject(console, system_id)
    else:
        _cmd_homebrew_help(console, system_id)


# ─────────────────────────────────────────────────────────────────────────────
# RACE / HERITAGE COMMAND
# ─────────────────────────────────────────────────────────────────────────────

def _cmd_homebrew_race(console: Console, system_id: str):
    """Generate a homebrew race/heritage via AI."""
    import homebrew_generator as hbg

    console.print()
    console.print(Panel(
        '[bold cyan]🧬 Homebrew Race / Heritage Generator[/bold cyan]\n'
        '[dim]Describe the race concept and the AI will design it with balanced mechanics.[/dim]',
        border_style='cyan'
    ))

    concept = console.input(
        '[bold white]Describe your race concept[/bold white] '
        '[dim](e.g. "A race of living coral beings from the ocean floor"): [/dim]'
    ).strip()

    if not concept:
        console.print('[yellow]Cancelled.[/yellow]')
        return

    console.print('[dim]Generating... this takes 10-30 seconds.[/dim]')
    race = hbg.generate_race(concept, system_id)

    if not race:
        console.print('[red]Generation failed. Make sure Ollama is running.[/red]')
        return

    console.print()
    console.print(Panel(
        hbg.format_race_display(race),
        title=f'[bold green]Generated Race: {race.get("name", "Unknown")}[/bold green]',
        border_style='green'
    ))

    # Offer subrace expansion if subraces were generated
    subraces = race.get('subrace_options', [])
    if subraces:
        console.print(f'[dim]{len(subraces)} subrace(s) included. Subraces appear in the character creation menu.[/dim]')

    choice = console.input(
        '\n[bold white]Save this race to your homebrew library? (y/n/regenerate): [/bold white]'
    ).strip().lower()

    if choice == 'y':
        hbg.save_race(race)
        console.print(f'[green]✓ {race["name"]} saved to homebrew library.[/green]')
        console.print('[dim]This race will now appear in character creation menus.[/dim]')
    elif choice == 'regenerate':
        _cmd_homebrew_race(console, system_id)
    else:
        console.print('[yellow]Race not saved.[/yellow]')


# ─────────────────────────────────────────────────────────────────────────────
# CLASS COMMAND
# ─────────────────────────────────────────────────────────────────────────────

def _cmd_homebrew_class(console: Console, system_id: str):
    """Generate a homebrew class via AI."""
    import homebrew_generator as hbg

    console.print()
    console.print(Panel(
        '[bold cyan]⚔  Homebrew Class Generator[/bold cyan]\n'
        '[dim]Describe a class concept and the AI will design it with features, '
        'proficiencies, and subclasses.[/dim]',
        border_style='cyan'
    ))

    concept = console.input(
        '[bold white]Describe your class concept[/bold white] '
        '[dim](e.g. "A holy chef who channels divinity through elaborate meals"): [/dim]'
    ).strip()

    if not concept:
        console.print('[yellow]Cancelled.[/yellow]')
        return

    console.print('[dim]Generating... this takes 15-45 seconds.[/dim]')
    cls = hbg.generate_class(concept, system_id)

    if not cls:
        console.print('[red]Generation failed. Make sure Ollama is running.[/red]')
        return

    console.print()
    console.print(Panel(
        hbg.format_class_display(cls),
        title=f'[bold green]Generated Class: {cls.get("name", "Unknown")}[/bold green]',
        border_style='green'
    ))

    choice = console.input(
        '\n[bold white]Save this class to your homebrew library? (y/n/regenerate): [/bold white]'
    ).strip().lower()

    if choice == 'y':
        hbg.save_class(cls)
        console.print(f'[green]✓ {cls["name"]} saved to homebrew library.[/green]')
        console.print('[dim]This class will now appear in character creation menus.[/dim]')
    elif choice == 'regenerate':
        _cmd_homebrew_class(console, system_id)
    else:
        console.print('[yellow]Class not saved.[/yellow]')


# ─────────────────────────────────────────────────────────────────────────────
# SUBCLASS COMMAND
# ─────────────────────────────────────────────────────────────────────────────

def _cmd_homebrew_subclass(console: Console, system_id: str):
    """Generate a homebrew subclass for an existing class."""
    import homebrew_generator as hbg

    console.print()
    console.print(Panel(
        '[bold cyan]🌟 Homebrew Subclass Generator[/bold cyan]\n'
        '[dim]Design a new subclass/archetype for any existing or homebrew class.[/dim]',
        border_style='cyan'
    ))

    base_class = console.input(
        '[bold white]Base class name[/bold white] '
        '[dim](e.g. Fighter, Wizard, or a homebrew class name): [/dim]'
    ).strip()

    if not base_class:
        console.print('[yellow]Cancelled.[/yellow]')
        return

    concept = console.input(
        '[bold white]Describe the subclass concept[/bold white] '
        '[dim](e.g. "A fighter who draws power from lightning storms"): [/dim]'
    ).strip()

    if not concept:
        console.print('[yellow]Cancelled.[/yellow]')
        return

    console.print('[dim]Generating subclass...[/dim]')
    sc = hbg.generate_subclass(base_class, concept, system_id)

    if not sc:
        console.print('[red]Generation failed.[/red]')
        return

    # Display
    lines = [
        f"[bold cyan]{sc.get('name', 'Unknown')}[/bold cyan] [dim](for {base_class}, level {sc.get('level_unlocked', 3)})[/dim]",
        f"[white]{sc.get('description', '')}[/white]",
        '',
        '[bold]Features:[/bold]',
    ]
    for f in sc.get('features', []):
        lines.append(f'  • {f}')

    console.print()
    console.print(Panel(
        '\n'.join(lines),
        title=f'[bold green]Generated Subclass[/bold green]',
        border_style='green'
    ))

    choice = console.input(
        '\n[bold white]Save this subclass? (y/n): [/bold white]'
    ).strip().lower()

    if choice == 'y':
        hbg.save_subclass(sc)
        console.print(f'[green]✓ Subclass "{sc["name"]}" saved.[/green]')


# ─────────────────────────────────────────────────────────────────────────────
# NPC COMMAND
# ─────────────────────────────────────────────────────────────────────────────

def _cmd_homebrew_npc(console: Console, system_id: str):
    """Generate a session-ready NPC."""
    import homebrew_generator as hbg

    console.print()
    console.print(Panel(
        '[bold cyan]👤 NPC Generator[/bold cyan]\n'
        '[dim]Generate a fully detailed NPC with personality, secrets, voice notes, and story hooks.[/dim]',
        border_style='cyan'
    ))

    role = console.input(
        '[bold white]NPC role / description[/bold white] '
        '[dim](e.g. "city guard captain", "shady tavern informant" — or press Enter for random): [/dim]'
    ).strip()

    location = console.input(
        '[bold white]Location where they are found[/bold white] '
        '[dim](e.g. "Ironhaven city docks" — or press Enter to skip): [/dim]'
    ).strip()

    attitude = console.input(
        '[bold white]Initial attitude toward strangers[/bold white] '
        '[dim](friendly / neutral / suspicious / hostile — or press Enter for random): [/dim]'
    ).strip()

    combat_role = console.input(
        '[bold white]Combat role[/bold white] '
        '[dim](non-combatant / minion / elite / boss — or press Enter for auto): [/dim]'
    ).strip()

    extra = console.input(
        '[bold white]Any extra requirements?[/bold white] [dim](or press Enter to skip): [/dim]'
    ).strip()

    console.print('[dim]Generating NPC... this takes 10-20 seconds.[/dim]')
    npc = hbg.generate_npc(
        role=role, location=location, attitude=attitude,
        combat_role=combat_role, system_id=system_id, extra_notes=extra
    )

    if not npc:
        console.print('[red]Generation failed.[/red]')
        return

    console.print()
    console.print(Panel(
        hbg.format_npc_display(npc),
        title=f'[bold green]Generated NPC: {npc.get("name", "Unknown")}[/bold green]',
        border_style='green'
    ))

    choice = console.input(
        '\n[bold white]Save NPC to library? (y/n/regenerate): [/bold white]'
    ).strip().lower()

    if choice == 'y':
        hbg.save_npc(npc)
        console.print(f'[green]✓ {npc["name"]} saved to NPC library.[/green]')
    elif choice == 'regenerate':
        _cmd_homebrew_npc(console, system_id)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION BATCH COMMAND
# ─────────────────────────────────────────────────────────────────────────────

def _cmd_homebrew_session(console: Console, system_id: str):
    """Generate a full suite of NPCs for a session location."""
    import homebrew_generator as hbg

    console.print()
    console.print(Panel(
        '[bold cyan]🌍 Session Content Generator[/bold cyan]\n'
        '[dim]Generate multiple NPCs tailored to a specific setting or location.[/dim]',
        border_style='cyan'
    ))

    setting = console.input(
        '[bold white]Describe the setting or location for this session[/bold white]\n'
        '[dim](e.g. "a corrupt port city tavern district run by thieves guilds"): [/dim]'
    ).strip()

    if not setting:
        console.print('[yellow]Cancelled.[/yellow]')
        return

    num_raw = console.input('[bold white]How many NPCs to generate?[/bold white] [dim][3]: [/dim]').strip()
    num_npcs = int(num_raw) if num_raw.isdigit() and 1 <= int(num_raw) <= 10 else 3

    console.print(f'[dim]Generating {num_npcs} NPCs for "{setting}"...[/dim]')

    result = hbg.generate_session_content(
        setting=setting,
        num_npcs=num_npcs,
        system_id=system_id
    )

    npcs = result.get('npcs', [])
    if not npcs:
        console.print('[red]Generation failed.[/red]')
        return

    console.print(f'\n[bold green]Generated {len(npcs)} NPCs:[/bold green]\n')
    for i, npc in enumerate(npcs, 1):
        console.print(Panel(
            hbg.format_npc_display(npc),
            title=f'[bold white]NPC {i}: {npc.get("name", "Unknown")}[/bold white]',
            border_style='dim'
        ))

    save_all = console.input(
        '\n[bold white]Save all NPCs to library? (y/n): [/bold white]'
    ).strip().lower()

    if save_all == 'y':
        for npc in npcs:
            hbg.save_npc(npc)
        console.print(f'[green]✓ {len(npcs)} NPCs saved to library.[/green]')


# ─────────────────────────────────────────────────────────────────────────────
# LIST COMMAND
# ─────────────────────────────────────────────────────────────────────────────

def _cmd_homebrew_list(console: Console):
    """Display all saved homebrew content."""
    import homebrew_generator as hbg

    summary = hbg.list_homebrew()

    tbl = Table(title='📚 Saved Homebrew Content', border_style='cyan',
                header_style='bold cyan', show_lines=True)
    tbl.add_column('Type',    style='bold white', min_width=14)
    tbl.add_column('Count',   style='cyan',       justify='center', width=7)
    tbl.add_column('Names',   style='white',       min_width=40)

    def names_str(names: list) -> str:
        if not names:
            return '[dim]None[/dim]'
        shown = names[:6]
        extra = len(names) - 6
        s = ', '.join(shown)
        return (s + f' [dim]+{extra} more[/dim]') if extra > 0 else s

    tbl.add_row('Races / Heritages', str(len(summary['races'])),     names_str(summary['races']))
    tbl.add_row('Classes',           str(len(summary['classes'])),   names_str(summary['classes']))
    tbl.add_row('Subclasses',        str(len(summary['subclasses'])),names_str(summary['subclasses']))
    tbl.add_row('NPCs',              str(len(summary['npcs'])),      names_str(summary['npcs']))

    console.print()
    console.print(tbl)

    if summary['total'] == 0:
        console.print('[dim]No homebrew content saved yet. '
                      'Type "homebrew race", "homebrew class", or "homebrew npc" to generate some.[/dim]')
    else:
        console.print(
            f'\n[dim]Total: {summary["total"]} items saved in data/homebrew/\n'
            f'Type "homebrew inject" to add homebrew races/classes to the character creation menu.[/dim]'
        )


# ─────────────────────────────────────────────────────────────────────────────
# INJECT COMMAND — add homebrew content into live character creation menus
# ─────────────────────────────────────────────────────────────────────────────

def _cmd_homebrew_inject(console: Console, system_id: str):
    """
    Adds saved homebrew races and classes to the character creation menus.
    This modifies the in-memory RACES and CLASSES lists in main.py for this session.
    """
    import homebrew_generator as hbg
    import main as _main  # import the running main module to patch its globals

    hb_races   = hbg.get_homebrew_race_names()
    hb_classes = hbg.get_homebrew_class_names()

    added_races   = []
    added_classes = []

    for name in hb_races:
        label = f'{name} [Homebrew]'
        if label not in _main.RACES:
            # Insert before 'Other (type your own)'
            insert_at = len(_main.RACES) - 1 if _main.RACES[-1].startswith('Other') else len(_main.RACES)
            _main.RACES.insert(insert_at, label)
            added_races.append(name)

    for name in hb_classes:
        label = f'{name} [Homebrew]'
        if label not in _main.CLASSES:
            insert_at = len(_main.CLASSES) - 1 if _main.CLASSES[-1].startswith('Other') else len(_main.CLASSES)
            _main.CLASSES.insert(insert_at, label)
            added_classes.append(name)

    if not added_races and not added_classes:
        console.print('[yellow]No new homebrew content to inject. '
                      'Save some content first with "homebrew race" or "homebrew class".[/yellow]')
        return

    if added_races:
        console.print(f'[green]✓ Added to race menu:[/green] {", ".join(added_races)}')
    if added_classes:
        console.print(f'[green]✓ Added to class menu:[/green] {", ".join(added_classes)}')

    console.print('[dim]These options will now appear in the character creation menus for this session.[/dim]')


# ─────────────────────────────────────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────────────────────────────────────

def _cmd_homebrew_help(console: Console, system_id: str):
    """Display homebrew command help."""
    console.print()
    console.print(Panel(
        '[bold cyan]🔮 Homebrew Generator Commands[/bold cyan]\n\n'
        '  [bold]homebrew race[/bold]        → AI generates a balanced homebrew race/heritage\n'
        '  [bold]homebrew class[/bold]       → AI generates a homebrew class with features & subclasses\n'
        '  [bold]homebrew subclass[/bold]    → AI generates a homebrew subclass for any class\n'
        '  [bold]homebrew npc[/bold]         → AI generates a detailed NPC (appearance, personality, secrets)\n'
        '  [bold]homebrew session[/bold]     → AI generates multiple NPCs tailored to your current location\n'
        '  [bold]homebrew list[/bold]        → Show all saved homebrew content\n'
        '  [bold]homebrew inject[/bold]      → Add saved races/classes to character creation menus\n\n'
        '[dim]All generated content can be saved to data/homebrew/ for future sessions.\n'
        'Homebrew races and classes integrate fully with the auto-apply system.[/dim]',
        border_style='cyan'
    ))
