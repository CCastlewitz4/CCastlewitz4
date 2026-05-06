# agent/image_generator.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Generates images from DnD scene descriptions using Stable Diffusion
#          running DIRECTLY in Python via the diffusers library.
#
# NO WEB UI — NO SERVER — NO BROWSER
# This runs entirely inside your existing Python process alongside the DM.
# The diffusers library loads the Stable Diffusion model directly into your
# GPU's VRAM the same way Ollama loads Llama — pure Python, no extra software.
#
# HOW IT FITS INTO THE SYSTEM:
#   After every DM response, dm_agent.py calls generate_image() here.
#   The flow is:
#
#     DM writes narrative text (Ollama call in dm_agent.py)
#           ↓
#     Ollama converts narrative → SD keyword prompt  (~1-2 seconds)
#           ↓
#     Stable Diffusion generates the image from those keywords  (~5-20 sec)
#           ↓
#     Image saved as PNG to data/images/
#           ↓
#     File path returned to dm_agent.py → displayed in main.py terminal
#
# HOW THE MODEL IS LOADED:
#   The first time generate_image() is called in a session, it downloads
#   the Stable Diffusion model from Hugging Face (~4-6GB one time download)
#   and loads it into your RTX 3080's VRAM.
#
#   The model stays loaded in VRAM for the rest of the session so every
#   subsequent image generates instantly without reloading.
#
#   This is called "lazy loading" — we don't load the model at startup,
#   only when the first image is actually needed. This means if you never
#   trigger an image in a session, Stable Diffusion never uses any VRAM.
#
# VRAM MANAGEMENT FOR RTX 3080 (10GB):
#   Ollama (Llama 3.1-8B q4_K_M) uses ~5-6GB VRAM
#   Stable Diffusion (SD 1.5) uses ~2-3GB VRAM
#   Total: ~7-9GB — fits within your 10GB with careful management
#
#   The key trick is that Ollama and SD are NEVER running simultaneously:
#   - Ollama generates the DM text FIRST, then unloads from VRAM
#   - THEN Stable Diffusion loads and generates the image
#   - The SD pipeline is kept loaded between turns so it doesn't reload
#     every turn, but it yields the GPU to Ollama during text generation
#
#   If you ever hit out-of-memory errors, set SD_MODEL to a lighter model
#   or set SD_HALF_PRECISION=true (see settings below).
#
# WHICH STABLE DIFFUSION MODEL IS USED:
#   Default: 'runwayml/stable-diffusion-v1-5'
#   This is the classic SD 1.5 model — well-tested, ~4GB download,
#   excellent for fantasy scenes, fully free and open source.
#
#   You can change SD_MODEL_ID to any diffusers-compatible model on
#   Hugging Face. Good fantasy alternatives:
#     'stabilityai/stable-diffusion-2-1'   (~5GB, higher quality)
#     'dreamlike-art/dreamlike-photoreal-2.0'  (~4GB, photorealistic)
#   These are all free but require accepting their license on Hugging Face.
#
# DEPENDENCIES:
#   pip install diffusers transformers accelerate Pillow
#   (already added to requirements.txt)
#
# LOCATION: dnd_ai_dm/agent/image_generator.py
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os

# ── Path fix ──────────────────────────────────────────────────────────────
# Ensures this file can find config.py regardless of working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from datetime import datetime

import config


# ═══════════════════════════════════════════════════════════════════════════
# SETTINGS — all overridable via environment variables
# ═══════════════════════════════════════════════════════════════════════════

# SD_ENABLED: Master on/off switch.
# If False, generate_image() returns None immediately without doing anything.
# Automatically set to False if diffusers/torch/Pillow are not installed.
SD_ENABLED = os.getenv('SD_ENABLED', 'true').lower() == 'true'

# SD_MODEL_ID: Which Stable Diffusion model to download and use.
# This is a Hugging Face model repository ID.
# The model downloads once and is cached locally after that.
#
# SDXL (Stable Diffusion XL) is the latest, highest-quality open-source model.
# It produces dramatically better results than SD 1.5, approaching Midjourney quality.
# Download size: ~6.5GB (slightly larger than SD 1.5, well worth it).
# VRAM usage: ~4-5GB (fits with Ollama on RTX 3080).
#
# Quality improvements with SDXL:
#   - Much sharper, more detailed images
#   - Better face generation (fewer artifacts)
#   - Stronger understanding of complex prompts
#   - More cinematic, professional-looking output
#   - Closer to Midjourney aesthetic
#
# Speed: ~10-15 seconds per image on RTX 3080 (vs 5-8 on SD 1.5)
#
# To use a different model, set the SD_MODEL_ID environment variable or change below.
# Other options:
#   'stabilityai/stable-diffusion-v1-5'             — faster but lower quality
#   'dreamlike-art/dreamlike-photoreal-2.0'         — good realism, ~4GB
#   's3atasets/midjourney-v4-diffusion'             — Midjourney-style, ~4GB
SD_MODEL_ID = os.getenv('SD_MODEL_ID', 'stabilityai/stable-diffusion-xl-base-1.0')

