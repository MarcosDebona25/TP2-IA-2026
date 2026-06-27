# agents/llm_factory.py
#
# Factory de LLM intercambiable vía variable de entorno LLM_PROVIDER.
# Valores soportados: "groq" (default) | "gemini"
#
# Variables de entorno requeridas por proveedor:
#   groq   → GROQ_API_KEY  + LLM_MODEL (default: qwen/qwen3-32b)
#   gemini → GOOGLE_API_KEY + LLM_MODEL (default: gemma-4-31b-it)

import os
from typing import Any

_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

_API_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


def build_llm(tools: list[Any] | None = None):
    """Construye el LLM configurado según LLM_PROVIDER y le bindea las tools dadas."""
    if _PROVIDER == "gemini":
        return _build_gemini(tools)
    return _build_groq(tools)


def has_api_key() -> bool:
    """Devuelve True si la API key del proveedor activo está configurada."""
    env_var = _API_KEY_ENV.get(_PROVIDER, "GROQ_API_KEY")
    return bool(os.environ.get(env_var))


def extract_content(response) -> str:
    """Extrae el texto de un AIMessage independientemente del proveedor.

    Groq devuelve response.content como str; Gemini como list[dict].
    """
    content = response.content or ""
    if isinstance(content, list):
        return "".join(
            p.get("text", "") if isinstance(p, dict) else str(p)
            for p in content
        )
    return content


def _build_groq(tools):
    from langchain_groq import ChatGroq

    model = os.getenv("LLM_MODEL", "qwen/qwen3-32b")
    llm = ChatGroq(model=model, temperature=0)
    return llm.bind_tools(tools) if tools else llm


def _build_gemini(tools):
    from langchain_google_genai import ChatGoogleGenerativeAI

    model = os.getenv("LLM_MODEL", "gemma-4-31b-it")
    llm = ChatGoogleGenerativeAI(model=model, temperature=0)
    return llm.bind_tools(tools) if tools else llm
