# coderca_tessa1

`coderca_tessa1` (Tessa1) is a **harness demo** that adapts the CodeRCA orchestration pattern into a simplified, explainable feed-ranking system.

The goal is not to reproduce a production recommendation stack. The goal is to show that the same architecture pattern can be reused in a different domain while staying:

- deterministic
- inspectable
- explainable
- runnable from a clean CLI

## What this project is

- a feed-ranking architecture demo
- a harness-oriented experiment
- a deterministic scoring + explanation prototype
- a reusable orchestration example derived from CodeRCA

## What this project is not

- a production recommendation system
- a faithful implementation of LinkedIn Feed
- a benchmark against proprietary ranking systems
- a learned ranking model

## Architecture at a glance

```text
+----------------------------------------------------------------------------------+
|                                   Tessa1 CLI                                     |
|                                                                                  |
|   coderca_tessa1 list-users                                                      |
|   coderca_tessa1 demo-feed --user-id <user> --max-posts <n>                      |
+---------------------------------------------+------------------------------------+
                                              |
                                              v
+----------------------------------------------------------------------------------+
|                                  Orchestrator                                    |
|                                                                                  |
|  1. Load inputs                                                                   |
|  2. Select fixed agent pipeline                                                   |
|  3. Execute agents                                                                |
|  4. Collect explanations                                                          |
|  5. Build final report                                                            |
+---------------------------------------------+------------------------------------+
                                              |
                     +------------------------+------------------------+
                     |                                                 |
                     v                                                 v
+-------------------------------------+         +-----------------------------------+
|           FeedInputLoader           |         |              RunLog               |
|                                     |         |                                   |
|  Reads local structured inputs      |         |  Optional execution trace         |
|  and converts them into FeedInputs  |         |  for phases and agents            |
+----------------+--------------------+         +-----------------------------------+
                 |
                 v
+----------------------------------------------------------------------------------+
|                                   Input Sources                                  |
|                                                                                  |
|  users.json            -> synthetic viewer profiles                              |
|  scoring.json          -> deterministic ranking policy                           |
|  News_Final.csv        -> public UCI news dataset snapshot                       |
+----------------+-----------------------------+-----------------------------------+
                 |                             |
                 |                             v
                 |               +-----------------------------------------------+
                 |               |              dataset_loader.py                |
                 |               |                                               |
                 |               |  CSV -> normalized FeedPost records           |
                 |               |  - parse title/headline/source/topic          |
                 |               |  - compute popularity bucket                  |
                 |               |  - compute recency bucket                     |
                 |               +-------------------+---------------------------+
                 |                                   |
                 +-------------------+---------------+
                                     |
                                     v
+----------------------------------------------------------------------------------+
|                                   FeedInputs                                     |
|                                                                                  |
|  users: UserProfile[]                                                            |
|  posts: FeedPost[]                                                               |
|  scoring_config: ScoringConfig                                                   |
+---------------------------------------------+------------------------------------+
                                              |
                                              v
+----------------------------------------------------------------------------------+
|                                Agent Pipeline                                    |
+----------------------------------------------------------------------------------+

    +---------------------------+
    |       ProfileAgent        |
    |---------------------------|
    | UserProfile               |
    |   -> ProfileIntent        |
    +-------------+-------------+
                  |
                  v
    +---------------------------+
    |  RetrievalRankingAgent    |
    |---------------------------|
    | ProfileIntent + FeedPost  |
    |   -> ScoreBreakdown[]     |
    +-------------+-------------+
                  |
                  v
    +---------------------------+
    |      SynthesisAgent       |
    |---------------------------|
    | ranked posts + scores     |
    |   -> explanations[]       |
    +-------------+-------------+
                  |
                  v
+----------------------------------------------------------------------------------+
|                                   FeedReport                                     |
|                                                                                  |
|  - selected user                                                                 |
|  - candidate count                                                               |
|  - ranked posts                                                                  |
|  - score breakdowns                                                              |
|  - explanations                                                                  |
|  - architecture mapping                                                          |
+---------------------------------------------+------------------------------------+
                                              |
                      +-----------------------+------------------------+
                      |                                                |
                      v                                                v
        +-------------------------------+              +------------------------------+
        |       CLI text output         |              |   optional saved artifacts   |
        |                               |              |                              |
        |  Tessa1 Feed Report           |              |  report.txt                  |
        |  Top Ranked Posts             |              |  runlog.txt                  |
        |  Generated Explanations       |              |  runlog.json                 |
        +-------------------------------+              +------------------------------+
```

