"""
GitHub Copilot SDK Integration

Provides LLM access for CodeRCA agents using the official GitHub Copilot SDK.
Follows the ATTS pattern: shared client, send_and_wait(), no event streaming.

No dependency on Anthropic/Claude - uses GitHub Copilot's LLM infrastructure.
"""

import asyncio
import json
import logging
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)
SDK_IMPORT_ERROR = None

try:
    from copilot import CopilotClient as GHCopilotClient
    try:
        from copilot.generated.session_events import SessionEventType
    except ImportError:
        SessionEventType = None
    COPILOT_SDK_AVAILABLE = True
except ImportError as e:
    COPILOT_SDK_AVAILABLE = False
    SDK_IMPORT_ERROR = str(e)
    GHCopilotClient = None
    SessionEventType = None
    logger.warning(f"GitHub Copilot SDK not available: {e}")

# Global shared SDK client (ATTS pattern)
_copilot_sdk_client = None


def set_copilot_client(client) -> None:
    """Set the shared Copilot SDK client for all agents (ATTS pattern)."""
    global _copilot_sdk_client
    _copilot_sdk_client = client


def get_copilot_client():
    """Get the shared Copilot SDK client (ATTS pattern)."""
    return _copilot_sdk_client


@dataclass
class LLMResponse:
    """Response from LLM API call"""
    
    content: str
    model: str
    usage: Dict[str, int]  # tokens used (estimated)
    finish_reason: str
    
    def __str__(self) -> str:
        return f"LLMResponse({len(self.content)} chars, {self.usage.get('total_tokens', 0)} tokens)"


class CopilotClient:
    """
    Client for LLM access in CodeRCA using GitHub Copilot SDK.
    
    This wrapper provides a synchronous interface to GitHub Copilot's
    async SDK, making it easy to use in agent workflows while maintaining
    compatibility with the rest of the codebase.
    
    Uses ONLY GitHub Copilot - no Anthropic/Claude dependency.
    """
    
    DEFAULT_MODEL = "gpt-5"  # GitHub Copilot default model
    DEFAULT_MAX_TOKENS = 2000
    DEFAULT_TEMPERATURE = 0.7
    
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        use_real_llm: bool = True
    ):
        """
        Initialize Copilot client.
        
        Args:
            model: Model to use (gpt-5, gpt-4, etc.)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0)
            use_real_llm: If True and SDK available, use real LLM. If False, use mock.
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.use_real_llm = use_real_llm and COPILOT_SDK_AVAILABLE
        self.gh_version = "GitHub Copilot SDK v0.1.25"
        self._sdk_loop: Optional[asyncio.AbstractEventLoop] = None
        self._sdk_loop_thread: Optional[threading.Thread] = None
    
    def check_auth(self) -> bool:
        """
        Check if client is ready.
        
        Returns:
            True if GitHub Copilot SDK is available and ready
        """
        return COPILOT_SDK_AVAILABLE
    
    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> LLMResponse:
        """
        Get completion from GitHub Copilot LLM.
        
        Args:
            prompt: User prompt/question
            system: System message (instructions for LLM)
            max_tokens: Override default max_tokens
            temperature: Override default temperature
            
        Returns:
            LLMResponse with content and metadata
        """
        if self.use_real_llm:
            # Use real GitHub Copilot SDK
            return self._complete_with_copilot_sdk(prompt, system, max_tokens, temperature)
        else:
            # Fallback to mock (for testing/demo when SDK not available)
            return self._complete_mock(prompt, system)
    
    def _complete_with_copilot_sdk(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: float = 420.0
    ) -> LLMResponse:
        """
        Make actual LLM call using GitHub Copilot SDK (ATTS pattern).
        
        This uses the official github-copilot-sdk with ATTS's proven approach:
        - Global shared client
        - Fresh session per call
        - send_and_wait() for request/response
        """
        # Combine system and user messages
        full_prompt = prompt
        if system:
            full_prompt = f"System: {system}\n\nUser: {prompt}"
        
        # Run async SDK call on a persistent event loop so the shared SDK client
        # is not rebound to a loop that gets closed after the first request.
        try:
            response_content = self._run_sdk_call(full_prompt, timeout)
        except Exception as e:
            # SDK call failed - fallback to mock will happen at higher level
            raise RuntimeError(f"SDK call failed: {e}")
        
        # Estimate token usage (SDK provides actual usage in newer versions)
        prompt_tokens = len(full_prompt) // 4
        completion_tokens = len(response_content) // 4
        
        return LLMResponse(
            content=response_content,
            model=self.model,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            },
            finish_reason="stop"
        )

    def _ensure_sdk_loop(self) -> asyncio.AbstractEventLoop:
        """Create or return the dedicated SDK event loop."""
        if self._sdk_loop and not self._sdk_loop.is_closed():
            return self._sdk_loop

        loop_ready = threading.Event()
        loop_holder: Dict[str, asyncio.AbstractEventLoop] = {}

        def _loop_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop_holder["loop"] = loop
            loop_ready.set()
            loop.run_forever()

        thread = threading.Thread(
            target=_loop_worker,
            name="coderca-copilot-sdk-loop",
            daemon=True,
        )
        thread.start()
        loop_ready.wait()

        self._sdk_loop = loop_holder["loop"]
        self._sdk_loop_thread = thread
        return self._sdk_loop

    def _run_sdk_call(self, prompt: str, timeout: float) -> str:
        """Execute an SDK coroutine on the dedicated background loop."""
        loop = self._ensure_sdk_loop()
        future = asyncio.run_coroutine_threadsafe(
            self._async_copilot_call(prompt, timeout),
            loop,
        )
        return future.result(timeout=timeout)
    
    async def _async_copilot_call(self, prompt: str, timeout: float = 420.0) -> str:
        """
        Async GitHub Copilot SDK call using ATTS pattern.
        
        Creates a fresh session, sends prompt, waits for response.
        Uses send_and_wait() for simple request/response (no event streaming).
        """
        client = get_copilot_client()
        if client is None:
            raise RuntimeError("Copilot SDK client not initialized. Call set_copilot_client() first.")
        
        try:
            # Create fresh session (ATTS pattern: no model arg, no context manager, no history bleed)
            session = await client.create_session()
            
            # Send and wait - simple request/response (ATTS pattern)
            response = await session.send_and_wait(
                {"prompt": prompt},
                timeout=timeout
            )
            
            # Extract content (ATTS pattern: check response type)
            if (
                response
                and SessionEventType is not None
                and response.type == SessionEventType.ASSISTANT_MESSAGE
            ):
                content = response.data.content
                return content
            elif response and hasattr(response, 'data') and hasattr(response.data, 'content'):
                content = response.data.content
                return content
            else:
                return ""
                
        except Exception as e:
            # Suppress error logging - caller will handle fallback
            raise
    
    def _complete_mock(self, prompt: str, system: Optional[str] = None) -> LLMResponse:
        """
        Mock response for testing/demo purposes.
        
        Used when GitHub Copilot SDK is not available or use_real_llm=False.
        """
        mock_content = f"""[Mock LLM Response - GitHub Copilot SDK not available or disabled]

