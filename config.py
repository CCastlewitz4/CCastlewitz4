# config.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Central configuration hub for the entire DnD AI DM system.
#          Every other file imports settings from here. Nothing is hard-coded
#          anywhere else. To change a setting, edit it once here and it
#          automatically applies across the whole project.
#
# HOW TO USE ENVIRONMENT VARIABLE OVERRIDES:
#   On Linux/macOS:  export DND_MODEL=llama3.1:8b-instruct-q4_K_M
#   On Windows CMD:  set DND_MODEL=llama3.1:8b-instruct-q4_K_M
#   Then run:        python main.py
# ─────────────────────────────────────────────────────────────────────────────

import os

# ── Model Settings ─────────────────────────────────────────────────────────

# MODEL_NAME: The Ollama model tag to use for all AI calls.
# os.getenv() reads an environment variable if set; otherwise uses the default.
# The q4_K_M suffix = 4-bit quantized model (half the RAM of full-precision).
MODEL_NAME = os.getenv('DND_MODEL', 'llama3.1:8b-instruct-q4_0')

# CONTEXT_WINDOW: How many tokens the model can "see" at once per call.
# 8192 is a good balance. Reduce to 4096 on machines with less than 8GB RAM.
CONTEXT_WINDOW = int(os.getenv('DND_CONTEXT', '8192'))

# TEMPERATURE: Controls how creative/random the AI's responses are.
# Range: 0.0 (fully deterministic) → 2.0 (very random).
# 0.85 gives creative but coherent storytelling. Raise for wilder sessions.
TEMPERATURE = float(os.getenv('DND_TEMP', '0.9'))

# TOP_P: Nucleus sampling threshold. Works with temperature.
# 0.9 means the model only considers tokens that make up the top 90% probability mass.
TOP_P = float(os.getenv('DND_TOP_P', '0.9'))

# MAX_TOKENS_PER_RESPONSE: Maximum tokens the DM generates per turn.
# 1024 = roughly 700-800 words. Reduce to 512 for faster responses.
MAX_TOKENS_PER_RESPONSE = int(os.getenv('DND_MAX_TOKENS', '1024'))

# ── Paths ──────────────────────────────────────────────────────────────────

# BASE_DIR: Absolute path to the project root folder (where this file lives).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# TRAINING_DIR: Where fine-tuning datasets and audio transcripts are stored.
# This is shared across all game systems.
TRAINING_DIR = os.path.join(BASE_DIR, 'data', 'training')

# ── Active Game System (set at runtime by main.py) ─────────────────────────
# These are populated when the player selects a system at startup.
# All other modules read from here to know which system is active.
# Do not set these manually — they are set by set_active_system() below.

ACTIVE_SYSTEM      = None   # The full system dict from systems.py
ACTIVE_SYSTEM_ID   = None   # e.g. 'dnd_5e'
ACTIVE_GENRE       = None   # Label of the chosen genre e.g. 'Dark & Gritty'
CAMPAIGN_PREFS_BLOCK = ''   # Formatted preferences string injected into every system prompt
CAMPAIGN_NAME        = None # Campaign name from setup, shown in status and UI

# These paths update to point to the active system's data folders
WORLD_DIR         = os.path.join(BASE_DIR, 'data', 'world')          # overridden at runtime
CONVERSATION_DIR  = os.path.join(BASE_DIR, 'data', 'conversations')  # overridden at runtime
IMAGE_DIR         = os.path.join(BASE_DIR, 'data', 'images')         # overridden at runtime
CHARACTER_FILE    = os.path.join(BASE_DIR, 'data', 'player_character.json')  # overridden


def set_active_system(system: dict):
    """
    Called by main.py after the player selects a game system.
    Updates all path globals so every module reads from the correct folder.

    Parameters:
      system — A system definition dict from systems.py
    """
    global ACTIVE_SYSTEM, ACTIVE_SYSTEM_ID
    global WORLD_DIR, CONVERSATION_DIR, IMAGE_DIR, CHARACTER_FILE, ACTIVE_IMAGE_STYLE

    ACTIVE_SYSTEM    = system
    ACTIVE_SYSTEM_ID = system['id']

    dirs = system['dirs']
    WORLD_DIR        = dirs['world']
    CONVERSATION_DIR = dirs['conversations']
    IMAGE_DIR        = dirs['images']
    CHARACTER_FILE   = dirs['character']

    # Set the default image style for this system
    ACTIVE_IMAGE_STYLE = system.get('image_style', SD_STYLE)

    # Ensure directories exist
    from systems import ensure_system_dirs
    ensure_system_dirs(system)

