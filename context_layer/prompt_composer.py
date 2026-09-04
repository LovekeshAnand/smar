"""
context_layer/prompt_composer.py
================================
Dynamic Prompt Composer for SMAR.
Generates customized, edge-case resilient system prompts for any user and turn.
Guarantees strict identity disambiguation (Assistant != User), prevents hallucinations,
enforces concise voice-friendly responses, and incorporates multi-user RAG context.
"""

from typing import Dict, Any, List, Optional
from context_layer.config import ContextConfig


class PromptComposer:
    """
    Assembles contextual system prompts dynamically.
    Completely eliminates hardcoded user names and inflexible prompt templates.
    """

    def __init__(self, config: Optional[ContextConfig] = None):
        self.config = config or ContextConfig()

    def compose_system_prompt(
        self,
        retrieval_result: Dict[str, Any],
        language_hint: str = "en-IN",
        custom_instructions: Optional[str] = None
    ) -> str:
        """
        Builds a dynamic system prompt containing:
          1. Core Persona & Identity Isolation (Assistant vs User)
          2. Known User Profile (Name, Location, Profession)
          3. Retrieved Long-Term Knowledge Graph & Semantic Memory
          4. Operational Guardrails for Voice Interaction
        """
        user_id = retrieval_result.get("user_id", self.config.default_user_id)
        profile = retrieval_result.get("user_profile", {})
        user_name = profile.get("name") or user_id
        facts = retrieval_result.get("structured_facts", [])
        semantic = retrieval_result.get("semantic_memories", [])

        # Core identity section with strict boundary
        prompt_lines = [
            f"You are {self.config.assistant_name}, a memory-driven autonomous voice assistant.",
            f"You are conversing with {user_name} (User ID: {user_id}).",
            "",
            "=== CRITICAL IDENTITY PROTECTION ===",
            f"1. Your name is strictly {self.config.assistant_name}. You are the assistant.",
            f"2. You are NOT {user_name}. {user_name} is the human speaking to you.",
            f"3. NEVER introduce yourself as {user_name}. If asked 'Who are you?', answer: 'I am {self.config.assistant_name}'.",
            f"4. If {user_name} asks 'Who am I?' or 'What is my name?', answer using the user's name: '{user_name}'.",
            ""
        ]

        # Contextual Knowledge Section
        has_context = False
        context_lines = ["=== RECALLED MEMORY & USER CONTEXT ==="]

        # Profile attributes
        profile_items = []
        if profile.get("location"):
            profile_items.append(f"Location: {profile['location']}")
        if profile.get("profession"):
            profile_items.append(f"Profession: {profile['profession']}")
        if profile.get("email"):
            profile_items.append(f"Email: {profile['email']}")
        for p in profile.get("preferences", []):
            profile_items.append(p)

        if profile_items:
            context_lines.append("[User Profile]")
            for item in profile_items:
                context_lines.append(f"- {item}")
            has_context = True

        if facts:
            context_lines.append("[Verified Relational Facts]")
            for f in facts:
                context_lines.append(f"- {f}")
            has_context = True

        if semantic:
            context_lines.append("[Relevant Past Notes]")
            for s in semantic:
                context_lines.append(f"- {s}")
            has_context = True

        if has_context:
            context_lines.append("Use these recalled memories naturally without explicitly saying 'According to my database'.")
            context_lines.append("")
            prompt_lines.extend(context_lines)

        # Voice interaction rules & formatting
        prompt_lines.extend([
            "=== VOICE INTERACTION RULES ===",
            "- Keep responses concise, spoken, and conversational (1 to 3 sentences).",
            "- Do NOT use markdown tables, asterisks, bullet points, or complex formatting since responses are spoken aloud via TTS.",
            "- Match the language of the user: If the user speaks English, respond in clear English. If the user speaks Hindi, respond in Hindi.",
            "- If the user shares a new personal detail (e.g. city, job, preference), acknowledge it warmly."
        ])

        if custom_instructions:
            prompt_lines.extend([
                "",
                "=== CUSTOM INSTRUCTIONS ===",
                custom_instructions.strip()
            ])

        return "\n".join(prompt_lines)
