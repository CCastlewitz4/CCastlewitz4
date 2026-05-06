# lora_manager.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: One script to train, manage, and activate all three of your
#          image style LoRAs (anime, realistic, cinematic).
#
# USAGE — run from your project root:
#
#   Train all three LoRAs one after another (recommended first run):
#     python lora_manager.py --train-all
#
#   Train just one style:
#     python lora_manager.py --train anime
#     python lora_manager.py --train realistic
#     python lora_manager.py --train cinematic
#
#   Check status of all LoRAs (trained / not trained):
#     python lora_manager.py --status
#
#   Register a LoRA that's already been trained (updates config):
#     python lora_manager.py --register anime
#
# YOUR FOLDER PATHS (set once below, used everywhere):
#   Source images:  the three folders where your images currently live
#   Project root:   where config.py lives
#   LoRA output:    where trained LoRA files are saved
#
# AFTER TRAINING:
#   - Type 'imagestyle' in your game and pick 'anime_lora',
#     'realistic_lora', or 'cinematic_lora'
#   - The correct LoRA loads automatically — no restarts needed
# ─────────────────────────────────────────────────────────────────────────────

import os
import sys
import json
import shutil
import argparse
from pathlib import Path

# ── PROJECT ROOT ───────────────────────────────────────────────────────────
# This is the folder where config.py lives.
PROJECT_ROOT = r'C:\Users\colin\Desktop\DND_AI_DM Backup\DND_AI_DM\dnd_ai_dm'
sys.path.insert(0, PROJECT_ROOT)

import config

# ── YOUR IMAGE FOLDERS ─────────────────────────────────────────────────────
# Where your images currently are. These are the source folders you named.
# Each key matches a style name used throughout this script.
#
# IMPORTANT: These should be the folders containing ONLY images for that style.
# If your images are all in one folder right now, see the note below the dict.
IMAGE_SOURCE_FOLDERS = {
    'anime':     r'C:\\Users\\colin\\Desktop\\DND_AI_DM Backup\\DND_AI_DM\\dnd_ai_dm\\dataset images for training\\character designs\\anime',
    'realistic': r'C:\\Users\\colin\\Desktop\\DND_AI_DM Backup\\DND_AI_DM\\dnd_ai_dm\\dataset images for training\\character designs\\realistic',
    'cinematic': r'C:\\Users\\colin\\Desktop\\DND_AI_DM Backup\\DND_AI_DM\\dnd_ai_dm\\dataset images for training\\character designs\\cinematic',
}
# NOTE: If all your images are in ONE folder called "dataset images for training"
# with no subfolders, run this first to split them:
#   python lora_manager.py --split
# It will show you all images and ask you to assign each to anime/realistic/cinematic.

# ── TRIGGER WORDS ──────────────────────────────────────────────────────────
# These short unique words activate each LoRA in prompts.
# They're automatically prepended to every prompt when that style is active.
TRIGGER_WORDS = {
    'anime':     'animestyle',
    'realistic': 'realisticstyle',
    'cinematic': 'cinematicstyle',
}

# ── TRAINING SETTINGS ─────────────────────────────────────────────────────
# Tuned for RTX 3080 10GB. Edit if needed.
LORA_SETTINGS = {
    'anime': {
        'steps':      200,   # Anime style trains fast — 200 is plenty
        'rank':       8,
        'lr':         1e-4,
        'resolution': 1024,
        'type':       'style',
    },
    'realistic': {
        'steps':      250,   # Realistic needs a few more steps for detail
        'rank':       8,
        'lr':         8e-5,  # Slightly lower LR for photorealistic styles
        'resolution': 1024,
        'type':       'style',
    },
    'cinematic': {
        'steps':      200,
        'rank':       8,
        'lr':         1e-4,
        'resolution': 1024,
        'type':       'style',
    },
}

# ── OUTPUT PATHS ───────────────────────────────────────────────────────────
LORA_OUTPUT_BASE = os.path.join(PROJECT_ROOT, 'data', 'image_lora')
PREPARED_BASE    = os.path.join(PROJECT_ROOT, 'data', 'training', 'image_dataset')