# SD_WIDTH / SD_HEIGHT: Output image dimensions in pixels.
# SDXL handles larger resolutions much better than SD 1.5.
# 1024x1024 is SDXL's native training resolution and produces excellent results.
# 768x1024 for portraits (taller), 1024x768 for landscapes (wider).
#   768x768   → ~10-12 seconds on RTX 3080, 4.5GB VRAM
#   1024x1024 → ~12-16 seconds on RTX 3080, 5GB VRAM (portrait sweet spot)
#   1024x768  → ~12-16 seconds on RTX 3080, 5GB VRAM (landscape sweet spot)
IMAGE_WIDTH  = int(os.getenv('SD_WIDTH',  '1024'))
IMAGE_HEIGHT = int(os.getenv('SD_HEIGHT', '1024'))

# SD_STEPS: Number of denoising steps.
# SDXL produces excellent results at 30-35 steps (more efficient than SD 1.5).
#   20 → acceptable quality, fast
#   30 → excellent quality, good speed  (recommended)
#   40 → ultra high quality, noticeably slower
INFERENCE_STEPS = int(os.getenv('SD_STEPS', '30'))

# SD_CFG: Classifier-Free Guidance scale.
# SDXL works best at slightly lower CFG than SD 1.5 (8.0 is optimal).
#   6.0  → creative, loose adherence to prompt
#   8.0  → balanced, excellent results  (recommended for SDXL)
#   10+  → rigid, can over-saturate
CFG_SCALE = float(os.getenv('SD_CFG', '8.0'))

# SD_EVERY_N_TURNS: Generate an image every N DM turns.
# 1 = every turn (most visual but uses GPU more frequently)
# 2 = every other turn
# 3 = every 3 turns (good balance for slower machines)
GENERATE_EVERY_N_TURNS = int(os.getenv('SD_EVERY_N_TURNS', '1'))

# SD_ALWAYS_GENERATE: If True, generate an image on every qualifying turn
# regardless of whether the response contains visual trigger phrases.
# If False (default), only generate when a scene-setting phrase is detected.
SD_ALWAYS_GENERATE = os.getenv('SD_ALWAYS_GENERATE', 'false').lower() == 'true'

# STYLE_SUFFIX: Reads the active image style from config.ACTIVE_IMAGE_STYLE.
# This is updated at runtime when the player uses the 'imagestyle' command.
# Do not change this line — change config.ACTIVE_IMAGE_STYLE or use the command.
def get_style_suffix() -> str:
    """
    Returns the currently active image style string from config.
    Reading dynamically (via function) rather than at import time means
    changes made by the 'imagestyle' command take effect immediately on
    the next image generation without restarting the session.
    """
    return getattr(config, 'ACTIVE_IMAGE_STYLE', config.SD_STYLE)

# NEGATIVE_PROMPT: Things to tell Stable Diffusion to AVOID in every image.
# Tuned for SDXL — optimized to prevent common artifacts and quality issues.
NEGATIVE_PROMPT = (
    'ugly, deformed, disfigured, bad anatomy, bad proportions, '
    'extra limbs, missing limbs, floating limbs, disconnected limbs, '
    'mutation, mutated, blurry, out of focus, noise, grain, '
    'low quality, jpeg artifacts, watermark, text, signature, logo, '
    'username, frame, border, modern clothing, modern technology, '
    'guns, cars, phones, neon signs, cartoon, anime, sketch, '
    'pencil drawing, flat shading, low resolution, distorted face, '
    'double face, two faces, multiple faces, duplicate, mirrored, '
    'reflection, stacked, layered, overlapping, twisted, '
    'extra features, repeated features, worst quality, '
    'poor quality, bad hands, mutated hands, poorly drawn hands'
)

