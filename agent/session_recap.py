# agent/session_recap.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Generates an AI-powered "Previously on…" recap when a player
#          resumes an existing campaign session.
#
# HOW IT WORKS:
#   1. Pulls the last N conversation turns from ConversationStore.
#   2. Pulls the most recent plot events from WorldState.
#   3. Pulls the player's current relationship summary from RelationshipGraph.
#   4. Sends all of that to Ollama with a focused prompt asking for a
#      concise, immersive story recap — written in the DM's voice.
#   5. Displays the recap in a styled Rich panel before the game loop starts.
#
# RECAP MODES:
#   'brief'   — 3-5 sentences. Fast, minimal. Good for short breaks.
#   'full'    — Full paragraph(s). Covers major events, NPCs, goals.
#   'bullet'  — Bullet-point list of key facts. Great for long gaps between sessions.
#
# WHERE TO CALL IT (main.py):
#   In run_session(), after the DM agent is initialized and ONLY when
#   is_new_session is False (i.e. a resumed session). Example:
#
#       if not is_new_session:
#           from agent.session_recap import show_session_recap
#           show_session_recap(dm, console)
#
# LOCATION: dnd_ai_dm/agent/session_recap.py
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ollama
import config

# Rich is already a dependency in the project (used in main.py).
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule


# ── Recap mode settings ────────────────────────────────────────────────────

RECAP_MODES = {
    'brief': {
        'label':       'Brief Recap',
        'turns':       20,       # Conversation turns to include
        'events':      4,        # Plot events to include
        'max_tokens':  300,
        'instruction': (
            'Write a brief 3-5 sentence recap of recent events. '
            'Capture the most important moment and the current situation. '
            'Write in second person ("You found yourself…"), DM narrative voice. '
            'Do not use bullet points. Be immersive and concise.'
        ),
    },
    'full': {
        'label':       'Full Recap',
        'turns':       60,
        'events':      8,
        'max_tokens':  600,
        'instruction': (
            'Write a full "Previously on…" style recap of recent events. '
            'Cover major story beats, important NPCs encountered, goals pursued, '
            'and any unresolved threads. Write in second person ("You…"), '
            'DM narrative voice. 2-4 paragraphs. Immersive and specific.'
        ),
    },
    'bullet': {
        'label':       'Key Facts Recap',
        'turns':       80,
        'events':      10,
        'max_tokens':  500,
        'instruction': (
            'Produce a bullet-point "Session Notes" list covering:\n'
            '- Where the player is\n'
            '- Last major action taken\n'
            '- Important NPCs met or interacted with\n'
            '- Active quests or goals\n'
            '- Any unresolved threats or mysteries\n'
            '- Current relationships (brief)\n'
            'Be specific and factual. No prose paragraphs. '
            'Use dashes for bullets. Keep each bullet under 20 words.'
        ),
    },
}

DEFAULT_MODE = 'full'


