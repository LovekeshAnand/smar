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
            "=== CRITICAL IDENTITY & MEMORY DIRECTIVES ===",
            f"1. Your name is strictly {self.config.assistant_name}. You are the assistant.",
            f"2. You are NOT {user_name}. The human speaking to you is {user_name}.",
            f"3. Only state 'My name is {self.config.assistant_name}' when the user EXPLICITLY asks for the ASSISTANT'S name",
            f"   (e.g. 'what is your name', 'who are you', 'what should I call you').",
            f"4. When the user says 'pronounce my name', 'say my name', 'what is my name', 'repeat my name',",
            f"   or any variation of 'MY name' — they are asking about THEIR OWN name, not yours.",
            f"   In those cases, respond with the USER'S name: '{user_name}'.",
            f"5. If the user corrects you with phrases like 'no my name not yours', 'I meant my name',",
            f"   'not your name, my name' — immediately acknowledge and say the USER'S name: '{user_name}'.",
            f"6. If {user_name} asks 'Who am I?' or 'What is my name?', answer: '{user_name}'.",
            f"7. If asked about earlier questions or what was asked before, refer directly to the [Conversation Session History] below.",
            f"8. NEVER state 'As an AI assistant, I don't have access to personal details or previous conversations' - you have full persistent memory of this user!",
            f"9. If {user_name} asks 'Do you have any information about me?' or 'What do you know about me?', explicitly and warmly list what you know from [User Profile] and [Verified Relational Facts] below.",
            ""
        ]

        # Contextual Knowledge Section
        has_context = False
        context_lines = ["=== RECALLED MEMORY & USER CONTEXT ==="]

        # Session Conversation History (for recall questions)
        session_hist = retrieval_result.get("session_history", {})
        if session_hist:
            context_lines.append("[Conversation Session History]")
            if session_hist.get("first_question"):
                context_lines.append(f"- 1st Question Asked By User: \"{session_hist['first_question']}\"")
            if session_hist.get("all_questions"):
                q_list = session_hist["all_questions"]
                context_lines.append("- Chronological User Questions in this Session:")
                for idx, q_text in enumerate(q_list[:6], 1):
                    context_lines.append(f"  {idx}. \"{q_text}\"")
            has_context = True

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