# IMAGE_TRIGGER_PHRASES: The DM response must contain at least one of these
# for an image to be generated (unless SD_ALWAYS_GENERATE=true).
# This prevents wasting GPU time on short responses like "Roll for stealth."
IMAGE_TRIGGER_PHRASES = [
    'you see', 'before you', 'you enter', 'you arrive',
    'you find yourself', 'you step into', 'the room', 'the hall',
    'the forest', 'the city', 'the dungeon', 'the tavern',
    'stands before you', 'looms', 'stretches out', 'in the distance',
    'you notice', 'appears before', 'the landscape', 'surrounds you',
    'a figure', 'the creature', 'battle begins', 'charges toward',
    'emerges from', 'draws their weapon', 'the castle', 'the ruins',
]

# Where to save generated images
IMAGE_OUTPUT_DIR = os.path.join(config.BASE_DIR, 'data', 'images')


# ═══════════════════════════════════════════════════════════════════════════
# DEPENDENCY CHECKS
# ═══════════════════════════════════════════════════════════════════════════

# Check for required libraries at import time so we get a clear error message
# rather than a cryptic crash when generate_image() is first called.

# Check torch (PyTorch — the deep learning engine SD runs on)
try:
    import torch
    TORCH_AVAILABLE = True
    # Detect whether CUDA (NVIDIA GPU) is available
    # If not, SD will run on CPU which is ~20x slower
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    TORCH_AVAILABLE = False
    CUDA_AVAILABLE = False

# Check diffusers (Hugging Face library that loads and runs SD)
try:
    from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
    DIFFUSERS_AVAILABLE = True
except ImportError:
    DIFFUSERS_AVAILABLE = False

# Check Pillow (used to save the generated image as a PNG file)
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

# Print a clear setup message if any dependency is missing
def _check_and_report_dependencies() -> bool:
    """
    Verifies all required libraries are installed and reports any that are missing.
    Returns True if everything is ready, False if setup is needed.

    Called once when the first image generation is attempted so the error
    appears in context rather than at program startup.
    """
    missing = []
    if not TORCH_AVAILABLE:
        missing.append('torch  →  pip install torch --index-url https://download.pytorch.org/whl/cu124')
    if not DIFFUSERS_AVAILABLE:
        missing.append('diffusers  →  pip install diffusers transformers accelerate')
    if not PILLOW_AVAILABLE:
        missing.append('Pillow  →  pip install Pillow')

    if missing:
        print('\n[ImageGen] Missing dependencies for image generation:')
        for m in missing:
            print(f'  pip install {m}')
        print('[ImageGen] Image generation disabled until these are installed.\n')
        return False

    if not CUDA_AVAILABLE:
        print(
            '\n[ImageGen] WARNING: No CUDA GPU detected. '
            'Image generation will run on CPU and be very slow (~5-10 minutes per image). '
            'Make sure your NVIDIA drivers and CUDA toolkit are installed correctly.'
        )

    return True


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE — the loaded Stable Diffusion model
# ═══════════════════════════════════════════════════════════════════════════

# _pipeline is the global reference to the loaded SD model.
# It starts as None and is loaded on the FIRST call to generate_image().
# After loading it stays in memory for the rest of the session.
#
# Why global?
#   Loading the SD model takes ~10-20 seconds and uses ~2-3GB of VRAM.
#   If we loaded it fresh for every image it would add 10-20 seconds to
#   every single turn. Keeping it loaded means image generation only adds
#   the actual rendering time (~5-15 seconds) after the first image.
#
# Why not load at startup?
#   If the player never triggers any image (e.g. purely text session),
#   we would have wasted 2-3GB of VRAM the entire session for nothing.
#   Lazy loading means zero overhead unless images are actually generated.
_pipeline = None


