# Privacy policy

**Voice Dictation** for Claude Code processes everything on your own computer.

- **Audio.** The microphone is recorded only while you are dictating. Audio is kept
  in memory, transcribed locally with faster-whisper and discarded. It is never saved
  to disk and never sent anywhere.
- **Text.** The transcribed text is shown in the band above the prompt and, when you
  send it, submitted to Claude Code as your own prompt. From that point it follows the
  Claude Code privacy terms, like any prompt you type. The plugin itself keeps no copy
  beyond a plain-text event log (`scripts/voice.log`) inside the plugin folder, which
  you can delete at any time.
- **Network.** The plugin makes no network requests. The only download is the Whisper
  model, fetched once by the faster-whisper library from Hugging Face.
- **Telemetry.** None. No analytics, no identifiers, no crash reports.

Questions: open an issue at https://github.com/juluesteves/claude-voice/issues.
