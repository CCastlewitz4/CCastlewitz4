#!/usr/bin/env python3
# setup_spells.py
# ─────────────────────────────────────────────────────────────────────────────
# ONE-TIME SETUP SCRIPT — Run this before your first game session to populate
# the spell cache that the character creation wizard depends on.
#
# HOW IT WORKS:
#   Calls the Open5e free REST API (api.open5e.com) to download all D&D 5e
#   spells in JSON format and saves them to data/wiki_cache/spells_cache.json.
#   No web scraping, no HTML parsing — just clean JSON from a purpose-built API.
#
# HOW TO RUN:
#   python setup_spells.py
#   python setup_spells.py --force    # re-fetch even if cache already exists
#
# TIME:
#   Usually completes in under 60 seconds (a few paginated API calls vs the
#   old wikidot scraper which needed 500+ individual page requests).
#
# OFFLINE / NO INTERNET:
#   The game falls back to the hardcoded spell list automatically if the cache
#   is missing. Re-run this script when you have internet access.
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
import subprocess


def check_and_install_deps():
    missing = []
    for pkg, import_name in [("requests", "requests")]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[Setup] Installing missing packages: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + missing,
            stdout=subprocess.DEVNULL
        )
        print("[Setup] Done.\n")
    else:
        print("[Setup] Dependencies OK (requests).\n")


def check_already_populated():
    try:
        from spell_scraper import _is_cache_populated
        return _is_cache_populated()
    except ImportError:
        return False


def main():
    force = "--force" in sys.argv

    print("=" * 60)
    print("  D&D 5e Spell Cache Setup  (Open5e API)")
    print("=" * 60)
    print()

    check_and_install_deps()

    if not force and check_already_populated():
        print("[Setup] Spell cache is already populated!")
        print("  Use --force to re-fetch from scratch.")
        print()
        print("  To verify, run:  python spell_scraper.py")
        return

    print("[Setup] Fetching spells from api.open5e.com …")
    print("[Setup] This usually takes under 60 seconds.\n")

    try:
        from spell_scraper import fetch_all_spells
        cache = fetch_all_spells(force=force)

        if cache:
            total = sum(
                sum(len(v) for v in lvls.values())
                for lvls in cache.values()
            )
            print()
            print("=" * 60)
            print(f"  ✓ Done! {len(cache)} classes, {total} spells cached.")
            print("=" * 60)
            print()
            print("  Spell selection during character creation will now show")
            print("  the full list with school, description, casting time,")
            print("  range, and duration for every spell.")
            print()
            print("  Arcane Trickster: Mage Hand auto-guaranteed; cantrips")
            print("    freely chosen; leveled spells Enchantment/Illusion")
            print("    restricted (+ 2 free any-school picks).")
            print()
            print("  Eldritch Knight: cantrips freely chosen; leveled spells")
            print("    Abjuration/Evocation restricted (+ 3 free picks).")
        else:
            print()
            print("[Setup] API returned no data.")
            print("  Check your internet connection and try again.")
            print("  The game will use the hardcoded fallback list in the meantime.")

    except ImportError:
        print("[Setup] ERROR: spell_scraper.py not found.")
        print("  Make sure you're running this from your dnd_ai_dm/ project root.")


if __name__ == "__main__":
    main()
