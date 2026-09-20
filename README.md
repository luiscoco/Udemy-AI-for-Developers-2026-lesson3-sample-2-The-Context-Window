# Sample 2 – The Context Window (Slide 4)

A small working Python app that demonstrates one idea from the lesson:

> The **context window** is the amount of information the model can consider at once.
> More relevant context → more accurate and useful answers.

The app asks the same question twice – once with **only the user prompt**, once with a **context window** that also contains past conversation and documentation – and prints both answers so you can compare them.

## Files

| File | Purpose |
|---|---|
| [context_window.py](context_window.py) | The app |
| [requirements.txt](requirements.txt) | Dependency (`anthropic` SDK) |

## Run it

```bash
pip install -r requirements.txt

# Windows PowerShell (note: `set NAME=value` does NOT work in PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-..."
# Windows cmd
set ANTHROPIC_API_KEY=sk-ant-...
# macOS / Linux / Git Bash
export ANTHROPIC_API_KEY="sk-ant-..."

python context_window.py             # calls Claude and compares the two answers
python context_window.py --dry-run   # only prints the assembled context (no API call, no key needed)
python context_window.py --max-tokens 120   # change the answer length limit (default 200, the slide uses 50)
```

Optional environment variables:

- `CLAUDE_MODEL` – use a different model (default: `claude-opus-5`).
- `ANTHROPIC_WORKSPACE_ID` – required only if your API key is not scoped to a workspace (the API otherwise answers `400: This API key is not scoped to a workspace`). Alternatively, create a workspace-scoped key in the Anthropic Console.

## From the slide to the code

The slide's snippet is pseudocode:

```python
# Context Window (Slide 4)
context_window = []

# Add relevant information
context_window.append(user_prompt)
context_window.append(past_chat)
context_window.append(documentation)

# Generate with full context
response = llm.generate(
    context=context_window,
    max_tokens=50
)
```

The app makes that snippet real. Below is each piece.

### 1. The information sources

```python
user_prompt = "How do I deploy my service to the staging environment?"

past_chat = (
    "User: We just migrated our team from Jenkins to the 'shipit' CLI.\n"
    "Assistant: Great, let me know if you need help with shipit commands."
)

documentation = (
    "shipit CLI reference (v2.3)\n"
    "- `shipit login --team <name>`: authenticate before any deploy.\n"
    ...
)
```

These are three of the things the slide lists under *"Context can include"*: **your prompt**, **previous conversation** and **documentation**. (Code, tool outputs and other relevant information work the same way – they are just more text in the window.)

`shipit` is an invented tool on purpose. The model cannot know it from training, so the only way it can answer correctly is by reading the context we give it. That makes the effect of the context window easy to see.

### 2. Building the context window

```python
def build_context_window() -> list[str]:
    context_window = []

    context_window.append(f"Documentation:\n{documentation}")
    context_window.append(f"Previous conversation:\n{past_chat}")
    context_window.append(f"User question: {user_prompt}")
    return context_window
```

This is the slide's `context_window = []` followed by the `append` calls. Two small differences from the slide:

- Each item gets a label (`Documentation:`, `Previous conversation:`, …) so the model can tell what each block is.
- The user question goes **last**, right before the model answers – it is the thing the model should respond to, with everything above it as supporting material.

### 3. The `llm.generate(...)` call

```python
class LLM:
    def __init__(self, model: str = MODEL):
        self.client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY
        self.model = model

    def generate(self, context: list[str], max_tokens: int = 200) -> str:
        prompt = "

".join(context)
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "disabled"},
            system="Answer concisely in plain text, no markdown, at most 4 short lines.",
            messages=[{"role": "user", "content": prompt}],
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        if response.stop_reason == "max_tokens":
            text += " [...cut off by max_tokens]"
        if not text.strip():
            text = f"[no answer: stop_reason={response.stop_reason}, ...]"
        return text
```

The slide's `llm` object doesn't exist in any library, so this small class provides it. Line by line:

- **`"

".join(context)`** – the list of context items is flattened into one text. Everything ends up in a single request, so the model sees all of it *at once* – that is what "context window" means.
- **`client.beta.messages.create(...)`** – the actual call to the Claude API (the beta endpoint is needed for the fallback option below).
- **`max_tokens`** – the maximum length of the *answer* (not of the context). The slide uses 50, but at 50 tokens most answers are cut off before the useful part, so the app defaults to 200 (`--max-tokens 50` reproduces the slide).
- **`thinking={"type": "disabled"}`** – internal reasoning would consume part of the `max_tokens` budget before any visible text is produced, so it is turned off for this demo.
- **`system=...`** – a short style instruction (same for both calls) so answers fit in the token limit.
- **`betas` + `fallbacks: "default"`** – the model's safety classifiers can occasionally decline a harmless request (we saw a `stop_reason=refusal` with an empty answer on the with-context call). With this option the API re-runs a declined request on a fallback model instead of returning nothing.
- **`response.content`** – a list of content blocks; we keep only the `text` blocks and join them.
- **`stop_reason == "max_tokens"`** – tells us the answer hit the limit, so the app marks it as truncated instead of silently showing half a sentence.
- **`if not text.strip()`** – if the model returns no text at all (for example a refusal), the app prints why instead of a blank line.

### 4. Comparing with and without context

```python
llm = LLM()
bare = llm.generate(context=[user_prompt], max_tokens=args.max_tokens)
full = llm.generate(context=context_window, max_tokens=args.max_tokens)
```

Same model, same question, same token limit – the **only** difference is what is inside the context window. Expected result:

- **Without context** – a generic answer ("it depends on your tooling: Kubernetes, Heroku, CI/CD…") or a request for more information.
- **With context** – an answer based on the documentation, e.g. run `shipit test <service>` first, then `shipit deploy <service> --env staging`.

(The exact wording varies from run to run.)

### 5. Error handling

```python
except (anthropic.AuthenticationError, TypeError):
    print("No valid credentials: set ANTHROPIC_API_KEY (or use --dry-run).", file=sys.stderr)
    return 1
except anthropic.APIError as e:
    print(f"API error: {e}", file=sys.stderr)
    return 1
```

- A missing key makes the SDK raise a `TypeError`; a wrong key raises `AuthenticationError`. Both give the same friendly message.
- Any other API failure (rate limit, network, …) is reported without a stack trace.

## Things to try

1. Delete `past_chat` from `build_context_window()` – does the answer still mention `shipit`? (The documentation alone is often enough; the chat mostly tells the model *which* tool you use.)
2. Delete `documentation` instead – the model now knows the tool name but has to guess the commands.
3. Add an irrelevant paragraph to the context. Relevant context helps; noise takes up space in the window and can distract the model.
4. Run with `--max-tokens 20` and watch the answer get truncated.

## Key takeaways

- The model only "knows" what was in its training data **plus what is in the context window** for this request.
- Assembling good context (prompt + history + docs + code + tool outputs) is often the cheapest way to get better answers – no retraining needed.
- The window is finite, so what you put into it should be **relevant**, not just large.
