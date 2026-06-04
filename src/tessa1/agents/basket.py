"""
BasketAgent - Investigates shopping basket issues

Specializes in:
- Basket operations (add, remove, update)
- Basket persistence
- Concurrency issues
- Basket item validation
- Anonymous vs authenticated baskets
"""

from typing import Dict, List, Any

from .base import BaseAgent
from ..models import Telemetry, AgentFinding, Severity


class BasketAgent(BaseAgent):
    """
    Agent specialized in shopping basket investigation.
    
    Loads context from: context/components/basket.md
    """
    
    def __init__(self, copilot_client=None):
        super().__init__(
            agent_name="BasketAgent",
            context_file="components/basket.md",
            copilot_client=copilot_client
        )
    
    def compute_facts(self, telemetry: Telemetry) -> Dict[str, Any]:
        """
        Compute basket-related facts from telemetry.
        
        Facts computed:
        - Basket operation types
        - Concurrency issues
        - Stale basket detection
        - Item validation errors
        """
        facts = {}
        
        errors = telemetry.get_errors()
        facts["error_count"] = len(errors)
        
        # Check for basket-related keywords
        basket_keywords = ["Basket", "BasketItem", "Cart", "ShoppingCart"]
        facts["is_basket_error"] = any(
            any(kw in (e.message + " " + (e.exception or "")) 
                for kw in basket_keywords)
            for e in errors
        )
        
        # Concurrency errors
        facts["has_concurrency_errors"] = any(
            "concurrency" in e.message.lower() or
            "concurrent" in e.message.lower() or
            (e.exception and "concurrency" in e.exception.lower())
            for e in errors
        )
        
        # Stale basket errors
        facts["has_stale_errors"] = any(
            "stale" in e.message.lower() or
            "expired" in e.message.lower()
            for e in errors
        )
        
        # Not found errors
        facts["has_not_found_errors"] = any(
            "not found" in e.message.lower() or
            (e.exception and "not found" in e.exception.lower())
            for e in errors
        )
        
        # Validation errors
        facts["has_validation_errors"] = any(
            "validation" in e.message.lower() or
            "invalid" in e.message.lower()
            for e in errors
        )
        
        # Determine primary issue
        if facts["has_concurrency_errors"]:
            facts["primary_issue"] = "concurrency"
        elif facts["has_stale_errors"]:
            facts["primary_issue"] = "stale_basket"
        elif facts["has_not_found_errors"]:
            facts["primary_issue"] = "basket_not_found"
        elif facts["has_validation_errors"]:
            facts["primary_issue"] = "validation"
        elif facts["is_basket_error"]:
            facts["primary_issue"] = "basket_operation"
        else:
            facts["primary_issue"] = "unknown"
        
        return facts
    
    def create_findings(
        self,
        facts: Dict[str, Any],
        telemetry: Telemetry
    ) -> List[AgentFinding]:
        """
        Create basket-specific findings.
        """
        findings = []
        
        # Finding 1: Concurrency issues
        if facts.get("has_concurrency_errors"):
            finding = AgentFinding(
                category="basket_concurrency",
                severity=Severity.HIGH,
                message="Basket concurrency conflicts detected",
                evidence=[f"{facts['error_count']} concurrency-related errors"],
                metadata={
                    "recommendation": "Review basket locking strategy and optimistic concurrency handling"
                }
            )
            findings.append(finding)
        
        # Finding 2: Stale basket issues
        if facts.get("has_stale_errors"):
            finding = AgentFinding(
                category="basket_stale",
                severity=Severity.MEDIUM,
                message="Stale or expired basket errors detected",
                evidence=["Stale/expired keywords in errors"],
                metadata={
                    "recommendation": "Review basket expiration policies and cleanup jobs"
                }
            )
            findings.append(finding)
        
        # Finding 3: Basket not found
        if facts.get("has_not_found_errors") and facts["is_basket_error"]:
            finding = AgentFinding(
                category="basket_not_found",
                severity=Severity.MEDIUM,
                message="Basket not found errors - possible data loss or session issues",
                evidence=[f"{facts['error_count']} basket lookup failures"],
                metadata={
                    "recommendation": "Check basket persistence and session management"
                }
            )
            findings.append(finding)
        
        # Finding 4: Validation errors
        if facts.get("has_validation_errors") and facts["is_basket_error"]:
            finding = AgentFinding(
                category="basket_validation",
                severity=Severity.LOW,
                message="Basket item validation errors",
                evidence=["Validation keywords in basket errors"],
                metadata={
                    "recommendation": "Review basket item validation rules"
                }
            )
            findings.append(finding)
        
        return findings
