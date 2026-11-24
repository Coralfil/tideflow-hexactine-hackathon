import json
import os
import urllib.request
import urllib.error
from pathlib import Path

# The base hackathon directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

def check_ollama_and_pull():
    """Check if local Ollama is running and pull the lightweight glyph model."""
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2.0) as response:
            if response.status == 200:
                print("[Agent Setup] Local Ollama detected.")
                # Trigger a pull for qwen2.5:0.5b (the glyph model)
                print("[Agent Setup] Ensuring glyph model 'qwen2.5:0.5b' is available...")
                pull_req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/pull",
                    data=json.dumps({"name": "qwen2.5:0.5b"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(pull_req, timeout=10.0) as pull_resp:
                    if pull_resp.status == 200:
                        print("[Agent Setup] Glyph model provisioned successfully.")
                return True
    except Exception as e:
        print(f"[Agent Setup] Local Ollama not reachable: {e}")
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
    has_local = check_ollama_and_pull()
    ensure_api_secrets()
    if not has_local:
        print("[Agent Setup] WARNING: No local Ollama. Ensure agent_secrets.json is populated for cloud inference.")
