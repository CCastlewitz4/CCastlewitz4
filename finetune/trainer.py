# finetune/trainer.py
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE: Fine-tunes Llama 3.1-8B-Instruct on your DnD training dataset
#          using QLoRA (Quantized Low-Rank Adaptation).
#
# OPTIMIZED FOR: RTX 3080 10GB VRAM + AMD Ryzen 7 3800X
#
# WHY QLORA INSTEAD OF LORA?
#   Standard LoRA loads the model in 16-bit (float16) precision.
#   Llama 3.1-8B in float16 = ~16GB VRAM just to load — more than your 10GB.
#
#   QLoRA solves this by loading the BASE model in 4-bit precision (~4-5GB),
#   then adding small 16-bit LoRA adapter layers on top (~1-2GB).
#   Total VRAM used: ~6-9GB — fits comfortably in your 10GB.
#
#   Quality trade-off: QLoRA is ~95-98% as good as standard LoRA for
#   style/behavior fine-tuning tasks like DM persona training.
#   The difference is essentially imperceptible for creative text generation.
#
# HOW THE FULL PIPELINE WORKS:
#   1. video_processor.py  → downloads/transcribes DnD videos to JSON
#   2. dataset_builder.py  → converts transcripts to training pairs (JSONL)
#   3. THIS FILE           → loads pairs, fine-tunes the model, saves adapter
#   4. (manual step)       → merge adapter + convert to GGUF for Ollama
#
# EXPECTED TRAINING TIME ON RTX 3080:
#   ~100 training pairs  → 30-60 minutes
#   ~500 training pairs  → 2-4 hours
#   ~2000 training pairs → 8-15 hours
#
# LOCATION: dnd_ai_dm/finetune/trainer.py
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os

# ── Path fix: ensures imports work from any working directory ──────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training

import config


# ── Hardware check ─────────────────────────────────────────────────────────
# Run this before anything else. If CUDA is not available, the training will
# run on CPU which is 10-50x slower and may take days instead of hours.
def check_hardware():
    """
    Verifies that PyTorch can see your RTX 3080 and reports VRAM available.
    Exits with a helpful message if CUDA is not detected.
    """
    if not torch.cuda.is_available():
        print("=" * 60)
        print("ERROR: CUDA GPU not detected by PyTorch.")
        print("Fine-tuning on CPU is possible but extremely slow.")
        print("")
        print("To fix this:")
        print("1. Install CUDA 12.4 from: https://developer.nvidia.com/cuda-12-4-0-download-archive")
        print("2. Reinstall PyTorch with CUDA:")
        print("   python -m pip install torch --index-url https://download.pytorch.org/whl/cu124")
        print("3. Restart your terminal and try again.")
        print("=" * 60)
        response = input("Continue on CPU anyway? This will be very slow. (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
        return False

    gpu_name = torch.cuda.get_device_name(0)
    vram_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    vram_free = (torch.cuda.get_device_properties(0).total_memory -
                 torch.cuda.memory_allocated(0)) / 1024**3

    print(f"GPU detected:   {gpu_name}")
    print(f"Total VRAM:     {vram_total:.1f} GB")
    print(f"Available VRAM: {vram_free:.1f} GB")
    print()
    return True


# ── Dynamic QLoRA Hyperparameters ──────────────────────────────────────────
# All values are overridable via environment variables before running.
# The defaults below are specifically tuned for 10GB VRAM (RTX 3080).
#
# To override, set before running:
#   Windows: set LORA_RANK=16 && python finetune/trainer.py
#   Linux:   LORA_RANK=16 python finetune/trainer.py

# LORA_RANK: Size of the adapter matrices.
# Lower = less VRAM, less learning capacity.
# 8 is safe for 10GB. Try 16 if you have headroom after loading.
LORA_RANK = int(os.getenv('LORA_RANK', '8'))

# LORA_ALPHA: Scaling factor. Typically 2x the rank.
# Controls how strongly the LoRA updates affect the model.
LORA_ALPHA = int(os.getenv('LORA_ALPHA', '16'))

# LORA_DROPOUT: Regularization to prevent overfitting on small datasets.
# 0.05 is a safe default. Raise to 0.1 if your dataset is under 100 pairs.
LORA_DROPOUT = float(os.getenv('LORA_DROPOUT', '0.05'))

# TRAIN_EPOCHS: How many times to loop through the full training dataset.
# 1-3 is enough for style adaptation. More = overfitting risk.
TRAIN_EPOCHS = int(os.getenv('TRAIN_EPOCHS', '2'))

# BATCH_SIZE: Examples processed per GPU step.
# MUST be 1 for RTX 3080 10GB with QLoRA to avoid out-of-memory.
# Do NOT increase this — use GRAD_ACCUM_STEPS instead.
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '1'))

