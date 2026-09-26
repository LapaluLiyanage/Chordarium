import pytest

from server.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.db")


def test_job_lifecycle(store):
    job_id = store.create_job("abcdefghijk", "fast")
    assert store.get_job(job_id)["state"] == "queued"
    store.update_job(job_id, state="chords", progress=60, message="Recognizing chords")
    job = store.get_job(job_id)
    assert (job["state"], job["progress"], job["message"]) == ("chords", 60, "Recognizing chords")
    assert store.get_job("missing") is None


def test_update_job_rejects_unknown_fields(store):
    job_id = store.create_job("abcdefghijk", "fast")
    with pytest.raises(ValueError):
        store.update_job(job_id, video_id="other")


def test_fail_interrupted_jobs(store):
    running = store.create_job("abcdefghijk", "fast")
    store.update_job(running, state="beats")
    done = store.create_job("abcdefghijk", "fast")
    store.update_job(done, state="done")
    assert store.fail_interrupted_jobs() == 1
    assert store.get_job(running)["state"] == "failed"
    assert store.get_job(done)["state"] == "done"


def test_save_is_upsert_by_video(store, timeline):
    first = store.save_song(timeline)
    timeline["title"] = "Renamed"
    assert store.save_song(timeline) == first
    song = store.get_song(first)
    assert song["title"] == "Renamed" and song["timeline"]["key"] == "G:min"
    assert store.get_song_by_video("abcdefghijk")["id"] == first
    assert [s["id"] for s in store.list_songs()] == [first]
    assert "timeline" not in store.list_songs()[0]


def test_edit_single_and_apply_to_all(store, timeline):
    timeline["segments"][2]["label"] = "C:min7"
    song_id = store.save_song(timeline)
    t = store.update_segment(song_id, 0, "A#:maj/3")
    assert t["segments"][0]["label"] == "A#:maj/3" and t["segments"][0]["bass"] == "D"
    assert t["segments"][0]["edited"] is True
    assert t["segments"][2]["label"] == "C:min7"
    t = store.update_segment(song_id, 2, "G:min", apply_to_all=True)
    assert t["segments"][2]["label"] == "G:min"


def test_edit_apply_to_all_changes_every_match(store, timeline):
    timeline["segments"][3]["label"] = "C:min7"
    song_id = store.save_song(timeline)
    t = store.update_segment(song_id, 0, "N", apply_to_all=True)
    assert [s["label"] for s in t["segments"]][:4] == ["N", "F:7", "A#:maj7", "N"]
    assert t["segments"][0]["bass"] is None


def test_edit_errors(store, timeline):
    song_id = store.save_song(timeline)
    with pytest.raises(KeyError):
        store.update_segment("missing", 0, "C:maj")
    with pytest.raises(IndexError):
        store.update_segment(song_id, 99, "C:maj")
    with pytest.raises(ValueError):
        store.update_segment(song_id, 0, "H:maj")


def test_reset_and_delete(store, timeline):
    song_id = store.save_song(timeline)
    store.update_segment(song_id, 0, "G:maj")
    assert store.reset_song(song_id)["segments"][0]["label"] == "C:min7"
    assert store.delete_song(song_id) is True
    assert store.get_song(song_id) is None
    assert store.delete_song(song_id) is False
