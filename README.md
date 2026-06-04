# Tessa1

Tessa1 is a **harness demo** that explores whether the orchestration pattern from CodeRCA can be adapted into a simplified feed-retrieval system inspired by public technical writeups.

## What this project is about

- Reusing the **CodeRCA architecture pattern** outside RCA
- Demonstrating **agent = LLM + harness**
- Showing deterministic orchestration over a toy feed-retrieval workflow
- Producing explainable outputs instead of opaque recommendations
- Using a local snapshot of a public UCI dataset for candidate posts

## Core idea

CodeRCA showed a reusable architecture:

1. information retrieval
2. specialized agents
3. deterministic fact computation
4. synthesis
5. report generation

Tessa1 applies the same pattern to a different domain:

- **from root cause analysis**
- **to simplified feed retrieval and ranking reasoning**

## Positioning

Tessa1 is **not**:

- a production recommendation system
- a faithful implementation of LinkedIn Feed
- a benchmark against LinkedIn or any proprietary system

Tessa1 **is**:

- an architecture demo
- a harness-oriented experiment
- a small, explainable feed-style retrieval prototype

## Why Tessa1 uses an explicit scoring config

Real feed systems are not usually driven by a single simple config file. In practice, ranking behavior is shaped by a larger combination of:

- feature engineering
- learned ranking models
- user-behavior signals
- policy rules

Tessa1 uses an explicit deterministic scoring config as a **simulation of that layer**.

That gives the demo three advantages:

1. each ranking feature is visible and inspectable
2. end users can see what each feature represents
3. the ranking behavior is easy to explain without pretending we rebuilt a production feed system

So the scoring config in Tessa1 should be read as a **teaching and inspection surface**, not as a claim that real systems reduce to a few static weights.

## Two-part delivery plan

### Part 1 - This Friday

Adapt the CodeRCA architecture into a toy feed-retrieval demo:

- small synthetic user/profile dataset
- small synthetic post dataset
- deterministic scoring and ranking
- agent-style explanation of why candidate posts were selected

### Part 2 - Next Friday

Extend the demo into a stronger end-to-end retrieval flow:

- richer synthetic data
- structured feature templating
- popularity, recency, and affinity buckets
- cleaner reporting and better demo UX

## Why this project exists

The goal is to test whether the CodeRCA architecture is domain-extensible. If the same harness/orchestrator pattern can be rearranged from telemetry-driven RCA into feed-style retrieval, that strengthens the case that the architecture is reusable beyond its original use case.
