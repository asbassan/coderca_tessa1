"""
CatalogAgent - Investigates product catalog issues

Specializes in:
- Product data queries
- Catalog item operations
- Brand and type management
- Search and filtering issues
- Data validation errors
"""

from typing import Dict, List, Any

from .base import BaseAgent
from ..models import Telemetry, AgentFinding, Severity


class CatalogAgent(BaseAgent):
    """
    Agent specialized in product catalog investigation.
    
    Loads context from: context/components/catalog.md
    """
    
    def __init__(self, copilot_client=None):
        super().__init__(
            agent_name="CatalogAgent",
            context_file="components/catalog.md",
            copilot_client=copilot_client
        )
    
    def compute_facts(self, telemetry: Telemetry) -> Dict[str, Any]:
        """
        Compute catalog-related facts from telemetry.
        
        Facts computed:
        - Catalog entity mentions (CatalogBrands, CatalogTypes, CatalogItems)
        - Query performance indicators
        - Data validation errors
        - Business impact assessment
        """
        facts = {}
        
        errors = telemetry.get_errors()
        facts["error_count"] = len(errors)
        
        # Check which catalog entities are involved
        catalog_entities = {
            "CatalogBrands": False,
            "CatalogTypes": False,
            "CatalogItems": False
        }
        
        for entry in errors:
            text = entry.message + " " + (entry.exception or "")
            for entity in catalog_entities.keys():
                if entity in text:
                    catalog_entities[entity] = True
        
        facts["affected_entities"] = [k for k, v in catalog_entities.items() if v]
        facts["is_catalog_error"] = len(facts["affected_entities"]) > 0
        
        # Check for specific error patterns
        facts["has_query_errors"] = any(
            "query" in e.message.lower() or
            (e.exception and "query" in e.exception.lower())
            for e in errors
        )
        
        facts["has_validation_errors"] = any(
            "validation" in e.message.lower() or
            "invalid" in e.message.lower()
            for e in errors
        )
        
        # Database dependency check
        facts["database_dependent"] = any(
            "database" in e.message.lower() or
            (e.exception and ("database" in e.exception.lower() or 
                             "DbContext" in e.exception.lower()))
            for e in errors
        )
        
        # Business impact assessment
        if facts["is_catalog_error"]:
            if "CatalogItems" in facts["affected_entities"]:
                facts["business_impact"] = "high"  # Products not loading
            elif len(facts["affected_entities"]) > 1:
                facts["business_impact"] = "medium"  # Multiple entities affected
            else:
                facts["business_impact"] = "low"  # Single entity type
        else:
            facts["business_impact"] = "none"
        
        return facts
    
    def create_findings(
        self,
        facts: Dict[str, Any],
        telemetry: Telemetry
    ) -> List[AgentFinding]:
        """
        Create catalog-specific findings.
        """
        findings = []
        
        # Finding 1: Catalog entities not accessible
        if facts.get("is_catalog_error"):
            # Severity based on business impact
            if facts["business_impact"] == "high":
                severity = Severity.HIGH
            elif facts["business_impact"] == "medium":
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW
            
            finding = AgentFinding(
                category="catalog_access_error",
                severity=severity,
                message=f"Catalog entities not accessible: {', '.join(facts['affected_entities'])}",
                evidence=[f"{facts['error_count']} catalog-related errors"],
                metadata={
                    "affected_entities": facts["affected_entities"],
                    "business_impact": facts["business_impact"],
                    "database_dependent": facts.get("database_dependent", False)
                }
            )
            findings.append(finding)
        
        # Finding 2: Database dependency issue
        if facts.get("database_dependent"):
            finding = AgentFinding(
                category="catalog_database_dependency",
                severity=Severity.INFO,
                message="Catalog errors are database-dependent - check DatabaseAgent findings",
                evidence=["Database-related keywords in catalog errors"],
                metadata={
                    "recommendation": "Resolve database issues first"
                }
            )
            findings.append(finding)
        
        # Finding 3: Query performance issues
        if facts.get("has_query_errors") and facts["error_count"] > 5:
            finding = AgentFinding(
                category="catalog_query_errors",
                severity=Severity.MEDIUM,
                message="Multiple catalog query errors detected",
                evidence=[f"{facts['error_count']} query-related errors"],
                metadata={
                    "recommendation": "Review catalog query patterns and indexing"
                }
            )
            findings.append(finding)
        
        return findings