def _load_pipeline():
    """
    Loads the Stable Diffusion pipeline into GPU VRAM.
    Called automatically on the first generate_image() call.
    Does nothing if the pipeline is already loaded.

    The pipeline object contains:
      - The UNet (the actual denoising neural network, ~3GB)
      - The VAE (encodes/decodes images to/from latent space, ~300MB)
      - The text encoder (converts the prompt to embeddings, ~500MB)
      - The tokenizer (converts prompt text to token IDs)
      - The scheduler (controls the denoising algorithm and step count)

    All of these are loaded onto the GPU together when this function runs.

    The DPMSolverMultistepScheduler is substituted for the default scheduler
    because it produces high-quality results in fewer steps (25 instead of 50),
    making generation ~2x faster with minimal quality loss.
    """
    global _pipeline

    if _pipeline is not None:
        return  # Already loaded — nothing to do

    if not _check_and_report_dependencies():
        return  # Dependencies missing — abort

    print(f'\n[ImageGen] Loading DreamShaper v8 model: {SD_MODEL_ID}')
    print('[ImageGen] First run downloads ~2GB of model files — subsequent runs are instant.')
    print('[ImageGen] This takes 10-30 seconds...')

    # Determine compute device and precision
    # CUDA = NVIDIA GPU (fast), CPU = fallback (very slow)
    device = 'cuda' if CUDA_AVAILABLE else 'cpu'

    # torch_dtype=torch.float16 loads the model in half-precision (16-bit).
    # This cuts VRAM usage roughly in half vs full float32 precision.
    # float16 is fully supported on RTX 3080 and produces identical output
    # for image generation tasks.
    # On CPU we must use float32 because most CPUs don't support float16 math.
    dtype = torch.float16 if CUDA_AVAILABLE else torch.float32

    try:
        # StableDiffusionPipeline.from_pretrained() downloads and loads the model.
        # The model files are cached in your Hugging Face cache folder after
        # the first download, so subsequent runs load from disk instantly.
        #
        # safety_checker=None: Disables the NSFW content filter.
        # For a fantasy DnD game this filter incorrectly flags battle scenes,
        # dark dungeons, and monsters. Disabling it gives much better results.
        # feature_extractor=None: Required when disabling safety_checker.
        _pipeline = StableDiffusionPipeline.from_pretrained(
            SD_MODEL_ID,
            torch_dtype=dtype,
            safety_checker=None,
            feature_extractor=None,
        )

        # Replace the default PNDM scheduler with DPMSolverMultistepScheduler.
        # DPM-Solver++ is a much faster scheduler that reaches the same quality
        # in 20-25 steps that PNDM needs 50 steps for.
        # This is the single biggest speed improvement we can make.
        _pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
            _pipeline.scheduler.config
        )

        # Move the entire pipeline to GPU (or CPU if no GPU available)
        _pipeline = _pipeline.to(device)

        # ── Load trained LoRA if one is registered for the active style ────
        # Checks config.LORA_REGISTRY for a path matching the current preset.
        # If found, fuses the LoRA weights into the pipeline so every image
        # generated with this style automatically uses the trained adapter.
        _try_load_active_lora()

        # enable_attention_slicing() reduces peak VRAM usage during generation
        # by processing the attention mechanism in smaller slices.
        # Costs ~10% speed but prevents OOM errors on 10GB cards.
        _pipeline.enable_attention_slicing()

        # enable_vae_slicing() applies the same slicing trick to the VAE decoder.
        # Essential for larger image sizes (768x768+) on 10GB VRAM.
        _pipeline.enable_vae_slicing()

        # xformers memory-efficient attention: if installed, gives a significant
        # speed boost (~20-30% faster) and reduces VRAM usage with no quality loss.
        # Install with: pip install xformers
        # Safe to skip — falls back to standard attention if not available.
        try:
            _pipeline.enable_xformers_memory_efficient_attention()
            print('[ImageGen] xformers memory-efficient attention enabled.')
        except Exception:
            pass  # xformers not installed — standard attention used instead

        print(f'[ImageGen] DreamShaper v8 loaded on {device.upper()}. Ready to generate images.')

    except Exception as e:
        print(f'[ImageGen] Failed to load Stable Diffusion model: {e}')
        print('[ImageGen] Image generation will be disabled for this session.')
        _pipeline = None


def _try_load_active_lora():
    """
    Checks if a trained LoRA is registered for the currently active image style
    and loads it into the pipeline if so.

    Called automatically inside _load_pipeline() after the base model loads.
    Also called by reload_lora_for_style() when the player switches styles
    mid-session using the 'imagestyle' command.

    How it works:
      1. Reads config.ACTIVE_IMAGE_STYLE to find the current style string
      2. Looks up which preset name matches that string in IMAGE_STYLE_PRESETS
      3. Checks config.LORA_REGISTRY for a LoRA path for that preset
      4. If found and the path exists, loads and fuses the LoRA weights
      5. If not found, the pipeline runs as normal (no LoRA = base SDXL)
    """
    global _pipeline
    if _pipeline is None:
        return

    try:
        lora_registry = getattr(config, 'LORA_REGISTRY', {})
        if not lora_registry:
            return  # No LoRAs trained yet — nothing to load

        # Find which preset name matches the current active style string
        active_style  = getattr(config, 'ACTIVE_IMAGE_STYLE', '')
        presets       = getattr(config, 'IMAGE_STYLE_PRESETS', {})
        active_preset = next(
            (name for name, style in presets.items() if style == active_style),
            None
        )

        if not active_preset or active_preset not in lora_registry:
            return  # No LoRA for this style — use base model

        lora_path = lora_registry[active_preset]
        if not os.path.exists(lora_path):
            print(f'  [ImageGen] LoRA path not found: {lora_path}')
            return

        print(f'  [ImageGen] Loading LoRA for style "{active_preset}"...')
        _pipeline.load_lora_weights(lora_path)
        _pipeline.fuse_lora(lora_scale=0.8)
        print(f'  [ImageGen] LoRA loaded: {os.path.basename(lora_path)}')

    except Exception as e:
        # LoRA loading failure should never crash the game — just log and continue
        print(f'  [ImageGen] LoRA load skipped ({e}) — using base model.')


