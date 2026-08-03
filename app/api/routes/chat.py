"""
About this file: chat.py
Structure: FastAPI router interfacing user prompts with a MemorySaver-backed LangGraph stateful chat workflow.
Methods used: chat_with_assistant.
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from langchain_core.messages import HumanMessage

from app.models import ChatRequest, ChatResponse
from app.agents.chat_graph import chat_graph

router = APIRouter(prefix="/api/v1/chat", tags=["Assistant Chat"])

@router.post(
    "",
    response_model=ChatResponse,
    summary="Chat with the AI Code Assistant",
    description="Send a message to the AI assistant regarding a specific session.",
)
async def chat_with_assistant(request: ChatRequest) -> ChatResponse:
    """
    Processes an interactive chat message within a code review session, maintaining history via MemorySaver checkpointer.
    """
    logger.info(f"[CHAT] Received message for session {request.session_id}, thread {request.thread_id}")

    # The config dictionary tells LangGraph's checkpointer which thread to load/save
    config = {"configurable": {"thread_id": request.thread_id}}

    # The input state
    input_state = {
        "messages": [HumanMessage(content=request.message)],
        "session_id": request.session_id,
    }

    try:
        # Run the graph
        result_state = await chat_graph.ainvoke(input_state, config)
        
        # Extract the last message from the assistant
        messages = result_state.get("messages", [])
        if not messages:
            return ChatResponse(response="I'm sorry, I encountered an error generating a response.")
            
        last_message = messages[-1].content
        return ChatResponse(response=str(last_message))
        
    except Exception as e:
        logger.error(f"[CHAT] Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while communicating with the AI assistant.",
        )