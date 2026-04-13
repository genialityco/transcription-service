import queue

# Cola de trabajos pendientes
job_queue = queue.Queue()

# Estado por job_id: "enqueued" | "processing" | "done" | "error"
job_status: dict[str, str] = {}

# Resultado por job_id: lista de segmentos o mensaje de error
job_results: dict[str, dict] = {}