def reload_lora_for_style():
    """
    Called by main.py when the player switches styles with the 'imagestyle'
    command. Unfuses any current LoRA and loads the one for the new style.

    This lets players switch between their trained anime/realistic/cinematic
    LoRAs mid-session without restarting.
    """
    global _pipeline
    if _pipeline is None:
        return  # Pipeline not loaded yet — LoRA will be loaded when it is

    try:
        # Unfuse the current LoRA before loading a new one
        _pipeline.unfuse_lora()
        _pipeline.unload_lora_weights()
    except Exception:
        pass  # No LoRA was loaded — that's fine

    _try_load_active_lora()


def _unload_pipeline():
    """
    Unloads the Stable Diffusion pipeline from VRAM.

    Called before Ollama generates text to free up VRAM for the LLM.
    After the LLM finishes, _load_pipeline() reloads SD for the next image.

    This VRAM swapping is the key technique that lets a 10GB card run both
    the 5-6GB LLM and 2-3GB image model without running out of memory.

    Note: Reloading from disk cache after the first session takes ~5-10 seconds.
    This is a trade-off vs running both simultaneously which risks OOM crashes.
    Set SD_KEEP_LOADED=true to skip unloading (only safe if you have 12GB+ VRAM).
    """
    global _pipeline

    # SD_KEEP_LOADED: Skip VRAM swapping if the user opts in.
    # Only use this if you have enough VRAM for both models simultaneously.
    if os.getenv('SD_KEEP_LOADED', 'false').lower() == 'true':
        return

    if _pipeline is None:
        return  # Nothing to unload

    # Move pipeline to CPU first (releases GPU VRAM while keeping weights in RAM)
    try:
        _pipeline = _pipeline.to('cpu')
        # Force CUDA to release the now-freed VRAM back to the system
        if CUDA_AVAILABLE:
            torch.cuda.empty_cache()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT CONVERSION
# ═══════════════════════════════════════════════════════════════════════════

