"""
Core data models for CodeRCA investigation system.

These models define the structure of data as it flows through the system:
- Telemetry: Input from log collection
- PhaseResult: Output from agent investigation
- InvestigationContext: State carried through pipeline
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Set, Any
from enum import Enum


class LogLevel(str, Enum):
    """Log severity levels"""
    ERROR = "Error"
    WARNING = "Warning"
    INFORMATION = "Information"
    DEBUG = "Debug"


class Severity(str, Enum):
    """Finding severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class TimeWindow:
    """Time range for investigation"""
    start: datetime
    end: datetime
    
    def duration_seconds(self) -> float:
        """Calculate duration in seconds"""
        return (self.end - self.start).total_seconds()
    
    def __str__(self) -> str:
        return f"{self.start.isoformat()} to {self.end.isoformat()}"


@dataclass
class LogEntry:
    """
    Single log entry from Serilog SQLite database.
    
    Maps to the Logs table schema:
    - Id, Timestamp, Level, Exception, RenderedMessage, Properties
    """
    id: int
    timestamp: datetime
    level: LogLevel
    message: str
    exception: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def is_error(self) -> bool:
        return self.level == LogLevel.ERROR
    
    def is_warning(self) -> bool:
        return self.level == LogLevel.WARNING
    
    def contains_keyword(self, keyword: str) -> bool:
        """Check if keyword appears in message or exception"""
        keyword_lower = keyword.lower()
        if keyword_lower in self.message.lower():
            return True
        if self.exception and keyword_lower in self.exception.lower():
            return True
        return False


@dataclass
class Telemetry:
    """
    Collected telemetry data for investigation.
    
    Represents logs and metadata extracted from the database
    for a specific time window.
    """
    time_window: TimeWindow
    log_entries: List[LogEntry]
    
    # Computed metadata
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    
    # Extracted patterns
    keywords: Set[str] = field(default_factory=set)
    error_types: Set[str] = field(default_factory=set)
    components: Set[str] = field(default_factory=set)
    
    @property
    def total_logs(self) -> int:
        return len(self.log_entries)
    
    @property
    def has_errors(self) -> bool:
        return self.error_count > 0
    
    @property
    def has_warnings(self) -> bool:
        return self.warning_count > 0
    
    def get_errors(self) -> List[LogEntry]:
        """Return only error-level entries"""
        return [entry for entry in self.log_entries if entry.is_error()]
    
    def get_warnings(self) -> List[LogEntry]:
        """Return only warning-level entries"""
        return [entry for entry in self.log_entries if entry.is_warning()]
    
    def contains_keyword(self, keyword: str) -> bool:
        """Check if keyword appears in any log entry"""
        return keyword.lower() in {k.lower() for k in self.keywords}
    
    def __str__(self) -> str:
        return (f"Telemetry({self.total_logs} logs, "
                f"{self.error_count} errors, "
                f"{self.warning_count} warnings)")


@dataclass
class AgentFinding:
    """
    Single finding discovered by an agent.
    
    Represents a specific issue, observation, or recommendation.
    """
    category: str
    severity: Severity
    message: str
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_critical(self) -> bool:
        return self.severity == Severity.CRITICAL
    
    def is_actionable(self) -> bool:
        """Check if finding has recommended actions"""
        return "recommendation" in self.metadata or "solution" in self.metadata


@dataclass
class PhaseResult:
    """
    Result from a single agent's investigation phase.
    
    Combines:
    - Deterministic facts (computed by code)
    - LLM-generated analysis (formatted summary)
    - Structured findings
    """
    agent_name: str
    executed: bool = True
    
    # Deterministic facts (computed, not LLM-generated)
    facts: Dict[str, Any] = field(default_factory=dict)
    
    # Structured findings
    findings: List[AgentFinding] = field(default_factory=list)
    
    # LLM-generated content
    analysis: str = ""
    
    # Agent metadata
    execution_time_ms: float = 0.0
    confidence: float = 1.0  # 0.0 - 1.0
    
    # Computed decision (code, not LLM)
    escalation_recommended: bool = False
    
    # Errors during investigation
    error: Optional[str] = None
    
    @property
    def has_critical_findings(self) -> bool:
        return any(f.is_critical() for f in self.findings)
    
    @property
    def succeeded(self) -> bool:
        return self.executed and self.error is None
    
    def get_findings_by_severity(self, severity: Severity) -> List[AgentFinding]:
        """Filter findings by severity"""
        return [f for f in self.findings if f.severity == severity]


