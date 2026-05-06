# character_manager.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Manages a roster of multiple player characters per game system.
#
# REPLACES the single player_character.json pattern with a per-system
# character roster stored under:
#
#   data/<system_id>/characters/
#     active/
#       Aria_Stonewood.json
#       Grom_Ironfist.json
#     archived/
#       OldChar_retired_2024-03-01.json
#
# ENTRY POINTS (called from main.py):
#   manager = CharacterManager(system_id)
#   manager.pick_or_create(console, system)  → character dict
#   manager.save(character)
#   manager.archive(character_id)
#   manager.delete(character_id)
#   manager.list_active()                    → list[dict]  (summary rows)
#   manager.list_archived()                  → list[dict]
#
# BACKWARD COMPATIBILITY:
#   On first run, if the old player_character.json exists in the system folder,
#   it is automatically migrated into the new roster as an active character.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    """Converts a display name to a safe filename slug (no spaces/special chars)."""
    name = re.sub(r"[^\w\s\-]", "", name or "unknown")
    name = re.sub(r"\s+", "_", name.strip())
    return name[:48] or "character"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ── CharacterManager ──────────────────────────────────────────────────────────

class CharacterManager:
    """
    Manages the full character roster for one game system.

    Directory layout (relative to the system's data folder):
      characters/
        active/      — playable characters
        archived/    — retired / archived characters
    """

    def __init__(self, system_data_dir: str):
        """
        Parameters:
          system_data_dir — Absolute path to the system's data folder
                            (e.g. /project/data/dnd_5e).
                            This is the same folder that previously held
                            player_character.json.
        """
        self.system_dir = system_data_dir
        self.active_dir   = os.path.join(system_data_dir, "characters", "active")
        self.archive_dir  = os.path.join(system_data_dir, "characters", "archived")

        os.makedirs(self.active_dir,  exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

        # Migrate the old single-file character if it exists
        self._migrate_legacy()

    # ── Migration ─────────────────────────────────────────────────────────────

    def _migrate_legacy(self):
        """
        If the old player_character.json exists in the system folder,
        imports it into the active roster automatically (one-time migration).
        A migration marker is written so this never runs twice.
        """
        old_file   = os.path.join(self.system_dir, "player_character.json")
        marker     = os.path.join(self.system_dir, ".character_migrated")

        if os.path.exists(marker) or not os.path.exists(old_file):
            return

        try:
            with open(old_file, "r", encoding="utf-8") as f:
                char = json.load(f)

            # Ensure the character has an id
            if not char.get("id"):
                char["id"] = _slug(char.get("name", "legacy_character"))

            char.setdefault("_created",  _utcnow())
            char.setdefault("_modified", _utcnow())

            dest = self._char_path(char["id"], archived=False)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(char, f, indent=2, ensure_ascii=False)

            # Write the migration marker
            with open(marker, "w") as f:
                f.write(_utcnow())

            print(f"[CharacterManager] Migrated legacy character → {dest}")

        except Exception as e:
            print(f"[CharacterManager] Migration warning: {e}")

    # ── Internal path helpers ──────────────────────────────────────────────────

    def _char_path(self, char_id: str, archived: bool = False) -> str:
        folder = self.archive_dir if archived else self.active_dir
        return os.path.join(folder, f"{char_id}.json")

    def _load_file(self, path: str) -> dict | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _all_json(self, folder: str) -> list[str]:
        """Returns sorted list of .json file paths in a folder."""
        if not os.path.exists(folder):
            return []
        return sorted(
            os.path.join(folder, fn)
            for fn in os.listdir(folder)
            if fn.endswith(".json")
        )

    # ── Public read methods ────────────────────────────────────────────────────

    def list_active(self) -> list[dict]:
        """
        Returns summary dicts for every active character.
        Each dict has: id, name, race, class/occupation, level, _modified.
        Sorted by most recently modified first.
        """
        chars = []
        for path in self._all_json(self.active_dir):
            c = self._load_file(path)
            if c:
                chars.append(self._summary(c))
        chars.sort(key=lambda x: x.get("_modified", ""), reverse=True)
        return chars

    def list_archived(self) -> list[dict]:
        """Returns summary dicts for every archived character."""
        chars = []
        for path in self._all_json(self.archive_dir):
            c = self._load_file(path)
            if c:
                chars.append(self._summary(c))
        chars.sort(key=lambda x: x.get("_modified", ""), reverse=True)
        return chars

    def load(self, char_id: str, archived: bool = False) -> dict | None:
        """Loads a full character dict by ID. Returns None if not found."""
        return self._load_file(self._char_path(char_id, archived))

    @staticmethod
    def _summary(c: dict) -> dict:
        return {
            "id":       c.get("id", "unknown"),
            "name":     c.get("name", "Unknown"),
            "race":     c.get("race", ""),
            "class":    c.get("class", c.get("occupation", c.get("role", ""))),
            "level":    c.get("level", 1),
            "_modified": c.get("_modified", ""),
            "_created":  c.get("_created", ""),
            "_archived_reason": c.get("_archived_reason", ""),
        }

    # ── Public write methods ───────────────────────────────────────────────────

    def save(self, character: dict):
        """
        Saves (or overwrites) an active character to disk.
        Stamps _modified. Ensures 'id' exists.
        """
        if not character.get("id"):
            character["id"] = _slug(character.get("name", "character"))
        character.setdefault("_created", _utcnow())
        character["_modified"] = _utcnow()

        path = self._char_path(character["id"], archived=False)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(character, f, indent=2, ensure_ascii=False)

    def archive(self, char_id: str, reason: str = "Retired") -> bool:
        """
        Moves a character from active/ to archived/.
        Stamps an archive reason and date.
        Returns True on success, False if the character wasn't found.
        """
        src = self._char_path(char_id, archived=False)
        if not os.path.exists(src):
            return False

        char = self._load_file(src)
        if not char:
            return False

        char["_archived_reason"] = reason
        char["_archived_date"]   = _utcnow()
        char["_modified"]        = _utcnow()

        dest = self._char_path(char_id, archived=True)
        # Avoid collisions if an archived version already exists
        if os.path.exists(dest):
            dest = dest.replace(".json", f"_{_date_str()}.json")

        with open(dest, "w", encoding="utf-8") as f:
            json.dump(char, f, indent=2, ensure_ascii=False)

        os.remove(src)
        return True

    def restore(self, char_id: str) -> bool:
        """
        Moves a character from archived/ back to active/.
        Returns True on success.
        """
        # Find the archived file (may have a date suffix)
        candidates = [
            p for p in self._all_json(self.archive_dir)
            if os.path.basename(p).startswith(char_id)
        ]
        if not candidates:
            return False

        src = candidates[0]
        char = self._load_file(src)
        if not char:
            return False

        char.pop("_archived_reason", None)
        char.pop("_archived_date", None)
        char["_modified"] = _utcnow()

        dest = self._char_path(char["id"], archived=False)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(char, f, indent=2, ensure_ascii=False)

        os.remove(src)
        return True

    def delete(self, char_id: str, archived: bool = False) -> bool:
        """
        Permanently deletes a character (active or archived).
        Returns True on success.
        """
        candidates = []
        folder = self.archive_dir if archived else self.active_dir
        for p in self._all_json(folder):
            if os.path.basename(p).startswith(char_id):
                candidates.append(p)

        if not candidates:
            return False

        for p in candidates:
            os.remove(p)
        return True

    # ── Interactive roster screen ─────────────────────────────────────────────

    def pick_or_create(self, console: Console, system: dict) -> dict:
        """
        Shows the character roster and lets the player:
          1. Load an existing active character
          2. Create a brand-new character
          3. Archive a character they no longer want
          4. Restore an archived character
          5. Delete a character permanently

        Returns the fully-loaded character dict that will be used for this session.

        Parameters:
          console — rich Console instance
          system  — Active game system dict (from systems.py)
        """
        while True:
            active   = self.list_active()
            archived = self.list_archived()

            _print_roster(console, active, archived, system)

            # Build action list dynamically
            options = []
            if active:
                options.append(("play",    "[bold green]Play[/bold green]   — Load an existing character"))
            options.append(    ("new",     "[bold cyan]New[/bold cyan]    — Create a brand-new character"))
            if active:
                options.append(("archive", "[bold yellow]Archive[/bold yellow] — Retire a character (keeps data)"))
            if archived:
                options.append(("restore", "[bold blue]Restore[/bold blue] — Bring an archived character back"))
            if active or archived:
                options.append(("delete",  "[bold red]Delete[/bold red]  — Permanently delete a character"))

            console.print()
            for i, (key, label) in enumerate(options, 1):
                console.print(f"  [dim]{i}.[/dim] {label}")
            console.print()

            raw = console.input("[bold white]  Choose an action (number): [/bold white]").strip()
            if not raw.isdigit() or not (1 <= int(raw) <= len(options)):
                console.print("  [red]Please enter a valid number.[/red]")
                continue

            action = options[int(raw) - 1][0]

            # ── Play ──────────────────────────────────────────────────────────
            if action == "play":
                char = _pick_from_list(console, active, "Load character")
                if char:
                    full = self.load(char["id"])
                    if full:
                        console.print(f"\n[green]Loading [bold]{full['name']}[/bold]...[/green]\n")
                        return full

            # ── New ───────────────────────────────────────────────────────────
            elif action == "new":
                from main import create_character_interactively
                new_char = create_character_interactively(system)
                self.save(new_char)
                console.print(f"\n[green]Character [bold]{new_char['name']}[/bold] saved![/green]\n")
                return new_char

            # ── Archive ───────────────────────────────────────────────────────
            elif action == "archive":
                char = _pick_from_list(console, active, "Archive character")
                if char:
                    reason = console.input(
                        "[bold white]  Reason (optional, e.g. 'Retired after campaign'): [/bold white]"
                    ).strip() or "Retired"
                    confirm = console.input(
                        f"  [yellow]Archive [bold]{char['name']}[/bold]? (y/n): [/yellow]"
                    ).strip().lower()
                    if confirm == "y":
                        self.archive(char["id"], reason)
                        console.print(f"  [green]✓ {char['name']} archived.[/green]")

            # ── Restore ───────────────────────────────────────────────────────
            elif action == "restore":
                char = _pick_from_list(console, archived, "Restore character", archived=True)
                if char:
                    self.restore(char["id"])
                    console.print(f"  [green]✓ {char['name']} restored to active roster.[/green]")

            # ── Delete ────────────────────────────────────────────────────────
            elif action == "delete":
                pool = active + [dict(s, _archived=True) for s in archived]
                char = _pick_from_list(console, pool, "Delete character (permanent)")
                if char:
                    confirm = console.input(
                        f"  [bold red]Permanently delete [bold]{char['name']}[/bold]?"
                        f" This CANNOT be undone. (type DELETE to confirm): [/bold red]"
                    ).strip()
                    if confirm == "DELETE":
                        is_archived = char.get("_archived", False)
                        self.delete(char["id"], archived=is_archived)
                        console.print(f"  [red]✓ {char['name']} permanently deleted.[/red]")
                    else:
                        console.print("  [dim]Deletion cancelled.[/dim]")


# ── UI helpers ────────────────────────────────────────────────────────────────

def _print_roster(console: Console, active: list, archived: list, system: dict):
    """Renders the full roster panel."""
    console.print()
    console.print(Panel(
        f"[bold cyan]🧙  {system.get('short_name', 'RPG')} — Character Roster[/bold cyan]\n\n"
        "[white]Your characters for this game system.[/white]\n"
        "[dim]Active characters can be played. Archived characters are stored safely.[/dim]",
        border_style="cyan",
    ))

    if not active and not archived:
        console.print("  [dim]No characters yet — create your first one![/dim]")
        return

    if active:
        console.print("\n[bold white]── Active Characters ─────────────────────────────────────[/bold white]")
        tbl = _make_roster_table()
        for c in active:
            race_class = " ".join(filter(None, [c.get("race"), c.get("class")]))
            lvl = str(c.get("level", 1))
            modified = c.get("_modified", "")[:10]
            tbl.add_row(c["id"], c["name"], race_class, lvl, modified, "")
        console.print(tbl)

    if archived:
        console.print("\n[bold white]── Archived Characters ───────────────────────────────────[/bold white]")
        tbl = _make_roster_table(show_reason=True)
        for c in archived:
            race_class = " ".join(filter(None, [c.get("race"), c.get("class")]))
            lvl = str(c.get("level", 1))
            modified = c.get("_modified", "")[:10]
            reason = c.get("_archived_reason", "")[:30]
            tbl.add_row(c["id"], c["name"], race_class, lvl, modified, reason)
        console.print(tbl)


def _make_roster_table(show_reason: bool = False) -> Table:
    tbl = Table(show_header=True, header_style="bold cyan",
                border_style="dim", padding=(0, 1))
    tbl.add_column("ID",       style="dim",        min_width=18)
    tbl.add_column("Name",     style="bold white",  min_width=18)
    tbl.add_column("Race / Class", style="white",   min_width=22)
    tbl.add_column("Lvl",      style="cyan",        width=4,  justify="right")
    tbl.add_column("Modified", style="dim",         width=12)
    tbl.add_column("Reason" if show_reason else "", style="dim yellow", min_width=18)
    return tbl


def _pick_from_list(
    console: Console,
    chars: list[dict],
    prompt: str,
    archived: bool = False,
) -> dict | None:
    """
    Presents a numbered list of characters and returns the chosen one.
    Returns None if the player cancels.
    """
    if not chars:
        console.print("  [dim]No characters available.[/dim]")
        return None

    console.print(f"\n[bold cyan]{prompt}[/bold cyan]")
    for i, c in enumerate(chars, 1):
        race_class = " ".join(filter(None, [c.get("race"), c.get("class")]))
        lvl_str    = f"Level {c.get('level', 1)}"
        console.print(f"  [dim]{i:2}.[/dim] [bold white]{c['name']}[/bold white]"
                      f"  [dim]{race_class} · {lvl_str}[/dim]")

    console.print("  [dim]0. Cancel[/dim]")
    console.print()

    while True:
        raw = console.input("[bold white]  → [/bold white]").strip()
        if raw == "0" or not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(chars):
            return chars[int(raw) - 1]
        console.print(f"  [red]Please enter 0–{len(chars)}.[/red]")