# GRAD_ACCUM_STEPS: Simulates a larger batch without using more VRAM.
# Effective batch size = BATCH_SIZE x GRAD_ACCUM_STEPS = 1 x 8 = 8
# This tells the optimizer to accumulate 8 steps of gradients before updating.
GRAD_ACCUM_STEPS = int(os.getenv('GRAD_ACCUM_STEPS', '8'))

# LEARNING_RATE: How fast the adapter weights change each step.
# 2e-4 is the well-tested default for QLoRA. Lower = safer but slower.
LEARNING_RATE = float(os.getenv('LR', '2e-4'))

# MAX_SEQ_LEN: Maximum token length per training example.
# 512 tokens ~= 350-400 words. Sufficient for most DnD turn/response pairs.
# Reduce to 256 if you get out-of-memory errors.
MAX_SEQ_LEN = int(os.getenv('MAX_SEQ_LEN', '512'))

# BASE_MODEL_ID: The Hugging Face model ID to fine-tune.
# This must match the base model your Ollama version uses.
# You will need a free Hugging Face account and to accept the Llama 3.1 license.
# Get your token at: https://huggingface.co/settings/tokens
BASE_MODEL_ID = os.getenv('BASE_MODEL_ID', 'meta-llama/Meta-Llama-3.1-8B-Instruct')

# ADAPTER_OUTPUT_DIR: Where the trained LoRA adapter files are saved.
# The adapter is only ~100-300MB (much smaller than the 4-5GB base model).
ADAPTER_OUTPUT_DIR = os.path.join(config.BASE_DIR, 'data', 'lora_adapter')


# ── 4-bit Quantization Config ──────────────────────────────────────────────
def build_bnb_config() -> BitsAndBytesConfig:
    """
    Builds the BitsAndBytes quantization configuration for 4-bit loading.

    This is the core of QLoRA. Instead of loading 8 billion parameters
    as 16-bit floats (2 bytes each = 16GB), we load them as 4-bit integers
    (~0.5 bytes each = ~4-5GB). The model loses very little quality because:

    - load_in_4bit=True:
        Loads the entire base model in NF4 (NormalFloat4) format.
        NF4 is specially designed for neural network weight distributions
        and preserves quality better than naive 4-bit rounding.

    - bnb_4bit_compute_dtype=torch.float16:
        Even though weights are STORED in 4-bit, all MATH is done in 16-bit.
        Before each computation, weights are temporarily dequantized to float16,
        the math is done, and the result is quantized back.
        This gives near-float16 quality with 4-bit storage costs.

    - bnb_4bit_quant_type='nf4':
        NormalFloat4 quantization — specifically optimized for the normal
        distribution that neural network weights follow. Better than standard
        int4 quantization for LLM weights.

    - bnb_4bit_use_double_quant=True:
        Quantizes the quantization constants themselves (a second round of
        compression). Saves another ~0.4 bits per parameter on average.
        Adds a tiny bit of extra computation but meaningfully reduces VRAM.
    """
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True,
    )


# ── Dataset Loading ────────────────────────────────────────────────────────
def load_training_data(dataset_path: str) -> Dataset:
    """
    Reads the JSONL training file and converts it to a Hugging Face Dataset.

    Each line in the JSONL file is one training pair:
      {"instruction": "player action text", "input": "", "output": "dm response text"}

    The Dataset object is what the Trainer class iterates over during training.
    It handles shuffling, batching, and efficient data loading automatically.

    Parameters:
      dataset_path — Full path to the .jsonl file from dataset_builder.py

    Returns a Hugging Face Dataset object with three columns:
      'instruction', 'input', 'output'
    """
    records = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f'  WARNING: Skipping malformed line {line_num}: {e}')

    print(f'Loaded {len(records)} training examples from dataset.')
    if len(records) == 0:
        raise ValueError(
            'Dataset is empty! Run finetune/dataset_builder.py first '
            'to generate training data from your transcripts.'
        )
    return Dataset.from_list(records)


