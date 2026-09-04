"""
main.py
=======
SMAR: Memory-Driven Autonomous Voice Automation System.
Entry point for CLI, Voice, and Diagnostic modes.
"""

import sys
import os
import argparse
import asyncio
from dotenv import load_dotenv

# Fix Windows terminal UTF-8 encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

load_dotenv()

from pipeline.session import VoiceAgentSession


async def run_cli_mode(session: VoiceAgentSession):
    print("=" * 60)
    print("  SMAR: Memory-Driven Autonomous Voice Assistant")
    print("  [Mode: Interactive CLI with Epsilon LLM & Context Memory]")
    print("  Type your prompt, or type 'exit' / 'quit' to stop.")
    print("=" * 60 + "\n")

    while True:
        try:
            prompt = input("\nYou: ").strip()
            if not prompt:
                continue
            if prompt.lower() in ["exit", "quit", "q"]:
                print("\n[SMAR] Exiting session. Memory state preserved.")
                break

            await session.process_text_turn(prompt, speak_output=False)
        except (KeyboardInterrupt, EOFError):
            print("\n[SMAR] Terminating session.")
            break


async def run_voice_mode(session: VoiceAgentSession, duration: float = 5.0):
    print("=" * 60)
    print("  SMAR: Voice Mode Active (Gnani STT/TTS + Epsilon LLM)")
    print("  Press Ctrl+C to terminate.")
    print("=" * 60 + "\n")

    while True:
        try:
            input("\n[Press ENTER to start speaking...]")
            await session.run_voice_turn(record_seconds=duration)
        except (KeyboardInterrupt, EOFError):
            print("\n[SMAR] Stopping voice loop.")
            break


async def run_diagnostic_test(session: VoiceAgentSession):
    print("\n--- Running SMAR Pipeline Diagnostics ---")
    
    # 1. Test Context Memory Layer
    print("\n1. Testing Memory Ingestion & Knowledge Graph...")
    test_input = "I like python programming and my email is dev@smar.ai"
    result = session.context.ingest_turn(test_input)
    print(f"  Ingested Triples: {result['triples']}")
    print(f"  Vector Memory Node ID: {result['vector_id']} (Updated: {result['vector_updated']})")

    # 2. Test Context Retrieval
    print("\n2. Testing Context Retrieval for query 'What do I like?'...")
    retrieved = session.context.retrieve_context("What do I like?")
    print(f"  Retrieved Context:\n{retrieved}")

    # 3. Test Epsilon Bridge
    print("\n3. Testing Epsilon Bridge Health Check...")
    is_healthy = await session.epsilon.is_server_healthy()
    print(f"  Epsilon llama-server reachable: {is_healthy}")

    # 4. Run sample turn
    print("\n4. Running Sample Conversation Turn...")
    turn_res = await session.process_text_turn("What programming language do I prefer?", speak_output=False)
    print("--- Diagnostic Completed Successfully ---\n")


def main():
    parser = argparse.ArgumentParser(description="SMAR Voice Automation System")
    parser.add_argument("--voice", action="store_true", help="Launch in continuous voice interaction mode")
    parser.add_argument("--cli", action="store_true", help="Launch in text/interactive terminal mode")
    parser.add_argument("--test", action="store_true", help="Run self-test diagnostics on memory and components")
    parser.add_argument("--duration", type=float, default=5.0, help="Voice recording duration per turn in seconds")

    args = parser.parse_args()
    session = VoiceAgentSession()

    if args.voice:
        asyncio.run(run_voice_mode(session, duration=args.duration))
    elif args.test:
        asyncio.run(run_diagnostic_test(session))
    else:
        # Default to CLI interactive mode
        asyncio.run(run_cli_mode(session))


if __name__ == "__main__":
    main()
