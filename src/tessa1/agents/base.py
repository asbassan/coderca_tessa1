"""
BaseAgent - Foundation for all specialized investigation agents

All agents follow the same pattern:
1. Load domain context (markdown files)
2. Compute deterministic facts (Python code - NO LLM)
3. Format facts into analysis (LLM formatting only)
4. Return structured PhaseResult
"""

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..models import Telemetry, PhaseResult, AgentFinding, Severity
from ..copilot_client import CopilotClient, create_client


class BaseAgent(ABC):
    """
    Base class for all investigation agents.
    
    Implements the deterministic + LLM hybrid pattern:
    - Subclass implements compute_facts() - pure Python logic
    - BaseAgent handles LLM formatting via format_analysis()
    - No LLM involvement in decisions or fact computation
    """
    
    def __init__(
        self,
        agent_name: str,
        context_file: str,
        copilot_client: Optional[CopilotClient] = None
    ):
        """
        Initialize base agent.
        
        Args:
            agent_name: Name of this agent (e.g., "DatabaseAgent")
            context_file: Relative path to context file (e.g., "components/database.md")
            copilot_client: Optional CopilotClient instance (creates default if None)
        """
        self.agent_name = agent_name
        self.context_file = context_file
        self.client = copilot_client or create_client()
        self.context_content: Optional[str] = None
    
    def load_context(self) -> str:
        """
        Load domain context from markdown file.
        
        Returns:
            Content of context file
            
        Raises:
            FileNotFoundError: If context file doesn't exist
        """
        if self.context_content:
            return self.context_content
        
        # Find context directory (relative to this file)
        base_dir = Path(__file__).parent.parent  # src/coderca/
        context_path = base_dir / "context" / self.context_file
        
        if not context_path.exists():
            raise FileNotFoundError(
                f"Context file not found: {context_path}\n"
                f"Expected at: {context_path.absolute()}"
            )
        
        with open(context_path, "r", encoding="utf-8") as f:
            self.context_content = f.read()
        
        return self.context_content
    
    @abstractmethod
    def compute_facts(self, telemetry: Telemetry) -> Dict[str, Any]:
        """
        Compute deterministic facts from telemetry.
        
        This is pure Python logic - NO LLM calls.
        Facts are verified by code, not guessed.
        
        Args:
            telemetry: Input telemetry data
            
        Returns:
            Dictionary of computed facts
            
        Example:
            {
                "error_count": 33,
                "error_type": "no_such_table",
                "database_file_exists": True,
                "migrations_run": False
            }
        """
        pass
    
    @abstractmethod
    def create_findings(
        self,
        facts: Dict[str, Any],
        telemetry: Telemetry
    ) -> List[AgentFinding]:
        """
        Create structured findings from facts.
        
        This is deterministic - severity and categories decided by code.
        
        Args:
            facts: Computed facts from compute_facts()
            telemetry: Input telemetry data
            
        Returns:
            List of AgentFinding objects
            
        Example:
            [
                AgentFinding(
                    category="database_not_initialized",
                    severity=Severity.CRITICAL,
                    message="Database tables do not exist",
                    evidence=["log entry 1", "log entry 2"]
                )
            ]
        """
        pass
    
    def create_telemetry_summary(
        self,
        telemetry: Telemetry,
        max_errors: int = 10
    ) -> str:
        """
        Create a summary of telemetry for LLM context.
        
        Limits the data sent to LLM to avoid context overflow.
        
        Args:
            telemetry: Input telemetry data
            max_errors: Maximum number of error samples to include
            
        Returns:
            Human-readable telemetry summary
        """
        lines = []
        lines.append(f"Time window: {telemetry.time_window}")
        lines.append(f"Total logs: {len(telemetry.log_entries)}")
        lines.append(f"Errors: {telemetry.error_count}")
        lines.append(f"Warnings: {telemetry.warning_count}")
        
        if telemetry.keywords:
            lines.append(f"Keywords: {', '.join(sorted(telemetry.keywords))}")
        
        if telemetry.error_types:
            lines.append(f"Error types: {', '.join(sorted(telemetry.error_types))}")
        
        if telemetry.components:
            lines.append(f"Components: {', '.join(sorted(telemetry.components))}")
        
        # Add sample errors
        errors = telemetry.get_errors()[:max_errors]
        if errors:
            lines.append(f"\nSample errors (first {len(errors)}):")
            for i, error in enumerate(errors, 1):
                lines.append(f"\n{i}. [{error.timestamp}] {error.message[:200]}")
                if error.exception:
                    # First line of exception only
                    exc_line = error.exception.split("\n")[0]
                    lines.append(f"   Exception: {exc_line[:150]}")
        
        return "\n".join(lines)
    
    def format_analysis(
        self,
        facts: Dict[str, Any],
        telemetry: Telemetry,
        context: str
    ) -> str:
        """
        Format facts into human-readable analysis using LLM.
        
        LLM only formats pre-computed facts - does not compute new facts.
        
        Args:
            facts: Pre-computed facts from compute_facts()
            telemetry: Input telemetry
            context: Domain context from markdown file
            
        Returns:
            Human-readable analysis text
        """
        telemetry_summary = self.create_telemetry_summary(telemetry)
        
        analysis = self.client.format_facts_to_analysis(
            facts=facts,
            context=context,
            telemetry_summary=telemetry_summary
        )
        
        return analysis
    
    def should_escalate(
        self,
        facts: Dict[str, Any],
        findings: List[AgentFinding]
    ) -> bool:
        """
        Determine if escalation is needed (deterministic).
        
        This is code-based logic, not LLM guessing.
        
        Args:
            facts: Computed facts
            findings: Detected findings
            
        Returns:
            True if escalation recommended, False otherwise
        """
        # Escalate if any critical findings
        if any(f.severity == Severity.CRITICAL for f in findings):
            return True
        
        # Escalate if high error count
        if facts.get("error_count", 0) > 20:
            return True
        
        # Escalate if multiple high-severity findings
        high_severity = [f for f in findings if f.severity == Severity.HIGH]
        if len(high_severity) >= 2:
            return True
        
        return False
    
    def investigate(self, telemetry: Telemetry, runlog: Optional[Any] = None) -> PhaseResult:
        """
        Run full investigation workflow.
        
        This is the main entry point called by the orchestrator.
        
        Args:
            telemetry: Input telemetry data
            runlog: Optional RunLog for detailed tracking
            
        Returns:
            PhaseResult with facts, findings, and analysis
        """
        start_time = time.time()
        
        try:
            # Track start
            if runlog:
                runlog.agent_start(self.agent_name)
            
            # Step 1: Load context
            context = self.load_context()
            
            if runlog:
                context_size_kb = len(context) / 1024
                runlog.context_loaded(self.agent_name, self.context_file, context_size_kb)
            
            # Step 2: Compute facts (deterministic)
            facts = self.compute_facts(telemetry)
            
            if runlog:
                # Write facts to scratchpad
                facts_str = f"Facts Computed:\n" + "\n".join([f"  {k}: {v}" for k, v in facts.items()])
                estimated_tokens = len(facts_str) // 4  # Rough estimate
                runlog.scratchpad_write(
                    self.agent_name,
                    "Facts Computation (Deterministic)",
                    facts_str,
                    estimated_tokens=estimated_tokens
                )
                
                # Log each fact
                for key, value in facts.items():
                    runlog.fact_computed(self.agent_name, key, value)
            
            # Step 3: Create findings (deterministic)
            findings = self.create_findings(facts, telemetry)
            
            if runlog:
                # Write findings to scratchpad
                findings_str = "Findings Created:\n" + "\n".join([
                    f"  [{f.severity.value.upper()}] {f.category}: {f.message}"
                    for f in findings
                ])
                estimated_tokens = len(findings_str) // 4
                runlog.scratchpad_write(
                    self.agent_name,
                    "Findings Creation (Deterministic)",
                    findings_str,
                    estimated_tokens=estimated_tokens
                )
                
                # Log each finding
                for finding in findings:
                    runlog.finding_created(
                        self.agent_name,
                        finding.category,
                        finding.severity.value
                    )
            
            # Step 4: Format analysis (LLM)
            analysis = self.format_analysis(facts, telemetry, context)
            
            if runlog:
                # Write LLM interaction to scratchpad
                llm_section = f"""
Context Provided:
  File: {self.context_file}
  Size: {len(context)} chars ({len(context) // 4} tokens est.)

Facts Provided:
  {len(facts)} facts computed

Telemetry Summary:
  {len(telemetry.log_entries)} log entries
  {telemetry.error_count} errors

LLM Response:
{analysis}
"""
                # Estimate tokens saved by keeping context/facts in scratchpad
                estimated_context_tokens = len(context) // 4
                runlog.scratchpad_write(
                    self.agent_name,
                    "LLM Analysis Formatting",
                    llm_section.strip(),
                    estimated_tokens=estimated_context_tokens
                )
                
                runlog.llm_call(
                    self.agent_name,
                    "Format analysis from facts",
                    tokens_used=0,  # Mock - would be actual tokens from LLM
                    duration_ms=0.0
                )
            
            # Step 5: Determine escalation (deterministic)
            escalation = self.should_escalate(facts, findings)
            
            # Step 6: Calculate confidence
            confidence = self._calculate_confidence(facts, findings)
            
            if runlog:
                decision_str = f"""
Escalation Decision:
  Recommended: {escalation}
  Confidence: {confidence:.0%}
  Reasoning:
    - Critical findings: {sum(1 for f in findings if f.severity == Severity.CRITICAL)}
    - High findings: {sum(1 for f in findings if f.severity == Severity.HIGH)}
    - Error count: {facts.get('error_count', 0)}
"""
                runlog.scratchpad_write(
                    self.agent_name,
                    "Escalation Decision (Deterministic)",
                    decision_str.strip(),
                    estimated_tokens=0
                )
            
            execution_time = (time.time() - start_time) * 1000  # ms
            
            if runlog:
                runlog.agent_end(
                    self.agent_name,
                    len(findings),
                    confidence,
                    duration_ms=execution_time
                )
            
            return PhaseResult(
                agent_name=self.agent_name,
                executed=True,
                facts=facts,
                findings=findings,
                analysis=analysis,
                execution_time_ms=execution_time,
                confidence=confidence,
                escalation_recommended=escalation
            )
            
        except Exception as e:
            # Return error result
            execution_time = (time.time() - start_time) * 1000
            
            if runlog:
                runlog.error(self.agent_name, str(e))
            
            return PhaseResult(
                agent_name=self.agent_name,
                executed=False,
                facts={"error": str(e)},
                findings=[],
                analysis=f"Agent execution failed: {e}",
                execution_time_ms=execution_time,
                confidence=0.0,
                escalation_recommended=True
            )
    
    def _calculate_confidence(
        self,
        facts: Dict[str, Any],
        findings: List[AgentFinding]
    ) -> float:
        """
        Calculate confidence score (deterministic).
        
        Args:
            facts: Computed facts
            findings: Detected findings
            
        Returns:
            Confidence score (0.0 - 1.0)
        """
        # Start with base confidence
        confidence = 0.5
        
        # Increase if we have clear error patterns
        if facts.get("error_type"):
            confidence += 0.2
        
        # Increase if we have specific findings
        if findings:
            confidence += 0.2
        
        # Increase if error count is high (more data = more confidence)
        error_count = facts.get("error_count", 0)
        if error_count > 10:
            confidence += 0.1
        
        # Cap at 1.0
        return min(confidence, 1.0)
    
    def __repr__(self) -> str:
        return f"{self.agent_name}(context={self.context_file})"
