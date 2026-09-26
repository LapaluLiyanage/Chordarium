"""144-template chord recognizer (12 roots x 12 qualities) on CQT chroma + Viterbi."""
import librosa
import numpy as np

from server.theory.chord import QUALITY_INTERVALS, SHARPS

TEMPLATE_QUALITIES = ["maj", "min", "7", "maj7", "min7", "dim", "dim7",
                      "hdim7", "aug", "sus2", "sus4", "min6"]
HOP = 2048
ROOT_WEIGHT = 1.5
P_STAY = 0.95
BETA = 20.0
SILENCE_RATIO = 0.02


def build_templates() -> tuple[list[str], np.ndarray]:
    labels, rows = [], []
    for quality in TEMPLATE_QUALITIES:
        for root in range(12):
            v = np.zeros(12)
            for i in QUALITY_INTERVALS[quality]:
                v[(root + i) % 12] = 1.0
            v[root] = ROOT_WEIGHT
            rows.append(v / np.linalg.norm(v))
            labels.append(f"{SHARPS[root]}:{quality}")
    return labels, np.array(rows)


def viterbi(log_emit: np.ndarray, p_stay: float = P_STAY) -> np.ndarray:
    """Most likely state path; transitions: stay=p_stay, any other state uniform."""
    n_states, n_frames = log_emit.shape
    log_stay = np.log(p_stay)
    log_move = np.log((1 - p_stay) / (n_states - 1))
    states = np.arange(n_states)
    delta = log_emit[:, 0].copy()
    back = np.zeros((n_states, n_frames), dtype=int)
    for t in range(1, n_frames):
        best_prev = int(delta.argmax())
        stay = delta + log_stay
        move = delta[best_prev] + log_move
        choose_stay = stay >= move
        back[:, t] = np.where(choose_stay, states, best_prev)
        delta = np.where(choose_stay, stay, move) + log_emit[:, t]
    path = np.zeros(n_frames, dtype=int)
    path[-1] = int(delta.argmax())
    for t in range(n_frames - 1, 0, -1):
        path[t - 1] = back[path[t], t]
    return path


def recognize(y: np.ndarray, sr: int, hop: int = HOP) -> list[dict]:
    labels, templates = build_templates()
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    chroma = chroma / (np.linalg.norm(chroma, axis=0, keepdims=True) + 1e-9)
    scores = templates @ chroma
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    n = min(scores.shape[1], len(rms))
    scores, rms = scores[:, :n], rms[:n]
    path = viterbi(BETA * scores)
    silent = rms < SILENCE_RATIO * (rms.max() + 1e-9)
    frame_labels = ["N" if silent[i] else labels[path[i]] for i in range(n)]

    duration = len(y) / sr
    times = np.minimum(librosa.frames_to_time(np.arange(n + 1), sr=sr, hop_length=hop), duration)
    segments, start = [], 0
    for i in range(1, n + 1):
        if i < n and frame_labels[i] == frame_labels[start]:
            continue
        label = frame_labels[start]
        if label == "N":
            alt, conf = None, 1.0
        else:
            mean = scores[:, start:i].mean(axis=1)
            best = labels.index(label)
            alt = next(labels[k] for k in np.argsort(mean)[::-1] if k != best)
            conf = float(np.clip(mean[best], 0.0, 1.0))
        segments.append({"start": float(times[start]), "end": float(times[i]),
                         "label": label, "alt": alt, "confidence": round(conf, 3)})
        start = i
    return segments
