"""
Base scenario class for fault injection and testing
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any


class ScenarioSeverity(Enum):
    """Scenario severity level"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ScenarioResult:
    """Result of scenario execution"""
    scenario_id: str
    scenario_name: str
    success: bool
    timestamp: datetime
    duration_ms: float
    
    # Telemetry
    logs_generated: int
    errors_generated: int
    
    # Investigation
    investigation_id: Optional[str] = None
    root_cause_identified: Optional[str] = None
    escalation_triggered: bool = False
    
    # Runlog
    runlog_path: Optional[Path] = None
    
    # Fault injection details
    fault_details: Dict[str, Any] = None
    
    def to_text(self) -> str:
        """Format as human-readable text"""
        lines = [
            "=" * 70,
            f"Scenario Result: {self.scenario_id} - {self.scenario_name}",
            "=" * 70,
            f"Status: {'SUCCESS' if self.success else 'FAILED'}",
            f"Timestamp: {self.timestamp.isoformat()}",
            f"Duration: {self.duration_ms:.0f}ms",
            "",
            "Telemetry:",
            f"  Logs Generated: {self.logs_generated}",
            f"  Errors Generated: {self.errors_generated}",
            ""
        ]
        
        if self.investigation_id:
            lines.extend([
                "Investigation:",
                f"  ID: {self.investigation_id}",
                f"  Root Cause: {self.root_cause_identified}",
                f"  Escalation: {'YES' if self.escalation_triggered else 'NO'}",
                ""
            ])
        
        if self.runlog_path:
            lines.extend([
                "Runlog:",
                f"  Path: {self.runlog_path}",
                ""
            ])
        
        if self.fault_details:
            lines.extend([
                "Fault Details:",
                *[f"  {k}: {v}" for k, v in self.fault_details.items()],
                ""
            ])
        
        lines.append("=" * 70)
        
        return "\n".join(lines)


class Scenario(ABC):
    """
    Base class for fault injection scenarios.
    
    Each scenario represents a specific incident that can be:
    1. Injected - create the fault condition
    2. Investigated - run RCA pipeline
    3. Replayed - reproduce from saved runlog
    """
    
    def __init__(self):
        self.scenario_id = self.__class__.__name__.replace("Scenario", "")
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable scenario name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed scenario description"""
        pass
    
    @property
    @abstractmethod
    def severity(self) -> ScenarioSeverity:
        """Scenario severity"""
        pass
    
    @abstractmethod
    def inject_fault(self) -> Dict[str, Any]:
        """
        Inject the fault into the system.
        
        Returns:
            Dictionary with fault injection details
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """
        Clean up after scenario execution.
        
        Restore system to normal state.
        """
        pass
    
    @abstractmethod
    def verify_telemetry(self, logs_generated: int, errors_generated: int) -> bool:
        """
        Verify that expected telemetry was generated.
        
        Args:
            logs_generated: Number of logs generated
            errors_generated: Number of errors generated
            
        Returns:
            True if telemetry matches expectations
        """
        pass
    
    def get_expected_agents(self) -> list:
        """
        Get expected agent selection for this scenario.
        
        Returns:
            List of agent names that should be selected
        """
        return []
    
    def get_expected_root_cause(self) -> str:
        """
        Get expected root cause identification.
        
        Returns:
            Expected root cause string
        """
        return ""
