# Changelog

## 0.2.0 - 2026-11-08

- Published as **Voice Dictation**: plugin `dictation`, slash command `/dictate`.
- Resident voice process: the Whisper model loads once per session and the
  microphone stays open, so each segment is transcribed in a couple of seconds.
- Mouse wheel button controls everything: click to record/pause, double-click to send.
- Interface in English or Portuguese; speech language auto-detected per segment.
- Spoken "send" / "cancel" words in six languages, plus user-defined extras.

## 0.1.0 - 2026-11-08

- First version: `/dictate` command and hotkey `0`, continuous dictation with
  faster-whisper, send by saying "enviar" or with the band buttons.
