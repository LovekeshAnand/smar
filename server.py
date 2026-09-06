"""
server.py
=========
FastAPI Backend Server for SMAR Autonomous Voice & Memory System.
Serves the web dashboard and handles real-time voice, chat, context synchronization,
knowledge graph inspection, and autonomous background actions.
"""

import os
import sys
import json
import base64
import asyncio
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("smar.server")

# Import SMAR core components
from core.epsilon_bridge import EpsilonBridge
from voice.gnani_stt import GnaniSTT
from voice.gnani_tts import GnaniTTS
from memory.context_manager import ContextManager
from context_layer import ContextLayerEngine, ContextConfig
from structured_data.adapters import AdapterRegistry, SQLiteStorageAdapter
from smart_data import SmartDataLayerEngine
from auth import user_manager

app = FastAPI(title="SMAR Autonomous Voice Platform", version="2.0.0")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize singletons
context_config = ContextConfig(default_user_id="lovekesh")
context_engine = ContextLayerEngine(config=context_config)
context_mgr = ContextManager()
stt_client = GnaniSTT()
tts_client = GnaniTTS(voice=os.getenv("GNANI_VOICE_NAME", "Nalini"))
epsilon_bridge = EpsilonBridge()

# Initialize Smart Data Layer & Multi-Source Storage Adapters
adapter_registry = AdapterRegistry()
primary_adapter = SQLiteStorageAdapter()  # smar_inventory.db with 100,000+ items
adapter_registry.register("primary_sqlite", primary_adapter, set_as_primary=True)
smart_data_engine = SmartDataLayerEngine(
    adapter_registry=adapter_registry,
    context_store=context_engine.store
)

# Active WebSocket clients
connected_clients: List[WebSocket] = []


# --- Multi-User Authentication Models & Endpoints ---
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    role: Optional[str] = "user"


@app.post("/api/auth/login")
async def login_user(req: LoginRequest):
    """Authenticate user with username and password."""
    res = user_manager.authenticate(req.username, req.password)
    if not res:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return res


