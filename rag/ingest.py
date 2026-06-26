# rag/ingest.py
#
# Etapa 1 del pipeline RAG: lee las guías clínicas en Markdown, las divide en
# chunks, genera embeddings con nomic-embed-text (Ollama) y los indexa en ChromaDB.
#
# Ejecutar una sola vez (o cada vez que cambian las guías):
#   uv run python rag/ingest.py
#
# ══════════════════════════════════════════════════════════════
#  PARÁMETROS TUNABLES — afectan directamente la calidad del RAG
# ══════════════════════════════════════════════════════════════

from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

# ── Fuente ────────────────────────────────────────────────────
GUIAS_DIR = Path(__file__).resolve().parent.parent / "data" / "guias"

# ── ChromaDB ──────────────────────────────────────────────────
CHROMA_DIR = Path(__file__).resolve().parent.parent / "data" / "chroma_db"
COLLECTION_NAME = "guias_clinicas"

# ── Modelo de embeddings ───────────────────────────────────────
# TUNABLE: cambiar el modelo cambia la dimensión del vector y la calidad semántica.
# Opciones probadas con Ollama: "nomic-embed-text" (768d), "mxbai-embed-large" (1024d).
# Si cambiás esto, borrá data/chroma_db/ y re-ingestás (los vectores son incompatibles).
EMBEDDING_MODEL = "nomic-embed-text"
OLLAMA_URL = "http://localhost:11434"

# ── Chunking ───────────────────────────────────────────────────
# TUNABLE: chunk_size controla cuánto texto entra en cada fragmento.
#   - Más grande (1000+): más contexto por chunk, pero el embedding "diluye" el tema.
#   - Más chico (200-300): embeddings más precisos, pero puede partir conceptos.
#   Recomendado para guías médicas densas: 400-600.
CHUNK_SIZE = 500

# TUNABLE: overlap es cuántos caracteres se repiten entre chunks consecutivos.
#   - Más overlap: menos riesgo de partir definiciones, pero más redundancia en el índice.
#   - Regla práctica: 10-20% del chunk_size.
CHUNK_OVERLAP = 50

# ── Separadores de chunk ───────────────────────────────────────
# TUNABLE: el chunker intenta cortar en estos separadores (en orden de preferencia).
# Para Markdown, priorizar títulos y párrafos antes que cortar en medio de una oración.
# Agregar "\n## " o "\n### " si las guías tienen secciones bien marcadas.
SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", ". ", " "]


# ──────────────────────────────────────────────────────────────
# Implementación
# ──────────────────────────────────────────────────────────────

def load_markdown_files(guias_dir: Path) -> list[dict]:
    """Lee todos los .md de guias_dir. Devuelve lista de {source, text}."""
    docs = []
    for path in sorted(guias_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            docs.append({"source": path.name, "text": text})
            print(f"  Cargado: {path.name} ({len(text):,} caracteres)")
    return docs


def split_text(text: str) -> list[str]:
    """
    Divide text en chunks respetando los SEPARATORS (en orden de preferencia).
    Garantiza que ningún chunk supere CHUNK_SIZE y que haya CHUNK_OVERLAP de solapamiento.
    """
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + CHUNK_SIZE, text_len)

        # Si no llegamos al final, retrocedemos hasta el mejor separador disponible
        if end < text_len:
            cut = end
            for sep in SEPARATORS:
                pos = text.rfind(sep, start, end)
                if pos != -1:
                    cut = pos + len(sep)
                    break
            end = cut

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # El siguiente chunk empieza CHUNK_OVERLAP caracteres antes del corte
        start = max(start + 1, end - CHUNK_OVERLAP)

    return chunks


def build_collection(docs: list[dict], collection: chromadb.Collection) -> int:
    """Chunkea los documentos y los agrega a la colección ChromaDB. Devuelve total de chunks."""
    total = 0
    for doc in docs:
        chunks = split_text(doc["text"])
        batch_size = 50
        for idx in range(0, len(chunks), batch_size):
            batch_chunks = chunks[idx : idx + batch_size]
            batch_ids = [f"{doc['source']}::chunk{i}" for i in range(idx, min(idx + batch_size, len(chunks)))]
            batch_metadatas = [{"source": doc["source"], "chunk_index": i} for i in range(idx, min(idx + batch_size, len(chunks)))]
            collection.add(
                ids=batch_ids,
                documents=batch_chunks,
                metadatas=batch_metadatas,
            )
        print(f"  {doc['source']}: {len(chunks)} chunks indexados")
        total += len(chunks)
    return total


def ingest() -> None:
    print(f"Modelo de embeddings : {EMBEDDING_MODEL}")
    print(f"Chunk size / overlap : {CHUNK_SIZE} / {CHUNK_OVERLAP}")
    print(f"Guías desde          : {GUIAS_DIR}")
    print(f"ChromaDB en          : {CHROMA_DIR}\n")

    docs = load_markdown_files(GUIAS_DIR)
    if not docs:
        print("No se encontraron archivos .md en data/guias/. Abortando.")
        return

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    embedding_fn = OllamaEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
        url=OLLAMA_URL,
    )

    # get_or_create: idempotente; si ya existe la colección, la reutiliza.
    # Para re-indexar desde cero: borrar data/chroma_db/ y volver a correr.
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        # TUNABLE: función de distancia entre vectores.
        # "cosine" es la más común para similitud semántica de texto.
        # Otras opciones: "l2" (distancia euclidiana), "ip" (inner product).
        metadata={"hnsw:space": "cosine"},
    )

    print("Indexando chunks...\n")
    total = build_collection(docs, collection)
    print(f"\nTotal chunks en la colección: {total}")
    print("Ingestión completada.")


if __name__ == "__main__":
    ingest()