# ══════════════════════════════════════════════════════════════════════════
# HELPER: CHECK DEPENDENCIES
# ══════════════════════════════════════════════════════════════════════════

def check_dependencies() -> bool:
    """
    Checks all Python packages needed for LoRA training are installed.
    Prints clear install instructions for anything missing.
    Returns True if everything is ready, False if setup is needed.
    """
    packages = {
        'torch':        'pip install torch --index-url https://download.pytorch.org/whl/cu124',
        'diffusers':    'pip install diffusers>=0.27.0',
        'transformers': 'pip install transformers',
        'accelerate':   'pip install accelerate',
        'peft':         'pip install peft',
        'PIL':          'pip install Pillow',
    }

    missing = []
    for pkg, install_cmd in packages.items():
        try:
            __import__(pkg)
        except ImportError:
            missing.append((pkg, install_cmd))

    if missing:
        print('\n' + '=' * 60)
        print('MISSING DEPENDENCIES — install these before training:')
        print('=' * 60)
        for pkg, cmd in missing:
            print(f'\n  {pkg}:')
            print(f'    {cmd}')
        print('\nRun all at once:')
        combined = ' && '.join(f'pip install {c.split("pip install ")[1]}' for _, c in missing)
        print(f'  {combined}')
        print('=' * 60)
        return False

    # Check CUDA
    import torch
    if not torch.cuda.is_available():
        print('\nWARNING: No CUDA GPU detected.')
        print('Training will run on CPU — this will take many hours.')
        print('Make sure your NVIDIA drivers and CUDA 12.4 are installed.')
        response = input('Continue on CPU anyway? (y/n): ').strip().lower()
        return response == 'y'

    import torch
    gpu  = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f'\nGPU: {gpu}  ({vram:.1f} GB VRAM)')

    if vram < 8:
        print('WARNING: Less than 8GB VRAM detected.')
        print('Reduce resolution to 768 by editing LORA_SETTINGS above.')

    return True


# ══════════════════════════════════════════════════════════════════════════
# STEP 1: SPLIT IMAGES (if all in one folder)
# ══════════════════════════════════════════════════════════════════════════

def split_images_interactively():
    """
    If all your images are in one folder, this walks you through assigning
    each image to anime / realistic / cinematic by showing the filename
    and asking you to type which style it belongs to.

    Creates the three subfolders and moves images into them.
    """
    source = r'C:\Users\colin\Desktop\DND_AI_DM Backup\DND_AI_DM\dnd_ai_dm\dataset images for training'

    if not os.path.exists(source):
        print(f'Folder not found: {source}')
        return

    exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    images = [f for f in Path(source).iterdir()
              if f.suffix.lower() in exts and f.is_file()]

    if not images:
        print('No images found in the source folder.')
        return

    # Create subfolders
    for style in ('anime', 'realistic', 'cinematic'):
        os.makedirs(os.path.join(source, style), exist_ok=True)

    print(f'\nFound {len(images)} images to sort.')
    print('For each image, type: a (anime) / r (realistic) / c (cinematic) / s (skip)')
    print()

    counts = {'anime': 0, 'realistic': 0, 'cinematic': 0, 'skipped': 0}
    mapping = {'a': 'anime', 'r': 'realistic', 'c': 'cinematic'}

    for i, img_path in enumerate(sorted(images), 1):
        while True:
            choice = input(f'[{i}/{len(images)}] {img_path.name}  → ').strip().lower()
            if choice in mapping:
                dest_folder = os.path.join(source, mapping[choice])
                shutil.copy2(str(img_path), os.path.join(dest_folder, img_path.name))
                counts[mapping[choice]] += 1
                print(f'  → {mapping[choice]}')
                break
            elif choice == 's':
                counts['skipped'] += 1
                break
            else:
                print('  Type a, r, c, or s')

    print(f'\nSorted:')
    for style, count in counts.items():
        print(f'  {style}: {count} images')

    print('\nUpdate IMAGE_SOURCE_FOLDERS in lora_manager.py to point to:')
    for style in ('anime', 'realistic', 'cinematic'):
        print(f"  '{style}': r'{os.path.join(source, style)}'")


