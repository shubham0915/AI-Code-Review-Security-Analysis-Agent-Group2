import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from app.cache import get_redis_client

router = APIRouter()

@router.websocket("/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logger.info(f"[WS] Client connected to session {session_id}")
    
    redis = await get_redis_client()
    
    if not hasattr(redis, "pubsub"):
        logger.error("[WS] PubSub not available on memory cache fallback.")
        await websocket.close()
        return

    pubsub = redis.pubsub()
    channel_name = f"ws:{session_id}"
    await pubsub.subscribe(channel_name)
    logger.info(f"[WS] Subscribed to Redis channel {channel_name}")
    
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if message is not None:
                data = message["data"]
                await websocket.send_text(data)
                
            await asyncio.sleep(0.01)
            
    except WebSocketDisconnect:
        logger.info(f"[WS] Client disconnected from session {session_id}")
    except Exception as e:
        logger.error(f"[WS] Error in websocket connection: {e}")
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()
