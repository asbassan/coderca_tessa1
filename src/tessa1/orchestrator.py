"""
Orchestrator - Coordinates the full investigation pipeline

Pipeline:
1. InfoRetrieval: Load telemetry from SQLite logs
2. AgentSelection: Pattern-match to select relevant agents
3. AgentExecution: Run selected agents in parallel
4. Synthesis: Combine findings into coherent analysis
5. ReportGeneration: Produce final investigation report

This is the main entry point for CodeRCA investigations.
"""

import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import (
    Telemetry,
    TimeWindow,
    LogEntry,
    LogLevel,
    InvestigationContext,
    InvestigationReport,
    PhaseResult
)
from .agent_selector import AgentSelector
from .agents import DatabaseAgent, CatalogAgent, OrderAgent, BasketAgent
from .copilot_client import CopilotClient, create_client, set_copilot_client, get_copilot_client, COPILOT_SDK_AVAILABLE
from .runlog import RunLog, LogEntryType
from .tooling import resolve_gh_command


class Orchestrator:
    """
    Main orchestrator for CodeRCA investigations.
    
    Coordinates the full pipeline from telemetry loading to report generation.
    Follows CCA orchestrator-worker pattern.
    """
    
    def __init__(
        self,
        log_db_path: Optional[Path] = None,
        copilot_client: Optional[CopilotClient] = None,
        enable_runlog: bool = True,
        use_real_llm: bool = False
    ):
        """
        Initialize orchestrator.
        
        Args:
            log_db_path: Path to SQLite log database (defaults to eshop-logs.db)
            copilot_client: Optional CopilotClient instance
            enable_runlog: Enable detailed runlog tracking
            use_real_llm: Use GitHub Copilot SDK for real LLM calls (vs mock mode)
        """
        self.log_db_path = log_db_path or self._find_log_database()
        self.enable_runlog = enable_runlog
        self.runlog: Optional[RunLog] = None
        self.use_real_llm = use_real_llm
        
        # Initialize shared Copilot SDK client (ATTS pattern)
        if use_real_llm and COPILOT_SDK_AVAILABLE:
            try:
                import subprocess
                from copilot import CopilotClient as GHCopilotClient
                
                # Get GitHub token from gh CLI (ATTS pattern)
                token_result = subprocess.run(
                    [resolve_gh_command(), "auth", "token", "--hostname", "github.com"],
                    capture_output=True, text=True
                )
                
                opts = {}
                if token_result.returncode == 0 and token_result.stdout.strip():
                    opts["github_token"] = token_result.stdout.strip()
                    print(f"[OK] Using GitHub token from gh CLI")
                else:
                    print(f"[WARN] gh auth token unavailable - trying default auth")
                
                sdk_client = GHCopilotClient(opts if opts else None)
                set_copilot_client(sdk_client)
                print("[OK] GitHub Copilot SDK client initialized (ATTS pattern)")
            except Exception as e:
                print(f"[WARN] Failed to initialize Copilot SDK: {e}")
                print("  Falling back to mock mode")
                use_real_llm = False
        
        # Create CopilotClient wrapper (routes to SDK or mock)
        self.client = copilot_client or create_client(use_real_llm=use_real_llm)
        
        # Initialize components
        self.agent_selector = AgentSelector()
        
        # Initialize agents (shared CopilotClient)
        self.agents = {
            "DatabaseAgent": DatabaseAgent(self.client),
            "CatalogAgent": CatalogAgent(self.client),
            "OrderAgent": OrderAgent(self.client),
            "BasketAgent": BasketAgent(self.client)
        }
    
    def _find_log_database(self) -> Path:
        """
        Find the eShopOnWeb log database.
        
        Returns:
            Path to log database
            
        Raises:
            FileNotFoundError: If database not found
        """
        # Try common locations
        candidates = [
            Path("eshop/src/Web/bin/Debug/net8.0/eshop-logs.db"),
            Path("eshop-logs.db"),
            Path("logs/eshop-logs.db")
        ]
        
        for path in candidates:
            if path.exists():
                return path.absolute()
        
        raise FileNotFoundError(
            "Log database not found. Tried:\n" +
            "\n".join(f"  - {p}" for p in candidates)
        )
    
    def load_telemetry(
        self,
        max_logs: int = 100,
        time_window_minutes: Optional[int] = None
    ) -> Telemetry:
        """
        Phase 1: InfoRetrieval - Load telemetry from SQLite database.
        
        This is deterministic - NO LLM involvement.
        
        Args:
            max_logs: Maximum number of log entries to load
            time_window_minutes: Optional time window (last N minutes)
            
        Returns:
            Telemetry object with logs and metadata
        """
        if not self.log_db_path.exists():
            raise FileNotFoundError(f"Log database not found: {self.log_db_path}")
        
        conn = sqlite3.connect(self.log_db_path)
        cursor = conn.cursor()
        
        # Build query
        query = "SELECT Id, Timestamp, Level, RenderedMessage, Exception FROM Logs"
        params = []
        
        if time_window_minutes:
            query += " WHERE Timestamp >= datetime('now', ?)"
            params.append(f"-{time_window_minutes} minutes")
        
        query += " ORDER BY Id DESC LIMIT ?"
        params.append(max_logs)
        
        rows = cursor.execute(query, params).fetchall()
        conn.close()
        
        # Convert to LogEntry objects
        log_entries = []
        for row in rows:
            log_id, timestamp_str, level, message, exception = row
            
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except:
                timestamp = datetime.now()
            
            try:
                log_level = LogLevel(level)
            except ValueError:
                log_level = LogLevel.INFORMATION
            
            entry = LogEntry(
                id=log_id,
                timestamp=timestamp,
                level=log_level,
                message=message or "",
                exception=exception,
                properties={}
            )
            log_entries.append(entry)
        
        # Create time window
        if log_entries:
            timestamps = [e.timestamp for e in log_entries]
            time_window = TimeWindow(min(timestamps), max(timestamps))
        else:
            now = datetime.now()
            time_window = TimeWindow(now, now)
        
        # Extract metadata (deterministic)
        errors = [e for e in log_entries if e.is_error()]
        warnings = [e for e in log_entries if e.is_warning()]
        
        # Extract keywords
        keywords = self._extract_keywords(log_entries)
        error_types = self._extract_error_types(log_entries)
        components = self._extract_components(log_entries)
        
        telemetry = Telemetry(
            time_window=time_window,
            log_entries=log_entries,
            error_count=len(errors),
            warning_count=len(warnings),
            info_count=len(log_entries) - len(errors) - len(warnings),
            keywords=keywords,
            error_types=error_types,
            components=components
        )
        
        return telemetry
    
    def _extract_keywords(self, log_entries: List[LogEntry]) -> set:
        """Extract keywords from log entries"""
        keywords = set()
        keyword_list = [
            "SQLite", "EntityFrameworkCore", "CatalogBrands", "CatalogTypes",
            "CatalogItems", "DbCommand", "DbContext", "Order", "OrderItem",
            "Basket", "BasketItem", "Payment", "Checkout"
        ]
        
        for entry in log_entries:
            text = entry.message + " " + (entry.exception or "")
            for keyword in keyword_list:
                if keyword in text:
                    keywords.add(keyword)
        
        return keywords
    
    def _extract_error_types(self, log_entries: List[LogEntry]) -> set:
        """Extract error types from exceptions"""
        error_types = set()
        
        for entry in log_entries:
            if entry.exception:
                # Extract exception type
                if "SqliteException" in entry.exception:
                    error_types.add("SqliteException")
                if "DbUpdateException" in entry.exception:
                    error_types.add("DbUpdateException")
                if "InvalidOperationException" in entry.exception:
                    error_types.add("InvalidOperationException")
                if "PaymentException" in entry.exception:
                    error_types.add("PaymentException")
                if "ConcurrencyException" in entry.exception:
                    error_types.add("ConcurrencyException")
        
        return error_types
    
    def _extract_components(self, log_entries: List[LogEntry]) -> set:
        """Extract component names from log entries"""
        components = set()
        
        for entry in log_entries:
            text = entry.message + " " + (entry.exception or "")
            
            if "Microsoft.eShopWeb" in text:
                components.add("Microsoft.eShopWeb")
            if "CatalogContext" in text:
                components.add("CatalogContext")
            if "Microsoft.EntityFrameworkCore" in text:
                components.add("Microsoft.EntityFrameworkCore")
            if "CatalogService" in text:
                components.add("CatalogService")
            if "OrderService" in text:
                components.add("OrderService")
            if "BasketService" in text:
                components.add("BasketService")
        
        return components
    
    def select_agents(self, telemetry: Telemetry) -> List[str]:
        """
        Phase 2: AgentSelection - Select relevant agents (deterministic).
        
        No LLM - pure pattern matching.
        
        Args:
            telemetry: Input telemetry
            
        Returns:
            List of agent names to execute
        """
        agent_scores = self.agent_selector.select_agents(telemetry)
        return [score.agent_name for score in agent_scores]
    
    def execute_agents(
        self,
        agent_names: List[str],
        telemetry: Telemetry
    ) -> List[PhaseResult]:
        """
        Phase 3: AgentExecution - Run selected agents.
        
        Each agent runs independently (could be parallelized).
        
        Args:
            agent_names: Names of agents to execute
            telemetry: Input telemetry
            
        Returns:
            List of PhaseResult objects
        """
        results = []
        
        for agent_name in agent_names:
            agent = self.agents.get(agent_name)
            if agent:
                # Pass runlog to agent for scratchpad generation
                result = agent.investigate(telemetry, runlog=self.runlog)
                results.append(result)
        
        return results
    
    def synthesize_findings(
        self,
        results: List[PhaseResult],
        telemetry: Telemetry
    ) -> Tuple[str, List[str], bool]:
        """
        Phase 4: Synthesis - Combine agent findings.
        
        Uses deterministic logic to identify root cause and recommendations.
        LLM only formats the synthesis into readable text.
        
        Args:
            results: Agent investigation results
            telemetry: Original telemetry
            
        Returns:
            Tuple of (root_cause, recommendations, escalation_needed)
        """
        # Deterministic root cause identification
        root_cause = "Unknown"
        recommendations = []
        escalation_needed = False
        
        # Check for critical findings
        critical_results = [r for r in results if r.has_critical_findings]
        
        if critical_results:
            # Root cause is from the agent with critical findings
            for result in critical_results:
                for finding in result.findings:
                    if finding.severity.value == "critical":
                        root_cause = finding.message
                        if finding.metadata.get("command"):
                            recommendations.append(finding.metadata["command"])
                        if finding.metadata.get("solution"):
                            recommendations.append(finding.metadata["solution"])
                        escalation_needed = True
                        break
                if root_cause != "Unknown":
                    break
        else:
            # No critical findings - check high severity
            high_results = [r for r in results 
                           if any(f.severity.value == "high" for f in r.findings)]
            
            if high_results:
                result = high_results[0]
                high_findings = [f for f in result.findings if f.severity.value == "high"]
                if high_findings:
                    root_cause = high_findings[0].message
                    
                    # Collect recommendations
                    for finding in result.findings:
                        if finding.metadata.get("recommendation"):
                            recommendations.append(finding.metadata["recommendation"])
        
        # Determine escalation
        if any(r.escalation_recommended for r in results):
            escalation_needed = True
        
        return root_cause, recommendations, escalation_needed
    
    def generate_report(
        self,
        context: InvestigationContext,
        telemetry: Telemetry,
        results: List[PhaseResult],
        root_cause: Optional[str],
        recommendations: List[str],
        escalation: bool
    ) -> InvestigationReport:
        """
        Phase 5: ReportGeneration - Create final investigation report.
        
        Args:
            context: Investigation context with all results
            telemetry: Telemetry data
            results: Agent results
            root_cause: Identified root cause
            recommendations: List of recommendations
            escalation: Whether escalation is needed
            
        Returns:
            InvestigationReport
        """
        # Create incident description
        incident_description = (
            f"{telemetry.error_count} errors detected in "
            f"{len(telemetry.log_entries)} log entries. "
            f"Error types: {', '.join(telemetry.error_types)}."
        )
        
        # Collect key findings
        key_findings = []
        for result in results:
            for finding in result.findings:
                key_findings.append(
                    f"[{finding.severity.value.upper()}] [{result.agent_name}] {finding.message}"
                )
        
        # Create overall summary
        overall_summary = f"""
Investigation completed with {len(results)} agent(s).
Root cause: {root_cause}
Escalation: {'Required' if escalation else 'Not required'}
        """.strip()
        
        # Create report
        report = InvestigationReport(
            investigation_id=context.investigation_id,
            timestamp=context.start_time,
            time_window=context.time_window,
            incident_description=incident_description,
            agents_executed=[r.agent_name for r in results],
            phase_results=results,
            overall_summary=overall_summary,
            key_findings=key_findings,
            root_cause=root_cause,
            recommendations=recommendations if recommendations else [
                "Review agent findings for detailed analysis"
            ],
            escalation_needed=escalation,
            escalation_reason="Critical findings detected" if escalation else None
        )
        
        return report
    
    def investigate(
        self,
        max_logs: int = 100,
        investigation_id: Optional[str] = None
    ) -> Tuple[InvestigationReport, Optional[RunLog]]:
        """
        Run full investigation pipeline.
        
        This is the main entry point.
        
        Args:
            max_logs: Maximum logs to load
            investigation_id: Optional investigation ID
            
        Returns:
            Tuple of (InvestigationReport, RunLog)
        """
        start_time = datetime.now()
        investigation_id = investigation_id or f"inv_{int(time.time())}"
        
        # Initialize runlog
        if self.enable_runlog:
            self.runlog = RunLog(investigation_id)
            self.runlog.info("Orchestrator", "Investigation started")
        
        # Phase 1: Load telemetry
        if self.runlog:
            self.runlog.phase_start(1, "InfoRetrieval")
        
        phase_start = time.time()
        print(f"[Phase 1/5] Loading telemetry from {self.log_db_path.name}...")
        telemetry = self.load_telemetry(max_logs=max_logs)
        print(f"  Loaded: {telemetry}")
        
        if self.runlog:
            duration_ms = (time.time() - phase_start) * 1000
            self.runlog.info(
                "Orchestrator",
                f"Loaded {len(telemetry.log_entries)} logs, {telemetry.error_count} errors",
                {"logs": len(telemetry.log_entries), "errors": telemetry.error_count}
            )
            self.runlog.phase_end(1, "InfoRetrieval", duration_ms)
        
        # Phase 2: Select agents
        if self.runlog:
            self.runlog.phase_start(2, "AgentSelection")
        
        phase_start = time.time()
        print(f"\n[Phase 2/5] Selecting agents (pattern matching)...")
        selected_agent_names = self.select_agents(telemetry)
        print(f"  Selected: {', '.join(selected_agent_names)}")
        
        if self.runlog:
            duration_ms = (time.time() - phase_start) * 1000
            self.runlog.decision(
                "AgentSelector",
                f"Selected {len(selected_agent_names)} agents",
                f"Pattern matching scores: {', '.join(selected_agent_names)}"
            )
            self.runlog.phase_end(2, "AgentSelection", duration_ms)
        
        # Create investigation context
        context = InvestigationContext(
            investigation_id=investigation_id,
            start_time=start_time,
            trigger="manual",
            time_window=telemetry.time_window,
            telemetry=telemetry,
            selected_agents=selected_agent_names
        )
        
        # Phase 3: Execute agents
        if self.runlog:
            self.runlog.phase_start(3, "AgentExecution")
        
        phase_start = time.time()
        print(f"\n[Phase 3/5] Executing {len(selected_agent_names)} agent(s)...")
        results = self.execute_agents(selected_agent_names, telemetry)
        
        if self.runlog:
            duration_ms = (time.time() - phase_start) * 1000
            self.runlog.phase_end(3, "AgentExecution", duration_ms)
        
        for result in results:
            context.add_phase_result(result)
            print(f"  {result.agent_name}: {len(result.findings)} findings, "
                  f"critical={result.has_critical_findings}")
        
        # Phase 4: Synthesize
        if self.runlog:
            self.runlog.phase_start(4, "Synthesis")
        
        phase_start = time.time()
        print(f"\n[Phase 4/5] Synthesizing findings...")
        root_cause, recommendations, escalation = self.synthesize_findings(results, telemetry)
        
        if self.runlog:
            duration_ms = (time.time() - phase_start) * 1000
            self.runlog.info(
                "Orchestrator",
                f"Synthesized: Root cause identified, {len(recommendations)} recommendations",
                {"root_cause": root_cause, "escalation": escalation}
            )
            self.runlog.phase_end(4, "Synthesis", duration_ms)
        
        # Phase 5: Generate report
        if self.runlog:
            self.runlog.phase_start(5, "ReportGeneration")
        
        phase_start = time.time()
        print(f"\n[Phase 5/5] Generating report...")
        report = self.generate_report(
            context,
            telemetry,
            results,
            root_cause,
            recommendations,
            escalation
        )
        
        if self.runlog:
            duration_ms = (time.time() - phase_start) * 1000
            self.runlog.phase_end(5, "ReportGeneration", duration_ms)
        
        # Complete
        duration = (datetime.now() - start_time).total_seconds()
        report.investigation_duration_ms = duration * 1000
        
        if self.runlog:
            self.runlog.info(
                "Orchestrator",
                f"Investigation complete: {duration:.2f}s",
                self.runlog.get_summary()
            )
        
        print(f"\n[Complete] Investigation {investigation_id} finished")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Root cause: {report.root_cause[:60]}..." if report.root_cause and len(report.root_cause) > 60 else f"  Root cause: {report.root_cause}")
        print(f"  Escalation: {report.escalation_reason is not None}")
        
        # Save runlog to disk
        if self.runlog:
            self.runlog.save()
            print(f"  Runlog saved: {self.runlog.output_dir / f'{investigation_id}.txt'}")
        
        return report, self.runlog