def _narrative_to_sd_prompt(narrative_text: str) -> str:
    """
    Converts the DM's narrative text into a high-quality SDXL/Midjourney-style prompt.

    WHY THIS CONVERSION IS NECESSARY:
    SDXL and Midjourney respond best to visual keywords with quality descriptors.
    The DM writes full narrative paragraphs. If we send the raw narrative to SD:
      - "You push open the heavy oak door" → SD might generate poor composition
      - "The innkeeper looks at you suspiciously" → SD might miss mood/lighting

    With conversion:
      - Same scene → "cinematic fantasy tavern interior, oak door, stone walls, 
                      innkeeper with suspicious expression, warm candlelight, 
                      volumetric lighting, highly detailed, sharp focus, 
                      trending on artstation, masterpiece, 8k"
    This produces dramatically better, more cinematic results.

    HOW IT WORKS:
    We send the narrative to Ollama with a very specific system prompt that
    instructs it to extract only the VISUAL elements and format them as 
    Midjourney-style keywords. The prompt is carefully designed to:
      - Extract key visual elements
      - Add quality descriptors (cinematic, artstation, etc.)
      - Include lighting and mood descriptions
      - Produce professional-grade output

    This is a short fast Ollama call (~1-2 seconds) using low temperature
    for focused, consistent output rather than creative variation.

    Parameters:
      narrative_text — The DM's full response text

    Returns a clean SDXL prompt string ready to pass to the pipeline.
    """
    # Truncate long narratives — the first 500 chars usually contains the
    # key scene-setting information we need for the image prompt
    truncated = narrative_text[:500]

    conversion_instruction = (
        f'Convert this DnD scene into a concise SDXL image prompt.\n\n'
        f'SCENE:\n{truncated}\n\n'
        f'STRICT RULES:\n'
        f'- Output ONLY the prompt — no preamble, no quotes\n'
        f'- Use comma-separated keywords (KEEP BRIEF)\n'
        f'- Include: setting, lighting, mood, characters, objects\n'
        f'- Add: cinematic, sharp focus, detailed, trending artstation, masterpiece\n'
        f'- MAXIMUM 60 words (CRITICAL for SDXL CLIP compatibility)\n'
        f'- NO dialogue, sounds, emotions, game mechanics\n'
        f'- Begin directly with first keyword\n\n'
        f'PROMPT:'
    )

    try:
        import ollama as ollama_client

        response = ollama_client.chat(
            model=config.MODEL_NAME,
            messages=[{'role': 'user', 'content': conversion_instruction}],
            options={
                'num_ctx':     1024,   # Very short context — this is a simple extraction task
                'temperature': 0.3,    # Slightly higher for better descriptor variety
                'num_predict': 150,    # Allow longer for quality descriptors
            }
        )

        raw = response['message']['content'].strip()

        # Strip any accidental preamble the model may add despite instructions
        # Some models prefix their response even when told not to
        for prefix in ['PROMPT:', 'HIGH-QUALITY PROMPT:', 'Image prompt:', 'Here is', "Here's", 'Sure,']:
            if raw.lower().startswith(prefix.lower()):
                raw = raw[len(prefix):].strip()

        # Remove any surrounding quotes the model may have added
        raw = raw.strip('"\'')

        return raw if raw else 'cinematic fantasy scene, dramatic lighting, detailed, sharp focus, 8k'

    except Exception as e:
        # If the Ollama call fails for any reason, use a sensible fallback
        # that will still produce a reasonable fantasy image
        print(f'  [ImageGen] Prompt conversion failed ({e}), using fallback prompt')
        return 'epic fantasy scene, dramatic lighting, detailed environment, cinematic'


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _should_generate(dm_response: str, turn_count: int) -> bool:
    """
    Decides whether to generate an image for this particular turn.

    Returns True only if ALL of the following conditions are met:
      1. SD_ENABLED is True (master switch)
      2. Required libraries (torch, diffusers, Pillow) are all installed
      3. This turn number is a multiple of GENERATE_EVERY_N_TURNS
      4. Either SD_ALWAYS_GENERATE is True, OR the response contains
         at least one IMAGE_TRIGGER_PHRASE

    The trigger phrase check (condition 4) is the most important filter.
    It prevents spending 10+ seconds generating an image for a response like
    "The guard shrugs. Roll for Persuasion." while still generating images
    for rich scene-setting narration.

    Parameters:
      dm_response — The full DM narrative text for this turn
      turn_count  — The current turn number in this session

    Returns True if image generation should proceed, False to skip.
    """
    if not SD_ENABLED:
        return False

    if not (TORCH_AVAILABLE and DIFFUSERS_AVAILABLE and PILLOW_AVAILABLE):
        return False

    # Every-N-turns throttle: only generate on turns divisible by N
    # turn_count of 0 bypasses this (used by the manual 'scene' command)
    if turn_count != 0 and turn_count % GENERATE_EVERY_N_TURNS != 0:
        return False

    if SD_ALWAYS_GENERATE:
        return True

    # Check for visual scene trigger phrases
    lower = dm_response.lower()
    return any(phrase in lower for phrase in IMAGE_TRIGGER_PHRASES)


def _build_filename(sd_prompt: str, in_game_date: str) -> str:
    """
    Builds a descriptive filename for the saved PNG image.

    Format: Year1_Month1_Day1_evening_dark_dungeon_torch_skeleton.png

    The in-game date makes images sortable chronologically.
    The first few SD prompt keywords make it easy to identify the scene
    from the filename alone without opening it.

    Parameters:
      sd_prompt    — The SD prompt used to generate this image
      in_game_date — The current in-game date string

    Returns a filename-safe string ending in .png
    """
    # Clean date: "Year 1, Month 1, Day 1 (evening)" → "Year1_Month1_Day1_evening"
    date_part = re.sub(r'[,\s()]+', '_', in_game_date).strip('_')

    # Take first 4 keywords from the prompt for the label
    keywords  = [w.strip() for w in sd_prompt.split(',') if w.strip()]
    label     = '_'.join(keywords[:4])
    # Remove characters that aren't safe in Windows filenames
    label     = re.sub(r'[^a-zA-Z0-9_\-]', '', label)[:50]

    # Add a timestamp suffix to prevent filename collisions if multiple images
    # are generated in the same turn (e.g. portrait + scene)
    timestamp = datetime.now().strftime('%H%M%S')

    return f'{date_part}_{label}_{timestamp}.png'


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API — called by dm_agent.py
# ═══════════════════════════════════════════════════════════════════════════

