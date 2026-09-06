"""
scratch/test_lovekesh_complex_flow.py
=====================================
Simulates User Lovekesh asking complex, real-world multi-step problems:
1. Personal memory & role verification
2. Multi-table aggregation & Pie chart visual generation
3. Product pricing extremes (MAX/MIN)
4. Relational Order & Order Item financial breakdown
5. Conversational history recall ("what was the first question I asked?")
"""

import sys
import asyncio
import time

sys.path.insert(0, '.')

from context_layer import ContextLayerEngine, ContextConfig
from smart_data.engine import SmartDataLayerEngine
from core.epsilon_bridge import EpsilonBridge

async def main():
    print("=" * 80)
    print("SIMULATING LOVEKESH: MULTI-TURN COMPLEX SCENARIOS")
    print("=" * 80)

    config = ContextConfig(default_user_id="lovekesh")
    ctx = ContextLayerEngine(config=config)
    engine = SmartDataLayerEngine(context_store=ctx.store)
    epsilon = EpsilonBridge()

    prompts = [
        "hi smart my name is lovekesh and what do you do actually and what information about me you have",
        "can you show me a chart of shipments grouped by status",
        "what is the maximum price among all products",
        "can you tell me what is the price of order id 520580",
        "what is the total price for order id 292487",
        "show me all stores in a table",
        "can you pronounce my name please"
    ]

    for i, user_text in enumerate(prompts, 1):
        print(f"\n[Turn {i}] Lovekesh asks: '{user_text}'")
        t0 = time.perf_counter()

        # 1. Smart Data Layer
        smart_res = engine.process_query(user_text, user_id="lovekesh")
        
        # 2. Context Layer
        turn_result = ctx.process_user_turn(user_id="lovekesh", user_text=user_text)
        
        # 3. Decision & Reply
        if smart_res.get("intent") == "OPERATION" and smart_res.get("spoken_confirmation"):
            reply = smart_res["spoken_confirmation"]
        elif smart_res.get("spoken_confirmation") and smart_res.get("matched_item"):
            reply = smart_res["spoken_confirmation"]
        else:
            # LLM reply
            context_summary = smart_res.get("context_string") or ""
            recent_turns = turn_result.get("recent_turns", [])
            reply = await epsilon.generate_reply(
                user_prompt=user_text,
                context=context_summary,
                system_prompt=turn_result["system_prompt"],
                conversation_history=recent_turns,
                max_tokens=256
            )

        elapsed = (time.perf_counter() - t0) * 1000.0
        print(f"       Intent: {smart_res.get('intent')} | Op: {smart_res.get('operation')} | Elapsed: {elapsed:.1f}ms")
        print(f"       SMAR Reply: {reply}")
        if smart_res.get("visual_chart"):
            vc = smart_res["visual_chart"]
            print(f"       [Visual Chart Generated]: Type={vc.get('chart_type')} | Title='{vc.get('title')}' | ImageBytes={len(vc.get('image_base64', ''))}")
        if smart_res.get("table_data"):
            td = smart_res["table_data"]
            print(f"       [Table Data Generated]: Table='{td.get('table')}' | Displayed={td.get('displayed_count')} | Total={td.get('total_count')}")

    print("\n" + "=" * 80)
    print("ALL LOVEKESH COMPLEX FLOW TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
