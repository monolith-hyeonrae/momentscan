"""Layer 1 daemon — warm detect container + control plane.

A long-lived process that loads the detector ONCE (``warm_init``) and processes
clips on demand over a control socket. This is where "warm" stops being a
placeholder: the buffalo_l model is resident, so each triggered clip pays only
the ~seconds of actual work, not the model load.

Control plane is visualbus's ``ControlServer`` (UDS, JSON-lines RPC); the client
is the stock ``python -m visualbus.control`` CLI. One custom command:

    process  {path, fps?}  ->  detect result   (synchronous: runs the clip
                                                through the warm detector, writes
                                                detect.mp4 + detections.parquet)

The bus pump is single-threaded, so concurrent jobs are serialized under a lock
(which also serializes GPU access — the right thing once models are resident). A
ride-system "clip ready" trigger wires into this `process` command later; for
now a human or a directory watcher calls it.
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from pathlib import Path

from visualbus.control.server import ControlServer
from visualbus.structured_log import log_context

from momentscan.subjects.detect import DEFAULT_MODEL_ROOT, process_clip, warm_init

log = logging.getLogger("momentscan.daemon")

DEFAULT_SOCKET = Path.home() / ".cache" / "momentscan" / "daemon.sock"

# idle ≠ dead: triggers are event-driven, so the daemon is legitimately silent
# between jobs — the beat is the log-side proof of life during that silence.
HEARTBEAT_S = 30.0


def serve(
    *,
    socket_path: str | Path = DEFAULT_SOCKET,
    out_root: str | Path = "output",
    fps: int | None = None,
    model_root: str | Path = DEFAULT_MODEL_ROOT,
) -> int:
    """Run the daemon until SIGINT/SIGTERM or a ``shutdown`` command."""
    warm = warm_init(model_root=model_root)   # COLD: once.
    job_lock = threading.Lock()               # serialize the single-threaded bus pump
    stop_event = threading.Event()
    t0 = time.monotonic()
    jobs = {"done": 0, "failed": 0}           # mutated only under job_lock

    def _process(req: dict) -> dict:
        path = req.get("path")
        if not path:
            raise ValueError("process requires 'path'")
        job_fps = req.get("fps", fps)
        # Lifecycle: accept (now) → clip.open (job start, after lock) → clip.done.
        # Queue wait is the timestamp gap between accept and clip.open.
        log.info("job.accept", extra={"path": str(path), "busy": job_lock.locked()})
        with job_lock, log_context(job_id=Path(str(path)).stem):
            try:
                result = process_clip(warm, path, out_root, fps=job_fps)  # HOT: reuses warm model
            except Exception:
                jobs["failed"] += 1
                raise
            jobs["done" if result.get("ok") else "failed"] += 1
            return result

    def _shutdown(req: dict) -> dict:
        stop_event.set()
        return {"stopping": True}

    def _heartbeat() -> None:
        while not stop_event.wait(HEARTBEAT_S):
            log.info("daemon.heartbeat", extra={
                "uptime_s": round(time.monotonic() - t0, 1),
                "jobs_done": jobs["done"],
                "jobs_failed": jobs["failed"],
                "busy": job_lock.locked(),
            })

    server = ControlServer(warm.bus, socket_path=Path(socket_path).expanduser())
    server.register("process", _process)
    server.register("shutdown", _shutdown)
    server.start()
    threading.Thread(target=_heartbeat, name="ms-heartbeat", daemon=True).start()
    log.info("daemon.ready", extra={"socket": str(server.socket_path), "out_root": str(out_root)})

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop_event.set())

    try:
        stop_event.wait()
    finally:
        log.info("daemon.stopping")
        server.stop()
    return 0