def generate_image(dm_response: str, in_game_date: str, turn_count: int) -> str | None:
    """
    Main entry point. Generates a scene image from a DM narrative response.

    Called by dm_agent.py after every DM response. Returns the saved image
    file path so main.py can display it, or None if no image was generated.

    Full pipeline:
      1. Check if image generation should happen this turn
      2. Load the SD pipeline (if not already loaded)
      3. Ask Ollama to convert the narrative into SD keywords
      4. Append style suffix and run through the SD pipeline
      5. Save the output image as a PNG
      6. Return the file path

    Parameters:
      dm_response  — The DM's full narrative text from this turn
      in_game_date — Current in-game date (from world_state.get_current_date_str())
      turn_count   — Current turn number (used for GENERATE_EVERY_N_TURNS throttle)
                     Pass 0 to bypass the throttle (used by manual 'scene' command)

    Returns:
      Full file path of the saved PNG image, or None if skipped/failed.
    """

    # ── Step 1: Should we generate an image this turn? ─────────────────────
    if not _should_generate(dm_response, turn_count):
        return None

    print('\n  [ImageGen] Generating scene image...')

    # ── Step 2: Load the SD pipeline (lazy load on first call) ────────────
    _load_pipeline()
    if _pipeline is None:
        return None  # Loading failed — error already printed in _load_pipeline

    # ── Step 3: Convert narrative → SD prompt via Ollama ──────────────────
    # This is a second Ollama call specifically to extract visual keywords.
    # It uses the same Ollama model but with very different parameters
    # (low temperature, short context, short output).
    print('  [ImageGen] Converting narrative to image prompt...')
    sd_prompt = _narrative_to_sd_prompt(dm_response)
    full_prompt = f'{sd_prompt}, {get_style_suffix()}'
    print(f'  [ImageGen] Prompt: {full_prompt[:90]}...')

    # ── Step 4: Generate the image ─────────────────────────────────────────
    # The pipeline() call is where Stable Diffusion actually runs.
    # It takes the text prompt, converts it to embeddings, starts from random
    # noise, and progressively denoises it over INFERENCE_STEPS iterations
    # to produce a coherent image that matches the prompt.
    try:
        # torch.no_grad() tells PyTorch not to track gradients during this call.
        # We're doing inference (generating), not training, so gradients would
        # just waste memory. This is important for keeping VRAM usage low.
        with torch.no_grad():
            output = _pipeline(
                prompt=full_prompt,
                negative_prompt=NEGATIVE_PROMPT,
                width=IMAGE_WIDTH,
                height=IMAGE_HEIGHT,
                num_inference_steps=INFERENCE_STEPS,
                guidance_scale=CFG_SCALE,
                num_images_per_prompt=1,
            )

        # output.images is a list of PIL Image objects
        # We always generate 1 image so we take index [0]
        generated_image = output.images[0]

    except torch.cuda.OutOfMemoryError:
        # This is the most common failure mode on 10GB cards
        # Give a specific, actionable error message
        print(
            '\n  [ImageGen] OUT OF VRAM ERROR during image generation.'
            '\n  Solutions:'
            '\n    1. Add "set SD_WIDTH=512" and "set SD_HEIGHT=512" before running'
            '\n    2. Add "set SD_STEPS=15" to reduce inference steps'
            '\n    3. Make sure no other GPU programs are running'
            '\n    4. Restart the DM session to clear VRAM'
        )
        return None

    except Exception as e:
        print(f'  [ImageGen] Image generation failed: {e}')
        return None

    # ── Step 5: Save the image to disk ────────────────────────────────────
    os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)
    filename    = _build_filename(sd_prompt, in_game_date)
    output_path = os.path.join(IMAGE_OUTPUT_DIR, filename)

    try:
        generated_image.save(output_path, 'PNG')
        print(f'  [ImageGen] Saved: {filename}')
        return output_path
    except Exception as e:
        print(f'  [ImageGen] Failed to save image: {e}')
        return None


