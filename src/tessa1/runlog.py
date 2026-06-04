"""
RunLog - Detailed execution tracking similar to ATTS

Tracks every step of the investigation with timestamps, metrics, and context.
Generates scratchpad files for each agent to reduce token usage.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pathlib import Path
import json


class LogEntryType(Enum):
    """Type of runlog entry"""
    PHASE_START = "phase_start"
    PHASE_END = "phase_end"
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    DECISION = "decision"
    CONTEXT_LOAD = "context_load"
    LLM_CALL = "llm_call"
    FACT_COMPUTED = "fact_computed"
    FINDING_CREATED = "finding_created"
    SCRATCHPAD_CREATED = "scratchpad_created"
    ERROR = "error"
    INFO = "info"


@dataclass
class RunLogEntry:
    """Single entry in the runlog"""
    timestamp: datetime
    entry_type: LogEntryType
    component: str  # "Orchestrator", "DatabaseAgent", etc.
    message: str
    
    # Optional details
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    tokens_used: Optional[int] = None
    
    def to_text(self, indent: int = 0) -> str:
        """Format as human-readable text"""
        prefix = "  " * indent
        time_str = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        
        # Base line
        line = f"{prefix}[{time_str}] {self.component}: {self.message}"
        
        # Add metrics
        metrics = []
        if self.duration_ms is not None:
            metrics.append(f"{self.duration_ms:.1f}ms")
        if self.tokens_used is not None:
            metrics.append(f"{self.tokens_used} tokens")
        
        if metrics:
            line += f" ({', '.join(metrics)})"
        
        return line
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.entry_type.value,
            "component": self.component,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used
        }


class RunLog:
    """
    Execution log tracker for investigations.
    
    Similar to ATTS runlog, tracks every step with timestamps and metrics.
    Generates per-agent scratchpad files to reduce token usage.
    """
    
    def __init__(self, investigation_id: str, output_dir: Optional[Path] = None):
        self.investigation_id = investigation_id
        self.output_dir = output_dir or Path("runlogs")
        self.output_dir.mkdir(exist_ok=True)
        
        self.entries: List[RunLogEntry] = []
        self.start_time = datetime.now()
        
        # Track metrics
        self.total_tokens = 0
        self.llm_calls = 0
        
        # Track scratchpads
        self.scratchpads: Dict[str, List[str]] = {}  # agent_name -> lines
        self.scratchpad_tokens_saved = 0  # Tokens that would be in main context
        
    def _get_scratchpad_path(self, agent_name: str) -> Path:
        """Get path for agent scratchpad file"""
        return self.output_dir / f"{self.investigation_id}_scratchpad_{agent_name}.txt"
        
    def log(
        self,
        entry_type: LogEntryType,
        component: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        tokens_used: Optional[int] = None
    ):
        """Add entry to runlog"""
        entry = RunLogEntry(
            timestamp=datetime.now(),
            entry_type=entry_type,
            component=component,
            message=message,
            details=details or {},
            duration_ms=duration_ms,
            tokens_used=tokens_used
        )
        
        self.entries.append(entry)
        
        # Update metrics
        if tokens_used:
            self.total_tokens += tokens_used
            self.llm_calls += 1
    
    def phase_start(self, phase_num: int, phase_name: str):
        """Log phase start"""
        self.log(
            LogEntryType.PHASE_START,
            "Orchestrator",
            f"Phase {phase_num}/5: {phase_name}",
            details={"phase": phase_num, "name": phase_name}
        )
    
    def phase_end(self, phase_num: int, phase_name: str, duration_ms: float):
        """Log phase completion"""
        self.log(
            LogEntryType.PHASE_END,
            "Orchestrator",
            f"Phase {phase_num}/5 complete: {phase_name}",
            details={"phase": phase_num, "name": phase_name},
            duration_ms=duration_ms
        )
    
    def agent_start(self, agent_name: str):
        """Log agent execution start"""
        self.log(
            LogEntryType.AGENT_START,
            agent_name,
            f"Starting investigation",
            details={"agent": agent_name}
        )
    
    def agent_end(
        self,
        agent_name: str,
        findings_count: int,
        confidence: float,
        duration_ms: float
    ):
        """Log agent completion"""
        self.log(
            LogEntryType.AGENT_END,
            agent_name,
            f"Investigation complete: {findings_count} findings, {confidence:.0%} confidence",
            details={
                "agent": agent_name,
                "findings": findings_count,
                "confidence": confidence
            },
            duration_ms=duration_ms
        )
    
    def context_loaded(self, agent_name: str, file_path: str, size_kb: float):
        """Log context document loading"""
        self.log(
            LogEntryType.CONTEXT_LOAD,
            agent_name,
            f"Loaded context: {file_path} ({size_kb:.1f} KB)",
            details={"file": file_path, "size_kb": size_kb}
        )
    
    def llm_call(
        self,
        component: str,
        purpose: str,
        tokens_used: int,
        duration_ms: float
    ):
        """Log LLM API call"""
        self.log(
            LogEntryType.LLM_CALL,
            component,
            f"LLM call: {purpose}",
            details={"purpose": purpose},
            duration_ms=duration_ms,
            tokens_used=tokens_used
        )
    
    def fact_computed(self, agent_name: str, fact_key: str, fact_value: Any):
        """Log fact computation"""
        self.log(
            LogEntryType.FACT_COMPUTED,
            agent_name,
            f"Computed fact: {fact_key} = {fact_value}",
            details={"key": fact_key, "value": str(fact_value)}
        )
    
    def finding_created(
        self,
        agent_name: str,
        category: str,
        severity: str
    ):
        """Log finding creation"""
        self.log(
            LogEntryType.FINDING_CREATED,
            agent_name,
            f"Created finding: [{severity}] {category}",
            details={"category": category, "severity": severity}
        )
    
    def decision(self, component: str, decision: str, reason: str):
        """Log decision made"""
        self.log(
            LogEntryType.DECISION,
            component,
            f"Decision: {decision}",
            details={"decision": decision, "reason": reason}
        )
    
    def info(self, component: str, message: str, details: Optional[Dict] = None):
        """Log informational message"""
        self.log(
            LogEntryType.INFO,
            component,
            message,
            details=details
        )
    
    def error(self, component: str, error_msg: str, details: Optional[Dict] = None):
        """Log error"""
        self.log(
            LogEntryType.ERROR,
            component,
            f"ERROR: {error_msg}",
            details=details
        )
    
    def scratchpad_write(
        self,
        agent_name: str,
        section: str,
        content: str,
        estimated_tokens: int = 0
    ):
        """
        Write to agent scratchpad file.
        
        This keeps detailed agent work out of main context, saving tokens.
        
        Args:
            agent_name: Name of agent (e.g., "DatabaseAgent")
            section: Section header (e.g., "Facts Computation", "LLM Prompt")
            content: Content to write
            estimated_tokens: Estimated tokens saved by offloading to scratchpad
        """
        if agent_name not in self.scratchpads:
            self.scratchpads[agent_name] = [
                "=" * 70,
                f"{agent_name} Investigation Scratchpad",
                "=" * 70,
                f"Investigation ID: {self.investigation_id}",
                f"Start Time: {self.start_time.isoformat()}",
                "=" * 70,
                ""
            ]
        
        # Add section
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.scratchpads[agent_name].extend([
            f"\n[{timestamp}] {section}",
            "-" * 70,
            content,
            ""
        ])
        
        # Track token savings
        if estimated_tokens > 0:
            self.scratchpad_tokens_saved += estimated_tokens
        
        # Log scratchpad write
        self.log(
            LogEntryType.SCRATCHPAD_CREATED,
            agent_name,
            f"Scratchpad: {section} ({estimated_tokens} tokens saved)",
            details={"section": section, "tokens_saved": estimated_tokens}
        )
    
    def scratchpad_save(self, agent_name: str):
        """Save agent scratchpad to file"""
        if agent_name not in self.scratchpads:
            return
        
        scratchpad_path = self._get_scratchpad_path(agent_name)
        content = "\n".join(self.scratchpads[agent_name])
        
        scratchpad_path.write_text(content, encoding='utf-8')
        
        self.log(
            LogEntryType.INFO,
            agent_name,
            f"Scratchpad saved: {scratchpad_path.name}",
            details={"path": str(scratchpad_path)}
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary"""
        total_duration = (datetime.now() - self.start_time).total_seconds() * 1000
        
        return {
            "investigation_id": self.investigation_id,
            "total_entries": len(self.entries),
            "total_duration_ms": total_duration,
            "total_tokens": self.total_tokens,
            "llm_calls": self.llm_calls,
            "phases_completed": len([e for e in self.entries if e.entry_type == LogEntryType.PHASE_END]),
            "agents_executed": len([e for e in self.entries if e.entry_type == LogEntryType.AGENT_END]),
            "facts_computed": len([e for e in self.entries if e.entry_type == LogEntryType.FACT_COMPUTED]),
            "findings_created": len([e for e in self.entries if e.entry_type == LogEntryType.FINDING_CREATED]),
            "scratchpads_created": len(self.scratchpads),
            "scratchpad_tokens_saved": self.scratchpad_tokens_saved,
            "errors": len([e for e in self.entries if e.entry_type == LogEntryType.ERROR])
        }
    
    def to_text(self, verbose: bool = False) -> str:
        """
        Format runlog as text.
        
        Args:
            verbose: Include all details, not just summary
        
        Returns:
            Formatted runlog text
        """
        lines = [
            "=" * 70,
            "Investigation RunLog",
            "=" * 70,
            f"Investigation ID: {self.investigation_id}",
            f"Start Time: {self.start_time.isoformat()}",
            ""
        ]
        
        # Add summary
        summary = self.get_summary()
        lines.extend([
            "Summary:",
            f"  Total Duration: {summary['total_duration_ms']:.0f}ms",
            f"  Phases Completed: {summary['phases_completed']}/5",
            f"  Agents Executed: {summary['agents_executed']}",
            f"  Facts Computed: {summary['facts_computed']}",
            f"  Findings Created: {summary['findings_created']}",
            f"  LLM Calls: {summary['llm_calls']} ({summary['total_tokens']} tokens)",
            f"  Scratchpads Created: {summary['scratchpads_created']}",
            f"  Tokens Saved (Scratchpads): {summary['scratchpad_tokens_saved']}",
            f"  Errors: {summary['errors']}",
            ""
        ])
        
        # Token efficiency
        if summary['scratchpad_tokens_saved'] > 0:
            total_tokens_used = summary['total_tokens']
            tokens_without_scratchpad = total_tokens_used + summary['scratchpad_tokens_saved']
            savings_pct = (summary['scratchpad_tokens_saved'] / tokens_without_scratchpad) * 100
            
            lines.extend([
                "Token Efficiency:",
                f"  Without Scratchpads: {tokens_without_scratchpad} tokens (estimated)",
                f"  With Scratchpads: {total_tokens_used} tokens (actual)",
                f"  Savings: {savings_pct:.1f}%",
                ""
            ])
        
        # Add entries
        if verbose or True:  # Always show for now
            lines.append("=" * 70)
            lines.append("Execution Timeline:")
            lines.append("=" * 70)
            
            for entry in self.entries:
                lines.append(entry.to_text())
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """Export runlog as JSON"""
        data = {
            "investigation_id": self.investigation_id,
            "start_time": self.start_time.isoformat(),
            "summary": self.get_summary(),
            "entries": [e.to_dict() for e in self.entries]
        }
        return json.dumps(data, indent=2)
    
    def save(self, output_path: Optional[str] = None, format: str = "text"):
        """
        Save runlog to file.
        
        Args:
            output_path: Path to save file (defaults to output_dir/<id>.txt or .json)
            format: "text" or "json"
        """
        # Determine output path
        if not output_path:
            ext = ".json" if format == "json" else ".txt"
            output_path = str(self.output_dir / f"{self.investigation_id}{ext}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if format == "json":
                f.write(self.to_json())
            else:
                f.write(self.to_text(verbose=True))
        
        # Save all scratchpads
        for agent_name in self.scratchpads:
            self.scratchpad_save(agent_name)