@app.post("/api/auth/register")
async def register_user(req: RegisterRequest):
    """Register a new user in the multi-user system."""
    try:
        res = user_manager.register_user(
            username=req.username,
            password=req.password,
            name=req.name,
            role=req.role or "user"
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/auth/me")
async def get_current_user_profile(token: Optional[str] = None, user_id: Optional[str] = None):
    """Return active user profile; defaults to lovekesh if session not specified."""
    if token:
        u = user_manager.verify_token(token)
        if u:
            return {"authenticated": True, "user": u}
    clean_id = user_id or "lovekesh"
    u = user_manager.get_user(clean_id)
    if u:
        return {"authenticated": True, "user": u}
    return {"authenticated": False, "user": None}


@app.get("/api/auth/users")
async def list_registered_users():
    """List all registered users for multi-user switching."""
    return {"users": user_manager.list_users()}


class ChatRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    language: Optional[str] = None
    user_id: Optional[str] = "lovekesh"


@app.get("/api/status")
async def get_system_status():
    """System health and context layer state overview."""
    epsilon_ok = await epsilon_bridge.check_health()
    triples_summary = context_engine.store.get_all_triples(limit=1)
    vectors_summary = context_engine.store.get_all_semantic(limit=1)
    
    return {
        "status": "online",
        "epsilon_llm": {
            "online": epsilon_ok,
            "endpoint": epsilon_bridge.api_base,
            "model": "Qwen2.5-Coder 7B Instruct (GGUF)"
        },
        "voice": {
            "stt_provider": "Gnani / Vachana.ai (Prisma v2.5)",
            "tts_provider": "Gnani / Vachana.ai (Timbre v2.5)",
            "voice_name": tts_client.voice,
            "configured": bool(tts_client.api_key)
        },
        "context_layer": {
            "status": "active",
            "has_graph": len(triples_summary) >= 0,
            "has_vectors": len(vectors_summary) >= 0
        },
        "smart_data_layer": {
            "status": "active",
            "source_name": adapter_registry.get_primary().get_source_name(),
            "source_type": adapter_registry.get_primary().get_source_type(),
            "total_records": adapter_registry.get_primary().get_total_count(),
            "kg_cache_hits": smart_data_engine.cache_hits,
            "kg_cache_misses": smart_data_engine.cache_misses
        }
    }


@app.get("/api/memory/graph")
async def get_memory_graph(user_id: Optional[str] = None):
    """Returns knowledge graph entities and relational facts scoped to user_id or all."""
    triples_data = context_engine.store.get_all_triples(user_id=user_id, limit=100)
    
    triples = []
    nodes = set()
    for r in triples_data:
        triples.append({
            "subject": r["subject"],
            "predicate": r["predicate"],
            "object": r["object"],
            "confidence": r.get("confidence", 1.0),
            "updated_at": r.get("updated_at", 0)
        })
        nodes.add(r["subject"])
        nodes.add(r["object"])

    graph_bundle = context_engine.get_memory_graph(user_id=user_id, limit=100)

    return {
        "nodes_count": len(nodes),
        "triples_count": len(triples),
        "triples": triples,
        "nodes": graph_bundle.get("nodes", []),
        "edges": graph_bundle.get("edges", [])
    }


@app.get("/api/memory/vectors")
async def get_memory_vectors(user_id: Optional[str] = None):
    """Returns recent semantic memory chunks stored in vector database."""
    items = context_engine.store.get_all_semantic(user_id=user_id, limit=50)
    return {"count": len(items), "items": items}


@app.get("/api/context/profile")
async def get_user_profile(user_id: Optional[str] = None):
    """Returns synthesized structured user profile."""
    uid = user_id or "default_user"
    return context_engine.get_user_profile(uid)


class ExplicitMemoryRequest(BaseModel):
    text: str
    user_id: Optional[str] = "lovekesh"
    category: Optional[str] = "explicit"


@app.post("/api/context/memory")
async def add_explicit_memory(req: ExplicitMemoryRequest):
    """Explicitly stores a user note/preference and extracts relational facts."""
    return context_engine.add_explicit_memory(
        user_id=req.user_id or "lovekesh",
        text=req.text,
        category=req.category or "explicit"
    )



@app.post("/api/chat")
async def process_chat(req: ChatRequest):
    """
    Processes user text:
    Extracts facts, executes hybrid RAG retrieval, composes dynamic system prompt,
    queries Epsilon LLM, and synthesizes audio.
    """
    user_text = req.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    user_id = req.user_id or "lovekesh"

    # 1. Query Smart Data Layer asynchronously (non-blocking over 1M+ rows & KG cache)
    smart_res = await smart_data_engine.process_query_async(user_text, user_id=user_id)
    inventory_context = smart_res.get("context_string")

    # 2. Ingest turn, run hybrid retrieval, compose dynamic prompt
    turn_result = context_engine.process_user_turn(
        user_id=user_id,
        user_text=user_text,
        language_hint=req.language or "en-IN"
    )
    system_prompt = turn_result["system_prompt"]
    retrieval = turn_result["retrieval"]
    structured_facts = retrieval.get("structured_facts", [])
    semantic_memories = retrieval.get("semantic_memories", [])
    recent_turns = turn_result.get("recent_turns", [])

    # Assemble rich context: database grounded inventory facts + personal user memory
    context_blocks = []

    # Numbers found in the verified DB record — used to detect conflicting past notes
    verified_numbers: set = set()
    if inventory_context:
        import re as _re
        verified_numbers = set(_re.findall(r'\b\d{2,}\b', inventory_context))
        # Prefix with absolute ground-truth instruction so LLM always uses DB data
        grounded_context = (
            "[DATABASE GROUND TRUTH — USE ONLY THESE NUMBERS FOR PRICES, IDs, AND QUANTITIES. "
            "Ignore any conflicting numbers from past notes or conversation history.]\n"
            + inventory_context
        )
        context_blocks.append(grounded_context)

    if structured_facts:
        context_blocks.append("[Personal User Knowledge]:\n" + "\n".join(f"- {f}" for f in structured_facts))

    if semantic_memories:
        # Filter out stale past notes that contain numeric values conflicting with the verified record
        clean_memories = []
        for m in semantic_memories:
            if verified_numbers:
                # If this memory contains DB-like numbers that conflict with the verified record, skip it
                mem_numbers = set(_re.findall(r'\b\d{4,}\b', m))
                if mem_numbers and not mem_numbers.issubset(verified_numbers):
                    # Memory has different large numbers — potentially stale/conflicting data
                    continue
            clean_memories.append(m)
        if clean_memories:
            context_blocks.append("[Recalled Personal Notes]:\n" + "\n".join(f"- {m}" for m in clean_memories))

    context_summary = "\n\n".join(context_blocks) if context_blocks else None

    # 2. Determine reply text: for operations or verified grounded database results, use authoritative calculation directly to avoid LLM hallucination
    if smart_res.get("intent") == "OPERATION" and smart_res.get("spoken_confirmation"):
        reply_text = smart_res["spoken_confirmation"]
    elif smart_res.get("spoken_confirmation") and smart_res.get("matched_item"):
        reply_text = smart_res["spoken_confirmation"]
    else:
        # Filter recent conversation turns to exclude any past hallucinated numbers conflicting with verified data
        clean_recent_turns = []
        for turn in recent_turns:
            if verified_numbers and turn.get("role") == "assistant":
                turn_numbers = set(_re.findall(r'\b\d{2,}\b', turn.get("content", "")))
                if turn_numbers and not turn_numbers.issubset(verified_numbers):
                    continue
            clean_recent_turns.append(turn)

        try:
            reply_text = await epsilon_bridge.generate_reply(
                user_prompt=user_text,
                context=context_summary,
                system_prompt=system_prompt,
                conversation_history=clean_recent_turns,
                max_tokens=256
            )
        except Exception as e:
            logger.error(f"Epsilon generation error: {e}")
            reply_text = "I experienced a temporary glitch accessing my neural core. How else can I assist you?"

    # 3. Commit turns to multi-turn conversation buffer
    try:
        context_engine.store.save_turn(user_id=user_id, role="user", content=user_text)
        context_engine.store.save_turn(user_id=user_id, role="assistant", content=reply_text)

        # Only store PERSONAL / BIOGRAPHICAL content in semantic memory.
        # NEVER store transactional, database lookup, or Q&A turn pairs.
        smart_intent = smart_res.get("intent", "CONVERSATION")
        is_transactional = smart_intent in ("OPERATION", "SEARCH", "PRICE", "QUANTITY", "STATUS", "LOCATION")
        is_refusal = any(p in reply_text.lower() for p in [
            "i don't have access", "as an ai assistant", "temporary glitch", "no matching records found"
        ])
        # Additional check: if reply contains specific numbers, it's likely a DB lookup turn
        import re as _re2
        has_numeric_answer = bool(_re2.search(r'\b\d{4,}\b', reply_text))  # 4+ digit numbers = DB data
        should_store = (
            not is_refusal
            and not is_transactional
            and not has_numeric_answer
            and context_engine.pipeline.should_store_semantic(user_text)
        )
        if should_store:
            context_engine.store.upsert_semantic(
                user_id=user_id,
                text=f"User: {user_text}\nAssistant: {reply_text}",
                category="conversation"
            )
        context_mgr.ingest_turn(user_text, reply_text)
    except Exception as e:
        logger.debug(f"Turn memory ingestion error: {e}")

    # 4. Background Cognitive Knowledge Formation via Local LLM
    async def _async_knowledge_formation():
        try:
            llm_facts = await context_engine.pipeline.extract_facts_llm(
                user_text=user_text,
                reply_text=reply_text,
                user_id=user_id,
                api_base=context_config.epsilon_api_base
            )
            if llm_facts:
                for f in llm_facts:
                    context_engine.store.upsert_triple(
                        user_id=user_id,
                        subject=f["subject"],
                        predicate=f["predicate"],
                        object_val=f["object"],
                        confidence=f.get("confidence", 0.95)
                    )
                logger.info(f"Dynamically formed {len(llm_facts)} new facts for '{user_id}': {llm_facts}")
                # Broadcast memory update to connected web clients
                for ws in connected_clients:
                    try:
                        await ws.send_json({
                            "type": "MEMORY_UPDATED",
                            "user_id": user_id,
                            "facts": llm_facts
                        })
                    except Exception:
                        pass
        except Exception as err:
            logger.debug(f"Background cognitive extraction error: {err}")

    asyncio.create_task(_async_knowledge_formation())

    # 5. Synthesize voice with Gnani TTS
    audio_b64 = None
    try:
        audio_bytes = await tts_client.synthesize(reply_text, voice=req.voice or tts_client.voice)
        if audio_bytes:
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        logger.error(f"TTS synthesis error: {e}")

    return {
        "reply": reply_text,
        "context_used": context_summary or "None",
        "retrieval": retrieval,
        "extracted_facts": turn_result.get("extracted_facts", []),
        "audio_base64": audio_b64,
        "operation_details": smart_res.get("operation_details"),
        "table_data": smart_res.get("table_data"),
        "visual_chart": smart_res.get("visual_chart"),
        "smart_data": {
            "intent": smart_res.get("intent"),
            "operation": smart_res.get("operation"),
            "operation_details": smart_res.get("operation_details"),
            "table_data": smart_res.get("table_data"),
            "visual_chart": smart_res.get("visual_chart"),
            "kg_cache_hit": smart_res.get("kg_cache_hit"),
            "matched_item": smart_res.get("matched_item"),
            "spoken_confirmation": smart_res.get("spoken_confirmation"),
            "elapsed_ms": smart_res.get("elapsed_ms")
        }
    }


@app.post("/api/voice/process")
async def process_voice(
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    user_id: Optional[str] = Form("lovekesh")
):
    """
    Complete end-to-end voice pipeline:
    Audio In (WAV) -> Gnani STT -> Context Layer Engine -> Epsilon LLM -> Gnani TTS Audio Out
    """
    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio received.")

    # 1. Transcribe audio via Gnani STT
    lang = language or stt_client.language_code
    transcription = await stt_client.transcribe_audio_bytes(
        audio_bytes=audio_bytes,
        language_code=lang
    )

    if not transcription or not transcription.strip():
        transcription = "(unrecognized speech)"

    if transcription.startswith("(Speech duration exceeded"):
        reply_text = "I heard you speaking for over 30 seconds! To keep our voice conversation smooth, please keep each speech under 25 seconds."
        audio_b64 = None
        try:
            ab = await tts_client.synthesize(reply_text, voice=tts_client.voice)
            if ab:
                audio_b64 = base64.b64encode(ab).decode("utf-8")
        except Exception:
            pass
        return {
            "transcription": transcription,
            "reply": reply_text,
            "context_used": "None",
            "retrieval": {},
            "extracted_facts": [],
            "audio_base64": audio_b64,
            "operation_details": None,
            "table_data": None,
            "visual_chart": None
        }

    # 2. Run chat processing with the transcribed text and user_id
    chat_resp = await process_chat(ChatRequest(
        text=transcription,
        language=lang,
        user_id=user_id or "lovekesh"
    ))

    return {
        "transcription": transcription,
        "reply": chat_resp["reply"],
        "context_used": chat_resp["context_used"],
        "retrieval": chat_resp.get("retrieval"),
        "extracted_facts": chat_resp.get("extracted_facts"),
        "audio_base64": chat_resp["audio_base64"],
        "operation_details": chat_resp.get("operation_details"),
        "table_data": chat_resp.get("table_data"),
        "visual_chart": chat_resp.get("visual_chart"),
        "smart_data": chat_resp.get("smart_data")
    }


# --- Universal Data Layer & Sync Endpoints ---
@app.get("/api/data/status")
@app.get("/api/inventory/status")
async def get_universal_data_status():
    """Returns readiness status, table inventory, row counts, and cache engine."""
    sync_status = smart_data_engine.get_sync_status()
    total_records = sync_status.get("total_rows", 0)
    tables = sync_status.get("tables", [])

    if total_records == 0 and not tables:
        primary = adapter_registry.get_primary()
        if primary:
            tables = primary.list_tables() if hasattr(primary, "list_tables") else []
            total_records = primary.get_total_count()

    is_ready = sync_status.get("ready_to_answer", total_records > 0)
    status_code = sync_status.get("status", "ready_to_answer" if total_records > 0 else "uninitialized")
    msg = sync_status.get("message") or (
        f"Ready to answer queries across {len(tables)} tables ({total_records:,} records)."
        if total_records > 0 else "No data synchronized yet. Awaiting file upload."
    )

    return {
        "status": status_code,
        "ready_to_answer": is_ready,
        "message": msg,
        "total_records": total_records,
        "tables_count": len(tables),
        "tables": tables,
        "schema_triples_in_kg": sync_status.get("schema_triples_in_kg", 0),
        "cache_engine": sync_status.get("cache_engine", "in_memory_lru"),
        "is_redis": sync_status.get("is_redis", False),
        "cache_hits": smart_data_engine.cache_hits,
        "cache_misses": smart_data_engine.cache_misses,
        "primary_source": "Retail Warehouse (12 Tables, 1.59M Rows)" if total_records > 0 else "warehouse.db"
    }


@app.post("/api/data/upload")
async def upload_multiple_data_files(files: List[UploadFile] = File(...)):
    """
    Accepts arbitrary, unexpected uploaded files (CSV, Excel, SQLite, JSON, Parquet),
    saves them, and runs the Universal Data Sync Engine to index and sync to KG.
    """
    import shutil
    uploads_dir = Path("data/uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    saved_paths = []

    try:
        for f in files:
            safe_name = Path(f.filename).name
            target_path = uploads_dir / safe_name
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            saved_paths.append(str(target_path))
            logger.info(f"Uploaded file saved: {target_path} ({os.path.getsize(target_path)} bytes)")

        # Run non-blocking sync pipeline
        result = await smart_data_engine.sync_files_async(saved_paths)

        # Broadcast update to connected WebSockets
        for ws in list(connected_clients):
            try:
                await ws.send_json({
                    "type": "MEMORY_UPDATED",
                    "event": "DATA_SYNC_COMPLETED",
                    "sync_status": result
                })
            except Exception:
                pass

        return result
    except Exception as e:
        logger.error(f"Error handling multi-file upload: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Upload processing error: {str(e)}",
                "ready_to_answer": False
            }
        )


@app.post("/api/data/sync")
async def trigger_data_sync():
    """
    Manually triggers the Universal Data Sync Engine over all files in data/uploads/ and data/.
    Introspects schema, indexes, writes triples to KG, and sets ready_to_answer = True.
    """
    target_files = []
    # Collect files from data/uploads and sample files from data/
    for folder in ["data/uploads", "data"]:
        p = Path(folder)
        if p.exists():
            for f in p.iterdir():
                if f.is_file() and f.suffix.lower() in [".csv", ".xlsx", ".xls", ".json", ".jsonl", ".parquet", ".db", ".sqlite"] and not f.name.startswith("test_"):
                    target_files.append(str(f))

    if not target_files:
        wh = Path("data/warehouse.db")
        if wh.exists():
            target_files.append(str(wh))

    result = await smart_data_engine.sync_files_async(target_files)

    for ws in list(connected_clients):
        try:
            await ws.send_json({
                "type": "MEMORY_UPDATED",
                "event": "DATA_SYNC_COMPLETED",
                "sync_status": result
            })
        except Exception:
            pass

    return result


@app.post("/api/data/reset")
async def reset_data_layer():
    """Wipes uploaded data and resets sync status to uninitialized."""
    uploads_dir = Path("data/uploads")
    if uploads_dir.exists():
        for f in uploads_dir.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                except Exception:
                    pass
    status = smart_data_engine.reset()
    for ws in list(connected_clients):
        try:
            await ws.send_json({
                "type": "MEMORY_UPDATED",
                "event": "DATA_SYNC_COMPLETED",
                "sync_status": status
            })
        except Exception:
            pass
    return {"status": "ok", "sync_status": status}


class DirectOperationRequest(BaseModel):
    operation: str  # "AGGREGATION", "INSERT", "UPDATE", "DELETE", "TABULAR"
    table: str
    function: Optional[str] = "COUNT"
    column: Optional[str] = "*"
    group_by: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    filter_data: Optional[Dict[str, Any]] = None
    update_data: Optional[Dict[str, Any]] = None
    limit: Optional[int] = 10
    wants_visual: Optional[bool] = False


@app.post("/api/data/operation")
async def execute_direct_operation(req: DirectOperationRequest):
    """
    Direct REST API endpoint to execute CRUD and Aggregation operations on any warehouse table.
    """
    op = req.operation.upper().strip()
    mgr = smart_data_engine.warehouse_manager
    viz = smart_data_engine.visualizer

    try:
        if op == "AGGREGATION":
            res = await mgr.execute_aggregation_async(
                table_name=req.table,
                agg_func=req.function or "COUNT",
                column=req.column or "*",
                group_by=req.group_by
            )
            chart = viz.generate_chart_for_operation(res) if req.wants_visual or req.group_by else None
            return {"status": "SUCCESS", "operation": op, "result": res, "visual_chart": chart}

        elif op == "INSERT":
            if not req.data:
                raise HTTPException(status_code=400, detail="Data payload required for INSERT.")
            res = await mgr.insert_record_async(table_name=req.table, data=req.data)
            return {"status": "SUCCESS", "operation": op, "result": res}

        elif op == "UPDATE":
            if not req.filter_data or not req.update_data:
                raise HTTPException(status_code=400, detail="Both filter_data and update_data required for UPDATE.")
            res = await mgr.update_record_async(table_name=req.table, filter_data=req.filter_data, update_data=req.update_data)
            return {"status": "SUCCESS", "operation": op, "result": res}

        elif op == "DELETE":
            if not req.filter_data:
                raise HTTPException(status_code=400, detail="filter_data required for DELETE.")
            res = await mgr.delete_record_async(table_name=req.table, filter_data=req.filter_data)
            return {"status": "SUCCESS", "operation": op, "result": res}

        elif op == "TABULAR":
            res = await mgr.query_tabular_async(table_name=req.table, limit=req.limit or 10)
            chart = viz.generate_chart_for_operation(res) if req.wants_visual else None
            return {"status": "SUCCESS", "operation": op, "result": res, "visual_chart": chart}

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported operation: {req.operation}")
    except Exception as e:
        logger.error(f"Error in direct operation endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/inventory/search")
async def search_inventory(q: str, limit: int = 10):
    """Direct search query against active storage engine."""
    res = await smart_data_engine.process_query_async(q)
    return {
        "query": q,
        "count": len(res.get("all_results", [])),
        "items": res.get("all_results", []),
        "spoken_confirmation": res.get("spoken_confirmation"),
        "elapsed_ms": res.get("elapsed_ms")
    }


@app.post("/api/inventory/load-file")
async def load_inventory_file(file: UploadFile = File(...)):
    """Uploads a CSV or Excel file and indexes it into the system."""
    import shutil
    uploads_dir = Path("data/uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = uploads_dir / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Ingest and sync
    res = await smart_data_engine.sync_files_async([str(file_path)])
    return {
        "success": True,
        "message": f"Successfully ingested and indexed '{file.filename}'. Ready to answer!",
        "sync_status": res
    }



@app.websocket("/ws/live")
async def live_websocket(websocket: WebSocket):
    """Duplex websocket for real-time visualizer state, transcription, and status telemetry."""
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            action = msg.get("action")
            
            if action == "PING":
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)


# Mount UI static directory
ui_dir = Path(__file__).parent / "ui"
os.makedirs(ui_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="ui")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5000"))
    print(f"==================================================")
    print(f"  SMAR Web Interface Running: http://127.0.0.1:{port}")
    print(f"==================================================")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
