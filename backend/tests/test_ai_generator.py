"""Tests for AIGenerator sequential tool calling functionality"""

from unittest.mock import Mock

import pytest
from ai_generator import AIGenerator


class MockResponse:
    """Mock Anthropic API response"""

    def __init__(self, text=None, tool_use_blocks=None, stop_reason="end_turn"):
        self.stop_reason = stop_reason
        self.model = "claude-sonnet-4-20250514"

        # Build content blocks
        self.content = []

        if tool_use_blocks:
            self.content = tool_use_blocks
        elif text:
            text_block = Mock()
            text_block.type = "text"
            text_block.text = text
            self.content = [text_block]


def make_tool_use_block(tool_name, tool_input, tool_use_id="test_id"):
    """Helper to create a tool_use content block"""
    block = Mock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_use_id
    return block


@pytest.fixture
def mock_client():
    """Mock Anthropic client"""
    return Mock()


@pytest.fixture
def generator(mock_client):
    """Create AIGenerator with mocked client"""
    gen = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    gen.client = mock_client  # Replace real client with mock
    return gen


@pytest.fixture
def mock_tool_manager():
    """Mock tool manager"""
    manager = Mock()
    manager.execute_tool = Mock(return_value="Tool result")
    return manager


def test_general_question_no_tools(generator, mock_client):
    """Test that general knowledge questions complete in one round without tools"""
    # Mock API to return text response immediately
    mock_client.messages.create.return_value = MockResponse(
        text="Python is a programming language.", stop_reason="end_turn"
    )

    response = generator.generate_response(query="What is Python?", tools=[], tool_manager=None)

    # Verify: Only 1 API call made
    assert mock_client.messages.create.call_count == 1

    # Verify: Response is correct
    assert response == "Python is a programming language."

    # Verify: No tools were in the API call
    call_args = mock_client.messages.create.call_args
    assert "tools" not in call_args[1] or call_args[1]["tools"] == []


def test_single_round_with_tool(generator, mock_client, mock_tool_manager):
    """Test simple tool use: one tool call, then final response"""
    # Round 1: Claude requests tool use
    tool_block = make_tool_use_block(
        tool_name="search_course_content",
        tool_input={"query": "MCP", "course_name": None},
        tool_use_id="tool_1",
    )

    # Round 2: Claude provides final answer
    mock_client.messages.create.side_effect = [
        MockResponse(tool_use_blocks=[tool_block], stop_reason="tool_use"),
        MockResponse(text="MCP is a protocol for...", stop_reason="end_turn"),
    ]

    mock_tool_manager.execute_tool.return_value = "MCP documentation content"

    response = generator.generate_response(
        query="What is MCP?",
        tools=[{"name": "search_course_content"}],
        tool_manager=mock_tool_manager,
    )

    # Verify: 2 API calls made (initial + response with tool results)
    assert mock_client.messages.create.call_count == 2

    # Verify: 1 tool executed
    assert mock_tool_manager.execute_tool.call_count == 1
    mock_tool_manager.execute_tool.assert_called_with(
        "search_course_content", query="MCP", course_name=None
    )

    # Verify: Final response returned
    assert response == "MCP is a protocol for..."

    # Verify: Second API call had tool results in messages
    second_call_args = mock_client.messages.create.call_args_list[1]
    messages = second_call_args[1]["messages"]
    assert len(messages) == 3  # user query, assistant tool_use, user tool_result


