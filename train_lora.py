import os
import torch
from datasets import load_from_disk
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

# --- paths ---
DATA_DIR = "codesearchnet_python_1pct_filtered"
OUT_DIR = "lora_qwen2_5_coder_1_5b_python"

# --- model ---
MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B"

# Reduce VRAM pressure (important for 5GB)
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

def main():
    ds = load_from_disk(DATA_DIR)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.float16,
    )
    model.config.use_cache = False  # needed for training

    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        init_lora_weights=True,
    )

    sft_config = SFTConfig(
        output_dir=OUT_DIR,
        dataset_text_field="text",
        max_length=512,
        packing=False,
        num_train_epochs=1,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        warmup_ratio=0.03,
        logging_steps=20,
        save_steps=200,
        save_total_limit=2,
        fp16=False,
        bf16=False,
        optim="paged_adamw_8bit",
        report_to=["tensorboard"],
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=ds,
        peft_config=lora_config,
        args=sft_config,
    )
    
    # Force LoRA parameters to float16
    for name, param in trainer.model.named_parameters():
        if param.requires_grad:
            param.data = param.data.to(torch.float16)

    trainer.train()
    trainer.save_model(OUT_DIR)
    tokenizer.save_pretrained(OUT_DIR)
    print("DONE. Saved to:", OUT_DIR)

if __name__ == "__main__":
    main()
