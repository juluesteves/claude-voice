"""Ditado continuo: ouve o microfone, transcreve cada trecho entre pausas e
so encerra com uma palavra de comando ("enviar" / "cancelar"), um arquivo de
sinal escrito pelo mod, ou um longo silencio.

Saida: uma linha JSON por evento em stdout:
  {"status": "loading"|"listening"|"speaking"|"transcribing"}
  {"partial": "texto acumulado ate agora"}
  {"text": "...", "action": "send"|"fill"|"cancel"}   resultado final
  {"error": "..."}

Uso: python voice.py [--model small] [--language pt] [--silence 1.2]
     [--start-timeout 10] [--idle-timeout 120] [--max 600]
     [--signal caminho]   arquivo cujo conteudo "send"/"cancel" encerra
     [--file audio.wav]   transcreve um .wav em vez de gravar (teste)
"""
import argparse
import json
import os
import queue
import re
import sys
import time

import numpy as np

SAMPLE_RATE = 16000
BLOCK_MS = 30
BLOCK = SAMPLE_RATE * BLOCK_MS // 1000
PREROLL_BLOCKS = 20  # ~600 ms antes da deteccao de fala

# Palavras faladas que encerram o ditado, por idioma. Todas valem ao mesmo
# tempo, pois o idioma pode ser detectado automaticamente a cada trecho.
SEND_WORDS = {
    "pt": ["enviar", "envia", "envie", "mandar", "manda", "mande", "envio"],
    "en": ["send", "send it", "submit", "send message"],
    "es": ["enviar", "envía", "envia", "mandar", "manda", "listo"],
    "fr": ["envoyer", "envoie", "envoi", "valider"],
    "de": ["senden", "abschicken", "absenden", "schicken"],
    "it": ["invia", "inviare", "manda", "mandare"],
}
CANCEL_WORDS = {
    "pt": ["cancelar", "cancela", "cancele"],
    "en": ["cancel", "cancel it", "never mind", "nevermind", "discard"],
    "es": ["cancelar", "cancela"],
    "fr": ["annuler", "annule"],
    "de": ["abbrechen", "abbruch"],
    "it": ["annulla", "annullare", "cancella"],
}
SEND_PREFIX = ["pode", "podes", "por favor", "please", "puedes", "por favor", "s'il te plaît", "bitte", "per favore"]


def _words(table: dict, extra: str) -> list[str]:
    out: list[str] = []
    for lst in table.values():
        out.extend(lst)
    out.extend(w.strip() for w in extra.split(",") if w.strip())
    # mais longas primeiro, para "send it" vencer "send"
    return sorted({strip_accents(w.lower()) for w in out}, key=len, reverse=True)


def strip_accents(text: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def build_patterns(extra_send: str = "", extra_cancel: str = "") -> tuple[re.Pattern, re.Pattern]:
    send = "|".join(re.escape(w) for w in _words(SEND_WORDS, extra_send))
    cancel = "|".join(re.escape(w) for w in _words(CANCEL_WORDS, extra_cancel))
    prefix = "|".join(re.escape(strip_accents(w)) for w in SEND_PREFIX)
    send_re = re.compile(rf"[\s,.;:!?]*(?:(?:{prefix})\s+)?(?:{send})[\s.!?]*$", re.IGNORECASE)
    cancel_re = re.compile(rf"[\s,.;:!?]*(?:{cancel})[\s.!?]*$", re.IGNORECASE)
    return send_re, cancel_re


SEND_RE, CANCEL_RE = build_patterns()


LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice.log")


def log(msg: str) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S") + " " + msg + chr(10))
    except OSError:
        pass


def emit(**kw):
    line = json.dumps(kw, ensure_ascii=False)
    log(f"emit {line}")
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def beep():
    try:
        import winsound

        winsound.Beep(880, 120)
    except Exception:  # noqa: BLE001
        pass


def rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))


def read_signal(path: str | None) -> str | None:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8-sig") as f:
            value = f.read().strip().lower()
        os.remove(path)
    except OSError:
        return None
    return value or None


def load_model(name: str):
    from faster_whisper import WhisperModel

    return WhisperModel(name, device="cpu", compute_type="int8")


