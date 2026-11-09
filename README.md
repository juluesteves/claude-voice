# Claude Voice — speak instead of typing in Claude Code

[🇧🇷 Versão em português](#português)

**Claude Voice** is a [Claude Code](https://code.claude.com) plugin (a *mod*) that adds
hands-free voice dictation to the terminal. You talk, it types the prompt for you
and sends it. Everything is controlled by the **mouse wheel button**, and the
transcription runs **100% locally** on your CPU with
[faster-whisper](https://github.com/SYSTRAN/faster-whisper). No audio ever leaves
your machine.

```
🎤 Ready. Click the mouse wheel to talk.
🔴 Recording… wheel: stop · double-click: send
   create a test file with the list of users and run the suite
```

## Features

- **Wheel-button control, in any window.** Click to start recording, click again
  to pause, double-click to send. Works while the terminal is in the background.
- **Continuous dictation.** Pauses to think never end the dictation. They only
  close a segment, which shows up transcribed in the band above the prompt.
- **Voice commands.** Say **"send"** or **"cancel"** at the end of a segment
  (also *enviar*, *envoyer*, *senden*, *invia*, *envía*… and any words you add).
- **Any language.** The spoken language is auto-detected per segment, or fixed
  with an ISO code. The interface comes in English and Portuguese.
- **Fast and private.** The Whisper model loads once per session and the
  microphone stays open, so each segment takes a couple of seconds even with the
  `medium` model. Nothing is sent to any server.
- **Keyboard fallback.** Band buttons `0` (toggle), `9` (send) and `8` (cancel)
  with an empty prompt, plus the `/dictate` command.

## Requirements

- **Claude Code** (CLI, desktop or IDE extension) with plugin support.
- **Python 3.10+** on the PATH with the voice libraries:

  ```
  pip install -r requirements.txt
  # or: pip install faster-whisper sounddevice pynput
  ```

- A **default microphone** configured in the OS. With Bluetooth headsets, the
  open microphone keeps the headset in hands-free mode while the session lasts.
- **Platforms:** tested on Windows 11. The global mouse hook uses `pynput`, which
  also supports macOS (needs Accessibility permission) and Linux/X11.
- GPU is optional. The default runs on CPU with int8 quantization.

## Install

Inside Claude Code:

```
/plugin marketplace add juluesteves/claude-voice
/plugin install voice@julu-plugins
```

Or from the shell:

```
claude plugin marketplace add juluesteves/claude-voice
claude plugin install voice@julu-plugins
```

The first run downloads the Whisper model (about 500 MB for `small`). When the
band above the prompt says **"Ready"**, click the mouse wheel and talk.

## How it works

1. When a session opens, the mod starts `scripts/voiced.py`, a resident Python
   process that loads the model, opens the microphone with a 1-second pre-roll and
   installs a global listener for the wheel button.
2. Each click toggles recording. Silence longer than the configured pause closes
   a segment, which is transcribed and appended to the running text.
3. A double-click, a spoken send word, or the `9` button finishes the dictation.
   The mod submits the text as your prompt, exactly as if you had typed it.

The mod and the process talk through JSON lines on stdout and a small signal file,
so no sockets or ports are opened.

## Options

Open the plugin configuration menu (`/plugin` → *Claude Voice* → *Configure*):

| Option | Default | Meaning |
| --- | --- | --- |
| Interface language | `en` | Band, toasts and command output: `en` or `pt` |
| Speech language | `auto` | ISO code (`pt`, `en`, `es`…) or `auto` to detect per segment |
| Model | `small` | `tiny`, `base`, `small`, `medium`, `large-v3` (bigger = more accurate, slower on CPU) |
| Pause (s) | `1.2` | Silence that closes a segment while recording |
| Extra send words | | Comma-separated spoken words that send, added to the built-in ones |
| Extra cancel words | | Comma-separated spoken words that discard, added to the built-in ones |

## Troubleshooting

- **"Preparing voice" never ends:** the model is still downloading, or Python
  could not be started. Check that `python -c "import faster_whisper, sounddevice, pynput"` works.
- **Nothing is recognized:** make sure the OS default microphone is the one you
  are using. `scripts/voice.log` records every event, including each wheel click.
- **Test without talking:** `python scripts/voice.py --file audio.wav` transcribes
  a 16 kHz WAV file and prints the JSON events.
- **Wheel clicks are ignored on macOS/Linux:** grant Accessibility (macOS) or run
  under X11 (Wayland does not expose global mouse events).

## Development

```
claude plugin validate . --strict      # manifest and marketplace checks
```

Tests live in `tests/voice.test.tsx` and use the Claude Code plugin testing
harness. Pull requests and issues are welcome.

## License

[MIT](LICENSE) © 2026 JuLu

---

# Português

**Claude Voice** é um plugin (*mod*) do [Claude Code](https://code.claude.com) que adiciona
ditado por voz ao terminal. Você fala, ele escreve o prompt e envia. Tudo é
controlado pelo **botão da rodinha do mouse**, e a transcrição roda **100%
local** na sua CPU com [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
Nenhum áudio sai da sua máquina.

## Como usar

- **Clique na rodinha** para começar a gravar. Fale, pare para pensar, continue:
  uma pausa nunca encerra o ditado, só fecha um trecho que aparece transcrito na
  faixa acima do prompt.
- **Clique de novo** para pausar. Mais um clique retoma.
- **Clique duplo** envia tudo como prompt.
- Também funcionam as palavras faladas **"enviar"** e **"cancelar"** no fim de um
  trecho, os botões da faixa (`0` alterna, `9` envia, `8` cancela, com o prompt
  vazio) e o comando `/dictate`.

## Requisitos

- Claude Code com suporte a plugins.
- Python 3.10+ no PATH com `faster-whisper`, `sounddevice` e `pynput`:

  ```
  pip install -r requirements.txt
  ```

- Um microfone padrão configurado no sistema. Com fones Bluetooth, o microfone
  aberto mantém o fone em modo mãos-livres durante a sessão.
- Testado no Windows 11. O gancho global do mouse usa `pynput`, que também
  funciona no macOS (precisa da permissão de Acessibilidade) e Linux/X11.

## Instalação

```
/plugin marketplace add juluesteves/claude-voice
/plugin install voice@julu-plugins
```

Na primeira execução o modelo Whisper é baixado (cerca de 500 MB no `small`).
Quando a faixa mostrar **"Pronto"**, clique na rodinha e fale.

## Opções

No menu de configuração do plugin (`/plugin` → *Claude Voice* → *Configure*):

| Opção | Padrão | Significado |
| --- | --- | --- |
| Interface language | `en` | Idioma da faixa e dos avisos: coloque `pt` |
| Speech language | `auto` | Código ISO (`pt`, `en`, `es`…) ou `auto` para detectar a cada trecho |
| Model | `small` | `tiny`, `base`, `small`, `medium`, `large-v3` |
| Pause (s) | `1.2` | Silêncio que fecha um trecho durante a gravação |
| Extra send words | | Palavras extras que enviam, separadas por vírgula |
| Extra cancel words | | Palavras extras que cancelam, separadas por vírgula |

## Problemas comuns

- **"Preparando a voz" não termina:** o modelo ainda está baixando ou o Python
  não iniciou. Teste `python -c "import faster_whisper, sounddevice, pynput"`.
- **Nada é reconhecido:** confira se o microfone padrão do sistema é o que você
  está usando. O arquivo `scripts/voice.log` registra cada evento e cada clique.
- **Testar sem falar:** `python scripts/voice.py --file audio.wav`.

## Licença

[MIT](LICENSE) © 2026 JuLu