# ══════════════════════════════════════════════════════════════════════════
# STEP 2: PREPARE DATASET (resize + caption)
# ══════════════════════════════════════════════════════════════════════════

def prepare_dataset(style: str) -> str:
    """
    Resizes all images for one style to 1024x1024 and creates caption files.

    Caption format for style LoRAs:
      "animestyle, anime art, [filename description], highly detailed, vibrant colors"

    Returns the path to the prepared folder.
    """
    from PIL import Image as PILImage
    import numpy as np

    source_dir  = IMAGE_SOURCE_FOLDERS[style]
    trigger     = TRIGGER_WORDS[style]
    resolution  = LORA_SETTINGS[style]['resolution']
    prepared_dir = os.path.join(PREPARED_BASE, style, 'prepared')

    os.makedirs(prepared_dir, exist_ok=True)

    if not os.path.exists(source_dir):
        print(f'\nERROR: Image folder not found: {source_dir}')
        print(f'Create this folder and add your {style} images to it.')
        print(f'Or run: python lora_manager.py --split')
        return prepared_dir

    exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    images = [f for f in Path(source_dir).iterdir() if f.suffix.lower() in exts]

    if not images:
        print(f'\nNo images found in: {source_dir}')
        return prepared_dir

    print(f'\n[{style.upper()}] Preparing {len(images)} images...')

    if len(images) < 8:
        print(f'  WARNING: Only {len(images)} images. Recommend at least 10 for good results.')

    style_captions = {
        'anime':     f'{trigger}, anime art, vibrant colors, clean lines, expressive, highly detailed',
        'realistic': f'{trigger}, photorealistic, sharp focus, cinematic lighting, highly detailed, 8k',
        'cinematic': f'{trigger}, cinematic photography, volumetric lighting, dramatic composition, 4k, detailed',
    }

    prepared = 0
    for img_path in images:
        try:
            img = PILImage.open(img_path).convert('RGB')

            # Center-crop to square then resize
            w, h    = img.size
            min_dim = min(w, h)
            left    = (w - min_dim) // 2
            top     = (h - min_dim) // 2
            img     = img.crop((left, top, left + min_dim, top + min_dim))
            img     = img.resize((resolution, resolution), PILImage.LANCZOS)

            out_path = os.path.join(prepared_dir, img_path.stem + '.png')
            img.save(out_path, 'PNG')

            # Build caption: base style keywords + filename hint
            desc_hint   = img_path.stem.replace('_', ' ').replace('-', ' ').lower()
            base_caption = style_captions[style]
            caption      = f'{base_caption}, {desc_hint}'

            cap_path = os.path.join(prepared_dir, img_path.stem + '.txt')
            with open(cap_path, 'w', encoding='utf-8') as f:
                f.write(caption)

            prepared += 1

        except Exception as e:
            print(f'  Skipping {img_path.name}: {e}')

    print(f'  Prepared {prepared} images → {prepared_dir}')
    return prepared_dir


# ══════════════════════════════════════════════════════════════════════════
# STEP 3: TRAIN THE LORA
# ══════════════════════════════════════════════════════════════════════════

