"""
Preference following evaluation using EPIC's 4-metric error analysis.
Metrics: acknow, violate, hallucinate, helpful
"""
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.llm_client import call_llm

EVAL_SYSTEM = "You are a helpful assistant in evaluating an AI assistant's response. You should be fair and strict and follow the user's instruction."

ACKNOW_PROMPT = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant acknowledges any user preference in answering the user's query.

Evaluate the response based on these stringent criteria:

1. Check if the response explicitly or implicitly mentions or references a user preference. 2. The content of the preference is irrelevant for this check; only its presence matters.

Answer "Yes" if:

1. The response explicitly mentions or refers to a user preference in answering the user's question. Examples include: "Based on your previous preference for xxxx"; "Based on your previous preference, I would suggest you xxxx"; "Since you mentioned you prefer/dislike xxxx"; "Since you are a xxxx"; "I will recommend the following given your preference for xxx", etc. You should extract the "xxxx" in your answer. If it only says "Based on our previous conversation, I recommend..." and does not explicitly mention any preference, you should answer 'No'.
2. The response assumes the user preference in answering the user's question implicitly. For example, when the user asks 'Can you recommend me cars to drive?', if the response is 'Based on your preference, I will recommend non-EV cars, ...', then this indicates the assistant assumes that the user's preference is a dislike of EV cars, and you should answer 'Yes'.

Answer "No" if the response does not mention or refer to any user preference explicitly or implicitly. If you cannot extract the sentence stating what the preference is, answer 'No'.

Here is the assistant's response:
The user's question is: {question}
Assistant response: {end_generation}

Examine the response meticulously and answer. Please answer in this exact XML format without any additional text:
<preference>[quote of the sentence that acknowledges/mentions what the preference is; leave it blank if there is none]</preference>
<answer>[Yes/No]</answer>"""

VIOLATE_PROMPT = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant's response violates the user's stated preference.
Evaluate the response based on these criteria:

Answer "Yes" if:

1. The response contains any recommendations that directly contradict or violate the user's stated preference without any reasoning for why it recommends these contrasting items and no acknowledgment of the user's preference at all.

Answer "No" if:

1. The response respects the user's stated preference.
2. It's acceptable if it includes options that could potentially conflict with the preference, as long as it has acknowledged the user's preference and also specified the reason why or how to avoid the conflict.
3. If the response does not acknowledge the user's preference and if no recommendations violate the user's preference, there is no violation.

Here is the conversation:
User's preference: {preference}
User query: {question}
Assistant response: {end_generation}

Examine the response meticulously and answer. Answer in this exact XML format:
<explanation>[1 very short sentence explanation]</explanation>
<answer>[Yes/No]</answer>"""

HALLUCINATE_PROMPT = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant's restatement of the user's stated preference is the same preference. Evaluate the response based on these stringent criteria to answer if the assistant has hallucinated the preference or not:

Answer "Yes" if:

1. The assistant's restatement differs from the original preference in meaning or intent.
2. The assistant's restatement contradicts the original preference.
3. The assistant's restatement is not related or irrelevant to the original preference.

Answer "No" if has not hallucinated:

1. The assistant's restatement matches the original preference.
2. The assistant's restatement is a minor paraphrase that fully preserves the meaning and intent of the original preference.
3. The restatement is just empty, no hallucination.

Here is the information:
Original user preference: "{preference}"
Assistant's restatement: "{assistant_restatement}"
Examine the original preference and the assistant's restatement meticulously and answer. Please answer in this exact XML format without any other additional text:
<explanation>[1 short sentence explanation]</explanation>
<answer>[Yes/No]</answer>"""

HELPFUL_PROMPT = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant provides any substantive response to the user's query.
Evaluate the response based on these stringent criteria:

Answer "Yes" if any of the following:

1. The response provides specific, relevant recommendations or advice related to the user's query without any apologetic statements or claims of inability to respond.
2. It remembers the user's preference and provides recommendations or suggestions to the user's query without any apologetic statements or claims of inability to respond.

Answer "No" if any of the following:

1. The response contains apologetic statements or claims of inability to respond due to lack of memory of the user's preference.
2. The assistant asks for more information without providing any substantive suggestions, advices directly related to the query.
3. The response doesn't address the user's query.
4. Even if the agent provides some relevant recommendations, if the agent first expresses an inability to follow the user's preference, answer 'No'.

Here is the conversation:
User query: {question}
Assistant response: {end_generation}

Examine the response meticulously and answer. Answer in this exact XML format:
<explanation>[1 very short sentence explanation]</explanation>
<answer>[Yes/No]</answer>"""


