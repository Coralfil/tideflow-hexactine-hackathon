import os

with open(r"D:\Kane Hackathon\all_skills_list.txt", "r", encoding="utf-16") as f:
    lines = [line.strip() for line in f if line.strip()]

project_groups = {}
for path in lines:
    if "node_modules" in path.lower() or "temp_skills" in path.lower() or ".vercel" in path.lower():
        continue
        
    # Group by prefix
    prefix = ""
    if path.startswith("D:\\Projects\\"):
        parts = path.split("\\")
        if len(parts) >= 3:
            prefix = "Project: " + parts[2]
    elif path.startswith("C:\\Users\\seafa\\.gemini\\config"):
        prefix = "Global Config"
    elif path.startswith("C:\\Users\\seafa\\.gemini\\antigravity"):
        prefix = "Antigravity Built-in"
    elif path.startswith("D:\\Kane Hackathon"):
        prefix = "Kane Hackathon"
    else:
        prefix = "Other"

    # Extract skill name from path (usually the parent folder name)
    skill_name = os.path.basename(os.path.dirname(path))
    if skill_name == "skills":
        # Some are just SKILL.md directly inside a project root
        skill_name = "root-skill"
        
    project_groups.setdefault(prefix, set()).add(skill_name)

with open(r"D:\Kane Hackathon\parsed_skills_groups.md", "w", encoding="utf-8") as out:
    for proj, skills in sorted(project_groups.items()):
        out.write(f"## {proj}\n")
        for s in sorted(list(skills)):
            out.write(f"- {s}\n")
        out.write("\n")
