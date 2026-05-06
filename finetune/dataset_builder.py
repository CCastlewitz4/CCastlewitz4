# finetune/dataset_builder.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Converts raw Whisper transcripts into structured instruction-following
#          training pairs for fine-tuning Llama.
#
# TRAINING PAIR FORMAT:
#   Each pair contains:
#     - 'instruction': A player action or question (the input)
#     - 'input':       Empty string (not used in this format)
#     - 'output':      The DM's narration response (what we want the model to learn)
#
# HOW SPEAKER DETECTION WORKS:
#   Transcripts from DnD actual-play videos don't label who's speaking.
#   This module uses configurable heuristic keyword lists to classify each
#   segment as either 'dm', 'player', or 'unknown'.
#   You can customize CUSTOM_DM_NAMES and CUSTOM_PLAYER_NAMES for your videos.
#
# OUTPUT FORMAT:
#   JSONL file (JSON Lines) — one training pair per line.
#   This is the standard format for LLM fine-tuning pipelines.
#
# LOCATION: dnd_ai_dm/finetune/dataset_builder.py
# ─────────────────────────────────────────────────────────────────────────────

import json
import os

import config


# ── Speaker Classification Keyword Lists ──────────────────────────────────
# These lists control how transcript segments are identified as DM or player speech.
# ADD your own DM's name or phrases to these lists for your specific videos.

# Phrases strongly associated with DM narration
DM_INDICATORS = [
    'dungeon master', ' dm:', ' gm:', 'narrator:', 'the dm says',
    'you see', 'before you', 'the air smells', 'the room is',
    'read aloud', 'as you approach', 'describe the scene',
    'roll for', 'make a', 'give me a', 'perception check',
    'the npc says', 'he says', 'she says', 'they say',
    'the guard replies', 'the merchant responds',
]

# Phrases strongly associated with player actions/dialogue
PLAYER_INDICATORS = [
    'i want to', 'i try to', 'my character', 'i roll',
    'can i', 'i would like to', 'i attack', 'i cast',
    'i search', 'i look', 'i ask', 'i say', "i'll",
    'player:', 'pc:', 'as my character',
]

# ── Customizable Speaker Names ─────────────────────────────────────────────
# Add the actual names used in YOUR videos here.
# Example: CUSTOM_DM_NAMES = ['Matt', 'Brennan', 'Aabria']
CUSTOM_DM_NAMES: list[str] = []

# Example: CUSTOM_PLAYER_NAMES = ['Marisha', 'Sam', 'Travis']
CUSTOM_PLAYER_NAMES: list[str] = []

# Minimum character length for a segment to be considered usable
MIN_SEGMENT_LENGTH = int(os.getenv('MIN_SEGMENT_LENGTH', '20'))

# Minimum DM response length to be included as training output
MIN_DM_RESPONSE_LENGTH = int(os.getenv('MIN_DM_LENGTH', '50'))


def _classify_segment(text: str) -> str:
    """
    Classifies a transcript segment as 'dm', 'player', or 'unknown'.

    Uses case-insensitive keyword matching against the indicator lists above.
    Custom speaker names are checked first for higher confidence.

    Parameters:
      text — The raw transcript segment text

    Returns:
      'dm', 'player', or 'unknown'
    """
    lower = text.lower()

    # Check custom names first (highest confidence)
    for name in CUSTOM_DM_NAMES:
        if name.lower() in lower:
            return 'dm'
    for name in CUSTOM_PLAYER_NAMES:
        if name.lower() in lower:
            return 'player'

    # Check standard indicator phrases
    if any(indicator in lower for indicator in DM_INDICATORS):
        return 'dm'
    if any(indicator in lower for indicator in PLAYER_INDICATORS):
        return 'player'

    return 'unknown'


def _clean_text(text: str) -> str:
    """
    Cleans a transcript segment for use as training data.
    Strips leading/trailing whitespace and normalizes multiple spaces.
    """
    return ' '.join(text.split()).strip()


