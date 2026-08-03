import pytest
import json
from unittest.mock import patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.agents.chat_graph import chat_graph

@pytest.mark.asyncio
@patch("app.agents.chat_graph.get_fast_llm")
@patch("app.agents.chat_graph.get_redis_client")
async def test_chat_graph_with_context(mock_get_redis, mock_get_llm):
    """Chat graph should inject context from Redis on the first message."""
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = [
        json.dumps({"code": "def hello(): pass"}),  # session_data
        json.dumps({"findings": []})                # result_data
    ]
    mock_get_redis.return_value = mock_redis

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content="Hello from AI!")
    mock_get_llm.return_value = mock_llm

    input_state = {
        "messages": [HumanMessage(content="What does this code do?")],
        "session_id": "test-session-123"
    }
    
    # We don't necessarily need a real checkpointer for the unit test, 
    # but we can pass config if we want
    config = {"configurable": {"thread_id": "test-thread-1"}}
    
    result = await chat_graph.ainvoke(input_state, config)
    
    messages = result["messages"]
    
    # Verify the LLM was called
    assert mock_llm.ainvoke.call_count == 1
    
    # Verify the final message is from the AI
    assert isinstance(messages[-1], AIMessage)
    assert messages[-1].content == "Hello from AI!"
    
    # Verify the SystemMessage was injected before the LLM call
    args, _ = mock_llm.ainvoke.call_args
    sent_messages = args[0]
    
    assert isinstance(sent_messages[0], SystemMessage)
    assert "def hello(): pass" in sent_messages[0].content
