# Demo Commands for Walkthrough Video

Here are the exact `curl` commands to copy and paste during the video presentation. Ensure your Flask server is running in another terminal window (`python3 app.py`).

### 1. Submit AI-Generated Text (Expected: High Score, Likely AI)
```bash
curl -s -X POST http://localhost:5001/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment.", "creator_id": "demo-ai"}' | python3 -m json.tool
```

### 2. Submit Human-Written Text (Expected: Low Score, Verified Original)
```bash
curl -s -X POST http://localhost:5001/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it.", "creator_id": "demo-human"}' | python3 -m json.tool
```

### 3. Appeal a Decision
*Note: Replace `PASTE-UUID-HERE` with the actual `content_id` returned from the first submission.*
```bash
curl -s -X POST http://localhost:5001/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "PASTE-UUID-HERE", "creator_reasoning": "This is a false positive! I wrote this academic paper myself."}' | python3 -m json.tool
```

### 4. View Audit Log
```bash
curl -s -X GET http://localhost:5001/log | python3 -m json.tool
```

### 5. Test Rate Limiter (Expected: 10x 200 OK, then 429 Too Many Requests)
```bash
for i in $(seq 1 12); do curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5001/submit -H "Content-Type: application/json" -d '{"text": "Rate limit test.", "creator_id": "test"}'; done
```
