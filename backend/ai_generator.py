import anthropic
import logging
from typing import List, Optional, Dict, Any

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
- Maximum one search per query

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without tools
- **Course structure questions**: Use outline tool first, then answer
- **Course content questions**: Use search tool first, then answer
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
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
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
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
            logger.debug(f"Tools enabled: {len(tools)} tools available")

        # Get response from Claude
        try:
            logger.debug(f"Making API call for query: {query[:100]}...")
            response = self.client.messages.create(**api_params)
            logger.debug(f"API response received: stop_reason={response.stop_reason}")
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

        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            logger.debug("Tool use detected, executing tools...")
            return self._handle_tool_execution(response, api_params, tool_manager)

        # Return direct response
        logger.debug("Returning direct response (no tools used)")
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls and get follow-up response.
        
        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools
            
        Returns:
            Final response text after tool execution
        """
        # Start with existing messages
        messages = base_params["messages"].copy()
        
        # Add AI's tool use response
        messages.append({"role": "assistant", "content": initial_response.content})
        
        # Execute all tool calls and collect results
        tool_results = []
        for content_block in initial_response.content:
            if content_block.type == "tool_use":
                logger.debug(f"Executing tool: {content_block.name} with params: {content_block.input}")
                tool_result = tool_manager.execute_tool(
                    content_block.name,
                    **content_block.input
                )
                logger.debug(f"Tool result length: {len(tool_result)} chars")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": content_block.id,
                    "content": tool_result
                })
        
        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        
        # Prepare final API call without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"]
        }
        
        # Get final response
        try:
            logger.debug("Making follow-up API call with tool results...")
            final_response = self.client.messages.create(**final_params)
            logger.debug("Follow-up API call successful")
            return final_response.content[0].text
        except Exception as e:
            logger.error(f"Error in follow-up API call: {type(e).__name__}: {e}")
            raise ValueError(f"Error synthesizing response with tool results: {e}")