# ── Memory (ChromaDB Vector Database) ─────────────────────────────────────

# CHROMA_PATH: The folder where ChromaDB stores its persistent vector database.
# This is where all characters, locations, nations, and plot events live long-term.
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'chroma_db')

# EMBED_MODEL: The sentence-transformer model used to convert text into vectors
# for semantic search. all-MiniLM-L6-v2 is ~80MB, fast, and accurate enough.
# Larger alternatives: 'all-mpnet-base-v2' (better quality, more RAM).
EMBED_MODEL = os.getenv('DND_EMBED_MODEL', 'all-MiniLM-L6-v2')

# ── Web Search ─────────────────────────────────────────────────────────────

# MAX_SEARCH_RESULTS: How many web results to fetch and inject into context
# when the DM performs a rules/lore lookup. More = richer context, slower response.
MAX_SEARCH_RESULTS = int(os.getenv('DND_SEARCH_RESULTS', '5'))

# ── World Generation ───────────────────────────────────────────────────────

# MAX_NPCS_PER_LOCATION: Soft cap on auto-generated NPCs per location.
# Prevents the memory database from growing uncontrollably in long campaigns.
MAX_NPCS_PER_LOCATION = int(os.getenv('DND_MAX_NPCS', '100'))

# RELATIONSHIP_DECAY_DAYS: In-game days of zero interaction before a
# relationship's sentiment intensity begins to fade toward neutral.
RELATIONSHIP_DECAY_DAYS = int(os.getenv('DND_REL_DECAY', '30'))

# RECENT_HISTORY_TURNS: How many past conversation turns to include in the
# prompt context each time the DM responds. More = better continuity, more RAM.
RECENT_HISTORY_TURNS = int(os.getenv('DND_HISTORY_TURNS', '100'))

# TIME_HOURS_PER_ACTION: Default in-game hours consumed by a short action.
TIME_HOURS_DEFAULT = int(os.getenv('DND_TIME_DEFAULT', '1'))
TIME_HOURS_TRAVEL = int(os.getenv('DND_TIME_TRAVEL', '4'))
TIME_HOURS_REST = int(os.getenv('DND_TIME_REST', '8'))

# ── Browser Configuration ──────────────────────────────────────────────────

# BROWSER_CHOICE: Which browser to open map generators in.
# Options: 'chrome', 'firefox', 'edge', 'safari', 'opera', 'chromium', 'brave'
# Default behavior: Uses your system default browser
# Set to a specific browser name to always use that browser for maps.
#
# Can be overridden via environment variable:
#   Windows CMD:  set DND_BROWSER=chrome
#   Linux/macOS:  export DND_BROWSER=chrome
BROWSER_CHOICE = os.getenv('DND_BROWSER', 'chrome')  # 'default' = system default browser

# ── Image Generation (Stable Diffusion v1.5 - Local, Free, Unlimited) ────

# SD_MODEL_ID: Which Stable Diffusion model to use locally
# 'runwayml/stable-diffusion-v1-5' = No token limits, completely free
# Download size: ~4GB (one-time only)
SD_MODEL_ID = os.getenv('SD_MODEL_ID', 'stabilityai/stable-diffusion-xl-base-1.0')

# IMAGE_DIR: Where generated scene and portrait images are saved.
IMAGE_DIR = os.path.join(BASE_DIR, 'data', 'images')

# SD_ENABLED: Master switch for image generation.
# Set to 'false' to disable image generation.
# The DM still works fully without it — this only controls image output.
SD_ENABLED = os.getenv('SD_ENABLED', 'true').lower() == 'true'

# SD_WIDTH / SD_HEIGHT: Image dimensions in pixels.
# 768x512 = good balance (landscape scenes, fast)
# 512x768 = good for portraits (taller)
# 512x512 = fastest
SD_WIDTH  = int(os.getenv('SD_WIDTH',  '768'))
SD_HEIGHT = int(os.getenv('SD_HEIGHT', '512'))

# SD_STEPS: Denoising steps. More = higher quality but slower.
# 30 = good balance (recommended for SD 1.5)
# 20 = fast, 40 = high quality
SD_STEPS = int(os.getenv('SD_STEPS', '30'))

# SD_CFG: How strictly the image follows the prompt (1-20).
# 7.5 is the well-tested default for fantasy scene generation.
SD_CFG = float(os.getenv('SD_CFG', '7.5'))

