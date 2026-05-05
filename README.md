
---

#  Menstrual Health Companion: Advanced Agentic Pipeline

## What this agent does
This is a goal-driven AI agent designed to bridge the gap between clinical jargon and unverified myths in menstrual health. Unlike a standard chatbot that relies on a single prompt, this agent uses a **6-step reasoning pipeline** to analyze intent, retrieve live medical data, verify facts, and deliver a personalized, empathetic response.

It is built specifically to handle **logical branching**: it provides objective education to researchers or curious users while switching to a supportive "older sister" tone for users reporting physical pain.

---

##  The Agentic Pipeline (Chain Structure)
The agent operates via a shared `state` dictionary that passes structured data through the following chain:

1.  **Step 1: Semantic Router (Intent Extraction)**
    *   **Input:** Raw user text.
    *   **Output:** Structured JSON object.
    *   **Role:** Identifies symptoms, myths, or educational queries. It serves as the "brain" that dictates how the rest of the chain behaves.
2.  **Step 2: Information Retrieval (Tavily Tool)**
    *   **Input:** Key terms from Step 1.
    *   **Output:** Filtered clinical snippets.
    *   **Role:** Uses the Tavily API to fetch data from trusted domains (ACOG, Mayo Clinic). It forces a "menstruation context" to avoid irrelevant health results.
3.  **Step 4: Scientific Analyst (Fact Extraction)**
    *   **Input:** Web context + user intent.
    *   **Output:** Structured facts (JSON).
    *   **Role:** An objective parser that identifies medical conditions (PCOS, Endometriosis) and recommended tests based strictly on the retrieved data.
4.  **Step 4: The Verifier (System Firewall)**
    *   **Input:** Analyst findings + original search sources.
    *   **Output:** Validation boolean + corrections.
    *   **Role:** This is the **Quality Assurance** layer. It compares the analyst’s findings against the sources to detect and correct hallucinations before they reach the user.
5.  **Step 5: Empathetic Translator (Tone Management)**
    *   **Input:** Extracted facts + emotional state.
    *   **Output:** Supportive draft.
    *   **Role:** A logic-gated step. If the user is in distress, it generates deep empathy. If the query is educational, it remains friendly but professional.
6.  **Step 6: Final Formatter (Presentation Layer)**
    *   **Input:** Empathetic draft + validated facts.
    *   **Output:** Conversational Markdown + Data Scorecard.
    *   **Role:** Synthesizes all data into a flowing, sisterly response and appends a structured summary for actionable clarity.

---

##  Production-Grade Features
*   **Observability:** Every run generates an `agent_log.json` file, allowing developers to inspect the intermediate state of every step in the chain.
*   **Schema Enforcement:** Every LLM step is forced to output valid JSON using `response_format` constraints to prevent pipeline breakage.
*   **Relevance Filtering:** Step 2 includes a keyword-based logic gate to discard search results unrelated to menstrual health.

---

## Installation
1.  **Clone the repository** and navigate to the project directory.
2.  **Install dependencies:**
    ```bash
    pip install requests python-dotenv
    ```
3.  **Setup Environment Variables:**
    Create a `.env` file in the root directory and add your keys:
    
```env
    GROQ_API_KEY=your_xai_grok_key_here
    TAVILY_API_KEY=your_tavily_key_here
    ```

---

##  How to Run
Launch the interactive CLI by running:
```bash
python agent.py
```
Type your query at the prompt. To exit the program, type `exit` or `quit`.

---

##  Expected Inputs
The agent is trained to handle three primary types of input:
*   **Symptom Reporting:** *"I have really heavy flow and my cramps are extreme."*
*   **Myth Busting:** *"Does drinking cold water during your period stop the flow?"*
*   **General Education:** *"What tests are used to diagnose Endometriosis?"* or *"How do menstrual cups work?"*

##  Output Files
*   **`triage_report.md`**: The human-readable report.
*   **`agent_log.json`**: The technical audit trail of the reasoning chain.

---
**Disclaimer:** *This agent is an educational AI project and does not provide professional medical diagnoses. Always consult a healthcare provider for medical concerns.*
```