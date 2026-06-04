"""CLI entry point for CodeRCA"""

import click
import sys
from pathlib import Path


@click.group()
@click.version_option()
def main() -> None:
    """
    CodeRCA - Application-Aware Incident Investigation
    
    Multi-agent system for investigating incidents by understanding both
    telemetry and application business logic.
    """
    pass


@main.command()
def init() -> None:
    """Initialize CodeRCA and check prerequisites"""
    from .preflight import run_preflight_checks
    
    # Run preflight checks
    all_passed = run_preflight_checks(verbose=True)
    
    if all_passed:
        click.echo("\n[OK] CodeRCA is ready to use!")
        click.echo("\nNext steps:")
        click.echo("  1. Run: coderca sync (check context documents)")
        click.echo("  2. Run: coderca investigate (run investigation)")
        sys.exit(0)
    else:
        click.echo("\n[FAIL] Fix the issues above before proceeding.")
        sys.exit(1)


@main.group()
def scenario() -> None:
    """Manage fault scenarios"""
    pass


@scenario.command("list")
def scenario_list() -> None:
    """List available fault scenarios"""
    click.echo("📋 Available Scenarios")
    click.echo("=" * 50)
    click.echo("⚠️  Not yet implemented")
    click.echo("\nPlanned scenarios:")
    click.echo("  S01: Order payment timeout")
    click.echo("  S02: Catalog slow query")
    click.echo("  S03: Basket race condition")
    click.echo("  S04: DB connection exhaustion")
    click.echo("  S05: Auth token expiry storm")


@scenario.command("run")
@click.argument("scenario_id")
def scenario_run(scenario_id: str) -> None:
    """Run a fault scenario and investigate"""
    click.echo(f"🚀 Running scenario: {scenario_id}")
    click.echo("=" * 50)
    click.echo("⚠️  Not yet implemented")


@main.command()
@click.option('--max-logs', default=100, help='Maximum log entries to analyze')
@click.option('--output', type=click.Path(), help='Save report to file')
@click.option('--id', 'investigation_id', help='Investigation ID')
@click.option('--save-runlog', is_flag=True, default=True, help='Save detailed runlog')
@click.option('--runlog-output', help='Runlog output path (default: runlogs/<id>.txt)')
@click.option('--use-real-llm', is_flag=True, default=False, help='Use GitHub Copilot SDK instead of mock mode')
def investigate(max_logs, output, investigation_id, save_runlog, runlog_output, use_real_llm):
    """
    Run incident investigation on captured telemetry.
    
    Loads logs from SQLite, selects relevant agents, executes investigations,
    and generates a comprehensive report.
    """
    from .orchestrator import Orchestrator
    
    click.echo("=" * 70)
    click.echo("CodeRCA - Incident Investigation")
    click.echo("=" * 70)
    
    try:
        # Create orchestrator
        click.echo("\nInitializing orchestrator...")
        orchestrator = Orchestrator(enable_runlog=True, use_real_llm=use_real_llm)
        click.echo(f"[OK] Found log database: {orchestrator.log_db_path.name}")
        
        # Run investigation
        click.echo(f"\nStarting investigation (max {max_logs} logs)...")
        click.echo("-" * 70)
        
        report, runlog = orchestrator.investigate(
            max_logs=max_logs,
            investigation_id=investigation_id
        )
        
        click.echo("-" * 70)
        
        # Display report
        click.echo("\n")
        click.echo(report.to_text())
        
        # Save to file if requested
        if output:
            output_path = Path(output)
            output_path.write_text(report.to_text(), encoding='utf-8')
            click.echo(f"\n[OK] Report saved to: {output_path}")
        
        # Save runlog
        if save_runlog and runlog:
            runlog.save(format="text")
            click.echo(f"[OK] Runlog saved to {runlog.output_dir / f'{report.investigation_id}.txt'}")
            
            # Also save JSON version
            runlog.save(format="json")
            click.echo(f"[OK] Runlog JSON saved to {runlog.output_dir / f'{report.investigation_id}.json'}")
            
            # Show scratchpads
            if runlog.scratchpads:
                click.echo(f"[OK] Scratchpads saved: {len(runlog.scratchpads)} agent(s)")
                for agent_name in runlog.scratchpads:
                    scratchpad_path = runlog._get_scratchpad_path(agent_name)
                    click.echo(f"    - {scratchpad_path.name}")
        
        # Exit code based on escalation
        if report.escalation_needed:
            click.echo("\n[!] Escalation recommended - manual review required")
            sys.exit(1)
        else:
            click.echo("\n[OK] Investigation complete - no escalation needed")
            sys.exit(0)
            
    except FileNotFoundError as e:
        click.echo(f"\n[ERROR] {e}", err=True)
        click.echo("\nMake sure eShopOnWeb has run and generated logs.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n[ERROR] Investigation failed: {e}", err=True)
        import traceback
        click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


