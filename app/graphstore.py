import re
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
    entity_map = {}
    for e in entities:
        name = str(e.get("name", "")).strip()
        key = entity_key(name)
        if key:
            entity_map[key] = {"id": key, "name": name, "type": e.get("type", "Other")}

    clean_relations = []
    for r in relations:
        source = str(r.get("source") or r.get("source_name") or "").strip()
        target = str(r.get("target") or r.get("target_name") or "").strip()
        rel_type = re.sub(r"[^A-Z0-9]+", "_", str(r.get("relation") or r.get("type") or "").upper()).strip("_")
        sid, tid = entity_key(source), entity_key(target)
        if sid and tid and rel_type and sid != tid:
            clean_relations.append({"sid": sid, "sname": source, "tid": tid, "tname": target, "type": rel_type})
            entity_map.setdefault(sid, {"id": sid, "name": source, "type": "Other"})
            entity_map.setdefault(tid, {"id": tid, "name": target, "type": "Other"})

    with driver.session() as session:
        session.run(
            "MERGE (c:Chunk {id: $chunk_id}) SET c.source_id = $source_id",
            chunk_id=chunk_id, source_id=source_id,
        )
        if entity_map:
            session.run(
                """
                MATCH (c:Chunk {id: $chunk_id})
                UNWIND $entities AS ent
                MERGE (e:Entity {id: ent.id})
                ON CREATE SET e.name = ent.name, e.type = ent.type
                MERGE (c)-[:MENTIONS]->(e)
                """,
                chunk_id=chunk_id, entities=list(entity_map.values()),
            )
        if clean_relations:
            session.run(
                """
                UNWIND $relations AS rel
                MERGE (a:Entity {id: rel.sid}) ON CREATE SET a.name = rel.sname
                MERGE (b:Entity {id: rel.tid}) ON CREATE SET b.name = rel.tname
                MERGE (a)-[x:RELATED_TO {type: rel.type}]->(b)
                SET x.chunk_id = $chunk_id
                """,
                relations=clean_relations, chunk_id=chunk_id,
            )
def entities_of_chunks(chunk_ids):
    with driver.session() as session:
        rows = session.run(
            "MATCH (c:Chunk)-[:MENTIONS]->(e:Entity) WHERE c.id IN $ids RETURN DISTINCT e.id AS id",
            ids=chunk_ids,
        )
        return [r["id"] for r in rows]


def find_entities_in_text(text):
    with driver.session() as session:
        rows = session.run(
            "MATCH (e:Entity) WHERE size(e.id) > 2 AND $q CONTAINS e.id RETURN e.id AS id",
            q=text.lower(),
        )
        return [r["id"] for r in rows]


def neighbourhood(entity_ids, hops=2):
    hops = max(1, min(int(hops), 3))
    with driver.session() as session:
        rows = session.run(
            f"""
            MATCH (e:Entity) WHERE e.id IN $ids
            MATCH p = (e)-[:RELATED_TO*1..{hops}]-(o:Entity)
            UNWIND relationships(p) AS r
            RETURN DISTINCT startNode(r).name AS source, startNode(r).id AS source_id,
                            r.type AS relation,
                            endNode(r).name AS target, endNode(r).id AS target_id
            LIMIT 60
            """,
            ids=entity_ids,
        )
        return [dict(r) for r in rows]


def chunks_for_entities(entity_ids, limit=4):
    with driver.session() as session:
        rows = session.run(
            """
            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity) WHERE e.id IN $ids
            RETURN c.id AS id, count(DISTINCT e) AS hits
            ORDER BY hits DESC LIMIT $limit
            """,
            ids=entity_ids, limit=limit,
        )
        return [r["id"] for r in rows]
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
def entity_key(name):
    words = re.sub(r"[^\w\s]", " ", str(name).lower()).split()
    if len(words) > 1 and words[0] == "the":
        words = words[1:]
    while len(words) > 1 and words[-1] in {"inc", "corp", "corporation", "ltd", "llc", "co", "company", "plc"}:
        words.pop()
    return " ".join(words)