# SD_EVERY_N_TURNS: Generate an image every N DM responses.
# 1 = every turn (most visual), 2-3 = balanced, 5 = only major scenes
SD_EVERY_N_TURNS = int(os.getenv('SD_EVERY_N_TURNS', '1'))

# SD_ALWAYS_GENERATE: If True, generate an image on every qualifying turn
# regardless of whether the response contains visual trigger phrases.
# If False (default), only generate when a scene-setting phrase is detected.
SD_ALWAYS_GENERATE = os.getenv('SD_ALWAYS_GENERATE', 'false').lower() == 'true'

# SD_STYLE: Visual style keywords appended to every image prompt.
# Change this string to shift the art style of your entire campaign.
# Can be overridden at runtime using the 'imagestyle' command in-game.
SD_STYLE = os.getenv(
    'SD_STYLE',
    'fantasy art, highly detailed, dramatic lighting, cinematic, digital painting, 8k'
)

# ── Image Style Presets ────────────────────────────────────────────────────
# Named style presets the player can switch between using the 'imagestyle'
# command during a session. Each preset changes the STYLE_SUFFIX appended
# to every image prompt, fundamentally shifting the visual aesthetic.
# The SD model itself stays the same — only the style keywords change.
#
# To add your own preset, add a new key/value pair to this dict.
IMAGE_STYLE_PRESETS = {
    # ── Painterly / Artistic styles ────────────────────────────────────────
    'fantasy':      'fantasy art, highly detailed, dramatic lighting, cinematic, digital painting, 8k',
    'realistic':    'photorealistic, hyperrealistic, 8k photography, cinematic lighting, detailed textures, sharp focus, real people',
    'dark':         'dark fantasy, gothic, grim dark, desaturated colors, gritty realism, ominous atmosphere, detailed',
    'painterly':    'oil painting, classical art, renaissance style, Rembrandt lighting, rich colors, detailed brushwork',
    'watercolor':   'watercolor illustration, soft edges, pastel tones, storybook art, whimsical, gentle lighting',
    'cinematic':    'cinematic photography, movie still, dramatic composition, volumetric lighting, depth of field, 4k',

    # ── Stylized / Artistic styles ─────────────────────────────────────────
    'anime':        'anime style, studio ghibli inspired, detailed, vibrant colors, clean lines, expressive',
    'comic':        'comic book art, bold outlines, cel shading, vibrant colors, dynamic composition, Marvel style',
    'sketch':       'pencil sketch, detailed crosshatching, black and white, concept art, rough lines',
    'pixel':        'pixel art, 16-bit style, retro RPG, detailed sprites, vibrant colors',

    # ── Setting-specific styles ────────────────────────────────────────────
    'epic':         'epic fantasy, massive scale, god rays, dramatic sky, highly detailed environment, 8k',
    'horror':       'horror atmosphere, dark, unsettling, fog, shadows, creepy, detailed, gothic',
    'warm':         'warm fantasy, golden hour lighting, cozy atmosphere, rich colors, detailed, inviting',

    # ── Your trained LoRA styles (auto-populated after training) ───────────
    # These entries are added automatically by lora_manager.py after each
    # training run. The trigger word is prepended to every prompt so the
    # LoRA activates on every image. Switch between them with 'imagestyle'.
    'anime_lora':     'animestyle, anime art, vibrant colors, clean lines, expressive, highly detailed',
    'realistic_lora': 'realisticstyle, photorealistic, cinematic lighting, sharp focus, highly detailed, 8k',
    'cinematic_lora': 'cinematicstyle, cinematic photography, volumetric lighting, dramatic composition, 4k, detailed',
}

# ── LoRA Registry ──────────────────────────────────────────────────────────
# Maps each style preset name to its trained LoRA folder path.
# Populated automatically by lora_manager.py after training completes.
# image_generator.py reads this to know which LoRA to load for each style.
#
# Structure: { 'preset_name': 'absolute/path/to/lora/folder' }
# Example:   { 'anime_lora': 'C:/Users/colin/.../data/image_lora/animestyle' }
LORA_REGISTRY: dict = {}

# ACTIVE_IMAGE_STYLE: Which preset is currently active.
# Changed at runtime by the 'imagestyle' command — persists for the session.
# Does NOT persist between sessions (resets to SD_STYLE default on restart).
ACTIVE_IMAGE_STYLE = SD_STYLE

# ── Auto-create all directories on first import ────────────────────────────
# exist_ok=True means no error if the folder already exists.
for _dir in [WORLD_DIR, CONVERSATION_DIR, TRAINING_DIR, CHROMA_PATH, IMAGE_DIR]:
    os.makedirs(_dir, exist_ok=True)