@main.command()
def sync() -> None:
    """Refresh agent context documents from source"""
    click.echo("Syncing Agent Context")
    click.echo("=" * 50)
    
    from pathlib import Path
    
    context_dir = Path(__file__).parent / "context"
    
    if not context_dir.exists():
        click.echo("❌ Context directory not found")
        return
    
    # Count documents
    component_docs = list((context_dir / "components").glob("*.md"))
    arch_docs = list((context_dir / "architecture").glob("*.md"))
    pattern_docs = list((context_dir / "patterns").glob("*.md")) if (context_dir / "patterns").exists() else []
    
    total = len(component_docs) + len(arch_docs) + len(pattern_docs)
    
    click.echo(f"\nContext Documents Found: {total}")
    click.echo(f"   Components: {len(component_docs)}")
    click.echo(f"   Architecture: {len(arch_docs)}")
    click.echo(f"   Patterns: {len(pattern_docs)}")
    
    click.echo("\nComponent Docs:")
    for doc in sorted(component_docs):
        size_kb = doc.stat().st_size / 1024
        click.echo(f"   * {doc.stem:15s} ({size_kb:5.1f} KB)")
    
    click.echo("\nArchitecture Docs:")
    for doc in sorted(arch_docs):
        size_kb = doc.stat().st_size / 1024
        click.echo(f"   * {doc.stem:15s} ({size_kb:5.1f} KB)")
    
    if pattern_docs:
        click.echo("\nPattern Docs:")
        for doc in sorted(pattern_docs):
            size_kb = doc.stat().st_size / 1024
            click.echo(f"   * {doc.stem:15s} ({size_kb:5.1f} KB)")
    
    click.echo(f"\nContext sync complete - {total} documents ready")
    click.echo("\nAgents will load these documents during investigation:")
    click.echo("  * DatabaseAgent -> components/database.md")
    click.echo("  * CatalogAgent  -> components/catalog.md")
    click.echo("  * OrderAgent    -> components/order.md")
    click.echo("  * BasketAgent   -> components/basket.md")


@main.group()
def scenario():
    """Run and manage fault injection scenarios"""
    pass


@scenario.command('list')
def scenario_list():
    """List all available scenarios"""
    from .scenarios import list_scenarios
    
    click.echo("Available Scenarios")
    click.echo("=" * 70)
    
    scenarios = list_scenarios()
    for s in scenarios:
        click.echo(f"\n{s['id']}: {s['name']}")
        click.echo(f"  Severity: {s['severity'].upper()}")
        click.echo(f"  Description: {s['description']}")
    
    click.echo("\n" + "=" * 70)
    click.echo(f"Total: {len(scenarios)} scenarios")
    

