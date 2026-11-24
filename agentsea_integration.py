import os
import json

def integrate_agentsea_skills(agents_dir, registry_path):
    with open(registry_path, "r") as f:
        registry = json.load(f)
        
    agentsea_skills = registry.get("AGENTSEA", [])
    
    for root, dirs, files in os.walk(agents_dir):
        if "agent_config.json" in files:
            config_path = os.path.join(root, "agent_config.json")
            with open(config_path, "r") as cfg_file:
                config = json.load(cfg_file)
            
            if config.get("domain") == "AGENTSEA":
                existing_skills = set(config.get("skills", []))
                existing_skills.update(agentsea_skills)
                config["skills"] = list(existing_skills)
                
                with open(config_path, "w") as cfg_file:
                    json.dump(config, cfg_file, indent=2)

if __name__ == "__main__":
    AGENTS_DIR = "D:/Projects/os/Atlantis_HSL/AGENTS"
    REGISTRY_PATH = "D:/Kane Hackathon/skill_routing_registry.json"
    integrate_agentsea_skills(AGENTS_DIR, REGISTRY_PATH)