import os
import uuid
import threading
from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()
from job_queue import job_queue, job_status, job_results
from queue_worker import worker

app = Flask(__name__)

# Iniciar el worker en segundo plano al arrancar
threading.Thread(target=worker, daemon=True).start()


# ─── POST /transcribe ──────────────────────────────────────────────────────────
@app.route("/transcribe", methods=["POST"])
def enqueue_transcription():
    """
    Encola un trabajo de transcripción.

    Body JSON:
      {
        "video_url":   "https://...",   (requerido)
        "activity_id": "abc123"         (opcional, se devuelve en el resultado)
      }

    Respuesta 202:
      { "job_id": "...", "status": "enqueued" }
    """
    data = request.get_json(silent=True) or {}
    video_url = data.get("video_url")
    activity_id = data.get("activity_id")
    name_activity = data.get("name_activity")

    if not video_url:
        return jsonify({"error": "video_url es requerido"}), 400

    use_gpu = bool(data.get("use_gpu", False))
    generate_embeddings = bool(data.get("generate_embeddings", True))

    job_id = str(uuid.uuid4())
    job_status[job_id] = "enqueued"
    job_queue.put({
        "job_id": job_id,
        "video_url": video_url,
        "activity_id": activity_id,
        "name_activity": name_activity,
        "use_gpu": use_gpu,
        "generate_embeddings": generate_embeddings,
    })

    return jsonify({
        "job_id": job_id,
        "status": "enqueued",
        "activity_id": activity_id,
    }), 202


# ─── GET /transcribe/<job_id>/status ──────────────────────────────────────────
@app.route("/transcribe/<job_id>/status", methods=["GET"])
def get_status(job_id):
    """
    Devuelve el estado actual del job.

    Respuesta:
      { "job_id": "...", "status": "enqueued|processing|done|error" }
    """
    status = job_status.get(job_id)
    if status is None:
        return jsonify({"error": "job_id no encontrado"}), 404

    return jsonify({"job_id": job_id, "status": status})


# ─── GET /transcribe/<job_id>/result ──────────────────────────────────────────
@app.route("/transcribe/<job_id>/result", methods=["GET"])
def get_result(job_id):
    """
    Devuelve el resultado de la transcripción cuando el job está completo.

    Respuesta cuando status = done:
      {
        "job_id": "...",
        "status": "done",
        "segments": [
          { "startTime": 0.0, "endTime": 3.5, "text": "..." },
          ...
        ]
      }

    Respuesta cuando status = processing/enqueued:
      { "job_id": "...", "status": "processing" }   → HTTP 202

    Respuesta cuando status = error:
      { "job_id": "...", "status": "error", "error": "..." }   → HTTP 500
    """
    status = job_status.get(job_id)

    if status is None:
        return jsonify({"error": "job_id no encontrado"}), 404

    if status in ("enqueued", "processing"):
        return jsonify({"job_id": job_id, "status": status}), 202

    result = job_results.get(job_id, {})

    if status == "error":
        return jsonify({
            "job_id": job_id,
            "status": "error",
            "error": result.get("error", "Error desconocido"),
        }), 500

    # status == "done"
    return jsonify({
        "job_id": job_id,
        "status": "done",
        "activity_id": result.get("activity_id"),
        "name_activity": result.get("name_activity"),
        "segments": result.get("segments", []),
    }), 200


# ─── Healthcheck ───────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    for d in ["downloads", "samples"]:
        os.makedirs(os.path.join(os.path.dirname(__file__), d), exist_ok=True)

    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