This is a placeholder response. To use real GitHub Copilot LLM:
1. Ensure github-copilot-sdk is installed: pip install github-copilot-sdk
2. Set use_real_llm=True when creating CopilotClient
3. Have an active GitHub Copilot subscription

System: {system[:100] if system else 'None'}...
Prompt: {prompt[:100]}...

The actual implementation uses the official GitHub Copilot SDK with no
Anthropic/Claude dependency."""
        
        return LLMResponse(
            content=mock_content,
            model=f"{self.model} (mock)",
            usage={
                "prompt_tokens": len(prompt) // 4,
                "completion_tokens": len(mock_content) // 4,
                "total_tokens": (len(prompt) + len(mock_content)) // 4
            },
            finish_reason="stop"
        )
    
    def format_facts_to_analysis(
        self,
        facts: Dict[str, Any],
        context: str,
        telemetry_summary: str
    ) -> str:
        """
        Format deterministic facts into human-readable analysis.
        
        This is the core LLM use case: facts are pre-computed by code,
        LLM only formats them into prose.
        
        Args:
            facts: Dictionary of computed facts (error counts, etc.)
            context: Domain knowledge from context documents
            telemetry_summary: Summary of relevant log entries
            
        Returns:
            Human-readable analysis text
        """
        system_prompt = """You are a technical incident analyst.
Your job is to format pre-computed facts into clear, actionable analysis.

IMPORTANT:
- Facts are ALREADY COMPUTED and VERIFIED by code - do not question them
- Your role is to EXPLAIN the facts in human-readable form
- Focus on root cause, impact, and actionable recommendations
- Be concise and specific
- Do not speculate beyond the provided facts"""

        user_prompt = f"""Given the following incident data, format it into a clear analysis.

CONTEXT (Domain Knowledge):
{context[:500]}...

FACTS (Pre-computed by code):
{json.dumps(facts, indent=2)}

TELEMETRY SUMMARY:
{telemetry_summary[:300]}...

Provide:
1. What happened (based on facts)
2. Root cause (if clear from facts)
3. Impact assessment
4. Specific recommendations (with commands if applicable)

Keep response under 300 words."""

        response = self.complete(
            prompt=user_prompt,
            system=system_prompt,
            max_tokens=500,
            temperature=0.3  # Lower temperature for factual analysis
        )
        
        return response.content
    
    def __repr__(self) -> str:
        return f"CopilotClient(model={self.model}, max_tokens={self.max_tokens})"


def create_client(**kwargs) -> CopilotClient:
    """
    Create a CopilotClient with default or custom settings.
    
    Args:
        **kwargs: Arguments passed to CopilotClient constructor
        
    Returns:
        Configured CopilotClient instance
    """
    return CopilotClient(**kwargs)
