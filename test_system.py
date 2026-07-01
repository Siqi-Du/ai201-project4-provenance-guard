import requests
import json

BASE_URL = "http://localhost:5001"

def test_submit(text, description):
    print(f"\n--- Testing: {description} ---")
    payload = {
        "text": text,
        "creator_id": "test-user"
    }
    response = requests.post(f"{BASE_URL}/submit", json=payload)
    if response.status_code == 200:
        data = response.json()
        print(f"Confidence: {data['confidence']}")
        print(f"Attribution: {data['attribution']}")
        print(f"Label: {data['label']}")
        print(f"LLM Score: {data['llm_score']}")
        print(f"Stylo Score: {data['stylometric_score']}")
        return data['content_id']
    elif response.status_code == 429:
        print("Rate limit exceeded!")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
    return None

def test_appeal(content_id):
    print(f"\n--- Testing Appeal for {content_id} ---")
    payload = {
        "content_id": content_id,
        "creator_reasoning": "I wrote this myself! It is my unique style."
    }
    response = requests.post(f"{BASE_URL}/appeal", json=payload)
    print(response.json())

def test_rate_limit():
    print("\n--- Testing Rate Limit ---")
    for i in range(12):
        response = requests.post(f"{BASE_URL}/submit", json={"text": "Spam spam spam", "creator_id": "spammer"})
        if response.status_code == 429:
            print(f"Request {i+1}: 429 Rate Limit Exceeded")
            break
        else:
            print(f"Request {i+1}: {response.status_code}")

if __name__ == "__main__":
    ai_text = "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment."
    
    human_text = "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there"
    
    formal_human = "The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations."
    
    edited_ai = "I've been thinking a lot about remote work lately. There are genuine tradeoffs — flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivity varies widely by individual and role type."
    
    id1 = test_submit(ai_text, "Clearly AI-generated")
    id2 = test_submit(human_text, "Clearly human-written")
    id3 = test_submit(formal_human, "Formal human writing")
    id4 = test_submit(edited_ai, "Lightly edited AI output")
    
    if id2:
        test_appeal(id2)
        
    print("\n--- Checking Logs ---")
    logs = requests.get(f"{BASE_URL}/log").json()
    print(f"Total log entries: {len(logs['entries'])}")
    if logs['entries']:
        print("Most recent log status:", logs['entries'][0]['status'])
        
    test_rate_limit()