def train_lora(style: str):
    """
    Runs SDXL LoRA training for one style.
    Calls the image_trainer.py training logic directly.

    After training completes, automatically registers the LoRA in
    config.LORA_REGISTRY so the game can find it.
    """
    import torch
    import torch.nn.functional as F
    from pathlib import Path

    settings     = LORA_SETTINGS[style]
    trigger      = TRIGGER_WORDS[style]
    prepared_dir = os.path.join(PREPARED_BASE, style, 'prepared')
    output_dir   = os.path.join(LORA_OUTPUT_BASE, style)

    os.makedirs(output_dir, exist_ok=True)

    # Check prepared dataset exists
    png_files = list(Path(prepared_dir).glob('*.png')) if os.path.exists(prepared_dir) else []
    if not png_files:
        print(f'\n[{style.upper()}] No prepared images found. Running prepare step first...')
        prepare_dataset(style)
        png_files = list(Path(prepared_dir).glob('*.png'))

    if not png_files:
        print(f'[{style.upper()}] ERROR: Still no images after prepare. Check your source folder.')
        return False

    print(f'\n{"=" * 60}')
    print(f'  Training {style.upper()} LoRA')
    print(f'{"=" * 60}')
    print(f'  Images:       {len(png_files)}')
    print(f'  Trigger word: {trigger}')
    print(f'  Steps:        {settings["steps"]}')
    print(f'  LoRA rank:    {settings["rank"]}')
    print(f'  Resolution:   {settings["resolution"]}x{settings["resolution"]}')
    est = settings['steps'] * 0.15
    print(f'  Est. time:    ~{est:.0f} minutes on RTX 3080')
    print(f'  Output:       {output_dir}')
    print(f'{"=" * 60}\n')

    try:
        from diffusers import AutoencoderKL, DDPMScheduler, UNet2DConditionModel
        from transformers import CLIPTextModel, CLIPTokenizer, CLIPTextModelWithProjection
        from peft import LoraConfig, get_peft_model
        from PIL import Image as PILImage

        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        dtype  = torch.float16 if device == 'cuda' else torch.float32
        res    = settings['resolution']

        print(f'Loading SDXL components on {device.upper()}...')
        print('(First run downloads ~6GB — subsequent runs load from cache instantly)\n')

        base_model = 'stabilityai/stable-diffusion-xl-base-1.0'

        unet = UNet2DConditionModel.from_pretrained(
            base_model, subfolder='unet',
            torch_dtype=dtype, low_cpu_mem_usage=True
        ).to(device)

        tokenizer_1    = CLIPTokenizer.from_pretrained(base_model, subfolder='tokenizer')
        tokenizer_2    = CLIPTokenizer.from_pretrained(base_model, subfolder='tokenizer_2')
        text_encoder_1 = CLIPTextModel.from_pretrained(
            base_model, subfolder='text_encoder', torch_dtype=dtype
        ).to(device)
        text_encoder_2 = CLIPTextModelWithProjection.from_pretrained(
            base_model, subfolder='text_encoder_2', torch_dtype=dtype
        ).to(device)
        vae = AutoencoderKL.from_pretrained(
            base_model, subfolder='vae', torch_dtype=dtype
        ).to(device)
        noise_scheduler = DDPMScheduler.from_pretrained(base_model, subfolder='scheduler')

        # Freeze everything — only LoRA adapter layers will be trained
        for model_part in (unet, text_encoder_1, text_encoder_2, vae):
            model_part.requires_grad_(False)

        # Inject LoRA into UNet attention layers
        lora_cfg = LoraConfig(
            r=settings['rank'],
            lora_alpha=settings['rank'] * 2,
            target_modules=['to_q', 'to_k', 'to_v', 'to_out.0'],
            lora_dropout=0.0,
        )
        unet = get_peft_model(unet, lora_cfg)
        unet.enable_gradient_checkpointing()

        trainable = sum(p.numel() for p in unet.parameters() if p.requires_grad)
        total     = sum(p.numel() for p in unet.parameters())
        print(f'Trainable parameters: {trainable:,} / {total:,} '
              f'({100 * trainable / total:.2f}%)\n')

        # Optimizer — only LoRA params
        optimizer = torch.optim.AdamW(
            [p for p in unet.parameters() if p.requires_grad],
            lr=settings['lr'],
            weight_decay=1e-4,
        )
        from torch.optim.lr_scheduler import CosineAnnealingLR
        lr_sched = CosineAnnealingLR(optimizer, T_max=settings['steps'], eta_min=1e-6)

        # Load + encode all images to latent space (pre-compute to save time)
        print('Encoding training images to latent space...')
        latents_list = []
        for img_path in png_files:
            import numpy as np
            img  = PILImage.open(img_path).convert('RGB').resize((res, res), PILImage.LANCZOS)
            arr  = np.array(img).astype('float32') / 127.5 - 1.0
            tens = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device=device, dtype=dtype)
            with torch.no_grad():
                lat = vae.encode(tens).latent_dist.sample() * vae.config.scaling_factor
            latents_list.append(lat.cpu())

        # Encode all captions
        print('Encoding captions...\n')
        embeds_list = []
        for img_path in png_files:
            cap_path = img_path.with_suffix('.txt')
            caption  = cap_path.read_text(encoding='utf-8').strip() if cap_path.exists() else trigger

            def _enc(tok, enc, text):
                toks = tok(text, padding='max_length', max_length=77,
                           truncation=True, return_tensors='pt')
                toks = {k: v.to(device) for k, v in toks.items()}
                with torch.no_grad():
                    out = enc(**toks, output_hidden_states=True)
                return out.hidden_states[-2].to(dtype=dtype)

            e1 = _enc(tokenizer_1, text_encoder_1, caption)
            e2 = _enc(tokenizer_2, text_encoder_2, caption)
            pe = torch.cat([e1, e2], dim=-1)

            toks2 = tokenizer_2(caption, padding='max_length', max_length=77,
                                truncation=True, return_tensors='pt')
            toks2 = {k: v.to(device) for k, v in toks2.items()}
            with torch.no_grad():
                pool = text_encoder_2(**toks2).text_embeds.to(dtype=dtype)

            embeds_list.append((pe.cpu(), pool.cpu()))

        # ── Training loop ──────────────────────────────────────────────────
        print(f'Starting training loop ({settings["steps"]} steps)...')
        print('Loss should decrease from ~0.4 down toward 0.10-0.15')
        print('Your GPU will run hot — this is normal\n')

        unet.train()
        grad_accum  = 4
        accum_loss  = 0.0
        best_loss   = float('inf')

        for step in range(settings['steps']):
            idx     = step % len(latents_list)
            latent  = latents_list[idx].to(device=device, dtype=dtype)
            pe, pool = embeds_list[idx]
            pe      = pe.to(device=device, dtype=dtype)
            pool    = pool.to(device=device, dtype=dtype)

            noise     = torch.randn_like(latent)
            timesteps = torch.randint(
                0, noise_scheduler.config.num_train_timesteps, (1,), device=device
            ).long()
            noisy = noise_scheduler.add_noise(latent, noise, timesteps)

            time_ids = torch.tensor(
                [[res, res, 0, 0, res, res]], device=device, dtype=dtype
            )

            pred = unet(
                noisy, timesteps,
                encoder_hidden_states=pe,
                added_cond_kwargs={'text_embeds': pool, 'time_ids': time_ids},
            ).sample

            loss = F.mse_loss(pred.float(), noise.float()) / grad_accum
            loss.backward()
            accum_loss += loss.item()

            if (step + 1) % grad_accum == 0:
                torch.nn.utils.clip_grad_norm_(
                    [p for p in unet.parameters() if p.requires_grad], 1.0
                )
                optimizer.step()
                lr_sched.step()
                optimizer.zero_grad()

            if step % 10 == 0:
                avg = accum_loss / max(step % 10 + 1, 1)
                lr_now = lr_sched.get_last_lr()[0] if step > 0 else settings['lr']
                status = ''
                if avg < 0.12:
                    status = '  ✓ Excellent'
                elif avg < 0.18:
                    status = '  ✓ Good'
                elif avg < 0.30:
                    status = '  (still learning...)'
                print(f'  Step {step:4d}/{settings["steps"]}  '
                      f'loss={avg:.4f}  lr={lr_now:.2e}{status}')
                if avg < best_loss:
                    best_loss = avg
                accum_loss = 0.0

            # Save checkpoint every 100 steps
            if step > 0 and step % 100 == 0:
                ckpt = os.path.join(output_dir, f'checkpoint-{step}')
                unet.save_pretrained(ckpt)
                print(f'  Checkpoint saved: checkpoint-{step}')

        # Save final LoRA
        print(f'\nSaving {style} LoRA...')
        unet.save_pretrained(output_dir)

        # Save metadata
        meta = {
            'style':        style,
            'trigger_word': trigger,
            'base_model':   base_model,
            'lora_rank':    settings['rank'],
            'train_steps':  settings['steps'],
            'resolution':   res,
            'n_images':     len(png_files),
            'best_loss':    best_loss,
        }
        with open(os.path.join(output_dir, 'lora_metadata.json'), 'w') as f:
            json.dump(meta, f, indent=2)

        print(f'[{style.upper()}] Training complete! Best loss: {best_loss:.4f}')
        print(f'  Saved to: {output_dir}\n')

        # Register the LoRA so the game can find it
        register_lora(style, output_dir)
        return True

    except torch.cuda.OutOfMemoryError:
        print(f'\nOUT OF VRAM during {style} training.')
        print('Solutions:')
        print('  1. Close other GPU programs (games, browsers with hardware acceleration)')
        print('  2. Lower resolution: edit LORA_SETTINGS[style][resolution] to 768')
        print('  3. Restart your PC to fully clear VRAM then try again')
        return False

    except Exception as e:
        print(f'\n[{style.upper()}] Training failed: {e}')
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════════════════════
# STEP 4: REGISTER — write LoRA path into config.py
# ══════════════════════════════════════════════════════════════════════════

