// helix_memory/schema.cypher
//
// One-time DDL + idempotent marine seed for a Helix Memory store.
// Apply with:
//   relate query --database data/helix_memory.rl --mode table --safe < helix_memory/schema.cypher
//
// DIMENSION NOTE: `vector.dimensions` below is the HELIX_EMBEDDING_DIM placeholder
// (default 384, the local all-MiniLM-L6-v2 embedder). It MUST equal the embedder
// dimension actually used at write time; a mismatch fails every write/recall with
// VectorIndexDimensionalityMismatch (exit code 6). If you swap embedders, drop and
// recreate this vector index with the matching dimension.

// ---------------------------------------------------------------------------
// Session spine: one node per agent session, chained by (:Session)-[:CONTINUES]->
// ---------------------------------------------------------------------------
CREATE CONSTRAINT session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE;

// ---------------------------------------------------------------------------
// Core memory model (adapted from the relate agent-memory docs,
// https://relatedb.ai/docs/guides/agents/model-agent-memory/):
//   Entity(key) / Episode(id,session,kind,at,text)
//   Fact(id,text,slot,kind,confidence,source_ref,valid_from,valid_to,
//        recorded_at,closed_at,embedding)
//   (:Episode)-[:MENTIONS]->(:Entity)
//   (:Fact)-[:FROM]->(:Episode)
//   (:Fact)-[:ABOUT]->(:Entity)
//   (:Fact)-[:SUPERSEDES]->(:Fact)   -- corrections close; nothing is deleted
// Fact.kind: observation | research | decision | correction | preference
// ---------------------------------------------------------------------------
CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.key IS UNIQUE;
CREATE CONSTRAINT episode_id IF NOT EXISTS FOR (ep:Episode) REQUIRE ep.id IS UNIQUE;
CREATE CONSTRAINT fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.id IS UNIQUE;
CREATE INDEX fact_slot IF NOT EXISTS FOR (f:Fact) ON (f.slot);
CREATE VECTOR INDEX fact_embedding IF NOT EXISTS
  FOR (f:Fact) ON (f.embedding) WITH [f.closed_at]
  OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}};

// ---------------------------------------------------------------------------
// Marine-domain seed (idempotent: MERGE keyed on the unique lowercase `key`,
// ON CREATE SET makes re-runs a no-op). Every domain node also carries :Entity.
// ---------------------------------------------------------------------------
MERGE (site:Entity:Site {key: 'site/barkley-sound'})
  ON CREATE SET site.name = 'Barkley Sound', site.kind = 'reef';

MERGE (species:Entity:Species {key: 'species/acropora-cervicornis'})
  ON CREATE SET species.name = 'Acropora cervicornis', species.common = 'staghorn coral';

MERGE (threat:Entity:Threat {key: 'threat/ocean-acidification'})
  ON CREATE SET threat.name = 'ocean acidification';

MERGE (formulation:Entity:Formulation {key: 'formulation/wqg-organic-binder'})
  ON CREATE SET formulation.name = 'WQG organic substrate binder', formulation.family = 'wqg';

MERGE (source:Entity:Source {key: 'source/noaa-pmel-ocean-acidification'})
  ON CREATE SET source.name = 'NOAA PMEL ocean acidification dataset', source.kind = 'dataset';

// Sanity check: list the seeded entity keys.
MATCH (e:Entity) RETURN e.key AS key ORDER BY key LIMIT 100;
