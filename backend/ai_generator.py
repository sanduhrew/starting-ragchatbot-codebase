import logging

import anthropic

logger = logging.getLogger(__name__)


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Tool Usage Guidelines:

**Outline Tool** (get_course_outline):
- Use when users ask about course structure, lesson lists, or "what's in this course"
- Use for questions like "show me the lessons", "what topics are covered", "course overview"
- Returns complete lesson list with links

**Search Tool** (search_course_content):
- Use for questions about specific course content or detailed educational materials
- Use when users need information from within lessons
- Can be used multiple times per query for complex questions

**Multi-Round Tool Calling**:
- You can use tools up to 2 times per query
- Use multiple rounds when you need to:
  * Retrieve information first, then search based on what you learned
  * Compare information from different courses or lessons
  * Answer multi-part questions that require separate tool calls
- After using a tool, analyze the results before deciding if you need another tool call
- Examples requiring multiple rounds:
  * "Search for a course that discusses the same topic as lesson 4 of course X"
    → First: get outline of course X to see lesson 4 title
    → Second: search for courses with that topic
  * "Compare how MCP and Prompt Caching courses teach error handling"
    → First: search MCP course for error handling
    → Second: search Prompt Caching course for error handling

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without tools
- **Course structure questions**: Use outline tool first, then answer
- **Course content questions**: Use search tool, potentially multiple times if needed
- **Complex multi-part questions**: Break down into sequential tool calls
- **No meta-commentary**: Provide direct answers only — no reasoning process or tool explanations

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        logger.info(f"Initializing AIGenerator with model: {model}")
        try:
            self.client = anthropic.Anthropic(api_key=api_key)
            logger.debug("Anthropic client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
            raise

        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: str | None = None,
        tools: list | None = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to 2 sequential rounds of tool calling for complex queries.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize messages for multi-round conversation
        messages = [{"role": "user", "content": query}]

        # Configuration for sequential tool calling
        MAX_ROUNDS = 2
        round_count = 0

        # Main loop for sequential tool calling
        while round_count < MAX_ROUNDS:
            # Make API call with tools available
            try:
                logger.debug(f"Making API call (round {round_count + 1}/{MAX_ROUNDS})")
                response = self._make_api_call(messages, system_content, tools)
                logger.debug(f"API response received: stop_reason={response.stop_reason}")
            except Exception as e:
                # If tools were already executed, log the error context
                if round_count > 0:
                    logger.error(f"API error in round {round_count + 1} after executing tools: {e}")
                raise

            # Check if Claude wants to use tools
            if response.stop_reason != "tool_use":
                # Got text response, we're done
                logger.debug(f"Received text response in round {round_count + 1}, completing")
                return response.content[0].text

            # Tool use detected
            if not tool_manager:
                logger.warning("Tool use requested but no tool_manager provided")
                return response.content[0].text

            logger.debug(f"Round {round_count + 1}: Tool use detected, executing tools...")

            # Execute tools and append results to messages
            try:
                messages = self._execute_and_append_tools(response, messages, tool_manager)
                round_count += 1
            except Exception as e:
                logger.error(f"Tool execution failed in round {round_count + 1}: {e}")
                # Pass error to Claude as tool result
                error_result = {
                    "type": "tool_result",
                    "tool_use_id": response.content[0].id,
                    "content": f"Tool execution failed: {str(e)}",
                }
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": [error_result]})
                round_count += 1

        # Max rounds reached - force final synthesis without tools
        if response.stop_reason == "tool_use":
            logger.warning(f"Max rounds ({MAX_ROUNDS}) reached, forcing final synthesis")
            try:
                final_response = self._make_api_call(messages, system_content, tools=None)
                return final_response.content[0].text
            except Exception as e:
                logger.error(f"Error in final synthesis call: {e}")
                raise ValueError(f"Error synthesizing final response: {e}")

        # Should not reach here, but handle gracefully
        return response.content[0].text if response.content else "Error: No response generated"

    def _make_api_call(self, messages: list[dict], system_content: str, tools: list | None = None):
        """
        Centralized API call logic with error handling.

        Args:
            messages: Message history for the conversation
            system_content: System prompt content
            tools: Optional tools to make available

        Returns:
            API response object

        Raises:
            ValueError: On API errors with user-friendly messages
        """
        api_params = {**self.base_params, "messages": messages, "system": system_content}

        # Add tools if provided
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
            logger.debug(f"Tools enabled: {len(tools)} tools available")

        # Make API call with error handling
        try:
            response = self.client.messages.create(**api_params)
            return response
        except anthropic.AuthenticationError as e:
            logger.error(f"API authentication failed: {e}")
            raise ValueError(f"Anthropic API key is invalid or expired: {e}")
        except anthropic.RateLimitError as e:
            logger.error(f"API rate limit exceeded: {e}")
            raise ValueError(f"Anthropic API rate limit exceeded. Please try again later: {e}")
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise ValueError(f"Anthropic API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during API call: {type(e).__name__}: {e}")
            raise ValueError(f"Unexpected error calling Anthropic API: {type(e).__name__}: {e}")

    def _execute_and_append_tools(self, response, messages: list[dict], tool_manager) -> list[dict]:
        """
        Execute tools from response and append results to messages.

        Args:
            response: API response containing tool_use blocks
            messages: Current message history
            tool_manager: Manager to execute tools

        Returns:
            Updated messages list with tool execution results

        Raises:
            Exception: If tool execution fails
        """
        # Add assistant's tool_use response
        messages.append({"role": "assistant", "content": response.content})

        # Execute all tool calls and collect results
        tool_results = []
        for content_block in response.content:
            if content_block.type == "tool_use":
                logger.debug(
                    f"Executing tool: {content_block.name} with params: {content_block.input}"
                )
                tool_result = tool_manager.execute_tool(content_block.name, **content_block.input)
                logger.debug(f"Tool result length: {len(tool_result)} chars")

                tool_results.append(
                    {"type": "tool_result", "tool_use_id": content_block.id, "content": tool_result}
                )

        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        return messages
