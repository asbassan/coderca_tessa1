"""
OrderAgent - Investigates order processing issues

Specializes in:
- Order creation and updates
- Checkout flow
- Order state transitions
- Payment processing integration
- Order fulfillment issues
"""

from typing import Dict, List, Any

from .base import BaseAgent
from ..models import Telemetry, AgentFinding, Severity


class OrderAgent(BaseAgent):
    """
    Agent specialized in order processing investigation.
    
    Loads context from: context/components/order.md
    """
    
    def __init__(self, copilot_client=None):
        super().__init__(
            agent_name="OrderAgent",
            context_file="components/order.md",
            copilot_client=copilot_client
        )
    
    def compute_facts(self, telemetry: Telemetry) -> Dict[str, Any]:
        """
        Compute order-related facts from telemetry.
        
        Facts computed:
        - Order operation types (create, update, cancel)
        - Payment integration issues
        - Timeout patterns
        - State transition errors
        """
        facts = {}
        
        errors = telemetry.get_errors()
        facts["error_count"] = len(errors)
        
        # Check for order-related keywords
        order_keywords = ["Order", "OrderItem", "Checkout", "Payment"]
        facts["is_order_error"] = any(
            any(kw in (e.message + " " + (e.exception or "")) 
                for kw in order_keywords)
            for e in errors
        )
        
        # Payment-related errors
        facts["has_payment_errors"] = any(
            "payment" in e.message.lower() or
            (e.exception and "payment" in e.exception.lower())
            for e in errors
        )
        
        # Timeout errors
        facts["has_timeout_errors"] = any(
            "timeout" in e.message.lower() or
            (e.exception and "timeout" in e.exception.lower())
            for e in errors
        )
        
        # State transition errors
        facts["has_state_errors"] = any(
            "state" in e.message.lower() or
            "transition" in e.message.lower()
            for e in errors
        )
        
        # Determine primary issue type
        if facts["has_payment_errors"]:
            facts["primary_issue"] = "payment"
        elif facts["has_timeout_errors"]:
            facts["primary_issue"] = "timeout"
        elif facts["has_state_errors"]:
            facts["primary_issue"] = "state_transition"
        elif facts["is_order_error"]:
            facts["primary_issue"] = "order_processing"
        else:
            facts["primary_issue"] = "unknown"
        
        return facts
    
    def create_findings(
        self,
        facts: Dict[str, Any],
        telemetry: Telemetry
    ) -> List[AgentFinding]:
        """
        Create order-specific findings.
        """
        findings = []
        
        # Finding 1: Payment processing errors
        if facts.get("has_payment_errors"):
            finding = AgentFinding(
                category="order_payment_error",
                severity=Severity.HIGH,
                message="Payment processing errors detected in order flow",
                evidence=[f"{facts['error_count']} payment-related errors"],
                metadata={
                    "primary_issue": facts["primary_issue"],
                    "recommendation": "Check payment gateway integration and credentials"
                }
            )
            findings.append(finding)
        
        # Finding 2: Timeout issues
        if facts.get("has_timeout_errors"):
            finding = AgentFinding(
                category="order_timeout",
                severity=Severity.MEDIUM,
                message="Timeout errors in order processing",
                evidence=[f"Timeout keywords detected in {facts['error_count']} errors"],
                metadata={
                    "recommendation": "Review timeout settings and external service response times"
                }
            )
            findings.append(finding)
        
        # Finding 3: State transition errors
        if facts.get("has_state_errors"):
            finding = AgentFinding(
                category="order_state_error",
                severity=Severity.MEDIUM,
                message="Order state transition errors detected",
                evidence=["State/transition keywords in errors"],
                metadata={
                    "recommendation": "Review order state machine and validation rules"
                }
            )
            findings.append(finding)
        
        return findings
