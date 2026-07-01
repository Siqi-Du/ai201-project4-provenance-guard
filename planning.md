# Provenance Guard Planning Document

## Detection Signals
1. **Signal 1: LLM Classification (Groq `llama-3.3-70b-versatile`)**
   - **What it measures:** Semantic coherence, contextual flow, and known AI conversational patterns.
   - **Why they differ:** LLMs tend to generate text that is highly logical, safely structured, and devoid of true personal idiosyncrasies, whereas human writing often contains natural structural flaws and varied pacing.
   - **Blind spot (What it misses):** It can be easily bypassed by highly creative prompt engineering ("write this with typos and a casual tone") or if an AI-generated draft is lightly edited by a human.
   - **Output:** A probability score between 0.0 and 1.0, where 1.0 indicates high certainty of AI generation.
2. **Signal 2: Stylometric Heuristics**
   - **What it measures:** Type-Token Ratio (vocabulary richness) and Sentence Length Variance (structural diversity). 
   - **Why they differ:** AI text is mathematically designed to produce predictable token distributions, converging on uniform sentence lengths (e.g., constantly 15-20 words) and repetitive vocabulary. Human writing is naturally messy, mixing very short fragments with long, complex sentences.
   - **Blind spot (What it misses):** Very formal or legally constrained human writing (like terms of service) naturally has low variance and can be falsely flagged as AI. It also completely fails on extremely short texts (1-2 sentences) where variance cannot be computed.
   - **Output:** A probability score between 0.0 and 1.0 mapped from the raw metrics (low variance and low TTR map to higher AI probability).
3. **Combination:** The two signals will be combined using a simple average `(Signal_1 + Signal_2) / 2.0` to produce the final confidence score.

## Uncertainty Representation
A confidence score is a float from `0.0` to `1.0`.
- **0.0 - 0.35:** High-confidence Human. The system is fairly certain the variance and semantics match human creativity.
- **0.36 - 0.65:** Uncertain / Borderline. The signals are mixed. For example, a score of 0.57 indicates that while some AI traits are present, there is not enough evidence to definitively flag it.
- **0.66 - 1.0:** High-confidence AI. Both signals strongly agree that the text is machine-generated.

## Transparency Label Design
- **High-confidence Human (0.0 - 0.35):** "Verified Original: This work exhibits the stylistic variance and natural patterns characteristic of human creativity."
- **Uncertain (0.36 - 0.65):** "Attribution Unclear: This content contains a mix of signals. It may be heavily edited human work, or AI-assisted."
- **High-confidence AI (0.66 - 1.0):** "Likely AI-Generated: Our analysis indicates structural and stylistic patterns strongly associated with artificial intelligence models."

## Appeals Workflow
- **Who:** The original creator of the text.
- **What they provide:** The `content_id` of the submission and their `creator_reasoning` (e.g., explaining their unique writing style).
- **System Action:** The system updates the submission's status in the SQLite audit log from `classified` to `under_review` and records the reasoning. A human moderator can later query the log to review these cases.

## Anticipated Edge Cases
1. **Formal or Legal Texts:** Very formal human writing (like terms of service or academic abstracts) often has low sentence length variance and rigid vocabulary. The stylometric signal might falsely flag this as AI.
2. **Extremely Short Texts:** If a user submits just one or two sentences, the stylometric variance cannot be meaningfully calculated, which might skew the confidence score toward "Uncertain".

## False Positive Scenario Analysis
*What happens when the system misclassifies a human writer's work?*
Let's trace a scenario where a human submits a highly technical manual. The stylometric signal misreads the formal uniformity and outputs a high AI score (e.g., 0.8), while the Groq LLM outputs an uncertain score (e.g., 0.4).
1. **Confidence Score Reflection:** Because the system averages the signals, the combined score is **0.6**. Instead of snapping to a binary "AI" decision, the score genuinely reflects the mixed signals.
2. **Label Displayed:** A score of 0.6 triggers the `Uncertain (0.36 - 0.65)` label: "Attribution Unclear: This content contains a mix of signals. It may be heavily edited human work, or AI-assisted." This avoids falsely accusing the human writer of blatant cheating.
3. **Appeals Workflow:** The human creator clicks the appeal button, submitting a `POST /appeal` with their `content_id` and `creator_reasoning` ("This is a technical manual, which requires strict sentence structure"). 
4. **Resolution:** The system updates the submission's status to `under_review` in the audit log, storing the reasoning alongside the original 0.6 score. A human moderator can now read the text and the reasoning to manually clear the false positive. This scenario directly shaped the decision to make the middle-tier threshold so broad (0.36 - 0.65) in Milestone 2.

