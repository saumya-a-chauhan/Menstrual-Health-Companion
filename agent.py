import os
import json
import requests
from dotenv import load_dotenv

# ==========================================
# LOAD ENV
# ==========================================
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY not found")

if not TAVILY_API_KEY:
    raise ValueError("❌ TAVILY_API_KEY not found")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


# ==========================================
# HELPERS
# ==========================================
def clean_json_string(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


def safe_json_load(text):
    try:
        return json.loads(clean_json_string(text))
    except:
        print("⚠️ JSON parse fail:\n", text)
        return {}


def call_llm(system_prompt, user_prompt, temperature=0.2):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("❌ LLM ERROR:", response.text if 'response' in locals() else str(e))
        raise e


# ==========================================
# STEP 1
# ==========================================
def step1_semantic_router(state):
    print(" -> Step 1")

    system_prompt = """You are a precise data extractor. Break the user's input into a strict JSON object.
    
    CRITICAL RULES:
    - ONLY extract what is explicitly written. 
    - DO NOT infer symptoms or emotions. If the user asks "what tests for endometriosis", the symptoms array must be EMPTY because they did not state they have pain.
    - Use empty arrays/strings if a category is not mentioned. Output ONLY valid JSON.
    
    Format strictly as:
    {
      "symptoms": [],
      "emotional_state": "string or empty",
      "myths_to_check": [],
      "lifestyle_queries": [],
      "education_queries": []
    }"""

    output = call_llm(system_prompt, f"Input: '{state['raw_input']}'", temperature=0.0)
    state.update(safe_json_load(output))
    return state


# ==========================================
# STEP 2 (FIXED SEARCH)
# ==========================================
def step2_medical_search(state):
    print(" -> Step 2")

    RELEVANCE_KEYWORDS = ["period", "menstruation", "menstrual", "cycle", "ovulation", "hormone", "pcos", "endometriosis"]
    queries = []

    if state.get("symptoms"):
        queries.append(
            f"site:mayoclinic.org OR site:acog.org menstruation OR period {', '.join(state['symptoms'])} causes and diagnosis"
        )

    if state.get("myths_to_check") or state.get("education_queries"):
        combined = state.get("myths_to_check", []) + state.get("education_queries", [])
        
        # 🔥 FIX: force menstruation context
        queries.append(
            f"site:plannedparenthood.org OR site:acog.org OR site:clevelandclinic.org "
            f"{', '.join(combined)} menstruation OR period transgender explanation"
        )

    if state.get("lifestyle_queries"):
        queries.append(
            f"site:hopkinsmedicine.org {', '.join(state['lifestyle_queries'])} during period"
        )

    if not queries:
        state["retrieved_sources"] = []
        state["tool_status"] = "No Search Required"
        return state

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": " | ".join(queries),
        "search_depth": "basic"
    }

    try:
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=10)
        response.raise_for_status()
        raw_results = response.json().get('results', [])

        if not raw_results:
            state["retrieved_sources"] = [{
                "url": "N/A",
                "content": "No relevant sources found."
            }]
        else:
            filtered = []
            for r in raw_results:
                content_lower = r['content'].lower()
                if any(k in content_lower for k in RELEVANCE_KEYWORDS):
                    filtered.append({"url": r["url"], "content": r["content"]})

            state["retrieved_sources"] = filtered if filtered else [
                {"url": r["url"], "content": r["content"]} for r in raw_results
            ]

        state["tool_status"] = "Success"

    except Exception as e:
        print("⚠️ Tool Error:", e)
        state["retrieved_sources"] = [{"url": "N/A", "content": "TOOL_ERROR"}]
        state["tool_status"] = f"Failed: {str(e)}"

    return state


# ==========================================
# STEP 3 (RELEVANCE FIX ADDED)
# ==========================================
def step3_scientific_analysis(state):
    print(" -> Step 3")

    system_prompt = """You are an expert in reproductive health. Review the retrieved context and extract facts based ONLY on what the user asked.
    
    RULES:
    1. If the user listed SYMPTOMS: State if it's normal or points to conditions like PCOS/Endometriosis.
    2. If the user asked about MYTHS/EDUCATION: Extract the direct scientific truth objectively. DO NOT assume they have a disease just because they asked about it.
    3. STRICT RELEVANCE FILTER: Only include findings directly answering the user's query. Ignore unrelated topics (e.g., pregnancy, fertility) unless explicitly asked.
    
    Output ONLY JSON with keys: 'findings' (list), 'conditions' (list), 'tests' (list), 'confidence_score' (0-1)."""

    context = "\n".join([f"Source: {s['content']}" for s in state["retrieved_sources"]])
    user_prompt = f"Symptoms: {state.get('symptoms')}\nMyths/Questions: {state.get('myths_to_check')} {state.get('education_queries')}\nContext: {context}"

    output = call_llm(system_prompt, user_prompt, temperature=0.1)
    state["analysis_data"] = safe_json_load(output)

    return state


