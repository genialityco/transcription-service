import os
import threading
from job_queue import job_queue, job_status, job_results
from transcriber import download_video, run_transcription
from embedder import generate_embeddings

_lock = threading.Lock()


def worker():
    while True:
        job = job_queue.get()
        job_id = job["job_id"]
        video_url = job["video_url"]
        activity_id = job.get("activity_id")
        name_activity = job.get("name_activity")
        use_gpu = job.get("use_gpu", False)
        should_embed = job.get("generate_embeddings", True)

        try:
            with _lock:
                job_status[job_id] = "processing"

            print(f"[WORKER] Procesando job {job_id} — url: {video_url}")

            downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
            video_path = download_video(video_url, output_dir=downloads_dir)
            segments = run_transcription(video_path, use_gpu=use_gpu)

            if should_embed:
                print(f"[WORKER] Generando embeddings para {len(segments)} segmentos...")
                texts = [seg["text"] for seg in segments]
                embeddings = generate_embeddings(texts)
                for seg, emb in zip(segments, embeddings):
                    seg["embedding"] = emb
            else:
                print(f"[WORKER] Embeddings omitidos por solicitud.")

            with _lock:
                job_results[job_id] = {
                    "activity_id": activity_id,
                    "name_activity": name_activity,
                    "segments": segments,
                }
                job_status[job_id] = "done"

            print(f"[WORKER] Job {job_id} completado con {len(segments)} segmentos y embeddings.")

        except Exception as e:
            print(f"[WORKER] Job {job_id} falló: {str(e)}")
            with _lock:
                job_results[job_id] = {"error": str(e)}
                job_status[job_id] = "error"

        finally:
            job_queue.task_done()