def transcribe(model, audio: np.ndarray, language: str) -> str:
    segments, _info = model.transcribe(
        audio,
        language=None if language in ("", "auto") else language,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return " ".join(s.text.strip() for s in segments).strip()


def join(acc: str, piece: str) -> str:
    piece = piece.strip()
    if not piece:
        return acc
    return f"{acc} {piece}".strip() if acc else piece


def finish(acc: str, piece: str) -> tuple[str, str] | None:
    """Aplica as palavras de comando ao trecho; None = continuar ouvindo."""
    plain = strip_accents(piece)
    if CANCEL_RE.search(plain):
        return "", "cancel"
    m = SEND_RE.search(plain)
    if m:
        return join(acc, piece[: m.start()]), "send"
    return None


def dictate(a) -> tuple[str, str]:
    """Retorna (texto, acao) com acao em send|fill|cancel."""
    import sounddevice as sd

    emit(status="loading")
    model = load_model(a.model)

    q: queue.Queue = queue.Queue()

    def on_audio(indata, _frames, _time, _status):
        q.put(indata[:, 0].copy())

    acc = ""
    preroll: list[np.ndarray] = []
    chunks: list[np.ndarray] = []
    speaking = False
    silent_blocks = 0
    silence_blocks = int(a.silence * 1000 / BLOCK_MS)
    levels: list[float] = []
    threshold = 0.012
    calibrated = False
    floor_levels: list[float] = []  # niveis recentes fora da fala, para o piso de ruido
    peak = 0.0
    last_voice = time.monotonic()
    started = time.monotonic()
    log(f"inicio model={a.model} silence={a.silence} signal={a.signal}")

    def set_threshold(quiet: float) -> float:
        # Entre 0.008 e 0.03: nem tao baixo que o ruido vire fala, nem tao alto
        # que a voz (quem fala ao apertar o botao contamina a calibracao) suma.
        return float(min(0.03, max(0.008, quiet * 4.0)))

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=BLOCK, callback=on_audio):
        if a.signal and os.path.exists(a.signal):
            os.remove(a.signal)
        emit(status="listening")
        beep()
        while True:
            signal = read_signal(a.signal)
            if signal in ("send", "cancel"):
                if signal == "send" and speaking and chunks:
                    emit(status="transcribing")
                    acc = join(acc, transcribe(model, np.concatenate(chunks), a.language))
                return acc, signal

            try:
                block = q.get(timeout=1.0)
            except queue.Empty:
                continue
            level = rms(block)
            now = time.monotonic()
            peak = max(peak, level)

            if not calibrated:
                # Guarda o audio desde o inicio: nada do que foi dito se perde.
                levels.append(level)
                preroll = (preroll + [block])[-PREROLL_BLOCKS:]
                if len(levels) >= 10:
                    quiet = float(np.percentile(levels, 30))
                    threshold = set_threshold(quiet)
                    calibrated = True
                    log(f"calibrado quiet={quiet:.4f} threshold={threshold:.4f} pico={peak:.4f}")
                    if level >= threshold:
                        speaking = True
                        last_voice = now
                        emit(status="speaking")
                        chunks = list(preroll)
                        preroll = []
                continue

            if speaking:
                chunks.append(block)
                if level < threshold:
                    silent_blocks += 1
                else:
                    silent_blocks = 0
                    last_voice = now
                if silent_blocks >= silence_blocks or now - started > a.max:
                    emit(status="transcribing")
                    audio = np.concatenate(chunks)
                    piece = transcribe(model, audio, a.language)
                    log(f"trecho {len(audio)/SAMPLE_RATE:.1f}s pico={peak:.4f} -> {piece!r}")
                    peak = 0.0
                    chunks = []
                    speaking = False
                    silent_blocks = 0
                    while not q.empty():  # o que chegou durante a transcricao vira pre-rolo
                        preroll = (preroll + [q.get_nowait()])[-PREROLL_BLOCKS:]

                    done = finish(acc, piece)
                    if done:
                        return done
                    acc = join(acc, piece)
                    emit(partial=acc)
                    emit(status="listening")
                    if now - started > a.max:
                        return acc, "fill"
            else:
                if level >= threshold:
                    speaking = True
                    last_voice = now
                    emit(status="speaking")
                    chunks = preroll + [block]
                    preroll = []
                else:
                    preroll = (preroll + [block])[-PREROLL_BLOCKS:]
                    # Piso de ruido recalculado com os ultimos ~3 s sem fala.
                    floor_levels = (floor_levels + [level])[-100:]
                    if len(floor_levels) == 100:
                        threshold = set_threshold(float(np.percentile(floor_levels, 30)))
                    if not acc and now - started > a.start_timeout:
                        log(f"sem fala em {a.start_timeout}s threshold={threshold:.4f} pico={peak:.4f}")
                        return "", "cancel"
                    if acc and now - last_voice > a.idle_timeout:
                        return acc, "fill"


def load_wav(path: str) -> np.ndarray:
    import wave

    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        ch = w.getnchannels()
        width = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[width]
    data = np.frombuffer(frames, dtype=dtype).astype(np.float32) / float(2 ** (8 * width - 1))
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if rate != SAMPLE_RATE:
        idx = np.linspace(0, len(data) - 1, int(len(data) * SAMPLE_RATE / rate))
        data = np.interp(idx, np.arange(len(data)), data).astype(np.float32)
    return data


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="small")
    p.add_argument("--language", default="auto")
    p.add_argument("--send-words", default="", help="palavras extras de envio, separadas por virgula")
    p.add_argument("--cancel-words", default="", help="palavras extras de cancelamento, separadas por virgula")
    p.add_argument("--silence", type=float, default=1.2)
    p.add_argument("--start-timeout", type=float, default=10.0)
    p.add_argument("--idle-timeout", type=float, default=120.0)
    p.add_argument("--max", type=float, default=600.0)
    p.add_argument("--signal")
    p.add_argument("--file")
    a = p.parse_args()
    global SEND_RE, CANCEL_RE
    SEND_RE, CANCEL_RE = build_patterns(a.send_words, a.cancel_words)

    try:
        if a.file:
            emit(status="loading")
            model = load_model(a.model)
            emit(status="transcribing")
            piece = transcribe(model, load_wav(a.file), a.language)
            done = finish("", piece)
            text, action = done if done else (piece, "fill")
            emit(text=text.strip(), action=action)
            return 0
        text, action = dictate(a)
        emit(text=text.strip(), action=action)
        return 0
    except Exception as exc:  # noqa: BLE001
        emit(error=f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
