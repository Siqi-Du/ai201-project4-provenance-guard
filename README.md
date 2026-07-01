# Provenance Guard

Provenance Guard is a multi-signal content classification backend designed to protect attribution on creative platforms. It provides a transparent, nuanced assessment of whether text submissions are human-written or AI-generated.

## Architecture Overview

When a user submits text, the request flows through the following pipeline:
1. **Submission (`POST /submit`)**: The backend receives the text and creator ID.
2. **Signal 1 (Groq LLM)**: The text is evaluated by the `llama-3.3-70b-versatile` model for holistic semantic and stylistic markers.
3. **Signal 2 (Stylometric Heuristics)**: The text is analyzed using pure Python to determine its Type-Token Ratio (vocabulary diversity) and Sentence Length Variance.
4. **Confidence Scoring**: The two signals are averaged into a combined confidence score (0.0 to 1.0).
5. **Transparency Label**: Based on the confidence score thresholds, a distinct label is generated to display to the end-user.
6. **Audit Log**: The entire decision, including the raw scores, is logged into a SQLite database.
7. **Appeals (`POST /appeal`)**: If a creator disagrees with the label, they can submit an appeal, which flags the content as `under_review` in the audit log for human moderation.

## Design Decisions
- **Web Framework (Flask):** Chosen because it is extremely lightweight, straightforward to set up for a small API, and seamlessly integrates with Flask-Limiter.
- **Database (SQLite):** Chosen over structured JSON files because it is built into Python and provides robust SQL schema support, making it safer for concurrent writes and much easier to query specific records (like finding a specific `content_id` for an appeal).
- **Rate Limiting (Flask-Limiter):** We used Flask-Limiter with an in-memory `storage_uri="memory://"`. This fulfills the rate-limiting requirement efficiently without the overhead of setting up Redis or another external caching service.

## API Contract

1. **`POST /submit`**
   - **Input:** JSON body with `text` (string) and `creator_id` (string).
   - **Output (200 OK):** JSON containing `content_id` (UUID), `attribution` (string), `confidence` (float), `label` (string), `llm_score` (float), and `stylometric_score` (float).
   - **Error Cases:** `400 Bad Request` if missing fields; `429 Too Many Requests` if rate limit is exceeded.
   - **Example:**
     ```bash
     curl -s -X POST http://localhost:5001/submit \
       -H "Content-Type: application/json" \
       -d '{"text": "The sun dipped below the horizon, painting the sky in hues of amber and rose. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.", "creator_id": "test-user-1"}' | python3 -m json.tool
     ```

2. **`POST /appeal`**
   - **Input:** JSON body with `content_id` (string) and `creator_reasoning` (string).
   - **Output (200 OK):** JSON message confirming the appeal was received and status updated.
   - **Error Cases:** `404 Not Found` if `content_id` doesn't exist; `429 Too Many Requests` if rate limit is exceeded.
   - **Example:**
     ```bash
     curl -s -X POST http://localhost:5001/appeal \
       -H "Content-Type: application/json" \
       -d '{"content_id": "PASTE-CONTENT-ID-HERE", "creator_reasoning": "I wrote this myself from personal experience."}' | python3 -m json.tool
     ```

3. **`GET /log`**
   - **Input:** None.
   - **Output (200 OK):** JSON containing a list of `entries`, which are the most recent audit log records including all metrics and timestamps.
   - **Example:**
     ```bash
     curl -s -X GET http://localhost:5001/log | python3 -m json.tool
     ```

## Detection Signals

1. **Signal 1: LLM Classification (Groq)**
   - **What it measures:** Semantic coherence, contextual flow, and known AI conversational patterns.
   - **Why I chose it:** LLMs excel at recognizing the "flavor" of other LLMs, detecting subtle structural repetitions that static heuristics miss.
   - **Blind spot:** Highly creative prompt engineering or lightly edited AI text can bypass it easily.

