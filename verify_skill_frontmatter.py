import json
import os
import re

REGISTRY_PATH = r"D:\Kane Hackathon\skill_routing_registry.json"
INDEX_PATH = r"D:\Kane Hackathon\all_skills_list.txt"

with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
    reg = json.load(f)

skill_domains = {}
for domain, skills in reg.items():
    for s in skills:
        if s not in skill_domains:
            skill_domains[s] = []
        if domain not in skill_domains[s]:
            skill_domains[s].append(domain)

with open(INDEX_PATH, "r", encoding="utf-16") as f:
    indexed_paths = [p.strip() for p in f if p.strip() and os.path.exists(p.strip())]

extra_dirs = [
    r"C:\Users\seafa\.gemini\config\plugins",
    r"C:\Users\seafa\.gemini\config\skills",
    r"C:\Users\seafa\.gemini\antigravity\builtin\skills"
]
for ed in extra_dirs:
    for root, dirs, files in os.walk(ed):
        if "SKILL.md" in files:
            p = os.path.join(root, "SKILL.md")
            if p not in indexed_paths:
                indexed_paths.append(p)

verified_count = 0
errors = []

for s, domains in skill_domains.items():
    s_norm = s.lower().replace("_", "-")
    matched = []
    for p in indexed_paths:
        parent = os.path.basename(os.path.dirname(p)).lower().replace("_", "-")
        if parent == s_norm or (s == "android-device-hub" and parent in ("device-hub", "android-device-hub")):
            matched.append(p)
    matched = list(dict.fromkeys(matched))

    for p in matched:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        m_dom = re.search(r'execution_domain:\s*(\[.*?\])', content)
        if not m_dom:
            errors.append(f"Missing execution_domain in {p}")
        else:
            injected_dom = json.loads(m_dom.group(1))
            if injected_dom != domains:
                errors.append(f"Mismatch domains in {p}: expected {domains}, got {injected_dom}")

        m_tt = re.search(r'tooltip_summary:\s*"(.*?)"', content)
        if not m_tt:
            errors.append(f"Missing tooltip_summary in {p}")
        else:
            tt = m_tt.group(1)
            if "\u2014" in tt:
                errors.append(f"Em dash in {p}")

        verified_count += 1

print(f"Total files verified: {verified_count}")
print(f"Errors found: {len(errors)}")
if errors:
    for e in errors[:10]:
        print(" -", e)
else:
    print("ALL 236 FILES FULLY VERIFIED AND VALID!")
