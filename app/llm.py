import json
from openai import OpenAI
from .config import settings
client = OpenAI(api_key=settings.openai_api_key, base_url=settings.llm_base_url)
def ask_llm(prompt, max_tokens=3000):
    response = client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""
def extract_graph(text):
    prompt = (
        "Extract entities and relationships from this text.\n"
        "Reply with JSON only, in exactly this format:\n"
        '{"entities": [{"name": "...", "type": "Person"}], '
        '"relations": [{"source": "...", "relation": "CEO_OF", "target": "..."}]}\n\n'
        "Text:\n" + text
    )
    reply = ask_llm(prompt)
    start = reply.find("{")
    end = reply.rfind("}")
    if start == -1 or end == -1:
        print("no json in llm reply:", reply[:200])
        return {"entities": [], "relations": []}
    try:
        data = json.loads(reply[start:end + 1])
    except json.JSONDecodeError:
        print("could not parse llm reply:", reply[:200])
        return {"entities": [], "relations": []}
    return {
        "entities": data.get("entities", []),
        "relations": data.get("relations", []),
    }
def answer_question(question, chunks, facts):
    passages = "\n\n".join(c["text"] for c in chunks)
    fact_lines = "\n".join(f"{f['source']} {f['relation']} {f['target']}" for f in facts)
    prompt = (
        "Answer the question using only the info below. "
        "If it is not there, say you don't know.\n\n"
        f"Passages:\n{passages}\n\n"
        f"Facts:\n{fact_lines}\n\n"
        f"Question: {question}"
    )
    return ask_llm(prompt, max_tokens=1500)