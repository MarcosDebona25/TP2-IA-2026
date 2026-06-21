# tools/rag_tools.py
#
# Expone las funciones del retriever como tools de LangChain para que el
# Agente Clínico (C) las pueda invocar dentro de su loop ReAct.
#
# El Agente Clínico llama search_clinical_guidelines_tool cuando necesita
# contextualizar un hallazgo del Monitor con evidencia de las guías ADA/SAD/MSAL.
#
# Parámetros tunables documentados en rag/RAG_TUNING.md → sección "LangChain Tools".

from langchain_core.tools import tool

from rag.retriever import get_rag_fragment, search_clinical_guidelines


@tool
def search_clinical_guidelines_tool(query: str) -> list[str]:
    """
    Busca en las guías clínicas (ADA, SAD, MSAL) los fragmentos más relevantes
    para la consulta dada. Usar cuando se necesite evidencia clínica para
    interpretar una alerta o métrica fuera de rango.

    Devuelve una lista de fragmentos de texto de las guías.

    Ejemplos de queries efectivas:
      - "manejo hipoglucemia nivel 1 diabetes tipo 2"
      - "objetivo HbA1c paciente adulto mayor"
      - "ajuste metformina insuficiencia renal"
    """
    # TUNABLE: k define cuántos fragmentos se recuperan. Ver RAG_TUNING.md → "k (top-k)".
    # Acá se puede pasar k=5 para consultas amplias o k=2 para consultas muy específicas.
    return search_clinical_guidelines(query, k=3)


@tool
def get_rag_context_tool(query: str) -> str:
    """
    Igual que search_clinical_guidelines_tool pero devuelve un único string
    formateado y listo para incluir directamente en el prompt del Agente Clínico.

    Preferir esta tool cuando el agente va a usar el contexto en una sola
    llamada al LLM (evita que el agente tenga que unir la lista manualmente).
    """
    # TUNABLE: k define cuántos fragmentos se recuperan. Ver RAG_TUNING.md → "k (top-k)".
    return get_rag_fragment(query, k=3)
