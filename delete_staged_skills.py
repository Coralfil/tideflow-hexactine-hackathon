import os
import shutil

TO_DELETE = {
    "create-a-backend", "queues", "vercel-connect", "vercel-sandbox", "vercel-schedules", "vercel-storage", "vercel-tracing",
    "alphagenome-variant-impact-score", "biomolecular-structure-viewer", "cheminformatics-cofolding", "cheminformatics-doc2mol",
    "foldseek-structural-search", "protein-sequence-msa", "protein-sequence-similarity-search", "ucsc-conservation-and-tfbs",
    "clinical-trials-database", "clinvar-database", "embl-ebi-ols", "encode-ccres-database", "ensembl-database",
    "human-protein-atlas-database", "interpro-database", "jaspar-database", "literature-search-europepmc", "openfda-database",
    "quickgo-database", "reactome-database", "string-database", "unibind-database", "uniprot-database", "gemini-live-api-dev",
    "gemini-omni-flash-api", "science-overview", "bio-nlp", "typescript-react-patterns", "vercel-deployment", "00-IDENTITY",
    "arize-annotation", "arize-experiment", "arize-instrumentation", "compliance-auditor", "scv-scan", "stripe-projects"
}

deleted_count = 0
with open(r"D:\Kane Hackathon\all_skills_list.txt", "r", encoding="utf-16") as f:
    paths = [line.strip() for line in f if line.strip()]

for path in paths:
    skill_dir = os.path.dirname(path)
    skill_name = os.path.basename(skill_dir)
    norm_name = skill_name.replace("_", "-")

    if norm_name in TO_DELETE or skill_name in TO_DELETE:
        if os.path.exists(skill_dir):
            try:
                shutil.rmtree(skill_dir)
                print(f"Deleted: {skill_dir}")
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete {skill_dir}: {e}")

print(f"Successfully deleted {deleted_count} skill directories.")
