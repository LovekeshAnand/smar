"""
core/epsilon_bridge.py
======================
Unified bridge to Epsilon Engine v2 for SMAR.

Provides an async, high-level API to interact with the local Epsilon LLM
tiers (Fast, Balanced, Deep), supporting prompt formatting, context injection,
and seamless communication with llama-server / local inference instances.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional, Dict, Any, AsyncGenerator
import httpx
import yaml

logger = logging.getLogger("smar.core.epsilon")

# ChatML Tokens for Qwen / Epsilon
CHATML_SYSTEM = "<|im_start|>system\n{system_content}<|im_end|>\n"
CHATML_USER   = "<|im_start|>user\n{user_content}<|im_end|>\n"
CHATML_ASST   = "<|im_start|>assistant\n"
STOP_TOKENS   = ["<|im_end|>", "<|endoftext|>", "User:", "\n\nUser"]

DEFAULT_SYSTEM_PROMPT = (
    "You are SMAR, an intelligent, polite, and friendly voice-first personal assistant. "
    "You speak fluently in Hindi, English, and Hinglish. Always match the language and tone of the user. "
    "If the user speaks Hindi or asks in Hindi, reply in natural, grammatically correct Hindi. "
    "If the user speaks English, reply in English. "
    "Keep answers concise, direct, and conversational (1-3 sentences) so they sound natural when read aloud. "
    "Ground your responses in the provided persistent memory context. "
    "Do not repeat words or phrases in a loop, and do not invent fake facts."
)


class EpsilonBridge:
    def __init__(self, config_path: Optional[str] = None):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if config_path is None:
            config_path = os.path.join(self.base_dir, "core", "config.yaml")
        
        self.config_path = config_path
        self.config = self._load_config()
        
        self.server_host = os.getenv("EPSILON_HOST", self.config.get("server_host", "127.0.0.1"))
        self.server_port = int(os.getenv("EPSILON_PORT", self.config.get("server_port", 8088)))
        self.active_tier = os.getenv("EPSILON_TIER", "fast")
        
        # Tier ports configuration
        self.tier_ports = {
            "fast": 8088,
            "balanced": 8089,
            "deep": 8090,
        }

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Could not load Epsilon config from {self.config_path}: {e}")
        return {}

    def format_prompt(self, user_prompt: str, context: Optional[str] = None, system_prompt: Optional[str] = None) -> str:
        """Wraps conversation and memory context in ChatML template."""
        sys_text = system_prompt or DEFAULT_SYSTEM_PROMPT
        if context:
            sys_text += f"\n\n[Persistent Memory Context]:\n{context}\n[End Context]"
        
        formatted = (
            CHATML_SYSTEM.format(system_content=sys_text.strip()) +
            CHATML_USER.format(user_content=user_prompt.strip()) +
            CHATML_ASST
        )
        return formatted

    @property
    def api_base(self) -> str:
        port = self.tier_ports.get(self.active_tier, self.server_port)
        return f"http://{self.server_host}:{port}"

    async def check_health(self) -> bool:
        """Alias for is_server_healthy."""
        return await self.is_server_healthy()

    async def is_server_healthy(self, port: Optional[int] = None) -> bool:
        """Check if llama-server / inference endpoint is listening and healthy."""
        p = port or self.tier_ports.get(self.active_tier, self.server_port)
        url = f"http://{self.server_host}:{p}/health"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(url)
                return r.status_code == 200
        except Exception:
            return False

    async def generate_reply(
        self,
        user_prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 256,
        temperature: float = 0.2
    ) -> str:
        """Convenience alias for generate()."""
        return await self.generate(
            prompt=user_prompt,
            context=context,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

    async def generate(

        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tier: Optional[str] = None,
        max_tokens: int = 256,
        temperature: float = 0.2,
    ) -> str:
        """
        Sends the prompt with memory context to Epsilon LLM and returns the generated text.
        """
        chosen_tier = tier or self.active_tier
        port = self.tier_ports.get(chosen_tier, self.server_port)
        formatted_prompt = self.format_prompt(prompt, context=context, system_prompt=system_prompt)
        
        url = f"http://{self.server_host}:{port}/completion"
        payload = {
            "prompt": formatted_prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "repeat_penalty": 1.15,
            "repeat_last_n": 64,
            "top_k": 40,
            "top_p": 0.9,
            "stop": STOP_TOKENS,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("content", "").strip()
                    return content
                else:
                    logger.error(f"Epsilon server returned HTTP {resp.status_code}: {resp.text}")
                    return f"Error: Epsilon engine returned HTTP status {resp.status_code}."
        except httpx.ConnectError:
            logger.warning(f"Could not connect to Epsilon server on {url}. Is llama-server running?")
            # Return a graceful fallback response indicating server state
            return (
                f"[Epsilon Local Engine Offline] I heard you say: '{prompt}'. "
                f"Please ensure Epsilon llama-server is active on port {port}."
            )
        except Exception as e:
            logger.error(f"Epsilon generation error: {e}")
            return f"Error during generation: {e}"

    async def generate_stream(
        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tier: Optional[str] = None,
        max_tokens: int = 256,
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        """
        Streams generated tokens token-by-token.
        """
        chosen_tier = tier or self.active_tier
        port = self.tier_ports.get(chosen_tier, self.server_port)
        formatted_prompt = self.format_prompt(prompt, context=context, system_prompt=system_prompt)
        
        url = f"http://{self.server_host}:{port}/completion"
        payload = {
            "prompt": formatted_prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "repeat_penalty": 1.15,
            "repeat_last_n": 64,
            "top_k": 40,
            "top_p": 0.9,
            "stop": STOP_TOKENS,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw_chunk = line[6:].strip()
                        if raw_chunk == "[DONE]":
                            break
                        try:
                            token_data = json.loads(raw_chunk)
                            token = token_data.get("content", "")
                            if token:
                                yield token
                        except Exception:
                            continue
        except Exception as e:
            logger.error(f"Streaming error from Epsilon: {e}")
            yield f"[Generation error: {e}]"