# ==========================================
# STEP 4 (RELEVANCE-AWARE VERIFIER)
# ==========================================
def step4_verifier(state):
    print(" -> Step 4")

    system_prompt = """You are a medical Quality Assurance bot. 
    Compare the Analysis Findings against the Retrieved Sources.

    You must check TWO things:
    1. FACTUAL ACCURACY: Are claims supported by sources?
    2. RELEVANCE: Do the findings directly answer the user's query?

    Return JSON:
    {
     "is_valid": bool,
     "hallucination_detected": bool,
     "irrelevant_detected": bool,
     "corrections": []
    }

    If content is irrelevant to the query, mark invalid and suggest corrected findings."""

    user_prompt = f"User Query: {state['raw_input']}\nSources: {state['retrieved_sources']}\nAnalysis: {state['analysis_data']}"
    output = call_llm(system_prompt, user_prompt, temperature=0.0)

    state["verification"] = safe_json_load(output)

    # 🔥 APPLY FIREWALL
    if not state["verification"].get("is_valid", True) or state["verification"].get("irrelevant_detected", False):
        state["analysis_data"]["findings"] = state["verification"].get("corrections", [])

    return state


# ==========================================
# STEP 5
# ==========================================
def step5_empathetic_translation(state):
    print(" -> Step 5")

    system_prompt = """You are a supportive health educator. 
    Draft a JSON object with a 'support_draft' key. 
    CRITICAL RULE: If the 'Emotions' field is empty and no symptoms exist, 'support_draft' must be a professional greeting only.
    If the user explicitly expresses negative emotions or pain, draft a warm, validating response.
    DO NOT assume they are asking about their own body unless they use "I" or "my"."""

    findings = state.get('analysis_data', {}).get('findings', [])
    user_prompt = f"Emotions: {state.get('emotional_state')}\nFacts: {findings}"

    output = call_llm(system_prompt, user_prompt, temperature=0.3)
    state["empathetic_data"] = safe_json_load(output)

    return state


# ==========================================
# STEP 6
# ==========================================
def step6_final_formatter(state):
    print(" -> Step 6")

    system_prompt = """You are a knowledgeable menstrual health educator and companion.
    Write a conversational, direct response answering the user's exact query.
    Return JSON with key 'final_markdown'.
    
    CRITICAL RULES:
    1. DO NOT ASSUME IT'S ABOUT THE USER'S BODY: Unless they used "I" or "my".
    2. NO HALLUCINATED SYMPTOMS. 
    3. IF THEY EXPLICITLY REPORT PAIN: Validate their pain warmly (like a smart older sister).
    4. Keep it to 2-3 flowing paragraphs. No clinical headers. No bullet points.
    5. End with a gentle, non-robotic disclaimer.
    """

    user_prompt = f"Support: {state['empathetic_data'].get('support_draft','')}\nFacts: {state['analysis_data']}"

    output = call_llm(system_prompt, user_prompt, temperature=0.2)
    parsed = safe_json_load(output)

    state["final_markdown_output"] = parsed.get("final_markdown", "⚠️ Could not generate response.")

    return state


# ==========================================
# MAIN
# ==========================================
def run_agent(user_input):
    state = {
        "raw_input": user_input,
        "agent_version": "2.3.0-relevance-safe"
    }

    try:
        state = step1_semantic_router(state)
        state = step2_medical_search(state)
        state = step3_scientific_analysis(state)
        state = step4_verifier(state)
        state = step5_empathetic_translation(state)
        state = step6_final_formatter(state)

        summary = f"\n\n---\n### 📊 AI Summary Scorecard\n"
        summary += f"- **Intent:** {'Symptom Analysis' if state.get('symptoms') else 'Educational'}\n"
        summary += f"- **Verification Status:** {'✅ Verified' if state.get('verification', {}).get('is_valid') else '⚠️ Adjusted'}\n"
        summary += f"- **Sources:** {len(state.get('retrieved_sources', []))}"

        full_output = state["final_markdown_output"] + summary

        print("\n" + "="*60)
        print(" 🌸 MENSTRUAL HEALTH COMPANION 🌸 ")
        print("="*60 + "\n")
        print(full_output)
        print("\n" + "="*60)

    except Exception as e:
        print("❌ FATAL ERROR:", e)


if __name__ == "__main__":
    print("🌸 Companion Ready (Relevance-Safe Build)\n")

    while True:
        user_text = input("How can I help you today? > ")

        if user_text.lower() in ['exit', 'quit']:
            print("Take care! 🌷")
            break

        if not user_text.strip():
            continue

        run_agent(user_text)