@dataclass
class InvestigationContext:
    """
    Context carried through the investigation pipeline.
    
    Accumulates state as investigation progresses through phases.
    """
    investigation_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    
    # Trigger information
    trigger: str = "manual"  # "manual", "scenario", "alert"
    trigger_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Time window being investigated
    time_window: Optional[TimeWindow] = None
    
    # Collected telemetry (by InfoRetAgent)
    telemetry: Optional[Telemetry] = None
    
    # Selected agents (by AgentSelector)
    selected_agents: List[str] = field(default_factory=list)
    
    # Phase results (as agents complete)
    phase_results: List[PhaseResult] = field(default_factory=list)
    
    # Synthesis output
    overall_analysis: str = ""
    escalation_decision: bool = False
    
    def add_phase_result(self, result: PhaseResult) -> None:
        """Add a phase result and update escalation decision"""
        self.phase_results.append(result)
        
        # Update escalation if any agent recommends it
        if result.escalation_recommended:
            self.escalation_decision = True
    
    @property
    def duration_seconds(self) -> float:
        """Total investigation duration"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def agents_executed(self) -> int:
        return sum(1 for r in self.phase_results if r.executed)
    
    @property
    def has_errors(self) -> bool:
        return any(r.error is not None for r in self.phase_results)
    
    def get_result_by_agent(self, agent_name: str) -> Optional[PhaseResult]:
        """Find result for specific agent"""
        for result in self.phase_results:
            if result.agent_name == agent_name:
                return result
        return None


@dataclass
class InvestigationReport:
    """
    Final investigation report output.
    
    Synthesized from all phase results into a structured report.
    """
    investigation_id: str
    timestamp: datetime
    time_window: TimeWindow
    
    # Summary
    incident_description: str
    agents_executed: List[str]
    
    # Phase results
    phase_results: List[PhaseResult]
    
    # Synthesis
    overall_summary: str
    key_findings: List[str]
    root_cause: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)
    
    # Decision
    escalation_needed: bool = False
    escalation_reason: Optional[str] = None
    
    # Metadata
    total_errors: int = 0
    total_warnings: int = 0
    investigation_duration_ms: float = 0.0
    
    def to_text(self) -> str:
        """Format report as plain text"""
        lines = [
            "=" * 70,
            "Investigation Report",
            "=" * 70,
            f"Investigation ID: {self.investigation_id}",
            f"Timestamp: {self.timestamp.isoformat()}",
            f"Time Window: {self.time_window}",
            f"Duration: {self.investigation_duration_ms:.0f}ms",
            "",
            "Incident:",
            f"  {self.incident_description}",
            "",
            f"Agents Executed: {', '.join(self.agents_executed)}",
            f"Total Errors: {self.total_errors}",
            f"Total Warnings: {self.total_warnings}",
            "",
            "=" * 70,
            "Overall Summary",
            "=" * 70,
            self.overall_summary,
            "",
        ]
        
        # Add key findings
        if self.key_findings:
            lines.append("Key Findings:")
            for i, finding in enumerate(self.key_findings, 1):
                lines.append(f"  {i}. {finding}")
            lines.append("")
        
        # Add root cause
        if self.root_cause:
            lines.append("Root Cause:")
            lines.append(f"  {self.root_cause}")
            lines.append("")
        
        # Add recommendations
        if self.recommendations:
            lines.append("Recommendations:")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
        
        # Add escalation
        lines.append("=" * 70)
        lines.append(f"Escalation Needed: {'YES' if self.escalation_needed else 'NO'}")
        if self.escalation_reason:
            lines.append(f"Reason: {self.escalation_reason}")
        lines.append("=" * 70)
        
        # Add phase details
        lines.append("")
        lines.append("Phase Details:")
        lines.append("-" * 70)
        for result in self.phase_results:
            lines.append(f"\n{result.agent_name}:")
            lines.append(f"  Status: {'Success' if result.succeeded else 'Failed'}")
            lines.append(f"  Findings: {len(result.findings)}")
            lines.append(f"  Confidence: {result.confidence:.1%}")
            if result.analysis:
                lines.append(f"  Analysis: {result.analysis[:200]}...")
        
        return "\n".join(lines)
