"""Runs analysis jobs one at a time in a background thread."""
import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from server.engine import pipeline
from server.engine.ingest import IngestError
from server.store import Store

log = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, store: Store, work_root: Path, analyze_fn=pipeline.analyze, keep_audio: bool = False):
        self._store = store
        self._work_root = Path(work_root)
        self._analyze = analyze_fn
        self._keep_audio = keep_audio
        self._cancel_flags: dict[str, threading.Event] = {}
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chordarium-job")

    def submit(self, video_id: str, mode: str) -> str:
        job_id = self._store.create_job(video_id, mode)
        self._cancel_flags[job_id] = threading.Event()
        self._pool.submit(self._run, job_id, video_id, mode)
        return job_id

    def cancel(self, job_id: str) -> bool:
        flag = self._cancel_flags.get(job_id)
        if flag is None:
            return False
        flag.set()
        job = self._store.get_job(job_id)
        if job and job["state"] == "queued":
            self._store.update_job(job_id, state="cancelled", message="Cancelled")
        return True

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)

    def _run(self, job_id: str, video_id: str, mode: str) -> None:
        flag = self._cancel_flags[job_id]
        work_dir = self._work_root / video_id

        def progress(state: str, percent: int, message: str) -> None:
            if flag.is_set():
                raise pipeline.Cancelled()
            self._store.update_job(job_id, state=state, progress=percent, message=message)

        try:
            if flag.is_set():
                raise pipeline.Cancelled()
            timeline = self._analyze(video_id, work_dir, pipeline.Options(mode=mode), progress)
            if flag.is_set():
                raise pipeline.Cancelled()
            song_id = self._store.save_song(timeline)
            self._store.update_job(job_id, state="done", progress=100, message="Done", song_id=song_id)
        except pipeline.Cancelled:
            self._store.update_job(job_id, state="cancelled", message="Cancelled")
        except IngestError as e:
            self._store.update_job(job_id, state="failed", error=str(e), message="Failed")
        except Exception as e:
            log.exception("Job %s failed", job_id)
            self._store.update_job(job_id, state="failed", error=f"Analysis failed: {e}", message="Failed")
        finally:
            self._cancel_flags.pop(job_id, None)
            if not self._keep_audio:
                shutil.rmtree(work_dir, ignore_errors=True)
