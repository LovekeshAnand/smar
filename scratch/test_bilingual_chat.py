import asyncio
import sys
from dotenv import load_dotenv
load_dotenv()

# Force utf-8 stdout
sys.stdout.reconfigure(encoding="utf-8")

from server import process_chat, ChatRequest

async def main():
    queries = [
        ("hamare db mai kitne stores present hai", "en-IN"),
        ("what tables are in the database", "en-IN"),
        ("डेटाबेस में कितने स्टोर्स हैं?", "hi-IN"),
        ("How many products do we have?", "en-IN"),
        ("hamare paas kitne products hain", "hi-IN")
    ]

    for q, lang in queries:
        print(f"\n==========================================")
        print(f"QUERY: {q} (hint: {lang})")
        resp = await process_chat(ChatRequest(text=q, language=lang, user_id="lovekesh"))
        print(f"REPLY: {resp.get('reply')}")
        print(f"INTENT: {resp.get('smart_data', {}).get('intent')}")
        print(f"HAS AUDIO: {bool(resp.get('audio_base64'))} (length: {len(resp.get('audio_base64') or '')})")
        print(f"TABLE DATA: {bool(resp.get('table_data'))}")

asyncio.run(main())
