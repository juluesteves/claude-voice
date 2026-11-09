"""Processo residente do mod Claude Voice: vive durante a sessao do Claude Code.

- Carrega o modelo faster-whisper uma vez e mantem o microfone aberto, com um
  pre-rolo de ~1 s, para nada do inicio da fala se perder.
- Escuta o botao do meio do mouse (rodinha) globalmente:
    clique            alterna gravar / parar (pausas na fala sao ignoradas)
    clique duplo      envia o texto acumulado
- Tambem aceita comandos por um arquivo de sinal (escrito pelo mod):
    toggle | send | cancel
- Palavras faladas no fim de um trecho: "enviar" envia, "cancelar" descarta.

Saida: uma linha JSON por evento em stdout:
  {"status": "loading"|"ready"|"recording"|"paused"|"transcribing"}
  {"partial": "texto acumulado"}
  {"text": "...", "action": "send"|"cancel"}
  {"error": "..."}
  {"log": "..."}
"""
import argparse
import json
import os
import queue
import sys
import threading
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice  # noqa: E402
from voice import join, load_model, log, transcribe  # noqa: E402

SAMPLE_RATE = 16000
BLOCK_MS = 30
BLOCK = SAMPLE_RATE * BLOCK_MS // 1000
PREROLL_BLOCKS = 33  # ~1 s
DOUBLE_CLICK_S = 0.40


def emit(**kw):
    line = json.dumps(kw, ensure_ascii=False)
    log(f"emit {line}")
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def finish(acc: str, piece: str):
    """Aplica as palavras de comando ao trecho; None = continuar."""
    return voice.finish(acc, piece)


def rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))


class Daemon:
    def __init__(self, a):
        self.a = a
        self.cmds: queue.Queue = queue.Queue()
        self.audio: queue.Queue = queue.Queue()
        self.recording = False
        self.acc = ""
        self.chunks: list[np.ndarray] = []
        self.preroll: list[np.ndarray] = []
        self.silence_blocks = int(a.silence * 1000 / BLOCK_MS)
        self.silent = 0
        self.threshold = 0.012
        self.floor: list[float] = []
        self.model = None
        self._last_click = 0.0
        self._click_timer: threading.Timer | None = None

    # ---- entradas -------------------------------------------------------
    def on_click(self, _x, _y, button, pressed):
        from pynput import mouse

        if button != mouse.Button.middle or not pressed:
            return
        now = time.monotonic()
        log(f"clique rodinha (recording={self.recording})")
        if now - self._last_click < DOUBLE_CLICK_S:
            if self._click_timer:
                self._click_timer.cancel()
                self._click_timer = None
            self._last_click = 0.0
            self.cmds.put("send")
            return
        self._last_click = now
        self._click_timer = threading.Timer(DOUBLE_CLICK_S, lambda: self.cmds.put("toggle"))
        self._click_timer.daemon = True
        self._click_timer.start()

    def watch_signal(self):
        path = self.a.signal
        while True:
            time.sleep(0.1)
            if not path or not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8-sig") as f:
                    value = f.read().strip().lower()
                os.remove(path)
            except OSError:
                continue
            if value in ("toggle", "send", "cancel"):
                self.cmds.put(value)

    def on_audio(self, indata, _frames, _time, _status):
        self.audio.put(indata[:, 0].copy())

    # ---- estados --------------------------------------------------------
    def start_recording(self):
        self.recording = True
        self.silent = 0
        self.chunks = list(self.preroll)
        self.preroll = []
        emit(status="recording")

    def flush_chunk(self) -> str:
        """Transcreve o que foi gravado ate aqui e devolve o trecho."""
        if not self.chunks:
            return ""
        audio = np.concatenate(self.chunks)
        self.chunks = []
        if len(audio) < SAMPLE_RATE * 0.4:
            return ""
        emit(status="transcribing")
        piece = transcribe(self.model, audio, self.a.language)
        log(f"trecho {len(audio)/SAMPLE_RATE:.1f}s -> {piece!r}")
        return piece

    def stop_recording(self):
        self.recording = False
        piece = self.flush_chunk()
        done = finish(self.acc, piece)
        if done:
            self.deliver(*done)
            return
        self.acc = join(self.acc, piece)
        emit(partial=self.acc)
        emit(status="paused" if self.acc else "ready")

    def deliver(self, text: str, action: str):
        self.recording = False
        self.chunks = []
        self.acc = ""
        emit(text=text.strip(), action=action)
        emit(status="ready")

    def handle(self, cmd: str):
        if cmd == "toggle":
            if self.recording:
                self.stop_recording()
            else:
                self.start_recording()
        elif cmd == "send":
            if self.recording:
                self.recording = False
                piece = self.flush_chunk()
                done = finish(self.acc, piece)
                if done and done[1] == "cancel":
                    self.deliver("", "cancel")
                    return
                self.acc = done[0] if done else join(self.acc, piece)
            self.deliver(self.acc, "send" if self.acc else "cancel")
        elif cmd == "cancel":
            self.deliver("", "cancel")

    # ---- laco principal -------------------------------------------------
    def run(self):
        import sounddevice as sd
        from pynput import mouse

        emit(status="loading")
        self.model = load_model(self.a.model)
        # Aquece o modelo para o primeiro trecho nao pagar a inicializacao.
        transcribe(self.model, np.zeros(SAMPLE_RATE, dtype=np.float32), self.a.language)

        if self.a.signal and os.path.exists(self.a.signal):
            os.remove(self.a.signal)
        threading.Thread(target=self.watch_signal, daemon=True).start()
        listener = mouse.Listener(on_click=self.on_click)
        listener.daemon = True
        listener.start()
        log("ouvindo o mouse (botao do meio)")

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            blocksize=BLOCK, callback=self.on_audio):
            emit(status="ready")
            log(f"pronto model={self.a.model} device={sd.default.device}")
            while True:
                try:
                    while True:
                        self.handle(self.cmds.get_nowait())
                except queue.Empty:
                    pass
                try:
                    block = self.audio.get(timeout=0.2)
                except queue.Empty:
                    continue
                level = rms(block)

                if self.recording:
                    self.chunks.append(block)
                    if level < self.threshold:
                        self.silent += 1
                        # Pausa longa: fecha o trecho para mostrar o parcial, mas
                        # continua gravando; a pausa nunca encerra o ditado.
                        if self.silent == self.silence_blocks and len(self.chunks) > self.silence_blocks + 10:
                            piece = self.flush_chunk()
                            done = finish(self.acc, piece)
                            if done:
                                self.deliver(*done)
                                continue
                            if piece.strip():
                                self.acc = join(self.acc, piece)
                                emit(partial=self.acc)
                            emit(status="recording")
                    else:
                        self.silent = 0
                else:
                    self.preroll = (self.preroll + [block])[-PREROLL_BLOCKS:]
                    self.floor = (self.floor + [level])[-100:]
                    if len(self.floor) == 100:
                        quiet = float(np.percentile(self.floor, 30))
                        self.threshold = float(min(0.03, max(0.008, quiet * 4.0)))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="small")
    p.add_argument("--language", default="auto")
    p.add_argument("--send-words", default="")
    p.add_argument("--cancel-words", default="")
    p.add_argument("--silence", type=float, default=1.2)
    p.add_argument("--signal")
    a = p.parse_args()
    voice.SEND_RE, voice.CANCEL_RE = voice.build_patterns(a.send_words, a.cancel_words)
    try:
        Daemon(a).run()
        return 0
    except Exception as exc:  # noqa: BLE001
        log(f"erro {type(exc).__name__}: {exc}")
        emit(error=f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