def generate_character_portrait(character_data: dict, in_game_date: str) -> str | None:
    """
    Generates a portrait image for a specific character.

    Called when the player types 'portrait <character name>' in main.py.
    Unlike generate_image() which converts a narrative, this builds the SD
    prompt directly from the character's stored data fields (race, appearance,
    personality) for a more targeted and accurate portrait.

    Parameters:
      character_data — The character dict from WorldState
      in_game_date   — Current in-game date (for the filename)

    Returns the saved portrait file path, or None if generation failed.
    """
    if not SD_ENABLED or not (TORCH_AVAILABLE and DIFFUSERS_AVAILABLE and PILLOW_AVAILABLE):
        return None

    _load_pipeline()
    if _pipeline is None:
        return None

    # Build a portrait-specific prompt from character fields
    # We construct this directly rather than going through Ollama conversion
    # because character data is already structured and we can extract exactly
    # the visual information we need without any ambiguity
    name       = character_data.get('name', 'Unknown')
    race       = character_data.get('race', '')
    occupation = character_data.get('class', character_data.get('occupation', ''))
    appearance = character_data.get('appearance', '')
    
    # Aggressively constrain the appearance field to prevent token overflow
    # The appearance field often contains very detailed descriptions that
    # exceed CLIP's 77-token limit. We need to be very strict here.
    if appearance:
        # Remove newlines and extra whitespace
        appearance = ' '.join(appearance.split())
        # Truncate to ~60 characters maximum (much smaller than before)
        if len(appearance) > 60:
            # Find word boundary for clean break
            appearance = appearance[:60].rsplit(' ', 1)[0]
        # Remove common phrase artifacts
        appearance = appearance.replace(' face and upper body', '').strip()
        appearance = appearance.replace(' portrait', '').strip()
        appearance = appearance.replace(' character', '').strip()
    
    # Start with full body portrait keywords
    prompt_parts = []
    prompt_parts.append('full body portrait,')
    prompt_parts.append('standing,')
    prompt_parts.append('full figure,')
    
    # Add race if available (very concise)
    if race and race.lower() not in ('unknown', 'none', ''):
        prompt_parts.append(f'{race},')
    
    # Add occupation if available (very concise)
    if occupation and occupation.lower() not in ('unknown', 'none', ''):
        prompt_parts.append(f'{occupation},')
    
    # Add appearance (heavily truncated)
    if appearance:
        prompt_parts.append(appearance + ',')
    
    # Add ONLY essential quality markers (keep it minimal)
    prompt_parts.extend([
        'sharp focus,',
        'detailed,',
        'cinematic,',
        'masterpiece',
    ])
    
    portrait_prompt = ' '.join(prompt_parts)
    
    # Enhanced negative prompt to specifically avoid artifacts
    enhanced_negative = (
        NEGATIVE_PROMPT + ', '
        'double face, two faces, multiple faces, '
        'duplicate, mirrored, reflection, '
        'stacked, layered, overlapping, '
        'distorted face, twisted, '
        'extra features, repeated features'
    )

    print(f'\n  [ImageGen] Generating portrait for {name}...')
    print(f'  [ImageGen] Prompt: {portrait_prompt[:80]}...')

    try:
        with torch.no_grad():
            output = _pipeline(
                prompt=portrait_prompt,
                negative_prompt=enhanced_negative,
                width=512,      # Portrait format — taller than wide
                height=768,
                num_inference_steps=INFERENCE_STEPS,
                guidance_scale=CFG_SCALE,
                num_images_per_prompt=1,
            )

        portrait_image = output.images[0]

    except Exception as e:
        print(f'  [ImageGen] Portrait generation failed: {e}')
        return None

    os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)

    # Use the character name in the filename for easy identification
    safe_name   = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    timestamp   = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename    = f'portrait_{safe_name}_{timestamp}.png'
    output_path = os.path.join(IMAGE_OUTPUT_DIR, filename)

    try:
        portrait_image.save(output_path, 'PNG')
        print(f'  [ImageGen] Portrait saved: {filename}')
        return output_path
    except Exception as e:
        print(f'  [ImageGen] Failed to save portrait: {e}')
        return None


def unload_for_llm():
    """
    Frees the SD pipeline from VRAM before Ollama runs.

    Called by dm_agent.py at the START of respond() before the Ollama call,
    so the LLM has the full GPU available. Called automatically — you do not
    need to call this manually.

    After respond() finishes, generate_image() calls _load_pipeline() again
    which reloads SD from the local cache (~5-10 seconds after first load).
    """
    _unload_pipeline()


# ── Ensure output directory exists on import ──────────────────────────────
os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)