## Core architecture idea

CodeRCA demonstrated a reusable pattern:

1. information retrieval
2. specialized agents
3. deterministic fact computation
4. synthesis
5. report generation

Tessa1 applies the same pattern to a different problem:

- **from root cause analysis**
- **to simplified feed retrieval and ranking reasoning**

## Fork, clone, and run

### 1. Fork the repository

Fork the repository on GitHub if you want your own copy:

- upstream: `https://github.com/asbassan/coderca_tessa1`

### 2. Clone your fork or clone upstream directly

Clone your fork:

```powershell
git clone https://github.com/<your-github-username>/coderca_tessa1.git
cd coderca_tessa1
```

Or clone upstream directly:

```powershell
git clone https://github.com/asbassan/coderca_tessa1.git
cd coderca_tessa1
```

### 3. Install the package

```powershell
python -m pip install -e .[dev]
```

### 4. Initialize Tessa1

Run the initialization flow to verify required files, create writable output folders, and check default real-LLM prerequisites:

```powershell
coderca_tessa1 init
```

You can also invoke the same flow from the root command:

```powershell
coderca_tessa1 --init
```

This checks:

- `data\users.json`
- `config\scoring.json`
- `data\raw\uci_news\News_Final.csv`
- GitHub Copilot SDK availability for default real-LLM mode
- writable `artifacts` and `runlogs` folders

### 5. List available demo users

```powershell
coderca_tessa1 list-users
```

### 6. Run the feed demo

```powershell
coderca_tessa1 demo-feed --user-id user-ava-ml --max-posts 20
```

By default, this run:

- uses real LLM mode by default
- saves the rendered report to `artifacts\<request-id>.txt`
- saves runlogs unless you disable them

### 7. Override the rendered report path

```powershell
coderca_tessa1 demo-feed --user-id user-ava-ml --max-posts 20 --output artifacts\ava-feed.txt
```

If you only want console output, disable report saving:

```powershell
coderca_tessa1 demo-feed --user-id user-ava-ml --no-save-report
```

You can also disable runlogs:

```powershell
coderca_tessa1 demo-feed --user-id user-ava-ml --max-posts 20 --no-save-runlog
```

## Run Tessa1 in a container

Tessa1 can be packaged as a **CLI-first container**. That fits the Barge model you described: start the image, mount writable folders if needed, and run the `coderca_tessa1` CLI inside the container.

### Build the image

```powershell
docker build -t coderca_tessa1 .
```

### Initialize inside the container

```powershell
docker run --rm ^
  -v ${PWD}\artifacts:/app/artifacts ^
  -v ${PWD}\runlogs:/app/runlogs ^
  coderca_tessa1 init
```

### Run the feed demo inside the container

```powershell
docker run --rm ^
  -v ${PWD}\artifacts:/app/artifacts ^
  -v ${PWD}\runlogs:/app/runlogs ^
  coderca_tessa1 demo-feed --user-id user-ava-ml --max-posts 20
```

### What the image already contains

The image bakes in:

- the Tessa1 source code
- Python dependencies
- `config\scoring.json`
- `data\users.json`
- `data\raw\uci_news\News_Final.csv`

### What Barge needs to provide

For a CLI-first Barge run, the container contract is simple:

1. run the image
2. invoke `coderca_tessa1 ...`
3. mount writable locations for `/app/artifacts` and `/app/runlogs` if you want persisted output
4. provide GitHub Copilot SDK/auth inside the container only if you want the default real-LLM mode to succeed

If you want deterministic-only execution in the container, run:

```powershell
coderca_tessa1 demo-feed --user-id user-ava-ml --max-posts 20 --no-use-real-llm
```

### How to spin up a Barge container

1. Get `barge.exe`: https://github.com/asbassan/barge/releases/tag/v0.1.0
2. Transfer `barge.exe` to the `tessa1` folder.
3. `Bargefile` is already included in this repository.
4. Run:

```powershell
barge build -f Bargefile -t tessa1:v1 .
barge run --name tessa1 -v D:\AIResearchAndStudies\AICoding\tessa1:C:\app tessa1:v1 cmd.exe
```

