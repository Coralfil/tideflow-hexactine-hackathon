import os
import shutil

CONFIG_DIR = r"C:\Users\seafa\.gemini\config"
SKILLS_DIR = os.path.join(CONFIG_DIR, "skills")
PLUGINS_DIR = os.path.join(CONFIG_DIR, "plugins")

# List of skills to remove completely based on user's excluded list
EXCLUDED_SKILLS = [
    "hf-cli", "modern-web-guidance", "chrome-extensions", "neo4j-graph-science",
    "ponytail", "vercel-flags", "finding-google-skills", "typescript-react-nextjs-patterns",
    "flags-sdk", "typescript-react-patterns", "alphagenome-atlas-website-links",
    "accidental-data-loss-prevention", "retrieving-developer-knowledge",
    "microfrontends", "vercel-cli", "alphagenome-single-variant-analysis", "eve"
]

def find_all_skills():
    skills = {}
    # Search in main skills dir
    if os.path.exists(SKILLS_DIR):
        for item in os.listdir(SKILLS_DIR):
            item_path = os.path.join(SKILLS_DIR, item)
            if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "SKILL.md")):
                skills.setdefault(item, []).append(item_path)
    
    # Search in plugins dir
    if os.path.exists(PLUGINS_DIR):
        for plugin in os.listdir(PLUGINS_DIR):
            plugin_skills_dir = os.path.join(PLUGINS_DIR, plugin, "skills")
            if os.path.exists(plugin_skills_dir):
                for item in os.listdir(plugin_skills_dir):
                    item_path = os.path.join(plugin_skills_dir, item)
                    # Sometime the skill is just SKILL.md in a folder
                    if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "SKILL.md")):
                        skills.setdefault(item, []).append(item_path)
                    elif item == "SKILL.md":
                        skills.setdefault(plugin, []).append(plugin_skills_dir)
    return skills

def main():
    skills = find_all_skills()
    removed = 0
    deduped = 0
    
    for skill_name, paths in skills.items():
        # Normalize skill name if needed
        norm_name = skill_name.replace("_", "-")
        # 1. Remove if in excluded list
        if norm_name in EXCLUDED_SKILLS or skill_name in EXCLUDED_SKILLS:
            for path in paths:
                try:
                    shutil.rmtree(path)
                    print(f"Removed excluded skill: {path}")
                    removed += 1
                except Exception as e:
                    print(f"Error removing {path}: {e}")
            continue
            
        # 2. Deduplicate
        if len(paths) > 1:
            # Keep the first one, remove the rest
            keep_path = paths[0]
            print(f"Keeping {keep_path} for skill {skill_name}")
            for path in paths[1:]:
                try:
                    shutil.rmtree(path)
                    print(f"Removed duplicate skill: {path}")
                    deduped += 1
                except Exception as e:
                    print(f"Error removing {path}: {e}")

    print(f"Done. Removed {removed} excluded skills and {deduped} duplicates.")

if __name__ == "__main__":
    main()