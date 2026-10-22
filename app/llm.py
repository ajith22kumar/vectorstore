import json
from openai import OpenAI, OpenAIError, RateLimitError
from .errors import AppError
from .config import settings
client = OpenAI(api_key=settings.openai_api_key, base_url=settings.llm_base_url)
NO_ANSWER = "I don't know based on the provided documents."
def ask_llm(prompt, max_tokens=3000):
    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=max_tokens,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
    except RateLimitError as e:
        raise AppError(429, "LLM rate limit or quota reached, try again later") from e
    except OpenAIError as e:
        raise AppError(502, "LLM call failed: " + str(e)[:150]) from e
    return response.choices[0].message.content or ""
def extract_graph(text):
    prompt = (
        "You extract a knowledge graph from text.\n"
        "Rules:\n"
        "- Use full names for entities. Never use pronouns or phrases like 'the company'; "
        "replace them with the real name.\n"
        "- Entity types: Person, Organization, Place, Product, Event, Concept, Date.\n"
        "- Relation names are SHORT_UPPERCASE_WITH_UNDERSCORES, for example CEO_OF, FOUNDED, "
        "ACQUIRED, LOCATED_IN, WORKS_AT, PART_OF.\n"
        "- Only include facts that are stated in the text.\n"
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
    passages = "\n\n".join(f"[{i + 1}] {c['text']}" for i, c in enumerate(chunks))
    fact_lines = "\n".join(f"- {f['source']} {f['relation']} {f['target']}" for f in facts) or "(none)"

    prompt = (
        "Answer the question using only the passages and graph facts below.\n"
        "Use the graph facts to connect information that is spread over different passages.\n"
        f"If the answer is not there, reply exactly: {NO_ANSWER}\n"
        "Keep the answer short and direct, and mention the passage numbers like [1] that support it.\n\n"
        f"Passages:\n{passages}\n\n"
        f"Graph facts:\n{fact_lines}\n\n"
        f"Question: {question}\nAnswer:")
    return ask_llm(prompt, max_tokens=1500).strip()