2. **Signal 2: Stylometric Heuristics**
   - **What it measures:** Type-Token Ratio (vocabulary richness) and Sentence Length Variance (structural diversity).
   - **Why I chose it:** AI generation tends to converge on uniform sentence lengths and repetitive word choices compared to the natural messiness of human writing.
   - **Blind spot:** Very formal, constrained human writing (e.g., technical or legal text) might be falsely flagged due to its intentional uniformity.

## Confidence Scoring

The combined confidence score is calculated by averaging the LLM Score and the Stylometric Score. This provides a balanced assessment that prevents one signal from overly skewing the result.

**Example 1: Lower-Confidence (Likely Human)**
- Input: "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after."
- Output Confidence: **0.20** 
- (LLM Score: 0.2, Stylo Score: 0.2)

**Example 2: Medium-Confidence (Uncertain - AI Generated)**
- Input: "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications."
- Output Confidence: **0.575**
- (LLM Score: 0.8, Stylo Score: 0.35)

*Note: The score effectively communicates uncertainty, avoiding a binary "yes/no" when the signals present mixed results.*

## Transparency Labels

The transparency label is dynamically chosen based on the confidence score:

| Category | Score Range | Label Text |
| :--- | :--- | :--- |
| **High-Confidence Human** | `0.00 - 0.35` | "Verified Original: This work exhibits the stylistic variance and natural patterns characteristic of human creativity." |
| **Uncertain** | `0.36 - 0.65` | "Attribution Unclear: This content contains a mix of signals. It may be heavily edited human work, or AI-assisted." |
| **High-Confidence AI** | `0.66 - 1.00` | "Likely AI-Generated: Our analysis indicates structural and stylistic patterns strongly associated with artificial intelligence models." |

## Rate Limiting

Rate limiting is enforced via `Flask-Limiter`. 
- **Submission Endpoint**: `10 per minute`
- **Appeal Endpoint**: `5 per minute`

**How it works**: `Flask-Limiter` uses an in-memory storage to track the number of requests made by each client (by default, based on their IP address) within a rolling time window. Once a client exceeds the defined threshold, the middleware intercepts the request before it reaches the core application logic and automatically returns a `429 Too Many Requests` HTTP error.

**Reasoning**: A human writer realistically cannot finish and submit new original content more than a few times a minute. 10 requests per minute accommodates burst saves or rapid edits while completely blocking automated scraping scripts or API abusers.

**Evidence of Rate Limit Triggering (429 Error):**
```bash
$ for i in $(seq 1 12); do curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5001/submit ...
200
200
200
200
200
200
200
200
200
200
429
429
```

## Known Limitations

- **Formal or Legal Texts**: The system is highly likely to misclassify human-written formal documents (like privacy policies or legal terms) as AI. The stylometric signal heavily penalizes low sentence-length variance, which is a hallmark of formal, highly-structured writing.

## Spec Reflection

- **How the spec helped**: Defining the label texts and confidence thresholds beforehand prevented me from getting stuck tweaking thresholds endlessly during implementation. The spec acted as a concrete contract.
- **Where implementation diverged**: In the spec, I anticipated that obvious AI text would trigger a >0.66 score. However, during testing, the stylometric score for my AI sample was `0.35` because it was too short to show significant variance anomalies, resulting in a combined score of `0.575` (Uncertain). I chose to leave the logic as-is because it successfully represented the system's genuine uncertainty on a small sample, which is preferable to forcing a false positive.

## AI Usage Section

1. **Prompting for Flask Skeleton**: I provided my Architecture diagram and Spec to an AI tool to generate the initial `app.py` skeleton with SQLite integration. 
   - *Revision*: I revised the database schema it provided to ensure `appeal_reasoning` was stored directly in the logs table rather than a separate table for simplicity.
2. **Prompting for Stylometrics**: I asked an AI tool to generate the pure Python regex parsing for the `Type-Token Ratio` and `Sentence Length Variance`.
   - *Revision*: The generated code threw `ZeroDivisionError` on single sentences. I overrode it by adding a length check and falling back to just the TTR score when `slv` could not be computed.