# ── Prompt Formatting ──────────────────────────────────────────────────────
def format_and_tokenize(example: dict, tokenizer) -> dict:
    """
    Formats a single training pair into the Llama 3.1 Instruct chat template
    and tokenizes it into integer token IDs for training.

    WHY THIS FORMAT?
    Llama 3.1-Instruct was trained with a specific conversation template
    using special tokens to mark roles (user vs assistant). Fine-tuning
    with the same template teaches the model to respond correctly when the
    same template is used during inference (which Ollama uses automatically).

    The template looks like:
      <|begin_of_text|>
      <|start_header_id|>user<|end_header_id|>
      [player's action]
      <|eot_id|>
      <|start_header_id|>assistant<|end_header_id|>
      [DM's response]
      <|eot_id|>

    After tokenization, we set labels = input_ids. This tells the trainer
    to compute loss on the ENTIRE sequence (both user and assistant parts).
    The model learns to generate the full conversation, which improves
    its understanding of when to start and stop responding.

    Parameters:
      example   — One training pair dict from the dataset
      tokenizer — The loaded Llama 3.1 tokenizer

    Returns a dict with 'input_ids', 'attention_mask', 'labels' as lists.
    """
    # Build the full chat-formatted prompt string
    prompt = (
        f"<|begin_of_text|>"
        f"<|start_header_id|>user<|end_header_id|>\n"
        f"{example.get('instruction', '')}"
        f"<|eot_id|>"
        f"<|start_header_id|>assistant<|end_header_id|>\n"
        f"{example.get('output', '')}"
        f"<|eot_id|>"
    )

    # Tokenize: convert the string to a list of integer token IDs
    # truncation=True:    cut at MAX_SEQ_LEN tokens (protects against VRAM overflow)
    # padding='max_length': pad short examples so all batches are the same size
    # return_tensors=None: return plain Python lists (not tensors) for Dataset compatibility
    tokens = tokenizer(
        prompt,
        truncation=True,
        max_length=MAX_SEQ_LEN,
        padding='max_length',
        return_tensors=None
    )

    # labels = input_ids: the model predicts each next token in the sequence.
    # The training loss is computed by comparing predicted tokens to the labels.
    tokens['labels'] = tokens['input_ids'].copy()

    return tokens


