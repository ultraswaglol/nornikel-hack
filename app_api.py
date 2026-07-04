# app_api.py
import os
import sys
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

# Поддержка импортов из структуры проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.neo4j_client import neo4j_client
from src.core.qdrant_client import vector_client
from src.core.yandex_ai import yandex_ai
from src.services.graph_rag_service import graph_rag_service
from src.services.conflict_resolver import conflict_resolver
from src.pipeline.document_loader import document_loader
from src.pipeline.text_splitter import text_splitter
from src.pipeline.entity_extractor import entity_extractor
from src.pipeline.entity_linker import entity_linker

app = FastAPI(title="Nornickel R&D Knowledge Graph API")

# Настройка CORS для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    user_role: str

@app.post("/api/search")
async def search(payload: QueryRequest):
    role_security_map = {
        "Исследователь R&D (Public)": "PUBLIC",
        "Аналитик (Internal)": "INTERNAL",
        "Главный инженер (Confidential)": "CONFIDENTIAL"
    }
    security_level = role_security_map.get(payload.user_role, "PUBLIC")
    
    try:
        # Получаем аналитический ответ
        answer = graph_rag_service.answer_question(payload.query, security_level=security_level)
        
        # Получаем связанные узлы графа для визуализации
        words = [w.strip(",.?!\"'").lower() for w in payload.query.split() if len(w) > 3]
        nodes = []
        edges = []
        
        if words:
            query_cypher = """
            MATCH (n)-[r]-(m)
            WHERE any(word IN $words WHERE toLower(n.name) CONTAINS word OR toLower(m.name) CONTAINS word)
            RETURN n, r, m LIMIT 40
            """
            records = neo4j_client.query(query_cypher, {"words": words})
        else:
            query_cypher = """
            MATCH (pub:Publication)
            WITH pub ORDER BY pub.year DESC LIMIT 3
            MATCH (pub)-[r]-(m)
            RETURN pub AS n, r, m LIMIT 40
            """
            records = neo4j_client.query(query_cypher)

        node_ids = set()
        color_map = {
            "Material": "#38bdf8",      # Голубой
            "Process": "#34d399",       # Зеленый
            "Property": "#facc15",      # Желтый
            "Publication": "#f87171",    # Красный
            "Equipment": "#c084fc",      # Фиолетовый
            "Expert": "#fb923c"          # Оранжевый
        }

        for rec in records:
            for key in ["n", "m"]:
                node = rec[key]
                node_id = node["id"]
                if node_id not in node_ids:
                    node_ids.add(node_id)
                    label_name = node.get("name") or node.get("title", "Без названия")
                    label_type = list(node.labels)[0] if node.labels else "Unknown"
                    nodes.append({
                        "id": node_id,
                        "label": label_name,
                        "color": color_map.get(label_type, "#94a3b8"),
                        "title": f"Тип: {label_type}"
                    })
            rel = rec["r"]
            edges.append({
                "from": rec["n"]["id"],
                "to": rec["m"]["id"],
                "label": rel.type
            })

        return {
            "answer": answer,
            "graph": {"nodes": nodes, "edges": edges}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard")
async def get_dashboard():
    try:
        nodes_count = neo4j_client.query("MATCH (n) RETURN count(n) as count")[0]["count"]
        rels_count = neo4j_client.query("MATCH ()-[r]->() RETURN count(r) as count")[0]["count"]
        pubs_count = neo4j_client.query("MATCH (p:Publication) RETURN count(p) as count")[0]["count"]
        
        conflicts_raw = conflict_resolver.find_technological_conflicts()
        gaps_raw = conflict_resolver.find_knowledge_gaps()
        
        compare_query = """
        MATCH (pub:Publication)-[:described_in]->(p:Process)-[:operates_at_condition]->(pr:Property)
        WHERE (pub.id = "PUB_REPORT_NICKEL_ELECTROWINNING_RU" AND pr.id = "PROP_CIRCULATION_SPEED_RU")
           OR (pub.id = "PUB_REPORT_NICKEL_ELECTROWINNING_GLOBAL" AND pr.id = "PROP_CIRCULATION_SPEED_GLOBAL")
           OR (pub.id = "PUB_REPORT_WATER_DESALINATION" AND pr.id = "PROP_DRY_RESIDUE")
        RETURN p.name AS Process, pub.title AS Source, pr.name AS Parameter, pr.value AS Value
        """
        compare_data = neo4j_client.query(compare_query)

        return {
            "metrics": {
                "nodes": nodes_count,
                "edges": rels_count,
                "publications": pubs_count
            },
            "conflicts": conflicts_raw,
            "gaps": gaps_raw,
            "compare": compare_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    security_level: str = Form("PUBLIC"),
    trust_level: str = Form("B")
):
    temp_path = f"temp_{file.filename}"
    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        
        raw_text, doc_metadata = document_loader.load_pdf(
            temp_path, 
            security_level=security_level, 
            trust_level=trust_level
        )
        chunks = text_splitter.split_text(raw_text, doc_metadata)
        
        for chunk in chunks:
            vector = yandex_ai.get_embedding(chunk["text"], is_query=False)
            vector_client.save_chunk(
                text_chunk=chunk["text"],
                vector=vector,
                metadata={
                    "title": doc_metadata["title"],
                    "security_level": security_level,
                    "year": doc_metadata["year"]
                }
            )
            extracted_graph = entity_extractor.extract_from_chunk(chunk["text"], doc_metadata)
            normalized_graph = entity_linker.normalize_graph(extracted_graph)
            neo4j_client.save_graph(normalized_graph)

        return {"status": "success", "chunks_count": len(chunks), "title": doc_metadata["title"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# Раздача статических файлов фронтенда
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    uvicorn.run("app_api:app", host="0.0.0.0", port=8000, reload=True)