def register_lora(style: str, lora_path: str = None):
    """
    Writes the trained LoRA path into config.py's LORA_REGISTRY dict so
    image_generator.py can find it at runtime.

    This edits config.py directly — it adds/updates the LORA_REGISTRY entry
    for this style. Run automatically after training, or manually with:
      python lora_manager.py --register anime
    """
    if lora_path is None:
        lora_path = os.path.join(LORA_OUTPUT_BASE, style)

    if not os.path.exists(lora_path):
        print(f'LoRA path not found: {lora_path}')
        print('Train the LoRA first, then register.')
        return

    # Map style → preset name used in IMAGE_STYLE_PRESETS and LORA_REGISTRY
    preset_key = f'{style}_lora'

    config_path = os.path.join(PROJECT_ROOT, 'config.py')
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Normalize path for JSON (forward slashes, escaped for Python string)
    norm_path = lora_path.replace('\\', '\\\\')

    # If LORA_REGISTRY is already in config, update it
    if 'LORA_REGISTRY' in content:
        # Check if this style is already registered
        if f"'{preset_key}'" in content:
            # Update existing entry
            import re
            content = re.sub(
                rf"'{preset_key}':\s*r?'[^']*'",
                f"'{preset_key}': '{norm_path}'",
                content
            )
        else:
            # Add new entry to the existing registry dict
            content = content.replace(
                'LORA_REGISTRY: dict = {}',
                f"LORA_REGISTRY: dict = {{'{preset_key}': '{norm_path}'}}"
            )
            # Or if registry already has entries, append
            if f"LORA_REGISTRY: dict = {{'{preset_key}'" not in content:
                content = content.replace(
                    'LORA_REGISTRY: dict = {',
                    f"LORA_REGISTRY: dict = {{'{preset_key}': '{norm_path}', "
                ).replace(
                    f"LORA_REGISTRY: dict = {{'{preset_key}': '{norm_path}', }}",
                    f"LORA_REGISTRY: dict = {{'{preset_key}': '{norm_path}'}}"
                )

    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'  Registered {style} LoRA in config.py')
    print(f'  Preset key: {preset_key}')
    print(f'  Path: {lora_path}')
    print(f'\n  In-game: type "imagestyle" and choose "{preset_key}"')