@scenario.command('run')
@click.argument('scenario_id')
@click.option('--investigate', is_flag=True, default=True, help='Run investigation after fault injection')
@click.option('--cleanup', is_flag=True, default=True, help='Clean up after scenario')
@click.option('--save-runlog', is_flag=True, default=True, help='Save detailed runlog')
def scenario_run(scenario_id, investigate, cleanup, save_runlog):
    """Run a fault injection scenario"""
    from .scenarios import get_scenario
    from .orchestrator import Orchestrator
    from datetime import datetime
    import time
    
    click.echo("=" * 70)
    click.echo(f"CodeRCA - Scenario Execution: {scenario_id}")
    click.echo("=" * 70)
    
    try:
        # Get scenario
        scenario = get_scenario(scenario_id)
        
        click.echo(f"\nScenario: {scenario.name}")
        click.echo(f"Description: {scenario.description}")
        click.echo(f"Severity: {scenario.severity.value.upper()}")
        click.echo("")
        
        # Inject fault
        start_time = datetime.now()
        fault_details = scenario.inject_fault()
        
        # Wait for telemetry
        click.echo(f"\n[INFO] Waiting for app to generate telemetry...")
        click.echo(f"[INFO] Start eShopOnWeb now to trigger the fault")
        click.echo(f"[INFO] Press Ctrl+C when ready to investigate")
        
        try:
            import time
            time.sleep(60)  # Wait for user to start app
        except KeyboardInterrupt:
            click.echo(f"\n\n[OK] Proceeding to investigation...")
        
        # Run investigation
        if investigate:
            click.echo(f"\n{'-' * 70}")
            click.echo(f"Running Investigation")
            click.echo(f"{'-' * 70}\n")
            
            orchestrator = Orchestrator(enable_runlog=True)
            report, runlog = orchestrator.investigate(
                max_logs=50,
                investigation_id=f"{scenario_id}_{int(time.time())}"
            )
            
            click.echo("\n\n" + "=" * 70)
            click.echo("Scenario Results")
            click.echo("=" * 70)
            
            # Verify results
            click.echo(f"\nExpected Agents: {', '.join(scenario.get_expected_agents())}")
            click.echo(f"Selected Agents: {', '.join(report.agents_executed)}")
            
            click.echo(f"\nExpected Root Cause: {scenario.get_expected_root_cause()}")
            click.echo(f"Identified Root Cause: {report.root_cause}")
            
            # Save runlog
            if save_runlog and runlog:
                runlog_dir = Path("runlogs")
                runlog_dir.mkdir(exist_ok=True)
                
                runlog_path = runlog_dir / f"{report.investigation_id}.txt"
                runlog.save(str(runlog_path), format="text")
                click.echo(f"\n[OK] Runlog saved to {runlog_path}")
                
                json_path = runlog_dir / f"{report.investigation_id}.json"
                runlog.save(str(json_path), format="json")
                click.echo(f"[OK] Runlog JSON saved to {json_path}")
        
        # Cleanup
        if cleanup:
            scenario.cleanup()
        
        click.echo("\n" + "=" * 70)
        click.echo("[OK] Scenario execution complete")
        click.echo("=" * 70)
        sys.exit(0)
        
    except Exception as e:
        click.echo(f"\n[ERROR] Scenario execution failed: {str(e)}", err=True)
        import traceback
        traceback.print_exc()
        
        # Try to cleanup
        try:
            scenario.cleanup()
        except:
            pass
        
        sys.exit(1)


@scenario.command('replay')
@click.argument('runlog_path', type=click.Path(exists=True))
def scenario_replay(runlog_path):
    """Replay investigation from saved runlog"""
    import json
    
    click.echo("=" * 70)
    click.echo("CodeRCA - Runlog Replay")
    click.echo("=" * 70)
    
    try:
        # Load runlog
        with open(runlog_path, 'r', encoding='utf-8') as f:
            if runlog_path.endswith('.json'):
                runlog_data = json.load(f)
                
                click.echo(f"\nInvestigation ID: {runlog_data['investigation_id']}")
                click.echo(f"Start Time: {runlog_data['start_time']}")
                
                summary = runlog_data['summary']
                click.echo(f"\nSummary:")
                click.echo(f"  Total Duration: {summary['total_duration_ms']:.0f}ms")
                click.echo(f"  Phases Completed: {summary['phases_completed']}/5")
                click.echo(f"  Agents Executed: {summary['agents_executed']}")
                click.echo(f"  Facts Computed: {summary['facts_computed']}")
                click.echo(f"  Findings Created: {summary['findings_created']}")
                click.echo(f"  LLM Calls: {summary['llm_calls']} ({summary['total_tokens']} tokens)")
                
                click.echo(f"\nExecution Timeline:")
                click.echo("-" * 70)
                for entry in runlog_data['entries']:
                    timestamp = entry['timestamp'].split('T')[1][:12]
                    component = entry['component']
                    message = entry['message']
                    click.echo(f"[{timestamp}] {component}: {message}")
                
            else:
                # Text format
                content = f.read()
                click.echo(content)
        
        click.echo("\n" + "=" * 70)
        click.echo("[OK] Runlog replay complete")
        sys.exit(0)
        
    except Exception as e:
        click.echo(f"\n[ERROR] Runlog replay failed: {str(e)}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