def test_two_sequential_rounds(generator, mock_client, mock_tool_manager):
    """Test sequential tool calls: outline → search → final response"""
    # Round 1: Get course outline
    tool_block_1 = make_tool_use_block(
        tool_name="get_course_outline", tool_input={"course_name": "MCP"}, tool_use_id="tool_1"
    )

    # Round 2: Search based on outline results
    tool_block_2 = make_tool_use_block(
        tool_name="search_course_content",
        tool_input={"query": "lesson 4 topic", "course_name": "MCP"},
        tool_use_id="tool_2",
    )

    # Round 3: Final answer
    mock_client.messages.create.side_effect = [
        MockResponse(tool_use_blocks=[tool_block_1], stop_reason="tool_use"),
        MockResponse(tool_use_blocks=[tool_block_2], stop_reason="tool_use"),
        MockResponse(text="Lesson 4 discusses advanced features...", stop_reason="end_turn"),
    ]

    mock_tool_manager.execute_tool.side_effect = [
        "Lesson 1: Intro\nLesson 4: Advanced Features",
        "Detailed content about advanced features",
    ]

    response = generator.generate_response(
        query="What does lesson 4 of MCP course discuss?",
        tools=[{"name": "get_course_outline"}, {"name": "search_course_content"}],
        tool_manager=mock_tool_manager,
    )

    # Verify: 3 API calls made (initial + 2 rounds with tools)
    assert mock_client.messages.create.call_count == 3

    # Verify: 2 tools executed in correct order
    assert mock_tool_manager.execute_tool.call_count == 2
    tool_calls = [call.args[0] for call in mock_tool_manager.execute_tool.call_args_list]
    assert tool_calls == ["get_course_outline", "search_course_content"]

    # Verify: Final response returned
    assert response == "Lesson 4 discusses advanced features..."

    # Verify: Message history grew correctly
    third_call_args = mock_client.messages.create.call_args_list[2]
    messages = third_call_args[1]["messages"]
    # user query, assistant tool_1, user result_1, assistant tool_2, user result_2
    assert len(messages) == 5


def test_max_rounds_enforcement(generator, mock_client, mock_tool_manager):
    """Test that execution stops after 2 rounds and forces synthesis"""
    # Create tool use responses for 2 rounds
    tool_block_1 = make_tool_use_block("search", {"query": "A"}, "tool_1")
    tool_block_2 = make_tool_use_block("search", {"query": "B"}, "tool_2")

    mock_client.messages.create.side_effect = [
        MockResponse(tool_use_blocks=[tool_block_1], stop_reason="tool_use"),  # Round 1
        MockResponse(tool_use_blocks=[tool_block_2], stop_reason="tool_use"),  # Round 2
        MockResponse(text="Final synthesis answer", stop_reason="end_turn"),  # Forced synthesis
    ]

    mock_tool_manager.execute_tool.return_value = "Search result"

    response = generator.generate_response(
        query="Complex query requiring many searches",
        tools=[{"name": "search"}],
        tool_manager=mock_tool_manager,
    )

    # Verify: 3 API calls (2 rounds + forced synthesis without tools)
    assert mock_client.messages.create.call_count == 3

    # Verify: Only 2 tools executed
    assert mock_tool_manager.execute_tool.call_count == 2

    # Verify: Final call had no tools (forced synthesis)
    final_call_args = mock_client.messages.create.call_args_list[2]
    assert "tools" not in final_call_args[1]

    # Verify: Got final response
    assert response == "Final synthesis answer"


def test_tool_execution_error_handling(generator, mock_client, mock_tool_manager):
    """Test that tool execution errors are passed to Claude as tool results"""
    tool_block = make_tool_use_block("search", {"query": "test"}, "tool_1")

    # Claude tries to use tool, tool fails, Claude responds with error message
    mock_client.messages.create.side_effect = [
        MockResponse(tool_use_blocks=[tool_block], stop_reason="tool_use"),
        MockResponse(
            text="I encountered an error searching. Please try again.", stop_reason="end_turn"
        ),
    ]

    # Tool execution raises exception
    mock_tool_manager.execute_tool.side_effect = Exception("Course not found")

    response = generator.generate_response(
        query="Find course X", tools=[{"name": "search"}], tool_manager=mock_tool_manager
    )

    # Verify: Tool was attempted
    assert mock_tool_manager.execute_tool.call_count == 1

    # Verify: Error was passed to Claude in second call
    second_call_args = mock_client.messages.create.call_args_list[1]
    messages = second_call_args[1]["messages"]

    # Check that error message was included in tool_result
    user_message = messages[-1]
    assert user_message["role"] == "user"
    tool_result_content = user_message["content"][0]["content"]
    assert "Tool execution failed" in tool_result_content
    assert "Course not found" in tool_result_content

    # Verify: Claude still generated a response
    assert "error" in response.lower() or "encountered" in response.lower()


