import subprocess
import json
import os
import uuid


def download_video(video_url: str, output_dir: str = "./downloads") -> str:
    """
    Descarga un video desde una URL (Vimeo, YouTube, etc.) usando yt-dlp
    y retorna la ruta local del archivo descargado.
    """
    os.makedirs(output_dir, exist_ok=True)
    video_id = str(uuid.uuid4())
    output_path = os.path.join(output_dir, f"{video_id}.mp4")

    command = ["yt-dlp", "-o", output_path, video_url]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        print("[ERROR] yt-dlp falló:")
        print(result.stderr)
        raise RuntimeError(f"No se pudo descargar el video: {result.stderr[:500]}")

    return output_path


def time_to_seconds(t: str) -> float:
    """
    Convierte timestamp tipo 'HH:MM:SS,mmm' a segundos float.
    """
    try:
        t = t.replace(",", ".")
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return 0.0


def _use_wsl() -> bool:
    """Detecta si WSL está disponible en el sistema."""
    import shutil
    return shutil.which("wsl") is not None


def _to_wsl_path(path: str) -> str:
    """Convierte una ruta de Windows (D:\\foo\\bar) al formato WSL (/mnt/d/foo/bar)."""
    path = path.replace("\\", "/")
    if len(path) >= 2 and path[1] == ":":
        path = "/mnt/" + path[0].lower() + path[2:]
    return path


def _to_git_bash_path(path: str) -> str:
    """Convierte una ruta de Windows (D:\\foo\\bar) al formato Git Bash (/d/foo/bar)."""
    path = path.replace("\\", "/")
    if len(path) >= 2 and path[1] == ":":
        path = "/" + path[0].lower() + path[2:]
    return path


def run_transcription(video_path: str, use_gpu: bool = False) -> list[dict]:
    """
    Ejecuta el script de transcripción y devuelve los segmentos estructurados.
    Cada segmento tiene: startTime, endTime (floats en segundos) y text (str).
    Usa WSL si está disponible (necesario para binarios ELF de Linux),
    de lo contrario usa Git Bash (requiere binario nativo Windows).
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "transcribir.sh")

    env = os.environ.copy()
    env["USE_GPU"] = "1" if use_gpu else "0"

    if _use_wsl():
        print("[INFO] Usando WSL para ejecutar transcribir.sh")
        command = [
            "wsl", "bash",
            _to_wsl_path(script_path),
            _to_wsl_path(video_path),
        ]
    else:
        print("[INFO] Usando Git Bash para ejecutar transcribir.sh")
        git_usr_bin = r"C:\Program Files\Git\usr\bin"
        git_bin = r"C:\Program Files\Git\bin"
        env["PATH"] = git_usr_bin + os.pathsep + git_bin + os.pathsep + env.get("PATH", "")
        bash = next(
            (p for p in [
                r"C:\Program Files\Git\usr\bin\bash.exe",
                r"C:\Program Files (x86)\Git\usr\bin\bash.exe",
            ] if os.path.exists(p)),
            "bash",
        )
        command = [bash, _to_git_bash_path(script_path), _to_git_bash_path(video_path)]

    print(f"[INFO] Ejecutando: {' '.join(command)}")

    result = subprocess.run(command, capture_output=True, text=True, env=env)

    if result.returncode != 0:
        print("[ERROR] El script de transcripción falló")
        print("[STDOUT]", result.stdout[:1000])
        print("[STDERR]", result.stderr[:1000])
        raise RuntimeError("Transcripción fallida. Ver logs para detalles.")

    stdout = result.stdout.strip()

    if not stdout.startswith("{"):
        print("[ERROR] Salida no es JSON válido.")
        print("Raw output:", stdout[:500])
        raise RuntimeError("Salida inválida del script de transcripción.")

    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as e:
        print("[ERROR] No se pudo parsear el JSON de salida.")
        print("Raw output:", stdout[:1000])
        raise RuntimeError(f"Error parseando JSON: {str(e)}")

    segments_raw = output.get("segments", [])
    segments = []

    for s in segments_raw:
        from_time = s.get("timestamps", {}).get("from")
        to_time = s.get("timestamps", {}).get("to")

        segments.append({
            "startTime": time_to_seconds(from_time),
            "endTime": time_to_seconds(to_time),
            "text": s.get("text", "").strip(),
        })

    print(f"[INFO] Transcripción completada: {len(segments)} segmentos.")
    return segments
