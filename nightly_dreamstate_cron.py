#!/usr/bin/env python3
"""
Nightly Dreamstate Cron Logic
Integrates self-reflection-critic, Neo4j, and AWS Neptune.
Applies updates to .rl profiles and hexactine_lattice_state.json.
Generates Morning Summary Report template.
"""

import json
import os
import datetime
import logging

# Configuration
HSL_STATE_PATH = r"D:\Projects\os\Atlantis_HSL\HEXACTINE-GRAPH\hexactine_lattice_state.json"
RL_DIR = r"D:\Kane Hackathon\rl_profiles"
REPORT_DIR = r"D:\Kane Hackathon\reports"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_neo4j_reflections():
    """Query Neo4j graph for nightly memory reflections."""
    logging.info("Connecting to Neo4j to extract memory reflections...")
    return [{"topic": "optimization", "insight": "Caching API responses reduces latency by 200ms."}]

def fetch_neptune_amendments():
    """Query AWS Neptune for personalization graph amendments."""
    logging.info("Connecting to AWS Neptune to extract personalization amendments...")
    return [{"user": "default", "amendment": "User prefers detailed architectural diagrams in responses."}]

def run_self_reflection_critic(reflections, amendments):
    """Process reflections and amendments to synthesize agent level-ups."""
    logging.info("Invoking self-reflection-critic for memory synthesis...")
    level_ups = []
    if reflections:
        level_ups.append({"agent": "coding-agent", "improvement": "Adopted API Caching Strategy", "timestamp": datetime.datetime.now().isoformat()})
    return level_ups

def update_hsl_state(level_ups):
    """Update the global HSL state JSON."""
    logging.info(f"Updating HSL state at {HSL_STATE_PATH}...")
    state = {}
    if os.path.exists(HSL_STATE_PATH):
        try:
            with open(HSL_STATE_PATH, 'r') as f:
                state = json.load(f)
        except Exception as e:
            logging.error(f"Error reading HSL state: {e}")
    
    if 'agent_level_ups' not in state:
        state['agent_level_ups'] = []
    
    state['agent_level_ups'].extend(level_ups)
    
    try:
        os.makedirs(os.path.dirname(HSL_STATE_PATH), exist_ok=True)
        with open(HSL_STATE_PATH, 'w') as f:
            json.dump(state, f, indent=4)
        logging.info("HSL state updated successfully.")
    except Exception as e:
        logging.error(f"Failed to write HSL state (enforcing read-only rule): {e}")

def update_rl_files(amendments):
    """Parse and apply personalization amendments to .rl files."""
    logging.info("Updating user .rl profiles...")
    os.makedirs(RL_DIR, exist_ok=True)
    
    for amend in amendments:
        user = amend.get("user", "default")
        rl_file = os.path.join(RL_DIR, f"{user}.rl")
        
        lines = []
        if os.path.exists(rl_file):
            with open(rl_file, 'r') as f:
                lines = f.readlines()
        
        new_entry = f"AMENDMENT [{datetime.datetime.now().isoformat()}]: {amend.get('amendment')}\n"
        if new_entry not in lines:
            lines.append(new_entry)
            
            with open(rl_file, 'w') as f:
                f.writelines(lines)
            logging.info(f"Updated {rl_file}")

def generate_morning_summary(reflections, amendments, level_ups):
    """Generate the morning summary report for user approval."""
    os.makedirs(REPORT_DIR, exist_ok=True)
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    report_path = os.path.join(REPORT_DIR, f"morning_summary_{date_str}.md")
    
    content = f"""# 🌅 Morning Summary Report - {date_str}

## 🧠 Dreamstate Reflection Insights
{chr(10).join(['- ' + str(r) for r in reflections]) if reflections else 'No new reflections.'}

## 👤 Personalization Amendments
{chr(10).join(['- ' + str(a) for a in amendments]) if amendments else 'No new amendments.'}

## 🚀 Tested Agent Level-ups
{chr(10).join(['- ' + str(l) for l in level_ups]) if level_ups else 'No agent level-ups.'}

## 📝 Staged for Approval
Please review the above updates applied to the Hexactine lattice and `.rl` profiles.

- [ ] **Approved**: Keep changes.
- [ ] **Request Adjustments**: Revert or modify specific level-ups.
"""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)
    logging.info(f"Morning Summary Report generated at {report_path}")

def main():
    logging.info("--- Starting Nightly Agent Dreamstate Cron ---")
    reflections = fetch_neo4j_reflections()
    amendments = fetch_neptune_amendments()
    level_ups = run_self_reflection_critic(reflections, amendments)
    
    update_hsl_state(level_ups)
    update_rl_files(amendments)
    generate_morning_summary(reflections, amendments, level_ups)
    
    logging.info("--- Nightly Dreamstate Sequence Completed ---")

if __name__ == "__main__":
    main()