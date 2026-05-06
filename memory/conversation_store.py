# memory/conversation_store.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Saves every conversation turn (player and DM messages) to disk as
#          a JSON file. Loads past sessions on startup so context is never
#          lost between program restarts.
#
# HOW IT WORKS:
#   - Each play session gets its own JSON file named by timestamp.
#   - Messages are saved to disk after EVERY turn (no data loss on crash).
#   - The DM agent retrieves the last N messages to include in each prompt.
#   - Old sessions can be resumed by passing their session_id.
#
# LOCATION: dnd_ai_dm/memory/conversation_store.py
# ─────────────────────────────────────────────────────────────────────────────

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from datetime import datetime


class ConversationStore:
    """
    Manages persistent conversation history for a DnD session.
    Each session is stored as a JSON file in the conversation's directory.
    """

    def __init__(self, session_id: str = None):
        """
        Initializes the conversation store.

        Parameters:
          session_id — A string identifier for this session.
                       If not provided, one is auto-generated from the current
                       date and time (e.g., "20240315_143022").
                       Pass an existing session_id to resume a previous session.
        """
        # Generate a human-readable session ID if none is provided.
        # Format: CharacterName_CampaignName_YYYY-MM-DD
        # Falls back to just the date if config values are not available.
        if session_id:
            self.session_id = session_id
        else:
            import re
            date_str = datetime.now().strftime('%Y-%m-%d')
            def _slug(s):
                s = re.sub(r'[^\w\s\-]', '', s or '')
                s = re.sub(r'\s+', '_', s.strip())
                return s[:24]
            try:
                char_name     = _slug(getattr(config, 'ACTIVE_CHARACTER_NAME', '') or '')
                campaign_name = _slug(getattr(config, 'CAMPAIGN_NAME', '') or '')
                parts = [p for p in [char_name, campaign_name, date_str] if p]
                self.session_id = '_'.join(parts)
            except Exception:
                self.session_id = date_str

        # Build the full file path for this session's JSON file
        self.session_file = os.path.join(
            config.CONVERSATION_DIR,
            f'session_{self.session_id}.json'
        )

        # Load existing messages from disk (empty list if new session)
        # messages is a list of dicts: [{'role': 'user'/'assistant', 'content': '...', 'timestamp': '...'}]
        self.messages: list[dict] = self._load()

    def _load(self) -> list[dict]:
        """
        Loads the message list from the session JSON file.
        Returns an empty list if the file doesn't exist yet (new session).
        """
        if os.path.exists(self.session_file):
            with open(self.session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save(self):
        """
        Writes the full message list to the session JSON file on disk.
        Called automatically after every add() to prevent data loss.
        """
        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(self.messages, f, indent=2, ensure_ascii=False)

    def add(self, role: str, content: str):
        """
        Appends a new message to the conversation history and saves to disk.

        Parameters:
          role    — Either 'user' (player) or 'assistant' (DM)
          content — The full text of the message

        A real UTC timestamp is also stored alongside each message
        for chronological record-keeping, though it is not passed to the AI.
        """
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        })
        # Save to disk immediately after every message
        self._save()

    def get_recent(self, n: int = None) -> list[dict]:
        """
        Returns the last n messages formatted for the Ollama API.
        Ollama expects messages as a list of {'role': ..., 'content': ...} dicts.
        We strip the 'timestamp' field since the API doesn't need it.

        n defaults to config.RECENT_HISTORY_TURNS if not specified.
        """
        limit = n or config.RECENT_HISTORY_TURNS
        recent = self.messages[-limit:]
        return [{'role': m['role'], 'content': m['content']} for m in recent]

    def get_full_history(self) -> list[dict]:
        """Returns every message in the session, formatted for the API."""
        return [{'role': m['role'], 'content': m['content']} for m in self.messages]

    def list_sessions(self) -> list[str]:
        """
        Scans the conversations directory and returns a sorted list of
        all existing session IDs (oldest to newest).
        """
        if not os.path.exists(config.CONVERSATION_DIR):
            return []
        files = os.listdir(config.CONVERSATION_DIR)
        session_ids = [
            f.replace('session_', '').replace('.json', '')
            for f in sorted(files)
            if f.startswith('session_') and f.endswith('.json')
        ]
        return session_ids

    def load_session(self, session_id: str):
        """
        Switches to a different session by ID (e.g., to resume a past campaign).
        Updates the session file path and reloads messages from disk.

        Parameters:
          session_id — The ID string of the session to load.
                       Use list_sessions() to see available IDs.
        """
        self.session_id = session_id
        self.session_file = os.path.join(
            config.CONVERSATION_DIR,
            f'session_{session_id}.json'
        )
        self.messages = self._load()

    def clear_session(self):
        """
        Removes all messages from the current session (in memory and on disk).
        Use with caution — this is permanent.
        """
        self.messages = []
        self._save()

    def get_session_summary(self) -> dict:
        """
        Returns basic metadata about the current session.
        Useful for displaying session info to the player.
        """
        return {
            'session_id': self.session_id,
            'total_turns': len(self.messages),
            'player_turns': sum(1 for m in self.messages if m['role'] == 'user'),
            'dm_turns': sum(1 for m in self.messages if m['role'] == 'assistant'),
            'started': self.messages[0]['timestamp'] if self.messages else None,
            'last_active': self.messages[-1]['timestamp'] if self.messages else None,
        }
