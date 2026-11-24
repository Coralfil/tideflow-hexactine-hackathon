import os
import json

def get_agent_files(base_dirs, exclude_dirs):
    agent_files = []
    agent_prompts = []
    
    for base_dir in base_dirs:
        for root, dirs, files in os.walk(base_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not any(ex in os.path.join(root, d).lower() for ex in exclude_dirs)]
            
            # Check if we are inside an agent directory
            if ".agents" in root.lower() or "\\agents" in root.lower() or "/agents" in root.lower():
                for file in files:
                    if file.endswith(".json") and ("agent" in file.lower() or "config" in file.lower()):
                        agent_files.append(os.path.join(root, file))
                    elif file.endswith(".md") and ("prompt" in file.lower() or "instruction" in file.lower() or "system" in file.lower()):
                        agent_prompts.append(os.path.join(root, file))
                        
    return agent_files, agent_prompts

def update_agent_json(file_path, registry_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        updated = False
        if isinstance(data, dict):
            if data.get("routing_registry") != registry_path:
                data["routing_registry"] = registry_path
                updated = True
            if data.get("synchronicity_protocol") != "strict_json_handoff":
                data["synchronicity_protocol"] = "strict_json_handoff"
                updated = True
                
        if updated:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
    except Exception as e:
        print(f"Error processing JSON {file_path}: {e}")
    return False

def update_agent_prompt(file_path, registry_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        directive = f"""
### Skill Attribution & Routing Architecture
- **Registry Reference**: `{registry_path}`
- **Protocol**: Integrated Synchronicity (Strict JSON Handoff Contracts required for subagent delegation).
"""
        if "Skill Attribution & Routing Architecture" not in content:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write("\n" + directive)
            return True
    except Exception as e:
        print(f"Error processing Prompt {file_path}: {e}")
    return False

def main():
    base_dirs = [r"D:\Projects", r"C:\Users\seafa\.gemini"]
    exclude_dirs = ["endosaurus", "node_modules", ".git", ".vercel", "temp_skills"]
    registry_path = r"D:\Kane Hackathon\skill_routing_registry.json"
    
    print("Scanning for agent configurations and prompts...")
    agent_files, agent_prompts = get_agent_files(base_dirs, exclude_dirs)
    
    print(f"Found {len(agent_files)} JSON configs and {len(agent_prompts)} Markdown prompts.")
    
    json_updates = 0
    for af in agent_files:
        if update_agent_json(af, registry_path):
            json_updates += 1
            
    prompt_updates = 0
    for ap in agent_prompts:
        if update_agent_prompt(ap, registry_path):
            prompt_updates += 1
            
    print(f"Successfully updated {json_updates} JSON configurations.")
    print(f"Successfully updated {prompt_updates} Markdown prompts.")

if __name__ == "__main__":
    main()
