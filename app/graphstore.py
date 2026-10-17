from neo4j import GraphDatabase
from .config import settings
driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_user, settings.neo4j_password),
    max_connection_lifetime=200,
    liveness_check_timeout=30,
)
with driver.session() as session:
    session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE")
    session.run("CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE")
def save_chunk(chunk_id, source_id, entities, relations):
    clean_entities = []
    for e in entities:
        if e.get("name"):
            clean_entities.append({"name": e["name"], "type": e.get("type", "Other")})
    clean_relations = []
    for r in relations:
        source = r.get("source") or r.get("source_name")
        target = r.get("target") or r.get("target_name")
        rel_type = r.get("relation") or r.get("type")
        if source and target and rel_type:
            clean_relations.append({"source": source, "target": target, "type": rel_type})
    with driver.session() as session:
        session.run(
            "MERGE (c:Chunk {id: $chunk_id}) SET c.source_id = $source_id",
            chunk_id=chunk_id,
            source_id=source_id,
        )
        if clean_entities:
            session.run(
                """
                MATCH (c:Chunk {id: $chunk_id}) UNWIND $entities AS ent
                MERGE (e:Entity {id: toLower(ent.name)}) ON CREATE SET e.name = ent.name, e.type = ent.type
                MERGE (c)-[:MENTIONS]->(e)
                """,
                chunk_id=chunk_id,
                entities=clean_entities,
            )
        if clean_relations:
            session.run(
                """
                UNWIND $relations AS rel MERGE (e1:Entity {id: toLower(rel.source)}) ON CREATE SET e1.name = rel.source
                MERGE (e2:Entity {id: toLower(rel.target)}) ON CREATE SET e2.name = rel.target
                MERGE (e1)-[x:RELATED_TO {type: rel.type}]->(e2) SET x.chunk_id = $chunk_id
                """,
                relations=clean_relations,
                chunk_id=chunk_id,
            )
def get_facts(chunk_ids, question):
    q = question.lower()
    with driver.session() as session:
        rows = session.run("MATCH (c:Chunk)-[:MENTIONS]->(e:Entity) WHERE c.id IN $ids RETURN DISTINCT e.id AS id",ids=chunk_ids,)
        seeds = {row["id"] for row in rows}
        rows = session.run("MATCH (e:Entity) WHERE size(e.id) > 2 AND $q CONTAINS e.id RETURN e.id AS id",q=q,)
        seeds |= {row["id"] for row in rows}
        if not seeds:
            return []
        result = session.run(
            """
            MATCH (e:Entity) WHERE e.id IN $seeds
            MATCH p = (e)-[:RELATED_TO*1..2]-(o:Entity) UNWIND relationships(p) AS r
            RETURN DISTINCT startNode(r).name AS source, r.type AS relation,endNode(r).name AS target LIMIT 60
            """,
            seeds=list(seeds),)
        return [dict(row) for row in result]
def get_stats():
    with driver.session() as session:
        nodes = {r["label"]: r["count"] for r in session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count")}
        rels = {r["type"]: r["count"] for r in session.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count")}
    return {"nodes": nodes, "relationships": rels}

def get_graph(limit=150):
    with driver.session() as session:
        rows = session.run(
            """
            MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)
            RETURN a.name AS source, r.type AS relation, b.name AS target
            LIMIT $limit
            """,
            limit=limit,
        )
        return [dict(r) for r in rows]