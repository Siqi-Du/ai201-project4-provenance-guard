import re
import statistics

def calculate_type_token_ratio(text: str) -> float:
    """
    Calculates the Type-Token Ratio (TTR), which is the ratio of unique words to total words.
    A higher TTR indicates more vocabulary diversity (often human).
    A lower TTR indicates repetitive vocabulary (often AI).
    """
    # Clean text and split into words
    words = re.findall(r'\b\w+\b', text.lower())
    if not words:
        return 0.0
    
    unique_words = set(words)
    return len(unique_words) / len(words)

def calculate_sentence_length_variance(text: str) -> float:
    """
    Calculates the variance in sentence lengths (measured in words).
    High variance usually means human writing (mix of short and long sentences).
    Low variance usually means AI writing (uniform sentence structures).
    """
    # Split text into sentences (basic approximation)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) <= 1:
        return 0.0 # Cannot compute variance for 0 or 1 sentence
    
    lengths = [len(re.findall(r'\b\w+\b', s)) for s in sentences]
    return statistics.variance(lengths)

def analyze_stylometrics(text: str) -> dict:
    """
    Analyzes text based on stylometric heuristics and returns an AI probability score.
    Returns a dictionary:
    {
        "stylometric_score": float (0.0 to 1.0, where 1.0 is highest certainty of AI),
        "metrics": dict of raw metrics
    }
    """
    ttr = calculate_type_token_ratio(text)
    slv = calculate_sentence_length_variance(text)
    
    # We need to map these metrics to an AI probability score (0.0 - 1.0)
    # These thresholds are heuristic and would normally be tuned on a dataset.
    
    # AI often has TTR below 0.55 (repetitive), humans often above 0.6.
    # Let's map TTR to a score (inverted: lower TTR -> higher AI score)
    # TTR > 0.7 -> score 0.1
    # TTR < 0.4 -> score 0.9
    ttr_score = 0.5
    if ttr < 0.45:
        ttr_score = 0.8
    elif ttr > 0.65:
        ttr_score = 0.2
        
    # AI often has low sentence length variance (e.g., < 20), humans often > 40.
    slv_score = 0.5
    if slv < 15:
        slv_score = 0.8 # Very uniform
    elif slv > 50:
        slv_score = 0.2 # Highly variable
        
    # Combined stylometric score (average)
    if slv == 0.0: # If only one sentence, fallback to TTR
        combined_score = ttr_score
    else:
        combined_score = (ttr_score + slv_score) / 2.0
        
    return {
        "stylometric_score": combined_score,
        "metrics": {
            "type_token_ratio": ttr,
            "sentence_length_variance": slv
        }
    }

if __name__ == "__main__":
    ai_text = "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment."
    human_text = "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there"
    
    print("AI Text Analysis:", analyze_stylometrics(ai_text))
    print("Human Text Analysis:", analyze_stylometrics(human_text))
