"""Scenarios package - fault injection and replay"""

from .base import Scenario, ScenarioResult, ScenarioSeverity
from .s01_database_not_initialized import S01DatabaseNotInitialized

__all__ = [
    "Scenario",
    "ScenarioResult",
    "ScenarioSeverity",
    "S01DatabaseNotInitialized",
    "get_scenario",
    "list_scenarios"
]


# Scenario registry
SCENARIOS = {
    "S01": S01DatabaseNotInitialized,
}


def get_scenario(scenario_id: str) -> Scenario:
    """
    Get scenario by ID.
    
    Args:
        scenario_id: Scenario ID (e.g., "S01")
        
    Returns:
        Scenario instance
        
    Raises:
        ValueError: If scenario not found
    """
    if scenario_id not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise ValueError(
            f"Scenario '{scenario_id}' not found. Available: {available}"
        )
    
    return SCENARIOS[scenario_id]()


def list_scenarios() -> list:
    """List all available scenarios"""
    scenarios = []
    for scenario_id, scenario_class in SCENARIOS.items():
        instance = scenario_class()
        scenarios.append({
            "id": scenario_id,
            "name": instance.name,
            "description": instance.description,
            "severity": instance.severity.value
        })
    return scenarios

