# Tessa1 Plan

## Objective

Demonstrate that the CodeRCA orchestration pattern can be adapted into a **simplified, explainable feed-retrieval demo** inspired by public descriptions of LinkedIn's feed architecture.

## Architecture translation

### CodeRCA pattern

1. load telemetry
2. select specialized agents
3. compute deterministic facts
4. synthesize findings
5. generate report

### Tessa1 translation

1. load user/profile data and post data
2. select feed-analysis agents
3. compute deterministic retrieval and ranking facts
4. synthesize candidate selection and ranking rationale
5. generate an explainable feed report

## Friday Part 1 scope

### Goal

Ship a working local demo that shows:

- a user profile
- a small candidate set of posts
- deterministic candidate scoring
- top results selected
- an explanation of why they ranked

### In scope

1. **Toy dataset**
   - 3 to 5 synthetic users
   - 12 to 20 synthetic posts
   - structured features such as skills, interests, popularity bucket, and recency bucket

2. **Simplified agents**
   - `ProfileAgent`
   - `PostAgent`
   - `FeatureTemplatingAgent`
   - `RetrievalRankingAgent`
   - `SynthesisAgent`

3. **Deterministic logic**
   - profile-topic matching
   - exact interest overlap
   - bucketed popularity
   - bucketed recency
   - optional affinity weights
   - explicit scoring config documented as a stand-in for feature engineering + learned ranking models + user-behavior signals + policy rules

4. **Outputs**
   - ranked post list
   - per-post score breakdown
   - short natural-language explanation
   - architecture mapping back to CodeRCA

### Out of scope

- embeddings
- large-scale retrieval infra
- real LinkedIn data
- low-latency serving
- production recommendation quality
- online learning
- experimentation framework

## Deliverables for Part 1

1. local project scaffold
2. synthetic dataset
3. orchestrator flow
4. deterministic scoring implementation
5. demo report or CLI output
6. short architecture note explaining how CodeRCA was adapted

## Implementation steps for Part 1

1. **Define data model**
   - user profile schema
   - post schema
   - score breakdown schema
   - document that the deterministic config is a demo-friendly representation of a larger real-world ranking layer

2. **Create synthetic dataset**
   - a few users with distinct interests
   - a few posts with overlapping and non-overlapping attributes

3. **Map CodeRCA phases**
   - rename RCA-specific concepts into retrieval-demo concepts

4. **Implement feed agents**
   - profile understanding
   - post understanding
   - feature templating
   - retrieval and ranking
   - synthesis

5. **Generate explainable output**
   - why each top post was selected
   - which features mattered
   - how deterministic scoring worked

6. **Prepare Friday demo**
   - one or two sample users
   - clear before/after or ranked-output walkthrough

## Part 2 preview for next Friday

1. increase dataset richness
2. add more realistic feature buckets
3. improve candidate selection and ranking flow
4. improve artifact/report generation
5. make the demo feel end-to-end instead of purely architectural
