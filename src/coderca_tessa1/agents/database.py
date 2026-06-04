"""
DatabaseAgent - Investigates database infrastructure issues

Specializes in:
- Entity Framework Core issues
- Database migrations
- Connection problems
- SQL errors
- Schema mismatches
"""

from pathlib import Path
from typing import Dict, List, Any

from .base import BaseAgent
from ..models import Telemetry, AgentFinding, Severity


class DatabaseAgent(BaseAgent):
    """
    Agent specialized in database infrastructure investigation.
    
    Loads context from: context/components/database.md
    """
    
    def __init__(self, copilot_client=None):
        super().__init__(
            agent_name="DatabaseAgent",
            context_file="components/database.md",
            copilot_client=copilot_client
        )
    
    def compute_facts(self, telemetry: Telemetry) -> Dict[str, Any]:
        """
        Compute database-related facts from telemetry.
        
        Facts computed (deterministic):
        - Error counts and types
        - Database file status
        - Migration status indicators
        - Affected tables
        """
        facts = {}
        
        # Basic error statistics
        errors = telemetry.get_errors()
        facts["error_count"] = len(errors)
        facts["total_logs"] = len(telemetry.log_entries)
        
        # Detect error type
        if any("no such table" in e.message.lower() or 
               (e.exception and "no such table" in e.exception.lower())
               for e in errors):
            facts["error_type"] = "no_such_table"
        elif any("database is locked" in e.message.lower() or
                 (e.exception and "database is locked" in e.exception.lower())
                 for e in errors):
            facts["error_type"] = "database_locked"
        elif any("constraint" in e.message.lower() or
                 (e.exception and "constraint" in e.exception.lower())
                 for e in errors):
            facts["error_type"] = "constraint_violation"
        else:
            facts["error_type"] = "unknown"
        
        # Extract affected tables
        affected_tables = set()
        for entry in errors:
            text = entry.message + " " + (entry.exception or "")
            # Look for common table patterns
            for table in ["CatalogBrands", "CatalogTypes", "CatalogItems",
                         "Orders", "OrderItems", "Baskets", "BasketItems"]:
                if table in text:
                    affected_tables.add(table)
        
        facts["affected_tables"] = list(affected_tables)
        
        # Check for SQLite-specific errors
        facts["is_sqlite_error"] = "SqliteException" in telemetry.error_types
        
        # Infer migration status
        # If "no such table" errors on core tables, migrations likely not run
        if facts["error_type"] == "no_such_table" and affected_tables:
            facts["migrations_run"] = False
        else:
            facts["migrations_run"] = None  # Unknown
        
        # Check for EntityFrameworkCore involvement
        facts["is_ef_core_error"] = "EntityFrameworkCore" in " ".join(telemetry.keywords)
        
        # Database connection indicators
        facts["has_connection_errors"] = any(
            "connection" in e.message.lower() or
            (e.exception and "connection" in e.exception.lower())
            for e in errors
        )
        
        return facts
    
    def create_findings(
        self,
        facts: Dict[str, Any],
        telemetry: Telemetry
    ) -> List[AgentFinding]:
        """
        Create structured findings from database facts.
        
        Severity levels determined by code, not LLM.
        """
        findings = []
        
        # Finding 1: Database not initialized
        if facts.get("error_type") == "no_such_table":
            severity = Severity.CRITICAL  # Blocks all DB operations
            
            evidence = []
            errors = telemetry.get_errors()[:3]  # First 3 errors
            for e in errors:
                evidence.append(f"[{e.timestamp}] {e.message[:150]}")
            
            finding = AgentFinding(
                category="database_not_initialized",
                severity=severity,
                message="Database tables do not exist - migrations not applied",
                evidence=evidence,
                metadata={
                    "error_count": facts["error_count"],
                    "affected_tables": facts.get("affected_tables", []),
                    "solution": "Run database migrations",
                    "command": "dotnet ef database update --context CatalogContext"
                }
            )
            findings.append(finding)
        
        # Finding 2: Database locked
        if facts.get("error_type") == "database_locked":
            severity = Severity.HIGH  # Causes failures but may be transient
            
            finding = AgentFinding(
                category="database_locked",
                severity=severity,
                message="Database is locked - concurrent access issue",
                evidence=[f"{facts['error_count']} lock errors detected"],
                metadata={
                    "solution": "Check for long-running transactions or multiple writers",
                    "is_transient": True
                }
            )
            findings.append(finding)
        
        # Finding 3: Constraint violations
        if facts.get("error_type") == "constraint_violation":
            severity = Severity.MEDIUM  # Data integrity issue
            
            finding = AgentFinding(
                category="constraint_violation",
                severity=severity,
                message="Database constraint violations detected",
                evidence=[f"{facts['error_count']} constraint errors"],
                metadata={
                    "solution": "Review data being inserted/updated for constraint compliance"
                }
            )
            findings.append(finding)
        
        # Finding 4: Connection errors
        if facts.get("has_connection_errors"):
            severity = Severity.HIGH
            
            finding = AgentFinding(
                category="database_connection_error",
                severity=severity,
                message="Database connection errors detected",
                evidence=[f"{facts['error_count']} connection-related errors"],
                metadata={
                    "solution": "Check database file path and permissions"
                }
            )
            findings.append(finding)
        
        return findings
