"""
About this file: chat_graph.py
Structure: StateGraph definition loading historical session reviews from cache and handling user Q&A interactions.
Methods used: responder_node, build_chat_graph.
"""

import json
from typing import Annotated, TypedDict

import logfire
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

from app.llm import get_fast_llm
from app.cache import get_redis_client


class ChatState(TypedDict):
    """State for the conversational assistant."""
    messages: Annotated[list[AnyMessage], add_messages]
    session_id: str


async def responder_node(state: ChatState) -> dict:
    """
    The sole node in the chat graph.
    Fetches the context from Redis (code + analysis results) on the first turn,
    injects it as a SystemMessage, and calls the LLM.
    """
    session_id = state.get("session_id")
    messages = state.get("messages", [])
    
    # Check if a SystemMessage is already in the history.
    # If not, this is the start of a new thread, so we must load the context.
    has_system = any(isinstance(m, SystemMessage) for m in messages)
    
    if not has_system and session_id:
        logger.info(f"[CHAT] Injecting context for session {session_id}")
        redis = await get_redis_client()
        session_raw = await redis.get(f"session:{session_id}")
        result_raw = await redis.get(f"result:{session_id}")
        
        system_content = (
            "You are an expert AI code review assistant. "
            "You are helping a developer understand and fix issues in their code. "
            "Answer their questions based on the provided source code and the AI review findings below.\n"
            "Be concise, actionable, and provide code examples if asked.\n\n"
        )
        
        if session_raw and result_raw:
            session_data = json.loads(session_raw)
            result_data = json.loads(result_raw)
            
            # Truncate result data to avoid massive prompts on huge repos
            result_json_str = json.dumps(result_data, indent=2)[:5000] 
            
            system_content += f"SOURCE CODE:\n```\n{session_data.get('code', '')}\n```\n\n"
            system_content += f"REVIEW FINDINGS:\n```json\n{result_json_str}\n```\n"
        else:
            logger.warning(f"[CHAT] Session or result not found in Redis for {session_id}")
            system_content += "Context unavailable. The session may have expired."
            
        messages = [SystemMessage(content=system_content)] + messages

    llm = get_fast_llm()
    
    with logfire.span(f"💬 Chat LLM Call (Session {session_id})"):
        response = await llm.ainvoke(messages)
        
    return {"messages": [response]}


# Build the graph
builder = StateGraph(ChatState)
builder.add_node("responder", responder_node)
builder.add_edge(START, "responder")
builder.add_edge("responder", END)

# Compile with in-memory checkpointer for conversational threads
memory = MemorySaver()
chat_graph = builder.compile(checkpointer=memory)
