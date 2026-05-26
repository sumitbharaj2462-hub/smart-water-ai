"""CLI for AquaOps AI assistant."""

from __future__ import annotations

import argparse
import sys

from assistant.agent import WaterAssistantAgent
from assistant.reports.emergency import generate_emergency_report


def main() -> None:
    parser = argparse.ArgumentParser(description="AquaOps AI water operations assistant")
    parser.add_argument("message", nargs="?", help="Question to ask")
    parser.add_argument("--report", action="store_true", help="Generate emergency report")
    parser.add_argument("--interactive", "-i", action="store_true", help="REPL mode")
    args = parser.parse_args()

    agent = WaterAssistantAgent()
    print(f"Provider: {agent.provider_info()}\n")

    if args.report:
        print(generate_emergency_report(save=True))
        return

    if args.interactive or not args.message:
        print("AquaOps AI — type 'exit' to quit, 'report' for emergency report\n")
        history: list[dict] = []
        while True:
            try:
                user = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user:
                continue
            if user.lower() in ("exit", "quit"):
                break
            if user.lower() == "report":
                print(generate_emergency_report(save=True))
                continue
            result = agent.chat(user, history)
            print(f"\nAquaOps ({result['provider']}):\n{result['content']}\n")
            history.append({"role": "user", "content": user})
            history.append({"role": "assistant", "content": result["content"]})
        return

    result = agent.chat(args.message)
    print(result["content"])


if __name__ == "__main__":
    main()