# ══════════════════════════════════════════════════════════════════════════
# STATUS — show what's trained and what isn't
# ══════════════════════════════════════════════════════════════════════════

def show_status():
    """Shows which LoRAs have been trained and their metadata."""
    print('\n' + '=' * 60)
    print('  LoRA Training Status')
    print('=' * 60)

    for style in ('anime', 'realistic', 'cinematic'):
        lora_dir  = os.path.join(LORA_OUTPUT_BASE, style)
        meta_file = os.path.join(lora_dir, 'lora_metadata.json')
        src_dir   = IMAGE_SOURCE_FOLDERS[style]

        # Count source images
        exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
        n_src = len([f for f in Path(src_dir).iterdir()
                     if f.suffix.lower() in exts]) if os.path.exists(src_dir) else 0

        if os.path.exists(meta_file):
            with open(meta_file) as f:
                meta = json.load(f)
            status   = '✓ TRAINED'
            details  = (f'  Steps: {meta.get("train_steps")}  '
                        f'Images: {meta.get("n_images")}  '
                        f'Best loss: {meta.get("best_loss", "?"):.4f}')
        else:
            status  = '○ NOT TRAINED'
            details = f'  Source images available: {n_src}'

        print(f'\n  {style.upper():<12} {status}')
        print(f'  Trigger word: {TRIGGER_WORDS[style]}')
        print(details)
        if os.path.exists(src_dir):
            print(f'  Source folder: {src_dir}  ({n_src} images)')
        else:
            print(f'  Source folder not found: {src_dir}')

    print('\n' + '=' * 60)

    # Show registry
    registry = getattr(config, 'LORA_REGISTRY', {})
    if registry:
        print('\n  Registered in config.py:')
        for k, v in registry.items():
            exists = '✓' if os.path.exists(v) else '✗ PATH MISSING'
            print(f'    {k}: {exists}')
    else:
        print('\n  No LoRAs registered in config.py yet.')
        print('  They register automatically after training.')
    print()


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Train and manage image style LoRAs for the DnD AI DM'
    )
    parser.add_argument('--train-all',  action='store_true',
                        help='Train all three LoRAs one after another')
    parser.add_argument('--train',      type=str, choices=['anime', 'realistic', 'cinematic'],
                        help='Train one specific style')
    parser.add_argument('--prepare',    type=str, choices=['anime', 'realistic', 'cinematic'],
                        help='Prepare dataset only (resize + caption), no training')
    parser.add_argument('--prepare-all',action='store_true',
                        help='Prepare all three datasets')
    parser.add_argument('--register',   type=str, choices=['anime', 'realistic', 'cinematic'],
                        help='Register an already-trained LoRA into config.py')
    parser.add_argument('--status',     action='store_true',
                        help='Show training status for all three styles')
    parser.add_argument('--split',      action='store_true',
                        help='Interactively sort mixed images into style subfolders')
    args = parser.parse_args()

    if args.status:
        show_status()

    elif args.split:
        split_images_interactively()

    elif args.prepare:
        if not check_dependencies():
            return
        prepare_dataset(args.prepare)

    elif args.prepare_all:
        if not check_dependencies():
            return
        for style in ('anime', 'realistic', 'cinematic'):
            prepare_dataset(style)

    elif args.register:
        register_lora(args.register)

    elif args.train:
        if not check_dependencies():
            return
        prepare_dataset(args.train)
        train_lora(args.train)

    elif args.train_all:
        if not check_dependencies():
            return
        print('\nTraining all three LoRAs in sequence.')
        print('Total estimated time: ~2-4 hours on RTX 3080')
        print('You can leave this running and come back.\n')
        results = {}
        for style in ('anime', 'realistic', 'cinematic'):
            prepare_dataset(style)
            results[style] = train_lora(style)
        print('\n' + '=' * 60)
        print('ALL TRAINING COMPLETE')
        print('=' * 60)
        for style, ok in results.items():
            print(f'  {style:<12} {"✓ Success" if ok else "✗ Failed"}')
        print()
        print('In your game, type "imagestyle" to switch between:')
        print('  anime_lora / realistic_lora / cinematic_lora')

    else:
        # No args — show help + status
        show_status()
        print('COMMANDS:')
        print('  python lora_manager.py --status          Check what is trained')
        print('  python lora_manager.py --split           Sort mixed images into subfolders')
        print('  python lora_manager.py --train anime     Train one style')
        print('  python lora_manager.py --train-all       Train all three (recommended)')
        print()
        print('FIRST TIME? Start here:')
        print('  1. Make sure images are in the right subfolders (run --split if needed)')
        print('  2. python lora_manager.py --status  (check images are found)')
        print('  3. python lora_manager.py --train-all')


if __name__ == '__main__':
    main()