def _gather_recap_context(dm, mode_config: dict) -> str:
    """
    Assembles the raw context data that will be fed into the recap prompt.
    Pulls from conversation history, plot events, and relationships.

    Parameters:
      dm          — The active DMAgent instance
      mode_config — The settings dict for the chosen recap mode

    Returns a formatted multi-section string.
    """
    sections = []

    # ── 1. Player character summary ────────────────────────────────────────
    pc = dm.player_character
    pc_name    = pc.get('name', 'The Player')
    pc_race    = pc.get('race', '')
    pc_class   = pc.get('class', pc.get('role', ''))
    pc_level   = pc.get('level', '')
    pc_location = pc.get('starting_location_id', 'Unknown')
    current_location = dm.current_location_id or pc_location

    sections.append(
        f"PLAYER CHARACTER:\n"
        f"  Name: {pc_name}\n"
        f"  Race/Class: {pc_race} {pc_class}"
        + (f" (Level {pc_level})" if pc_level else "")
        + f"\n  Current Location ID: {current_location}"
    )

    # ── 2. Current in-game date ────────────────────────────────────────────
    current_date = dm.world.get_current_date_str()
    sections.append(f"CURRENT IN-GAME DATE: {current_date}")

    # ── 3. Recent conversation turns ──────────────────────────────────────
    n_turns = mode_config['turns']
    recent_msgs = dm.conv.get_recent(n=n_turns)

    if recent_msgs:
        turn_lines = []
        for msg in recent_msgs:
            role    = 'PLAYER' if msg['role'] == 'user' else 'DM'
            content = msg['content']
            # Truncate very long DM turns to keep prompt size manageable
            if role == 'DM' and len(content) > 400:
                content = content[:400] + '...'
            turn_lines.append(f"  [{role}]: {content}")

        sections.append(
            f"RECENT CONVERSATION ({len(recent_msgs)} turns shown):\n"
            + '\n'.join(turn_lines)
        )
    else:
        sections.append("RECENT CONVERSATION: (No conversation history found)")

    # ── 4. Plot events ─────────────────────────────────────────────────────
    n_events = mode_config['events']
    events = dm.world.get_recent_plot_events(n=n_events)

    if events:
        event_lines = []
        for ev in events:
            date  = ev.get('in_game_date', '?')
            desc  = ev.get('description', '')[:200]
            etype = ev.get('type', '')
            event_lines.append(f"  [{date}] ({etype}) {desc}")
        sections.append(
            f"RECENT PLOT EVENTS:\n" + '\n'.join(event_lines)
        )
    else:
        sections.append("RECENT PLOT EVENTS: (None recorded yet)")

    # ── 5. Player relationships ────────────────────────────────────────────
    player_id = pc.get('id', 'player_character')
    rel_summary = dm.graph.summarize_for_prompt(player_id)
    sections.append(f"PLAYER RELATIONSHIPS:\n{rel_summary}")

    return '\n\n'.join(sections)


def generate_recap(
    dm,
    mode: str = DEFAULT_MODE,
) -> str:
    """
    Calls Ollama to generate a session recap in the specified style.

    Parameters:
      dm   — The active DMAgent instance (must be fully initialized)
      mode — Recap style: 'brief', 'full', or 'bullet'

    Returns the recap as a plain text string.
    Returns a fallback message if the AI call fails.
    """
    mode_config = RECAP_MODES.get(mode, RECAP_MODES[DEFAULT_MODE])

    # Build the context block from memory systems
    context = _gather_recap_context(dm, mode_config)

    # Get the active system name for the DM persona reference
    active_system = getattr(config, 'ACTIVE_SYSTEM', None)
    system_name   = active_system['name'] if active_system else 'Tabletop RPG'

    # Build the full prompt
    system_prompt = (
        f"You are the Game Master of an ongoing {system_name} campaign. "
        "The player is returning after a break and needs to be reminded of recent events. "
        "Use the context below to write a recap. "
        "Never say 'as the game master' or reveal you are an AI. "
        "Write as though narrating a story the player lived through.\n\n"
        f"{mode_config['instruction']}"
    )

    user_prompt = (
        f"Here is the campaign context:\n\n"
        f"{context}\n\n"
        f"Now write the recap."
    )

    try:
        response = ollama.chat(
            model=config.MODEL_NAME,
            messages=[
                {'role': 'system',  'content': system_prompt},
                {'role': 'user',    'content': user_prompt},
            ],
            options={
                'num_ctx':     min(config.CONTEXT_WINDOW, 6144),
                'temperature': 0.75,    # Slightly creative but grounded in facts
                'num_predict': mode_config['max_tokens'],
                'top_p':       0.9,
            }
        )
        return response['message']['content'].strip()

    except Exception as e:
        # Never crash the session over a recap failure
        return (
            f"[Could not generate AI recap: {e}]\n\n"
            f"You resume your adventure. "
            f"The world clock reads: {dm.world.get_current_date_str()}."
        )


