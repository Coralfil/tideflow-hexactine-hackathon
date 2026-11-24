import os
import json
import uuid
from neo4j import GraphDatabase

class UserSiloProvisioner:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def generate_rl_boundary(self, user_id):
        silo_path = f"D:/Projects/os/Atlantis_HSL/MEMORY_SILOS/{user_id}.rl"
        os.makedirs(os.path.dirname(silo_path), exist_ok=True)
        
        boundary_config = {
            "user_id": user_id,
            "privacy_level": "strict",
            "encryption": "AES-256-GCM",
            "neo4j_sync_enabled": True
        }
        
        with open(silo_path, "w") as f:
            f.write(f"// HSL Privacy Boundary: {user_id}\n")
            f.write(json.dumps(boundary_config, indent=2))
            
        return silo_path

    def provision_neo4j_bridge(self, user_id):
        with self.driver.session() as session:
            session.run(
                "MERGE (u:UserSilo {userId: $user_id}) "
                "SET u.privacyBoundary = 'active', u.lastSync = timestamp()",
                user_id=user_id
            )

    def close(self):
        self.driver.close()

if __name__ == "__main__":
    provisioner = UserSiloProvisioner(
        neo4j_uri=os.getenv("NEO4J_URI", "neo4j+s://<aws-aura-id>.databases.neo4j.io"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "password")
    )
    user = str(uuid.uuid4())
    rl_file = provisioner.generate_rl_boundary(user)
    provisioner.provision_neo4j_bridge(user)
    provisioner.close()