## How execution works

The end-to-end path is:

1. `FeedInputLoader` reads `users.json`, `scoring.json`, and the local UCI post snapshot
2. `dataset_loader.py` converts raw CSV rows into normalized `FeedPost` records
3. the orchestrator selects one user
4. `ProfileAgent` interprets that user into `ProfileIntent`
5. `RetrievalRankingAgent` scores, shortlists, and reranks candidate posts
6. `SynthesisAgent` turns score facts into concise explanations
7. the orchestrator returns a `FeedReport`
8. the CLI prints or saves the result

## Input sources

### `data\users.json`

Synthetic viewer profiles used to simulate feed consumers.

Why synthetic?

- the UCI dataset contains content-side records, not viewer profiles
- Tessa1 needs stable demo personas for per-user ranking
- this keeps the architecture honest instead of inventing fake public user data

### `data\raw\uci_news\News_Final.csv`

Local snapshot of a public UCI news popularity dataset.

It provides content-side signals such as:

- title
- headline
- source
- topic
- publish date
- popularity columns like `LinkedIn`, `Facebook`, and `GooglePlus`

Tessa1 uses it as the candidate post pool, not as a full recommendation dataset.

### `config\scoring.json`

Visible deterministic ranking policy for the demo.

It defines:

- feature weights
- recency and popularity bucket bonuses
- shortlist behavior
- diversity reranking penalties
- feature descriptions for inspection

## Current agents

The current runtime uses three feed agents:

1. `ProfileAgent`
2. `RetrievalRankingAgent`
3. `SynthesisAgent`

### `ProfileAgent`

**Purpose:** turn a raw viewer profile into a ranking-ready intent model.

It:

- normalizes skills, interests, recent engagement topics, and preferred sources
- derives additional topic hints from the headline
- applies deterministic topic weighting
- expands topics through a bounded map
- infers `profile_modes` such as `technical-builder` or `business-analyst`

Output:

- `FeedPhaseResult`
- `ProfileIntent`

### `RetrievalRankingAgent`

**Purpose:** compute deterministic ranking scores for each user-post pair.

It:

- matches posts against primary, secondary, and expanded profile intent
- checks skill overlap
- checks recent engagement overlap
- applies preferred-source affinity
- adds recency and popularity bonuses
- builds a candidate shortlist
- applies diversity-aware reranking

Output:

- `FeedPhaseResult`
- `ScoreBreakdown[]`

### `SynthesisAgent`

**Purpose:** turn deterministic ranking facts into readable report explanations.

It:

- builds an explanation plan
- selects the most salient reasons
- adapts wording to profile mode
- compares adjacent ranked posts
- keeps explanation generation separate from score computation

Output:

- `FeedPhaseResult`
- `explanations[]`

## Why Tessa1 uses an explicit scoring config

Real feed systems are not usually driven by one simple static config. In practice, ranking behavior emerges from a larger stack of:

- feature engineering
- learned ranking models
- user-behavior signals
- policy rules

Tessa1 does **not** try to replicate that full stack.

Instead, `scoring.json` acts as an explicit stand-in for the ranking-policy surface so a reader can inspect:

- which features exist
- what each feature means
- how each feature contributes to ranking

That keeps the demo honest. It is a **teaching and inspection surface**, not a claim that real feed systems reduce to a few handwritten weights.

## Repository structure

```text
src/coderca_tessa1/
  cli.py               # public CLI
  orchestrator.py      # harness control flow
  input_loader.py      # structured input loading
  dataset_loader.py    # CSV -> FeedPost normalization
  feed_agents.py       # ProfileAgent, RetrievalRankingAgent, SynthesisAgent
  models/feed.py       # domain contracts and final report rendering

data/
  users.json
  raw/uci_news/News_Final.csv

config/
  scoring.json

tests/
  test_orchestrator.py
  test_profile_agent.py
  test_ranking_agent.py
  test_synthesis_agent.py
  test_cli.py
```

## Why this project exists

The point of Tessa1 is to test whether the CodeRCA architecture is domain-extensible. If the same harness/orchestrator pattern can be rearranged from telemetry-driven RCA into feed-style retrieval, that strengthens the case that the architecture is reusable beyond its original use case.