# ── Main Training Function ─────────────────────────────────────────────────
def run_finetuning(dataset_path: str = None):
    """
    The main QLoRA fine-tuning pipeline. Call this to start training.

    Full workflow:
      1. Check hardware (GPU/CUDA detection)
      2. Locate or auto-find the training dataset
      3. Load the Llama tokenizer
      4. Load Llama 3.1-8B in 4-bit quantization (fits in 10GB VRAM)
      5. Prepare the model for QLoRA training
      6. Apply LoRA adapter layers to attention projection matrices
      7. Tokenize and format the training dataset
      8. Configure training arguments (batch size, learning rate, etc.)
      9. Run the Trainer training loop
      10. Save the LoRA adapter weights to disk

    Parameters:
      dataset_path — Optional path to the .jsonl training file.
                     Defaults to data/training/dnd_training.jsonl
    """

    # ── Step 1: Hardware check ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("DnD AI DM — QLoRA Fine-Tuning")
    print("Optimized for RTX 3080 10GB")
    print("=" * 60 + "\n")

    using_gpu = check_hardware()

    # ── Step 2: Locate dataset ─────────────────────────────────────────────
    if dataset_path is None:
        dataset_path = os.path.join(config.TRAINING_DIR, 'dnd_training.jsonl')

    if not os.path.exists(dataset_path):
        raise FileNotFoundError(
            f"\nTraining dataset not found at: {dataset_path}\n"
            f"You need to run these first:\n"
            f"  1. python finetune/video_processor.py\n"
            f"  2. python finetune/dataset_builder.py\n"
        )

    print(f"Training dataset: {dataset_path}")

    # ── Step 3: Load tokenizer ─────────────────────────────────────────────
    # The tokenizer converts text strings into integer token IDs.
    # It must exactly match the base model — using the wrong tokenizer
    # will produce garbage output even if training completes successfully.
    #
    # NOTE: On first run, this downloads ~500MB of tokenizer files.
    # You may be prompted to log in to Hugging Face:
    #   1. Create a free account at https://huggingface.co
    #   2. Accept the Llama 3.1 license at https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct
    #   3. Get your token at https://huggingface.co/settings/tokens
    #   4. Run: python -c "from huggingface_hub import login; login()" and paste your token
    print("\nLoading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)

    # Llama 3.1 has no explicit pad token — we use the EOS token instead.
    # This is required for batching to work correctly.
    tokenizer.pad_token = tokenizer.eos_token

    # Set padding to the LEFT side for decoder-only models like Llama.
    # Left padding means the actual content is right-aligned, which is
    # what causal attention masks expect during training.
    tokenizer.padding_side = 'left'
    print("Tokenizer loaded.")

    # ── Step 4: Load base model in 4-bit quantization ─────────────────────
    # This is the most memory-intensive step. The 4-bit config (built above)
    # reduces the ~16GB float16 model to ~4-5GB of quantized weights.
    #
    # device_map='auto': automatically places layers across GPU and CPU RAM.
    # With 10GB VRAM, almost all layers will fit on GPU. Any overflow goes
    # to system RAM (much slower but prevents crashes).
    print("\nLoading Llama 3.1-8B in 4-bit quantization...")
    print("(First run downloads ~4-5GB of model files — this may take a while)")

    bnb_config = build_bnb_config()

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        quantization_config=bnb_config,     # Use 4-bit quantization
        device_map='auto',                   # Auto-distribute across GPU/CPU
        torch_dtype=torch.float16,           # Compute dtype for non-quantized ops
        low_cpu_mem_usage=True,              # Load model layer-by-layer to save RAM during loading
    )
    print("Base model loaded.")

    # ── Step 5: Prepare model for QLoRA training ───────────────────────────
    # prepare_model_for_kbit_training() does two important things:
    #
    # 1. Enables gradient checkpointing:
    #    Instead of storing ALL intermediate activations in VRAM during the
    #    forward pass (needed for backpropagation), it recomputes them on
    #    demand during backpropagation. This trades compute time for VRAM —
    #    roughly 30% slower but saves ~30-40% of activation memory.
    #    Essential for fitting 8B parameters in 10GB.
    #
    # 2. Casts normalization layers to float32:
    #    LayerNorm and other normalization layers need higher precision to
    #    produce stable gradients. This is critical for training stability
    #    when the base model weights are in 4-bit.
    model = prepare_model_for_kbit_training(model)
    print("Model prepared for QLoRA training.")

    # ── Step 6: Apply LoRA adapter layers ─────────────────────────────────
    # LoRA works by inserting two small matrices (A and B) alongside each
    # targeted weight matrix W in the model. During training, only A and B
    # are updated; W remains frozen (unchanged) in 4-bit.
    #
    # The update applied to W during inference is: W + (A × B) × (alpha/rank)
    #
    # target_modules: which attention weight matrices to apply LoRA to.
    # q_proj = Query projection  (what the model asks about)
    # k_proj = Key projection    (what the model matches against)
    # v_proj = Value projection  (what information to retrieve)
    # o_proj = Output projection (how to combine attention heads)
    # These four matrices control most of the model's language generation behavior.
    # Adding gate_proj/up_proj/down_proj targets the feed-forward layers too
    # for deeper style adaptation, but uses slightly more VRAM.
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=[
            'q_proj',
            'k_proj',
            'v_proj',
            'o_proj',
        ],
        bias='none',            # Don't train bias terms (saves a tiny amount of VRAM)
        inference_mode=False,   # Set to training mode
    )

    model = get_peft_model(model, lora_config)

    # Print how many parameters are actually being trained
    # Should be ~0.5-1% of total parameters — everything else is frozen
    model.print_trainable_parameters()

    # ── Step 7: Prepare and tokenize the dataset ───────────────────────────
    print("\nLoading and tokenizing training data...")
    raw_dataset = load_training_data(dataset_path)

    # Apply format_and_tokenize to every example in the dataset
    # remove_columns: drop the original text columns (we only need token IDs for training)
    # desc: shows a progress bar with this label
    tokenized_dataset = raw_dataset.map(
        lambda example: format_and_tokenize(example, tokenizer),
        remove_columns=raw_dataset.column_names,
        desc='Tokenizing examples'
    )
    print(f"Dataset tokenized: {len(tokenized_dataset)} examples ready.")

    # ── Step 8: Configure training arguments ──────────────────────────────
    os.makedirs(ADAPTER_OUTPUT_DIR, exist_ok=True)

    # Calculate and display estimated training time
    steps_per_epoch = len(tokenized_dataset) // (BATCH_SIZE * GRAD_ACCUM_STEPS)
    total_steps = steps_per_epoch * TRAIN_EPOCHS
    estimated_minutes = total_steps * 0.3  # rough estimate: ~0.3 min per step on RTX 3080
    print(f"\nEstimated training: ~{estimated_minutes:.0f} minutes ({total_steps} steps)")

    training_args = TrainingArguments(
        output_dir=ADAPTER_OUTPUT_DIR,

        # ── Epochs and batch settings ─────────────────────────────────────
        num_train_epochs=TRAIN_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,           # 1 for 10GB VRAM
        gradient_accumulation_steps=GRAD_ACCUM_STEPS,     # Effective batch = 8

        # ── Memory optimization flags ─────────────────────────────────────
        # gradient_checkpointing: recompute activations instead of storing them
        # Saves ~30-40% VRAM at the cost of ~30% slower training
        gradient_checkpointing=True,

        # fp16: train in float16 instead of float32
        # Cuts VRAM usage for gradient storage roughly in half
        # Only use fp16 (not bf16) on RTX 3080 — bf16 requires Ampere A-series chips
        fp16=True if using_gpu else False,

        # ── Learning rate settings ────────────────────────────────────────
        learning_rate=LEARNING_RATE,

        # warmup_ratio: spend the first 3% of steps gradually increasing LR
        # Prevents large gradient updates at the start from destabilizing training
        warmup_ratio=0.03,

        # lr_scheduler_type: cosine decay reduces LR smoothly as training progresses
        # This avoids overshooting the optimal adapter weights near the end
        lr_scheduler_type='cosine',

        # ── Logging and checkpointing ─────────────────────────────────────
        logging_steps=10,                   # Print training loss every 10 steps
        save_steps=50,                      # Save a checkpoint every 50 steps
        save_total_limit=2,                 # Keep only the 2 most recent checkpoints
        report_to='none',                   # Disable wandb/tensorboard (no account needed)

        # ── Miscellaneous ─────────────────────────────────────────────────
        dataloader_pin_memory=False,        # Disable pin_memory for stability on Windows
        dataloader_num_workers=0,           # Single-threaded data loading (safer on Windows)
        remove_unused_columns=False,        # Keep all columns until we explicitly remove them
        group_by_length=True,               # Group similar-length examples together (faster)
    )

    # ── Step 9: Run training ───────────────────────────────────────────────
    # DataCollatorForLanguageModeling handles batching automatically.
    # mlm=False means causal language modeling (next-token prediction),
    # not masked language modeling (like BERT). Llama is causal.
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    print("\n" + "=" * 60)
    print("Starting QLoRA fine-tuning...")
    print(f"  Model:          {BASE_MODEL_ID}")
    print(f"  Quantization:   4-bit NF4 QLoRA")
    print(f"  LoRA rank:      {LORA_RANK}")
    print(f"  Epochs:         {TRAIN_EPOCHS}")
    print(f"  Batch size:     {BATCH_SIZE} (effective: {BATCH_SIZE * GRAD_ACCUM_STEPS})")
    print(f"  Learning rate:  {LEARNING_RATE}")
    print(f"  Max seq length: {MAX_SEQ_LEN} tokens")
    print(f"  Training pairs: {len(tokenized_dataset)}")
    print(f"  Output dir:     {ADAPTER_OUTPUT_DIR}")
    print("=" * 60)
    print()
    print("Watch the 'loss' value — it should decrease over time.")
    print("A good final loss is below 1.0. Under 0.5 is excellent.")
    print("Your GPU will run hot and loud — this is expected.")
    print()

    trainer.train()

    # ── Step 10: Save the LoRA adapter ────────────────────────────────────
    # save_pretrained() saves ONLY the small adapter weights (~100-300MB),
    # not the 4-5GB base model. The adapter is what you need to keep.
    print("\nSaving LoRA adapter...")
    model.save_pretrained(ADAPTER_OUTPUT_DIR)
    tokenizer.save_pretrained(ADAPTER_OUTPUT_DIR)

    print("\n" + "=" * 60)
    print("FINE-TUNING COMPLETE!")
    print(f"LoRA adapter saved to: {ADAPTER_OUTPUT_DIR}")
    print()
    print("NEXT STEPS TO USE WITH OLLAMA:")
    print()
    print("1. Merge the adapter into the base model:")
    print("   Run: python finetune/merge_adapter.py")
    print()
    print("2. Convert the merged model to GGUF format:")
    print("   See the guide for llama.cpp conversion instructions.")
    print()
    print("3. Create an Ollama Modelfile pointing to your GGUF file")
    print("   and update config.py with the new model name.")
    print("=" * 60)


