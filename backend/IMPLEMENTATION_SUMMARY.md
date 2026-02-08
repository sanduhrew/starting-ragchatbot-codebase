# Sequential Tool Calling Implementation Summary

## Overview

Successfully refactored `ai_generator.py` to support **sequential tool calling** where Claude can make up to 2 tool calls in separate API rounds, enabling complex multi-step queries.

## Changes Made

### 1. Updated System Prompt (`ai_generator.py:11-54`)

**Removed:**
- "Maximum one search per query" restriction

**Added:**
- Multi-round tool calling guidance section
- Examples of when to use multiple rounds
- Explicit mention that tools can be used "multiple times per query"
- Instructions to "analyze results before deciding if you need another tool call"

### 2. Refactored `generate_response()` Method (`ai_generator.py:73-157`)

**Before:**
- Single API call with tools
- If tool_use detected → execute tools → make final call WITHOUT tools
- No ability to chain tool calls

**After:**
- Loop structure with MAX_ROUNDS = 2
- Tools remain available in all loop iterations
- Message history accumulates across rounds
- Natural termination when Claude returns text (stop_reason != "tool_use")
- Forced synthesis without tools if max rounds reached

**Flow:**
```
1. Initialize messages with user query
2. While round_count < MAX_ROUNDS:
   a. Make API call with tools enabled
   b. If text response → return (done)
   c. If tool_use → execute tools, append to messages, increment round
3. If max rounds reached with pending tool_use:
   → Make final API call WITHOUT tools (forced synthesis)
```

### 3. Added Helper Methods

**`_make_api_call()`** (`ai_generator.py:159-188`)
- Centralized API call logic
- Handles error cases (auth, rate limit, API errors)
- Conditionally adds tools parameter
- Consistent error handling across all API calls

**`_execute_and_append_tools()`** (`ai_generator.py:190-226`)
- Executes all tool_use blocks from response
- Appends assistant message with tool_use
- Appends user message with tool_results
- Returns updated messages list

**Removed:**
- Old `_handle_tool_execution()` method (replaced by loop + helpers)

### 4. Error Handling

**Tool Execution Errors:**
- Caught and passed to Claude as tool_result
- Claude can see error message and respond appropriately
- Round still increments (counts toward max rounds)

**API Errors:**
- Enhanced logging with round context
- Proper exception propagation
- User-friendly error messages

### 5. Comprehensive Test Suite (`tests/test_ai_generator.py`)

Created 10 tests covering external behavior:

1. **test_general_question_no_tools** - Verify no tool calls for general knowledge
2. **test_single_round_with_tool** - Standard search flow (2 API calls)
3. **test_two_sequential_rounds** - Chained tools: outline → search (3 API calls)
4. **test_max_rounds_enforcement** - Stops after 2 rounds, forces synthesis
5. **test_tool_execution_error_handling** - Errors passed to Claude
6. **test_natural_termination_after_first_round** - Claude stops when satisfied
7. **test_api_error_during_tool_round** - API failures handled gracefully
8. **test_no_tool_manager_provided** - Graceful handling of missing manager
9. **test_conversation_history_preserved** - History in system prompt
10. **test_tools_enabled_in_all_rounds** - Tools available throughout loop

**All tests pass** ✅

## Key Design Decisions

### Approach: Minimal Refactor (Loop-based)
- Simple while loop with round counter
- Tools enabled in every iteration
- Local variable state tracking
- Minimal changes to existing codebase

### Termination Conditions
1. **Natural**: `stop_reason == "end_turn"` (Claude stops on its own)
2. **Max rounds**: `round_count >= 2` → force synthesis without tools
3. **No tool manager**: Return immediately even if tool_use requested

### Message History Management
- Messages accumulate in a list: `[user, assistant, user, assistant, ...]`
- Tools stay available throughout (except forced synthesis)
- System prompt includes conversation_history as string (unchanged pattern)

### Error Handling Philosophy
- **Tool errors** → Pass to Claude (let Claude explain to user)
- **API errors** → Propagate to caller (critical failures)
- **Max rounds with pending tools** → Force synthesis (guarantee text response)

## Example Flow

**User Query:** "Search for a course that discusses the same topic as lesson 4 of course X"

```
Round 1:
  API Call → Claude requests get_course_outline("course X")
  Execute Tool → Returns "Lesson 4: Advanced MCP Features"
  Messages: [user query, assistant tool_use, user tool_result]
  round_count: 1

Round 2:
  API Call → Claude requests search_course_content("Advanced MCP Features")
  Execute Tool → Returns course content
  Messages: [user, assistant, user, assistant tool_use, user tool_result]
  round_count: 2

Round 3 (Natural):
  API Call → Claude returns text: "Based on lesson 4 of course X..."
  Return response (complete)
```

## Benefits

1. **Complex queries**: Multi-step reasoning (outline → search, compare courses)
2. **Better answers**: Claude can refine searches based on initial results
3. **Backward compatible**: Single-round queries work exactly as before
4. **Safe limits**: Max 2 rounds prevents runaway tool calling
5. **Graceful degradation**: Errors handled, always returns response

## Testing

All tests pass:
```bash
uv run pytest tests/test_ai_generator.py -v
# 10 passed in 0.16s

uv run pytest tests/test_diagnostic.py -v
# 7 passed in 4.46s (existing tests still work)
```

## Files Modified

1. **backend/ai_generator.py** - Core refactoring
2. **backend/tests/test_ai_generator.py** - New test file (created)

## Performance Impact

- **Latency**: Up to 3 API calls per query (vs 2 before) for complex queries
- **Cost**: Additional API calls only when Claude needs multiple rounds
- **Simple queries**: No change (1-2 API calls as before)

## Future Enhancements (Not Implemented)

- Infinite loop detection (same tool + same params twice)
- Configurable MAX_ROUNDS (currently hardcoded to 2)
- Token budget management for long message histories
- Evolving system prompts based on round state
- Tool execution metadata (timing, result size)