def show_session_recap(
    dm,
    console: Console,
    mode: str = None,
    skip_prompt: bool = False,
) -> None:
    """
    Displays a "Previously on…" recap panel when resuming a session.
    This is the main function to call from main.py.

    Parameters:
      dm           — The active DMAgent instance
      console      — The Rich Console instance from main.py
      mode         — Recap mode: 'brief', 'full', or 'bullet'.
                     If None, asks the player to choose.
      skip_prompt  — If True, uses DEFAULT_MODE without asking.

    How to add to main.py (in run_session, after DM agent init):

        if not is_new_session:
            from agent.session_recap import show_session_recap
            show_session_recap(dm, console)
    """
    # Don't show recap if there's no history
    if not dm.conv.messages:
        return

    console.print()
    console.rule('[bold cyan]📜  Returning to your adventure…[/bold cyan]')
    console.print()

    # ── Ask player which recap style they want ─────────────────────────────
    if mode is None and not skip_prompt:
        session_info = dm.conv.get_session_summary()
        total_turns  = session_info.get('total_turns', 0)

        console.print(
            f"[dim]Session [bold]{dm.conv.session_id}[/bold]  |  "
            f"{total_turns} total messages  |  "
            f"World time: {dm.world.get_current_date_str()}[/dim]\n"
        )
        console.print('[bold cyan]How would you like to catch up?[/bold cyan]')
        console.print('  [green]1[/green] — Brief recap (3-5 sentences, fastest)')
        console.print('  [green]2[/green] — Full recap (story summary, recommended)')
        console.print('  [green]3[/green] — Bullet notes (key facts list)')
        console.print('  [green]4[/green] — Skip recap (jump straight in)')
        console.print()

        while True:
            choice = console.input('[bold white]  Choose [1-4]: [/bold white]').strip()
            if choice == '1':
                mode = 'brief'
                break
            elif choice == '2':
                mode = 'full'
                break
            elif choice == '3':
                mode = 'bullet'
                break
            elif choice == '4':
                console.print('[dim]Skipping recap. The adventure continues…[/dim]\n')
                return
            else:
                console.print('  [red]Please enter 1, 2, 3, or 4.[/red]')
    elif mode is None:
        mode = DEFAULT_MODE

    # ── Generate the recap ─────────────────────────────────────────────────
    mode_config = RECAP_MODES.get(mode, RECAP_MODES[DEFAULT_MODE])
    console.print(f'\n[dim]Generating {mode_config["label"]}…[/dim]')

    recap_text = generate_recap(dm, mode=mode)

    # ── Display in a styled panel ──────────────────────────────────────────
    panel_title = f'[bold yellow]📜  Previously…  ({mode_config["label"]})[/bold yellow]'
    console.print()
    console.print(
        Panel(
            recap_text,
            title=panel_title,
            border_style='yellow',
            padding=(1, 2),
            expand=True,
        )
    )
    console.print()

    # ── Offer a follow-up option ───────────────────────────────────────────
    # Let the player ask for a different style or dive in
    if not skip_prompt:
        console.print('[dim]Press Enter to continue, or type [bold]r[/bold] for a different recap style.[/dim]')
        follow = console.input('[bold white]  → [/bold white]').strip().lower()

        if follow == 'r':
            # Recursive call to re-select a mode
            show_session_recap(dm, console, mode=None, skip_prompt=False)
            return

    console.rule('[dim]Adventure resumed[/dim]')
    console.print()


def generate_recap_on_demand(dm, console: Console) -> None:
    """
    Generates a recap on demand during gameplay.
    Called when the player types 'recap' in the game loop.

    Skips the style-selection prompt and always uses 'full' mode
    since the player is already mid-session and just wants a reminder.

    How to add to main.py game loop:
        elif lower_input == 'recap':
            from agent.session_recap import generate_recap_on_demand
            generate_recap_on_demand(dm, console)
            continue
    """
    console.print('\n[dim]Generating mid-session recap…[/dim]')
    recap_text = generate_recap(dm, mode='full')

    console.print()
    console.print(
        Panel(
            recap_text,
            title='[bold yellow]📜  Story So Far[/bold yellow]',
            border_style='yellow',
            padding=(1, 2),
            expand=True,
        )
    )
    console.print()