# ── Adapter Merging Helper ─────────────────────────────────────────────────
def merge_and_save():
    """
    Merges the trained LoRA adapter back into the base model weights.

    WHY MERGE?
    During training, the LoRA adapter sits alongside the frozen base model.
    For inference you can use them separately (PEFT handles this), but to
    use the fine-tuned model with Ollama you need a single merged model file
    that can be converted to GGUF format.

    The merge operation computes:
      W_merged = W_original + (A × B) × (alpha/rank)

    for every adapted weight matrix, producing a standard model with the
    adapter's learned behavior baked in permanently.

    VRAM NOTE: Merging requires loading the base model in float16 (~16GB).
    If this runs out of VRAM, use CPU merging by removing device_map='auto'
    and letting it run on RAM (slow but works with 32GB+ system RAM).
    """
    print("Merging LoRA adapter into base model for Ollama conversion...")

    if not os.path.exists(ADAPTER_OUTPUT_DIR):
        raise FileNotFoundError(
            f"No adapter found at {ADAPTER_OUTPUT_DIR}. Run training first."
        )

    from peft import PeftModel

    MERGED_OUTPUT_DIR = os.path.join(config.BASE_DIR, 'data', 'merged_model')
    os.makedirs(MERGED_OUTPUT_DIR, exist_ok=True)

    # Load base model in float16 for merging (not 4-bit — merging needs full precision)
    print("Loading base model in float16 for merging...")
    print("(This requires ~16GB of VRAM or system RAM)")
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        torch_dtype=torch.float16,
        device_map='cpu',       # Merge on CPU to avoid VRAM overflow
        low_cpu_mem_usage=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)

    # Load the trained adapter on top of the base model
    print("Loading LoRA adapter...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_OUTPUT_DIR)

    # Merge adapter weights into the base model
    print("Merging adapter into base model (this takes a few minutes)...")
    model = model.merge_and_unload()

    # Save the merged model
    print(f"Saving merged model to: {MERGED_OUTPUT_DIR}")
    model.save_pretrained(MERGED_OUTPUT_DIR, safe_serialization=True)
    tokenizer.save_pretrained(MERGED_OUTPUT_DIR)

    print("\nMerge complete!")
    print(f"Merged model saved to: {MERGED_OUTPUT_DIR}")
    print()
    print("Next: Convert to GGUF using llama.cpp:")
    print("  git clone https://github.com/ggerganov/llama.cpp")
    print("  cd llama.cpp && pip install -r requirements.txt")
    print("  python convert_hf_to_gguf.py --outtype q4_K_M \\")
    print(f"    {MERGED_OUTPUT_DIR} \\")
    print("    --outfile data/dnd_dm_finetuned.gguf")
    print()
    print("Then create an Ollama Modelfile and register it:")
    print("  echo 'FROM ./data/dnd_dm_finetuned.gguf' > Modelfile")
    print("  ollama create dnd-dm -f Modelfile")
    print("  Then update config.py: MODEL_NAME = 'dnd-dm'")


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'merge':
        # Run: python finetune/trainer.py merge
        merge_and_save()
    else:
        # Run: python finetune/trainer.py
        run_finetuning()
