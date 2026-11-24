import os
import glob
import json

batches = glob.glob(r"D:\Kane Hackathon\attribution_batch_*.md")

domain_map = {
    "GLOBAL": [],
    "AGENTSEA": [],
    "PROJECT-SPECIFIC": [],
    "UNSLOTH": []
}

for batch_file in batches:
    with open(batch_file, 'r', encoding='utf-8') as f:
        current_domain = None
        for line in f:
            line = line.strip()
            if line.endswith(":"):
                current_domain = line[:-1]
            elif line.startswith("- ") and "(None)" not in line:
                skill = line[2:].split(' ')[0].strip() # strip out comments if any
                if current_domain in domain_map and skill not in domain_map[current_domain]:
                    domain_map[current_domain].append(skill)

registry_path = r"D:\Kane Hackathon\skill_routing_registry.json"
with open(registry_path, 'w', encoding='utf-8') as f:
    json.dump(domain_map, f, indent=2)

print(f"Registry generated with {sum(len(v) for v in domain_map.values())} total routings.")
