import os
import google.generativeai as genai

_MODEL = "models/gemini-embedding-001"
_TASK_TYPE = "RETRIEVAL_DOCUMENT"
_BATCH_SIZE = 100  # límite seguro por llamada a la API


def _client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no está configurado")
    genai.configure(api_key=api_key)


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Genera embeddings para una lista de textos usando gemini-embedding-001.
    Procesa en batches para respetar los límites de la API.
    Retorna una lista de vectores en el mismo orden que la entrada.
    """
    _client()
    embeddings = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        result = genai.embed_content(
            model=_MODEL,
            content=batch,
            task_type=_TASK_TYPE,
        )
        # embed_content retorna {"embedding": [...]} para un texto
        # o {"embedding": [[...], [...]]} para una lista
        raw = result["embedding"]
        if batch and isinstance(raw[0], float):
            # Caso un solo texto devuelto como vector plano
            embeddings.append(raw)
        else:
            embeddings.extend(raw)

        print(f"[EMBEDDER] Batch {i // _BATCH_SIZE + 1}: {len(batch)} embeddings generados.")

    return embeddings
