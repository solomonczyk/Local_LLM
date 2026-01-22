from datasets import load_from_disk

SRC = "F:/Dev/Projects/LLM_local/codesearchnet_python_1pct"
DST = "F:/Dev/Projects/LLM_local/codesearchnet_python_1pct_filtered"

ds = load_from_disk(SRC)
cols = set(ds.column_names)

code_col = next(
    (c for c in ["func_code_string", "code", "whole_func_string", "original_string"] if c in cols),
    None
)
doc_col = next(
    (c for c in ["func_documentation_string", "docstring", "docstring_summary"] if c in cols),
    None
)

if code_col is None:
    raise ValueError(f"No code column found. Have: {sorted(cols)}")

def build_text(example):
    code = (example.get(code_col) or "").strip()
    doc = (example.get(doc_col) or "").strip() if doc_col else ""
    if doc:
        text = (
            "### Task\n"
            "Write Python code for the following description.\n\n"
            f"{doc}\n\n"
            "### Solution\n"
            f"{code}\n"
        )
    else:
        text = f"{code}\n"
    return {"text": text}

ds = ds.map(build_text, remove_columns=[c for c in ds.column_names if c != "text"])
ds.save_to_disk(DST)

print("saved with text ->", DST, "rows:", len(ds))
