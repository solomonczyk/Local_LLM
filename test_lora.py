import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B"
LORA_PATH = "lora_qwen2_5_coder_1_5b_python"

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True,
)

model = PeftModel.from_pretrained(model, LORA_PATH)
model.eval()

prompt = prompt = """You are a senior software engineer.
Task: Implement a robust Python function parse_money(s: str) -> int that converts strings like:
- "$1,234.56" -> 123456
- "EUR 9.99" -> 999
- "  -12.5 " -> -1250
Rules:
- Return value is in cents.
- Reject ambiguous formats with ValueError.
- Include 8-10 unit tests (pytest).
Write clean, production-quality code with docstrings."""


inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

with torch.no_grad():
    output = model.generate(
        **inputs,
        max_new_tokens=200,
        do_sample=True,
        temperature=0.2,
        top_p=0.95,
        pad_token_id=tokenizer.eos_token_id,
    )


print(tokenizer.decode(output[0], skip_special_tokens=True))
