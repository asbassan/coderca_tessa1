# Tessa1 Architecture

## Purpose

Tessa1 is a **Friday-reachable harness demo** that adapts the CodeRCA architecture pattern into a simplified feed-retrieval system.

The purpose is not to reproduce LinkedIn Feed. The purpose is to show that the same orchestration pattern used in CodeRCA can be rearranged into a different domain while staying:

- deterministic
- explainable
- inspectable
- demo-friendly

## Architecture goal for Part 1

Given a synthetic user profile and a small synthetic set of posts, Tessa1 should:

1. load the user and candidate posts
2. run specialized analysis agents
3. compute deterministic ranking facts
4. select the top candidate posts
5. generate an explanation of why they ranked

## Architectural mapping from CodeRCA

### CodeRCA

1. info retrieval
2. agent selection
3. agent execution
4. synthesis
5. report generation

### Tessa1

1. feed context loading
2. feed agent routing
3. feed agent execution
4. ranking synthesis
5. feed report generation

## System components

### 1. Input layer

Loads the local demo inputs.

Inputs for Part 1:

- synthetic users
- local snapshot of public dataset posts
- scoring configuration

Suggested files:

- `data/users.json`
- `data/raw/uci_news/News_Final.csv`
- `config/scoring.json`

### Why a scoring config exists in this demo

In a production feed system, ranking behavior would normally emerge from a broader stack of:

- feature engineering
- learned ranking models
- user-behavior signals
- policy rules

Tessa1 does not attempt to replicate that full stack.

Instead, `config/scoring.json` acts as a deterministic stand-in for that combined ranking policy layer. This is intentional because the demo should let a reader inspect exactly:

- which features exist
- what each feature represents
- how each feature contributes to ranking

That keeps the project honest: we are simulating the ranking-policy surface for educational purposes, not claiming that a real LinkedIn-style feed is powered by a small hand-written config alone.

### 2. Orchestrator

The orchestrator is the harness entry point. It controls the execution order and data flow.

Responsibilities:

- load demo input data
- choose which agents to run
- pass structured inputs to agents
- collect deterministic outputs
- call synthesis
- generate final report

This should remain the architectural center, just like CodeRCA.

### 3. Specialized agents

Part 1 should use five agents.

#### ProfileAgent

Responsibilities:

- normalize user profile attributes
- extract interests, skills, and topical preferences
- emit structured profile facts

Output examples:

- normalized interests
- weighted topics
- explicit skill tags

#### PostAgent

Responsibilities:

- normalize post attributes
- extract post topics and metadata
- emit structured post facts

Output examples:

- post topics
- author category
- recency bucket
- popularity bucket

#### FeatureTemplatingAgent

Responsibilities:

- convert raw structured features into model-friendly and report-friendly labels
- bucket numeric fields
- standardize tags

Examples:

- views -> `popularity_bucket = high`
- age_hours -> `recency_bucket = recent`

This is where the article-inspired “feature templating” idea can be demonstrated in simplified form.

#### RetrievalRankingAgent

Responsibilities:

- compute deterministic scores for each user-post pair
- rank posts
- attach score breakdowns

Part 1 scoring should stay simple and explicit.

The scoring config should therefore be interpreted as a visible approximation of the feature and policy layer behind a real system, not as a literal reproduction of how a production feed stack is tuned.

Suggested scoring model:

- topic overlap score
- skill overlap score
- popularity bucket bonus
- recency bucket bonus
- optional author-affinity bonus

#### SynthesisAgent

Responsibilities:

- combine score outputs into ranked candidate explanations
- generate concise natural-language reasoning
- produce the final artifact for demo use

This is the best place to optionally use an LLM, but only after deterministic scoring is complete.

### 4. Reporting layer

Produces the demo artifact.

Required output for Friday:

- top ranked posts for a selected user
- per-post score breakdown
- short explanation of why each post ranked
- mapping back to the CodeRCA architecture pattern

Possible output modes:

- CLI text report
- JSON artifact
- markdown report saved locally

## Data model

### User profile

Minimum fields:

- `user_id`
- `name`
- `headline`
- `skills`
- `interests`
- `recent_engagement_topics`

### Post

Minimum fields:

- `post_id`
- `author`
- `title`
- `body`
- `topics`
- `popularity_bucket`
- `recency_bucket`

### Score breakdown

Minimum fields:

- `post_id`
- `total_score`
- `topic_overlap_score`
- `skill_overlap_score`
- `popularity_bonus`
- `recency_bonus`
- `affinity_bonus`
- `explanation_facts`

## Part 1 execution flow

1. load user profile and post set
2. run `ProfileAgent`
3. run `PostAgent`
4. run `FeatureTemplatingAgent`
5. run `RetrievalRankingAgent`
6. select top K posts
7. run `SynthesisAgent`
8. render final report

## Deterministic-first rule

Part 1 should follow this rule strictly:

- **facts and scores in code**
- **LLM only for explanation**

That keeps the architecture aligned with CodeRCA and makes the demo easy to inspect.

More specifically:

- the demo exposes ranking features directly
- the demo uses static weights as a stand-in for learned and policy-driven behavior
- the demo makes feature meaning visible so the user can understand why each post ranked where it did

## Permission and harness boundaries

Even in Part 1, Tessa1 should behave like a harness and not just a ranking script.

Part 1 boundaries:

- local files only
- no arbitrary shell execution
- no external writes
- fixed input dataset
- fixed agent set
- deterministic scoring config

This demonstrates the harness idea in a lightweight way:

- controlled tools
- bounded execution
- explicit state
- explainable outputs

## Out of scope for Friday

- embeddings
- ANN/vector search
- real article ingestion
- multi-user state
- persistent long-term memory
- online feedback learning
- latency optimization
- production serving

## Folder suggestion

```text
tessa1/
├── README.md
├── PLAN.md
├── ARCHITECTURE.md
├── data/
│   ├── users.json
│   └── posts.json
├── config/
│   └── scoring.json
├── src/
│   ├── orchestrator.py
│   ├── models.py
│   ├── scoring.py
│   ├── report.py
│   └── agents/
│       ├── profile.py
│       ├── post.py
│       ├── feature_templating.py
│       ├── retrieval_ranking.py
│       └── synthesis.py
└── outputs/
```

## Friday success criteria

Part 1 is successful if we can demo:

1. a user profile entering the system
2. a ranked list of posts coming out
3. deterministic score components shown clearly
4. a short explanation generated for the ranking
5. a clear narrative that this is **CodeRCA architecture adapted to feed retrieval**
