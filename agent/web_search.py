# agent/web_search.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Provides real-time web search capability to the DM agent.
#          Used when the player asks rules questions, lore lookups, or the DM
#          needs current factual information to enrich a scene.
#
# HOW IT WORKS:
#   - Uses the duckduckgo_search library to query DuckDuckGo.
#   - Completely FREE — no API key, no account, no rate limit fees.
#   - Returns a list of search result dicts with title, URL, and snippet.
#   - If the search fails (no internet, rate limit), it silently returns []
#     so the DM can still function fully offline.
#
# LOCATION: dnd_ai_dm/agent/web_search.py
# ─────────────────────────────────────────────────────────────────────────────
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from duckduckgo_search import DDGS


def search_web(query: str, max_results: int = None) -> list[dict]:
    """
    Performs a web search and returns a list of result dictionaries.

    Each result dict contains:
      - 'title' : The page title
      - 'href'  : The page URL
      - 'body'  : A short text snippet from the page

    Parameters:
      query       — The search query string
      max_results — Number of results to fetch. Defaults to config.MAX_SEARCH_RESULTS.

    Returns an empty list if the search fails (offline mode safe).
    """
    # Use config value if max_results not explicitly specified
    n = max_results or config.MAX_SEARCH_RESULTS

    try:
        # DDGS() is a context manager that handles connection cleanup
        with DDGS() as ddgs:
            # ddgs.text() performs a text search and returns a generator
            # list() materializes the generator into a concrete list
            results = list(ddgs.text(query, max_results=n))
        return results

    except Exception as e:
        # Catch ALL exceptions so a failed search never crashes the DM.
        # Common failure causes: no internet, DuckDuckGo rate limiting,
        # or the library version mismatch.
        print(f'[WebSearch] Search failed (offline mode active): {e}')
        return []


def format_search_results(results: list[dict]) -> str:
    """
    Converts the raw list of search result dicts into a compact, readable
    text block that can be injected into the DM's system prompt as context.

    Each result is formatted as:
      [1] Page Title: Text snippet (truncated to 300 characters)

    Parameters:
      results — List of dicts returned by search_web()

    Returns a single formatted string, or a 'No results' message if empty.
    """
    if not results:
        return 'No web search results available.'

    lines = []
    for i, result in enumerate(results, start=1):
        title = result.get('title', 'Untitled')
        # Truncate the body to 300 chars to avoid using too much of the context window
        body = result.get('body', '')[:300]
        lines.append(f"[{i}] {title}: {body}")

    return '\n'.join(lines)


# ── Keyword lists for detecting search-worthy queries ──────────────────────
# The DM agent checks the player's input against these lists to decide
# whether to perform a web lookup before generating a response.

RULES_LOOKUP_SIGNALS = [
    'how does', 'what are the rules', 'rules for', 'can i cast',
    'what spell', 'how many hit points', 'what damage does', 'grapple rules',
    'initiative rules', 'saving throw', 'what does this condition do'
]

LORE_LOOKUP_SIGNALS = [
    'what is', 'tell me about', 'history of', 'lore of', 'mythology',
    'legend of', 'who were the', 'background on', 'origin of'
]

RESEARCH_SIGNALS = [
    'search for', 'look up', 'find information', 'research', 'lookup'
]

ALL_SEARCH_SIGNALS = RULES_LOOKUP_SIGNALS + LORE_LOOKUP_SIGNALS + RESEARCH_SIGNALS


def should_search(player_input: str) -> bool:
    """
    Heuristic check: returns True if the player's input looks like it
    would benefit from a web search (rules question, lore query, etc.)

    Parameters:
      player_input — The raw text typed by the player

    Returns True if any search signal keyword is found in the input.
    """
    lower_input = player_input.lower()
    return any(signal in lower_input for signal in ALL_SEARCH_SIGNALS)