def build_training_pairs(transcript_path: str) -> list[dict]:
    """
    Reads a transcript JSON file and extracts (player_action → dm_response)
    training pairs.

    Algorithm:
      - Iterate through segments in order
      - When a 'player' segment is found, store it as a pending instruction
      - When a 'dm' segment follows a pending instruction, form a pair
      - Consecutive DM segments are concatenated to capture full responses
      - Pairs are filtered by minimum length requirements

    Parameters:
      transcript_path — Path to a _transcript.json file from video_processor.py

    Returns:
      A list of training pair dicts:
        [{'instruction': '...', 'input': '', 'output': '...'}, ...]
    """
    with open(transcript_path, 'r', encoding='utf-8') as f:
        segments = json.load(f)

    pairs = []
    pending_player_text = None   # Stores the last player action seen
    accumulated_dm_text = ''     # Accumulates consecutive DM segments

    for segment in segments:
        raw_text = segment.get('text', '').strip()

        # Skip very short segments (likely noise, filler words, etc.)
        if len(raw_text) < MIN_SEGMENT_LENGTH:
            continue

        text = _clean_text(raw_text)
        role = _classify_segment(text)

        if role == 'player':
            # If we had an accumulated DM response before this player action,
            # save the completed pair first
            if pending_player_text and len(accumulated_dm_text) >= MIN_DM_RESPONSE_LENGTH:
                pairs.append({
                    'instruction': pending_player_text,
                    'input': '',
                    'output': accumulated_dm_text.strip()
                })

            # Start a new pending player action
            pending_player_text = text
            accumulated_dm_text = ''  # Reset DM accumulator

        elif role == 'dm' and pending_player_text:
            # Accumulate this DM segment into the current response
            # (DM responses often span multiple transcription segments)
            accumulated_dm_text += ' ' + text

        elif role == 'unknown':
            # Unknown segments that follow a player action may be DM narration
            # — accumulate them tentatively
            if pending_player_text and accumulated_dm_text:
                accumulated_dm_text += ' ' + text

    # Don't forget the final pending pair if we reached the end of the transcript
    if pending_player_text and len(accumulated_dm_text) >= MIN_DM_RESPONSE_LENGTH:
        pairs.append({
            'instruction': pending_player_text,
            'input': '',
            'output': accumulated_dm_text.strip()
        })

    return pairs


def save_dataset(pairs: list[dict], name: str = 'dnd_training') -> str:
    """
    Saves training pairs to a JSONL file (one JSON object per line).
    JSONL is the standard format for LLM fine-tuning with Hugging Face.

    Parameters:
      pairs — List of training pair dicts
      name  — Base filename (without extension) for the output file

    Returns:
      Full path of the saved .jsonl file.
    """
    out_path = os.path.join(config.TRAINING_DIR, f'{name}.jsonl')

    with open(out_path, 'w', encoding='utf-8') as f:
        for pair in pairs:
            # json.dumps() converts the dict to a JSON string
            # Writing one per line = JSONL format
            f.write(json.dumps(pair, ensure_ascii=False) + '\n')

    print(f'Saved {len(pairs)} training pairs to: {out_path}')
    return out_path


def process_all_transcripts(output_name: str = 'dnd_training') -> list[dict]:
    """
    Convenience function: processes ALL transcript files in the transcripts
    directory and combines them into a single JSONL training dataset.

    Use this after running video_processor.py on all your source videos.

    Parameters:
      output_name — Base filename for the combined output JSONL file

    Returns:
      The combined list of all training pairs.
    """
    transcript_dir = os.path.join(config.TRAINING_DIR, 'transcripts')

    if not os.path.exists(transcript_dir):
        print(f'Transcripts directory not found: {transcript_dir}')
        print('Run video_processor.py first to create transcripts.')
        return []

    all_pairs = []
    transcript_files = [
        f for f in os.listdir(transcript_dir)
        if f.endswith('_transcript.json')
    ]

    if not transcript_files:
        print('No transcript files found. Run video_processor.py first.')
        return []

    print(f'Found {len(transcript_files)} transcript file(s) to process.')

    for filename in sorted(transcript_files):
        path = os.path.join(transcript_dir, filename)
        print(f'\nProcessing: {filename}')
        pairs = build_training_pairs(path)
        print(f'  Extracted {len(pairs)} training pairs.')
        all_pairs.extend(pairs)

    print(f'\nTotal training pairs: {len(all_pairs)}')

    if all_pairs:
        save_dataset(all_pairs, name=output_name)
    else:
        print('WARNING: No training pairs extracted. Check your transcript files')
        print('and consider adjusting the DM_INDICATORS / PLAYER_INDICATORS lists.')

    return all_pairs


def preview_dataset(dataset_path: str, n: int = 5):
    """
    Prints the first n training pairs from a JSONL file.
    Useful for spot-checking the quality of extracted pairs before training.

    Parameters:
      dataset_path — Path to a .jsonl training file
      n            — Number of pairs to preview
    """
    if not os.path.exists(dataset_path):
        print(f'Dataset not found: {dataset_path}')
        return

    print(f'\n=== Preview: {os.path.basename(dataset_path)} ===\n')
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            pair = json.loads(line.strip())
            print(f'--- Pair {i + 1} ---')
            print(f'INSTRUCTION: {pair["instruction"][:150]}')
            print(f'OUTPUT:      {pair["output"][:200]}')
            print()
