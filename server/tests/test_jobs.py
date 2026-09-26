import threading

from server.engine.ingest import IngestError
from server.jobs import JobRunner
from server.store import Store


def make(tmp_path, analyze_fn, keep_audio=False):
    store = Store(tmp_path / "db.sqlite")
    return store, JobRunner(store, tmp_path / "audio", analyze_fn=analyze_fn, keep_audio=keep_audio)


def test_successful_job_saves_song_and_cleans_audio(tmp_path, timeline):
    def analyze(video_id, work_dir, options, progress):
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "audio.wav").write_bytes(b"x")
        assert options.mode == "accurate"
        progress("chords", 60, "Recognizing chords")
        return timeline

    store, runner = make(tmp_path, analyze)
    job_id = runner.submit("abcdefghijk", "accurate")
    runner.shutdown(wait=True)
    job = store.get_job(job_id)
    assert job["state"] == "done" and job["progress"] == 100
    assert store.get_song(job["song_id"])["title"] == "Test Song"
    assert not (tmp_path / "audio" / "abcdefghijk").exists()


def test_ingest_error_message_reaches_job(tmp_path):
    def analyze(*a):
        raise IngestError("This video is private.")

    store, runner = make(tmp_path, analyze)
    job_id = runner.submit("abcdefghijk", "fast")
    runner.shutdown(wait=True)
    job = store.get_job(job_id)
    assert (job["state"], job["error"]) == ("failed", "This video is private.")


def test_unexpected_error_is_wrapped(tmp_path):
    def analyze(*a):
        raise RuntimeError("kaboom")

    store, runner = make(tmp_path, analyze)
    job_id = runner.submit("abcdefghijk", "fast")
    runner.shutdown(wait=True)
    assert store.get_job(job_id)["error"] == "Analysis failed: kaboom"


def test_cancel_running_job(tmp_path, timeline):
    started, release = threading.Event(), threading.Event()

    def analyze(video_id, work_dir, options, progress):
        started.set()
        release.wait(5)
        progress("chords", 60, "Recognizing chords")
        return timeline

    store, runner = make(tmp_path, analyze)
    job_id = runner.submit("abcdefghijk", "fast")
    assert started.wait(5)
    assert runner.cancel(job_id) is True
    release.set()
    runner.shutdown(wait=True)
    assert store.get_job(job_id)["state"] == "cancelled"
    assert store.list_songs() == []


def test_cancel_unknown_job(tmp_path):
    _, runner = make(tmp_path, lambda *a: None)
    assert runner.cancel("nope") is False
    runner.shutdown()
