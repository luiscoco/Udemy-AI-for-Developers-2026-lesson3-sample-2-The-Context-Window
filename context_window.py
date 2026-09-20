"""Slide 4 - Context Window.

The context window is everything the model can consider at once. This app
assembles several information sources (user prompt, past chat, documentation)
into a `context_window` list and sends it to the model, then compares the
answer with and without that context.

Usage:
    python context_window.py              # calls Claude (needs ANTHROPIC_API_KEY)
    python context_window.py --dry-run    # only prints the assembled context
"""

import argparse
import os
import sys

import anthropic

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")

# --- Information sources that can go into the context window -----------------

user_prompt = "How do I deploy my service to the staging environment?"

past_chat = (
    "User: We just migrated our team from Jenkins to the 'shipit' CLI.\n"
    "Assistant: Great, let me know if you need help with shipit commands."
)

documentation = (
    "shipit CLI reference (v2.3)\n"
    "- `shipit login --team <name>`: authenticate before any deploy.\n"
    "- `shipit deploy <service> --env staging|production`: deploy a service.\n"
    "- Staging deploys require a passing `shipit test <service>` run first.\n"
    "- `shipit rollback <service> --env <env>`: revert to the previous release."
)


class LLM:
    """Thin wrapper so the call reads like the slide: llm.generate(context=..., max_tokens=...)."""

    def __init__(self, model: str = MODEL):
        # Reads ANTHROPIC_API_KEY from the environment. Keys that are not scoped to a
        # workspace also need the workspace ID (ANTHROPIC_WORKSPACE_ID).
        workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
        self.client = anthropic.Anthropic(default_headers=headers)
        self.model = model

    def generate(self, context: list[str], max_tokens: int = 50) -> str:
        # Everything in the context window is presented to the model at once.
        prompt = "\n\n".join(context)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            # max_tokens is tiny, so keep it all for the visible answer.
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        if response.stop_reason == "max_tokens":
            text += " [...cut off by max_tokens]"
        return text


def build_context_window() -> list[str]:
    # Context Window (Slide 4)
    context_window = []

    # Add relevant information
    context_window.append(f"Documentation:\n{documentation}")
    context_window.append(f"Previous conversation:\n{past_chat}")
    context_window.append(f"User question: {user_prompt}")
    return context_window


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the context window without calling the model")
    parser.add_argument("--max-tokens", type=int, default=50, help="answer length limit (slide uses 50)")
    args = parser.parse_args()

    context_window = build_context_window()

    print("=== Context window ===")
    for i, item in enumerate(context_window, 1):
        print(f"[{i}] {item}\n")

    if args.dry_run:
        return 0

    llm = LLM()
    try:
        # Generate with only the prompt vs. with full context
        bare = llm.generate(context=[user_prompt], max_tokens=args.max_tokens)
        full = llm.generate(context=context_window, max_tokens=args.max_tokens)
    except (anthropic.AuthenticationError, TypeError):
        # TypeError: the SDK raises it when no credentials are configured at all.
        print("No valid credentials: set ANTHROPIC_API_KEY (or use --dry-run).", file=sys.stderr)
        return 1
    except anthropic.APIError as e:
        print(f"API error: {e}", file=sys.stderr)
        return 1

    print("=== Without context (prompt only) ===")
    print(bare, "\n")
    print("=== With full context ===")
    print(full)
    return 0


if __name__ == "__main__":
    sys.exit(main())
