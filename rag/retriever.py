# rag/retriever.py
#
# Etapa 2 del pipeline RAG: dado un texto de consulta, busca en ChromaDB los
# fragmentos de guías clínicas más relevantes y los devuelve listos para inyectar
# en el prompt del Agente Clínico.
#
# Parámetros tunables documentados en rag/RAG_TUNING.md → sección "Retrieval".

from pathlib import Path

import logging

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

# ── Debe coincidir exactamente con los valores usados en ingest.py ─────────────
# Si cambiás EMBEDDING_MODEL o COLLECTION_NAME en ingest.py, cambiálos acá también.
CHROMA_DIR = Path(__file__).resolve().parent.parent / "data" / "chroma_db"
COLLECTION_NAME = "guias_clinicas"
EMBEDDING_MODEL = "nomic-embed-text"
OLLAMA_URL = "http://localhost:11434"

# TUNABLE: cuántos fragmentos devolver por consulta. Ver RAG_TUNING.md → "k (top-k)".
DEFAULT_K = 3

logger = logging.getLogger(__name__)


def _get_collection() -> chromadb.Collection:
    """Abre la colección ChromaDB persistida. Lanza error si no fue ingestada antes."""
    if not CHROMA_DIR.exists():
        raise RuntimeError(
            "ChromaDB no encontrada. Ejecutá primero: uv run python rag/ingest.py"
        )
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embedding_fn = OllamaEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
        url=OLLAMA_URL,
    )
    return client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)


def search_clinical_guidelines(query: str, k: int = DEFAULT_K) -> list[str]:
    """
    Busca en ChromaDB los `k` fragmentos de guías clínicas más relevantes para `query`.

    Devuelve una lista de strings (los fragmentos), ordenados de mayor a menor
    similitud. Lista vacía si la colección está vacía, no hay resultados, o si
    la infraestructura (Ollama/ChromaDB) no está disponible.

    Parámetro tunable principal: `k`. Ver RAG_TUNING.md → "k (top-k)".
    """
    try:
        col = _get_collection()
        results = col.query(
            query_texts=[query],
            n_results=k,
            # TUNABLE: qué campos incluir en la respuesta. "documents" son los textos;
            # "metadatas" incluye la fuente (nombre del archivo) y el chunk_index.
            # Agregar "distances" si querés filtrar por score mínimo (ver RAG_TUNING.md).
            include=["documents", "metadatas", "distances"],
        )

        documents = results["documents"][0] if results["documents"] else []
        distances = results["distances"][0] if results["distances"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []

        # TUNABLE: umbral de distancia coseno. Con "cosine" en ChromaDB, la distancia
        # devuelta es 1 - similitud (0 = idéntico, 2 = opuesto). Filtrar por < 0.5
        # descarta fragmentos poco relevantes. Ver RAG_TUNING.md → "Umbral de distancia".
        DISTANCE_THRESHOLD = 1.0  # 1.0 = sin filtro (acepta todo); bajar para ser más estricto

        filtered = []
        for doc, dist, meta in zip(documents, distances, metadatas):
            if dist < DISTANCE_THRESHOLD:
                source = meta.get("source", "Guía Desconocida")
                filtered.append(f"[{source}] {doc}")

        return filtered
    except Exception as e:
        logger.warning("RAG no disponible (Ollama/ChromaDB no accesibles): %s", e)
        return []


def get_rag_fragment(query: str, k: int = DEFAULT_K) -> str:
    """
    Versión formateada de search_clinical_guidelines: devuelve un único string
    listo para inyectar en el prompt del Agente Clínico.

    Formato:
        [Fragmento 1]
        <texto>

        [Fragmento 2]
        <texto>
        ...
    """
    fragments = search_clinical_guidelines(query, k=k)
    if not fragments:
        return "No se encontraron fragmentos relevantes en las guías clínicas."

    parts = [f"[Fragmento {i + 1}]\n{frag}" for i, frag in enumerate(fragments)]
    return "\n\n".join(parts)


if __name__ == "__main__":
    # Prueba rápida del retriever. Ajustar la query para evaluar calidad.
    # Ver rag/RAG_TUNING.md para saber qué parámetros tocar.
    TEST_QUERY = "manejo hipoglucemia nivel 1 diabetes tipo 2"
    print(f"Query: {TEST_QUERY}\n")
    print(get_rag_fragment(TEST_QUERY))