def test_natural_termination_after_first_round(generator, mock_client, mock_tool_manager):
    """Test that Claude can stop naturally after first tool use without forcing second round"""
    tool_block = make_tool_use_block("search", {"query": "Python"}, "tool_1")

    # Round 1: Tool use
    # Round 2: Claude decides it has enough information and responds
    mock_client.messages.create.side_effect = [
        MockResponse(tool_use_blocks=[tool_block], stop_reason="tool_use"),
        MockResponse(text="Based on the search, Python is...", stop_reason="end_turn"),
    ]

    mock_tool_manager.execute_tool.return_value = "Python documentation"

    response = generator.generate_response(
        query="What is Python?", tools=[{"name": "search"}], tool_manager=mock_tool_manager
    )

    # Verify: Only 2 API calls (didn't force a third round)
    assert mock_client.messages.create.call_count == 2

    # Verify: Only 1 tool executed
    assert mock_tool_manager.execute_tool.call_count == 1

    # Verify: Response returned
    assert response == "Based on the search, Python is..."


def test_api_error_during_tool_round(generator, mock_client, mock_tool_manager):
    """Test error handling when API fails during a tool round"""
    tool_block = make_tool_use_block("search", {"query": "test"}, "tool_1")

    # First call succeeds with tool use, second call fails
    mock_client.messages.create.side_effect = [
        MockResponse(tool_use_blocks=[tool_block], stop_reason="tool_use"),
        Exception("API connection failed"),
    ]

    mock_tool_manager.execute_tool.return_value = "Tool result"

    # Should raise ValueError with user-friendly message
    with pytest.raises(ValueError) as exc_info:
        generator.generate_response(
            query="Test query", tools=[{"name": "search"}], tool_manager=mock_tool_manager
        )

    assert "Unexpected error calling Anthropic API" in str(exc_info.value)

    # Verify: Tool was executed before the error
    assert mock_tool_manager.execute_tool.call_count == 1


def test_no_tool_manager_provided(generator, mock_client):
    """Test that tool use is skipped if no tool_manager provided"""
    tool_block = make_tool_use_block("search", {"query": "test"}, "tool_1")

    mock_client.messages.create.return_value = MockResponse(
        tool_use_blocks=[tool_block], stop_reason="tool_use"
    )

    # No tool_manager provided
    response = generator.generate_response(
        query="Test query", tools=[{"name": "search"}], tool_manager=None
    )

    # Verify: Only 1 API call made
    assert mock_client.messages.create.call_count == 1

    # Verify: Response extracted from first call (no tool execution)
    # Since we have tool_use blocks but no text, content[0] will be the tool block
    # The code returns response.content[0].text which would be None
    # But the mock returns the tool block, so this tests the edge case
    assert response is not None


def test_conversation_history_preserved(generator, mock_client, mock_tool_manager):
    """Test that conversation history is included in system prompt"""
    mock_client.messages.create.return_value = MockResponse(
        text="Response with history context", stop_reason="end_turn"
    )

    conversation_history = "User: Hello\nAssistant: Hi there!"

    _response = generator.generate_response(
        query="New question",
        conversation_history=conversation_history,
        tools=[],
        tool_manager=mock_tool_manager,
    )

    # Verify: System prompt includes conversation history
    call_args = mock_client.messages.create.call_args
    system_content = call_args[1]["system"]
    assert "Previous conversation:" in system_content
    assert conversation_history in system_content


def test_tools_enabled_in_all_rounds(generator, mock_client, mock_tool_manager):
    """Test that tools remain available in all API calls during the loop rounds"""
    tool_block_1 = make_tool_use_block("search", {"query": "A"}, "tool_1")

    mock_client.messages.create.side_effect = [
        MockResponse(tool_use_blocks=[tool_block_1], stop_reason="tool_use"),
        MockResponse(text="Final answer", stop_reason="end_turn"),
    ]

    mock_tool_manager.execute_tool.return_value = "Result"

    test_tools = [{"name": "search"}]

    _response = generator.generate_response(
        query="Test", tools=test_tools, tool_manager=mock_tool_manager
    )

    # Verify: Tools were available in both calls
    first_call = mock_client.messages.create.call_args_list[0]
    second_call = mock_client.messages.create.call_args_list[1]

    assert first_call[1]["tools"] == test_tools
    assert second_call[1]["tools"] == test_tools