## Architecture

```text
[ User / Client ]
       │
       ├── 1. POST /submit (text, creator_id)
       │      ├──> [ Rate Limiter (10/min) ]
       │      ├──> [ Signal 1: Groq LLM ] ──(Score 1)──┐
       │      │                                        v
       │      ├──> [ Signal 2: Stylometrics ] ─(Score 2)─> [ Confidence Scoring ]
       │      │                                                  │
       │      │                                                  v
       │      │                                      [ Transparency Label Generator ]
       │      │                                                  │
       │      └──< (Returns content_id, label, scores) <─────────┤
       │                                                         │
       └── 2. POST /appeal (content_id, reasoning)               │
              ├──> [ Rate Limiter (5/min) ]                      │
              │                                                  v
              └──> (Updates status to 'under_review') ──> [ SQLite Audit Log ]
```

**Narrative Flow:**
- **Submission Flow:** A piece of text is submitted via `POST /submit`. It passes through a rate limiter, then is analyzed in parallel by the Groq LLM and the Python Stylometrics module. The two scores are averaged into a confidence score, which determines the Transparency Label. The entire decision is logged to the SQLite database before returning the result to the user.
- **Appeal Flow:** A creator submits a `POST /appeal` with their `content_id` and reasoning. The system rate-limits this endpoint, then updates the corresponding record in the SQLite audit log to `under_review`, storing the reasoning for future human moderation.

## Design Decisions
- **Web Framework (Flask):** Chosen because it is extremely lightweight, straightforward to set up for a small API, and seamlessly integrates with Flask-Limiter.
- **Database (SQLite):** Chosen over structured JSON files because it is built into Python and provides robust SQL schema support, making it safer for concurrent writes and much easier to query specific records (like finding a specific `content_id` for an appeal).
- **Rate Limiting (Flask-Limiter):** We used Flask-Limiter with an in-memory `storage_uri="memory://"`. This fulfills the rate-limiting requirement efficiently without the overhead of setting up Redis or another external caching service.

## API Contract

1. **`POST /submit`**
   - **Input:** JSON body with `text` (string, the content to evaluate) and `creator_id` (string, the ID of the author).
   - **Output (200 OK):** JSON containing `content_id` (UUID), `attribution` (string category), `confidence` (float between 0.0-1.0), `label` (string, transparency label text), `llm_score` (float), and `stylometric_score` (float).
   - **Error Cases:** `400 Bad Request` if missing fields; `429 Too Many Requests` if rate limit is exceeded.
   - **Example:**
     ```bash
     curl -s -X POST http://localhost:5001/submit \
       -H "Content-Type: application/json" \
       -d '{"text": "The sun dipped below the horizon, painting the sky in hues of amber and rose. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.", "creator_id": "test-user-1"}' | python3 -m json.tool
     ```

2. **`POST /appeal`**
   - **Input:** JSON body with `content_id` (string) and `creator_reasoning` (string).
   - **Output (200 OK):** JSON message confirming the appeal was received and the status was updated to `under_review`.
   - **Error Cases:** `404 Not Found` if `content_id` doesn't exist; `429 Too Many Requests` if rate limit is exceeded.
   - **Example:**
     ```bash
     curl -s -X POST http://localhost:5001/appeal \
       -H "Content-Type: application/json" \
       -d '{"content_id": "PASTE-CONTENT-ID-HERE", "creator_reasoning": "I wrote this myself from personal experience."}' | python3 -m json.tool
     ```

3. **`GET /log`**
   - **Input:** None.
   - **Output (200 OK):** JSON containing a list of `entries`, which are the most recent audit log records including all metrics, timestamps, and `appeal_reasoning` (if any).
   - **Example:**
     ```bash
     curl -s -X GET http://localhost:5001/log | python3 -m json.tool
     ```

## AI Tool Plan
- **M3 (Submission & Signal 1):** I will provide the API contract and Groq signal specs to the AI to generate the Flask skeleton and `signal_groq.py`, verifying by curling the `/submit` endpoint.
- **M4 (Signal 2 & Confidence):** I will provide the Stylometrics spec and scoring thresholds to the AI to generate `signal_stylometrics.py` and integrate the average calculation. I will verify using 4 distinct test cases (AI, human, formal, edited).
- **M5 (Production Layer):** I will provide the Label texts and Appeals workflow to the AI to generate the `POST /appeal` endpoint and the `Flask-Limiter` setup, verifying that the SQLite log correctly updates to `under_review`.
