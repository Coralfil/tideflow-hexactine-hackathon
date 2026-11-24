import os
import shutil

CONFIG_DIR = r"C:\Users\seafa\.gemini\config"
SKILLS_DIR = os.path.join(CONFIG_DIR, "skills")
PLUGINS_DIR = os.path.join(CONFIG_DIR, "plugins")

# Least used skills (usage <= 60)
LEAST_USED_SKILLS = [
    "wayfinder", "unslop", "llm-deep-learning", "stripe-cli", "llm-dreamstate",
    "python-debug-expert", "postgres-session-optimizer", "customer-pathway-simulator",
    "dependency-grapher"
]

def find_all_skills():
    skills = {}
    if os.path.exists(SKILLS_DIR):
        for item in os.listdir(SKILLS_DIR):
            item_path = os.path.join(SKILLS_DIR, item)
            if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "SKILL.md")):
                skills.setdefault(item, []).append(item_path)
    if os.path.exists(PLUGINS_DIR):
        for plugin in os.listdir(PLUGINS_DIR):
            plugin_skills_dir = os.path.join(PLUGINS_DIR, plugin, "skills")
            if os.path.exists(plugin_skills_dir):
                for item in os.listdir(plugin_skills_dir):
                    item_path = os.path.join(plugin_skills_dir, item)
                    if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "SKILL.md")):
                        skills.setdefault(item, []).append(item_path)
                    elif item == "SKILL.md":
                        skills.setdefault(plugin, []).append(plugin_skills_dir)
    return skills

def main():
    skills = find_all_skills()
    removed = 0
    
    for skill_name, paths in skills.items():
        norm_name = skill_name.replace("_", "-")
        if norm_name in LEAST_USED_SKILLS or skill_name in LEAST_USED_SKILLS:
            for path in paths:
                try:
                    shutil.rmtree(path)
                    print(f"Removed least used skill: {path}")
                    removed += 1
                except Exception as e:
                    print(f"Error removing {path}: {e}")

    print(f"Done. Removed {removed} rarely used skills.")

if __name__ == "__main__":
    main()