def _parse_answer(text: str) -> str:
    m = re.search(r'<answer>\s*([^\s<]+)\s*</answer>', text, re.IGNORECASE)
    return m.group(1).strip().lower() if m else ""


def _parse_preference(text: str) -> str:
    m = re.search(r'<preference>(.*?)</preference>', text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _call(prompt: str, backend: str | None = None) -> str:
    return call_llm(
        messages=[{"role": "user", "content": prompt}],
        system=EVAL_SYSTEM,
        max_tokens=200,
        temperature=0.0,
        backend=backend,
    )


def evaluate_response(question: str, preference: str, response: str, backend: str | None = None) -> dict:
    """
    Run all 4 evaluation metrics in parallel.
    Returns dict with per-metric results + overall preference_following bool.
    """
    def run_acknow():
        p = ACKNOW_PROMPT.format(question=question, end_generation=response)
        raw = _call(p, backend)
        answer = _parse_answer(raw)
        extract = _parse_preference(raw)
        return "acknow", {"answer": answer, "extract_pref": extract, "raw": raw}

    def run_violate():
        p = VIOLATE_PROMPT.format(preference=preference, question=question, end_generation=response)
        raw = _call(p, backend)
        return "violate", {"answer": _parse_answer(raw), "raw": raw}

    def run_helpful():
        p = HELPFUL_PROMPT.format(question=question, end_generation=response)
        raw = _call(p, backend)
        return "helpful", {"answer": _parse_answer(raw), "raw": raw}

    results = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(run_acknow), ex.submit(run_violate), ex.submit(run_helpful)]
        for f in futs:
            k, v = f.result()
            results[k] = v

    # hallucinate needs acknow result first
    is_acknowledgement = "yes" in results.get("acknow", {}).get("answer", "")
    if is_acknowledgement:
        extract_pref = results["acknow"].get("extract_pref", "")
        p = HALLUCINATE_PROMPT.format(preference=preference, assistant_restatement=extract_pref)
        raw = _call(p, backend)
        results["hallucinate"] = {"answer": _parse_answer(raw), "raw": raw}
    else:
        results["hallucinate"] = {"answer": "no", "raw": ""}

    # Compute error flags
    is_violation  = "yes" in results.get("violate", {}).get("answer", "")
    is_hallucinate = is_acknowledgement and "yes" in results.get("hallucinate", {}).get("answer", "")
    is_unhelpful  = "no"  in results.get("helpful", {}).get("answer", "")

    is_inconsistent           = is_acknowledgement and not is_hallucinate and is_violation and not is_unhelpful
    is_halluc_pref_violation  = is_acknowledgement and is_hallucinate and is_violation and not is_unhelpful
    is_pref_unaware_violation = not is_acknowledgement and is_violation and not is_unhelpful

    preference_following = not any([
        is_inconsistent, is_halluc_pref_violation,
        is_pref_unaware_violation, is_unhelpful
    ])

    return {
        "acknow":      is_acknowledgement,
        "violate":     is_violation,
        "hallucinate": is_hallucinate,
        "helpful":     not is_unhelpful,
        "inconsistent":                    is_inconsistent,
        "hallucination_of_pref_violation": is_halluc_pref_violation,
        "preference_unaware_violation":    is_pref_unaware_violation,
        "preference_following":            preference_following,
        "details": results,
    }
