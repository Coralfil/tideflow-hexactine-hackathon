import json
import os
import urllib.request
import urllib.error
from pathlib import Path
import shutil

# The base hackathon directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / ".models"

QWEN_URL = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
QWEN_FILENAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"

def download_portable_model():
    """Download the Qwen 2.5 0.5B model for 100% offline portable usage."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / QWEN_FILENAME
    
    if model_path.exists() and model_path.stat().st_size > 300_000_000:
        print(f"[Agent Setup] Portable model already exists at {model_path.name}")
        return True

    print(f"[Agent Setup] Downloading lightweight portable agent brain (Qwen 0.5B)...")
    print(f"[Agent Setup] This is a ~390MB download and only happens once.")
    try:
        with urllib.request.urlopen(QWEN_URL) as response, open(model_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        print(f"[Agent Setup] Successfully downloaded to {model_path}")
        return True
    except Exception as e:
        print(f"[Agent Setup] Failed to download portable model: {e}")
        if model_path.exists():
            model_path.unlink()
        return False

def ensure_api_secrets():
    """Create a placeholder agent_secrets.json if Ollama isn't used or for external integrations."""
    secrets_dir = BASE_DIR / ".testmuai" / "variables"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    secrets_file = secrets_dir / "agent_secrets.json"
    
    if not secrets_file.exists():
        print("[Agent Setup] Creating placeholder agent_secrets.json for API keys.")
        payload = {
            "OPENAI_API_KEY": {"value": "", "secret": True},
            "ANTHROPIC_API_KEY": {"value": "", "secret": True},
            "ATLANTIS_API_KEY": {"value": "", "secret": True}
        }
        secrets_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        print("[Agent Setup] agent_secrets.json already exists.")

if __name__ == "__main__":
    has_local = download_portable_model()
    ensure_api_secrets()
    if not has_local:
        print("[Agent Setup] WARNING: Could not setup local portable model. Ensure agent_secrets.json is populated for cloud inference.")
    else:
        print("[Agent Setup] Portable offline environment is 100% ready.")
