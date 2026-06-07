"""
Feed orchestrator for Tessa1.

Pipeline:
1. FeedInputs: Load structured users, posts, and scoring config
2. AgentSelection: Select the fixed feed-analysis agents
3. AgentExecution: Run profile analysis, ranking, and synthesis
4. Synthesis: Collect ranked explanations
5. ReportGeneration: Produce the final feed report
"""

from __future__ import annotations

import time
from datetime import datetime

from .copilot_client import CopilotClient, create_client
from .feed_agents import ProfileAgent, RetrievalRankingAgent, SynthesisAgent
from .input_loader import FeedInputLoader
from .models import (
    FeedContext,
    FeedInputs,
    FeedPost,
    FeedReport,
    ScoreBreakdown,
    UserProfile,
)
from .runlog import RunLog


class Orchestrator:
    """Main orchestrator for the Tessa1 feed retrieval demo."""

    def __init__(
        self,
        input_loader: FeedInputLoader | None = None,
        copilot_client: CopilotClient | None = None,
        enable_runlog: bool = True,
        use_real_llm: bool = False,
    ):
        self.input_loader = input_loader or FeedInputLoader()
        self.enable_runlog = enable_runlog
        self.runlog: RunLog | None = None
        self.use_real_llm = use_real_llm
        self.client = copilot_client or create_client(use_real_llm=use_real_llm)

        self.agents = {
            "ProfileAgent": ProfileAgent(),
            "RetrievalRankingAgent": RetrievalRankingAgent(),
            "SynthesisAgent": SynthesisAgent(copilot_client=self.client if use_real_llm else None),
        }

    def load_inputs(self, max_posts: int = 200) -> FeedInputs:
        """Phase 1: load structured feed inputs from the harness layer."""
        if hasattr(self.input_loader, "max_posts"):
            self.input_loader.max_posts = max_posts
        return self.input_loader.load_inputs()

    def select_agents(self) -> list[str]:
        """Phase 2: select the fixed feed-analysis agent pipeline."""
        return ["ProfileAgent", "RetrievalRankingAgent", "SynthesisAgent"]

    def _select_user(self, inputs: FeedInputs, user_id: str | None) -> UserProfile:
        if user_id:
            user = inputs.get_user_by_id(user_id)
            if user is None:
                raise ValueError(f"Unknown user_id: {user_id}")
            return user

        if not inputs.users:
            raise ValueError("No user profiles were loaded.")

        return inputs.users[0]

    def _select_top_posts(
        self,
        ranked_posts: list[ScoreBreakdown],
        posts: list[FeedPost],
        top_k: int,
    ) -> list[FeedPost]:
        posts_by_id = {post.post_id: post for post in posts}
        selected: list[FeedPost] = []

        for score in ranked_posts[:top_k]:
            post = posts_by_id.get(score.post_id)
            if post is not None:
                selected.append(post)

        return selected

    def investigate(
        self,
        user_id: str | None = None,
        max_posts: int = 200,
        investigation_id: str | None = None,
        max_logs: int | None = None,
    ) -> tuple[FeedReport, RunLog | None]:
        """
        Run the feed retrieval pipeline end to end.

        max_logs is accepted as a compatibility alias from the copied CodeRCA CLI
        and is treated as max_posts when provided.
        """
        if max_logs is not None:
            max_posts = max_logs

        start_time = datetime.now()
        investigation_id = investigation_id or f"feed_{int(time.time())}"

        if self.enable_runlog:
            self.runlog = RunLog(investigation_id)
            self.runlog.info("Orchestrator", "Feed investigation started")

        if self.runlog:
            self.runlog.phase_start(1, "FeedInputs")
        phase_start = time.time()
        inputs = self.load_inputs(max_posts=max_posts)
        selected_user = self._select_user(inputs, user_id=user_id)
        if self.runlog:
            self.runlog.info(
                "Orchestrator",
                f"Loaded {len(inputs.users)} users and {len(inputs.posts)} posts",
                {"user_count": len(inputs.users), "post_count": len(inputs.posts)},
            )
            self.runlog.phase_end(1, "FeedInputs", (time.time() - phase_start) * 1000)

        selected_agent_names = self.select_agents()
        if self.runlog:
            self.runlog.phase_start(2, "AgentSelection")
            self.runlog.decision(
                "Orchestrator",
                "Selected fixed feed pipeline",
                ", ".join(selected_agent_names),
            )
            self.runlog.phase_end(2, "AgentSelection", 0.0)

        context = FeedContext(
            feed_request_id=investigation_id,
            start_time=start_time,
            selected_user=selected_user,
            candidate_posts=inputs.posts,
            selected_agents=selected_agent_names,
            top_k=inputs.scoring_config.top_k,
        )

        if self.runlog:
            self.runlog.phase_start(3, "AgentExecution")
        phase_start = time.time()

        profile_result, profile_intent = self.agents["ProfileAgent"].analyze(
            selected_user,
            runlog=self.runlog,
        )
        context.add_phase_result(profile_result)

        ranking_result, ranked_posts = self.agents["RetrievalRankingAgent"].rank(
            profile=selected_user,
            profile_intent=profile_intent,
            posts=inputs.posts,
            scoring_config=inputs.scoring_config,
            runlog=self.runlog,
        )
        context.add_phase_result(ranking_result)
        context.ranked_posts = ranked_posts

        top_posts = self._select_top_posts(ranked_posts, inputs.posts, inputs.scoring_config.top_k)

        synthesis_result, explanations = self.agents["SynthesisAgent"].synthesize(
            profile=selected_user,
            top_posts=top_posts,
            ranked_posts=ranked_posts[: inputs.scoring_config.top_k],
            scoring_config=inputs.scoring_config,
            runlog=self.runlog,
        )
        context.add_phase_result(synthesis_result)

        if self.runlog:
            self.runlog.phase_end(3, "AgentExecution", (time.time() - phase_start) * 1000)

        if self.runlog:
            self.runlog.phase_start(4, "Synthesis")
            self.runlog.phase_end(4, "Synthesis", 0.0)

        context.end_time = datetime.now()
        focus_topics = profile_intent.primary_topics[:3]
        focus_summary = ", ".join(focus_topics) if focus_topics else "general interest"
        context.overall_analysis = (
            f"Selected {len(top_posts)} posts for {selected_user.name} "
            f"from {len(inputs.posts)} candidates "
            f"with strongest alignment to {focus_summary}."
        )

        report = FeedReport(
            feed_request_id=investigation_id,
            timestamp=context.end_time,
            selected_user=selected_user,
            candidate_posts_count=len(inputs.posts),
            ranked_posts=ranked_posts,
            top_posts=top_posts,
            phase_results=context.phase_results,
            overall_summary=context.overall_analysis,
            explanations=explanations,
            architecture_mapping=[
                "FeedInputs -> harness-side input loading",
                "ProfileAgent -> bounded profile interpretation into ranking-ready intent",
                "RetrievalRankingAgent -> deterministic ranking over interpreted profile signals",
                "SynthesisAgent -> explanation generation",
            ],
        )

        if self.runlog:
            self.runlog.phase_start(5, "ReportGeneration")
            self.runlog.info(
                "Orchestrator",
                f"Generated feed report with {len(report.top_posts)} ranked posts",
                {"top_posts": len(report.top_posts)},
            )
            self.runlog.phase_end(5, "ReportGeneration", 0.0)

        return report, self.runlog
