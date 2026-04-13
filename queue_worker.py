import os
import threading
from job_queue import job_queue, job_status, job_results
from transcriber import download_video, run_transcription

_lock = threading.Lock()


def worker():
    while True:
        job = job_queue.get()
        job_id = job["job_id"]
        video_url = job["video_url"]

        try:
            with _lock:
                job_status[job_id] = "processing"

            print(f"[WORKER] Procesando job {job_id} — url: {video_url}")

            downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
            video_path = download_video(video_url, output_dir=downloads_dir)
            segments = run_transcription(video_path)

            with _lock:
                job_results[job_id] = {"segments": segments}
                job_status[job_id] = "done"

            print(f"[WORKER] Job {job_id} completado con {len(segments)} segmentos.")

        except Exception as e:
            print(f"[WORKER] Job {job_id} falló: {str(e)}")
            with _lock:
                job_results[job_id] = {"error": str(e)}
                job_status[job_id] = "error"

        finally:
            job_queue.task_done()
