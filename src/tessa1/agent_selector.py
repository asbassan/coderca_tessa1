"""
AgentSelector - Deterministic agent selection based on telemetry patterns

Scores agents based on:
- Keywords in logs (EntityFrameworkCore, CatalogBrands, etc.)
- Error types (SqliteException, TimeoutException, etc.)
- Stack traces and components
- No LLM involvement - pure pattern matching
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass

from .models import Telemetry


@dataclass
class AgentScore:
    """Score for a single agent"""
    
    agent_name: str
    score: float  # 0-100
    matched_patterns: List[str]
    
    def __str__(self) -> str:
        return f"{self.agent_name}={self.score:.0f}"


class AgentSelector:
    """
    Deterministically selects agents based on telemetry patterns.
    
    Selection is purely rule-based to avoid LLM unpredictability.
    Each agent has specific keywords/patterns it specializes in.
    """
    
    # Selection threshold
    SELECTION_THRESHOLD = 30.0  # Lower threshold to include business context agents
    
    # Keyword weights for scoring
    KEYWORD_WEIGHT = 10.0
    ERROR_TYPE_WEIGHT = 20.0
    COMPONENT_WEIGHT = 15.0
    EXCEPTION_PATTERN_WEIGHT = 25.0
    
    def __init__(self):
        """Initialize agent selector with pattern rules"""
        
        # Database agent patterns
        self.database_patterns = {
            "keywords": [
                "EntityFrameworkCore",
                "DbContext",
                "DbCommand",
                "SqliteException",
                "DatabaseError",
                "Migration",
                "no such table",
                "constraint",
                "foreign key",
            ],
            "error_types": [
                "SqliteException",
                "DbUpdateException",
                "InvalidOperationException",
            ],
            "components": [
                "CatalogContext",
                "AppIdentityDbContext",
                "Microsoft.EntityFrameworkCore",
            ],
            "exception_patterns": [
                "no such table",
                "database is locked",
                "constraint failed",
                "foreign key constraint",
            ],
        }
        
        # Catalog agent patterns
        self.catalog_patterns = {
            "keywords": [
                "CatalogBrands",
                "CatalogTypes",
                "CatalogItems",
                "CatalogService",
                "Product",
                "Catalog",
            ],
            "error_types": [],
            "components": [
                "CatalogService",
                "CatalogController",
                "Microsoft.eShopWeb.Web.Services.CatalogService",
            ],
            "exception_patterns": [
                "CatalogBrands",
                "CatalogTypes",
                "CatalogItems",
            ],
        }
        
        # Order agent patterns
        self.order_patterns = {
            "keywords": [
                "Order",
                "OrderService",
                "OrderItem",
                "Checkout",
                "Payment",
            ],
            "error_types": [
                "PaymentException",
                "OrderProcessingException",
            ],
            "components": [
                "OrderService",
                "OrderController",
                "CheckoutService",
            ],
            "exception_patterns": [
                "order processing failed",
                "payment timeout",
                "checkout failed",
            ],
        }
        
        # Basket agent patterns
        self.basket_patterns = {
            "keywords": [
                "Basket",
                "BasketService",
                "BasketItem",
                "ShoppingCart",
                "Cart",
            ],
            "error_types": [
                "ConcurrencyException",
            ],
            "components": [
                "BasketService",
                "BasketController",
            ],
            "exception_patterns": [
                "basket not found",
                "concurrency",
                "stale basket",
            ],
        }
    
    def select_agents(self, telemetry: Telemetry) -> List[AgentScore]:
        """
        Select agents based on telemetry patterns.
        
        Args:
            telemetry: Telemetry data to analyze
            
        Returns:
            List of AgentScore objects for agents scoring above threshold,
            sorted by score (highest first)
        """
        scores = []
        
        # Score each agent
        scores.append(self._score_database_agent(telemetry))
        scores.append(self._score_catalog_agent(telemetry))
        scores.append(self._score_order_agent(telemetry))
        scores.append(self._score_basket_agent(telemetry))
        
        # Filter by threshold and sort
        selected = [s for s in scores if s.score >= self.SELECTION_THRESHOLD]
        selected.sort(key=lambda x: x.score, reverse=True)
        
        return selected
    
    def _score_database_agent(self, telemetry: Telemetry) -> AgentScore:
        """Score DatabaseAgent based on database-related patterns"""
        return self._score_agent(
            "DatabaseAgent",
            telemetry,
            self.database_patterns
        )
    
    def _score_catalog_agent(self, telemetry: Telemetry) -> AgentScore:
        """Score CatalogAgent based on catalog-related patterns"""
        return self._score_agent(
            "CatalogAgent",
            telemetry,
            self.catalog_patterns
        )
    
    def _score_order_agent(self, telemetry: Telemetry) -> AgentScore:
        """Score OrderAgent based on order-related patterns"""
        return self._score_agent(
            "OrderAgent",
            telemetry,
            self.order_patterns
        )
    
    def _score_basket_agent(self, telemetry: Telemetry) -> AgentScore:
        """Score BasketAgent based on basket-related patterns"""
        return self._score_agent(
            "BasketAgent",
            telemetry,
            self.basket_patterns
        )
    
    def _score_agent(
        self,
        agent_name: str,
        telemetry: Telemetry,
        patterns: Dict[str, List[str]]
    ) -> AgentScore:
        """
        Generic agent scoring based on pattern matching.
        
        Scoring formula:
        - +10 points per matched keyword
        - +20 points per matched error type
        - +15 points per matched component
        - +25 points per matched exception pattern
        
        Args:
            agent_name: Name of the agent
            telemetry: Telemetry to analyze
            patterns: Pattern dictionary with keywords, error_types, etc.
            
        Returns:
            AgentScore with calculated score and matched patterns
        """
        score = 0.0
        matched_patterns = []
        
        # Check keywords
        for keyword in patterns.get("keywords", []):
            if keyword.lower() in [k.lower() for k in telemetry.keywords]:
                score += self.KEYWORD_WEIGHT
                matched_patterns.append(f"keyword:{keyword}")
        
        # Check error types
        for error_type in patterns.get("error_types", []):
            if error_type in telemetry.error_types:
                score += self.ERROR_TYPE_WEIGHT
                matched_patterns.append(f"error_type:{error_type}")
        
        # Check components
        for component in patterns.get("components", []):
            if component in telemetry.components:
                score += self.COMPONENT_WEIGHT
                matched_patterns.append(f"component:{component}")
        
        # Check exception patterns (in log messages and exceptions)
        for pattern in patterns.get("exception_patterns", []):
            pattern_lower = pattern.lower()
            
            # Check in log messages
            for entry in telemetry.log_entries[:20]:  # Check first 20 for efficiency
                if entry.exception and pattern_lower in entry.exception.lower():
                    score += self.EXCEPTION_PATTERN_WEIGHT
                    matched_patterns.append(f"exception_pattern:{pattern}")
                    break
                elif pattern_lower in entry.message.lower():
                    score += self.EXCEPTION_PATTERN_WEIGHT / 2  # Half weight for message match
                    matched_patterns.append(f"message_pattern:{pattern}")
                    break
        
        # Cap score at 100
        score = min(score, 100.0)
        
        return AgentScore(
            agent_name=agent_name,
            score=score,
            matched_patterns=matched_patterns
        )
    
    def explain_selection(self, telemetry: Telemetry) -> str:
        """
        Generate human-readable explanation of agent selection.
        
        Args:
            telemetry: Telemetry used for selection
            
        Returns:
            Formatted explanation string
        """
        all_scores = [
            self._score_database_agent(telemetry),
            self._score_catalog_agent(telemetry),
            self._score_order_agent(telemetry),
            self._score_basket_agent(telemetry),
        ]
        all_scores.sort(key=lambda x: x.score, reverse=True)
        
        lines = ["Agent Selection Results:"]
        lines.append("=" * 60)
        
        for agent_score in all_scores:
            status = "SELECTED" if agent_score.score >= self.SELECTION_THRESHOLD else "SKIPPED"
            lines.append(f"{agent_score.agent_name}: {agent_score.score:.1f} [{status}]")
            
            if agent_score.matched_patterns:
                for pattern in agent_score.matched_patterns:
                    lines.append(f"  - {pattern}")
        
        lines.append("=" * 60)
        lines.append(f"Threshold: {self.SELECTION_THRESHOLD}")
        
        selected_count = len([s for s in all_scores if s.score >= self.SELECTION_THRESHOLD])
        lines.append(f"Selected: {selected_count}/{len(all_scores)} agents")
        
        return "\n".join(lines)
