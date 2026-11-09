# Voice Dictation — speak instead of typing in Claude Code

[🇧🇷 Versão em português](#português)

**Voice Dictation** is a [Claude Code](https://code.claude.com) plugin (a *mod*) that adds
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
/plugin install dictation@julu-plugins
```

Or from the shell:

```
claude plugin marketplace add juluesteves/claude-voice
claude plugin install dictation@julu-plugins
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

## What this plugin does on your machine

This plugin is a *mod*: it runs code inside Claude Code through the hooks module
`hooks/register.tsx`. For transparency, here is everything it does.

- **Programs it runs.** On every interactive session start (and again at the end of a
  turn if the process has died) it spawns one Python process:
  `python -X utf8 <plugin>/scripts/voiced.py --model <model> --language <lang>
  --silence <s> --send-words <words> --cancel-words <words> --signal <plugin>/scripts/.voice-signal`.
  That script imports `scripts/voice.py`, loads a faster-whisper model, records the
  default microphone with `sounddevice` and listens to the mouse wheel button with
  `pynput`. The `/dictate` command starts the same process if it is not running.
  No other program, shell or command is executed.
- **Network.** Nothing. The only download is the Whisper model, fetched by
  faster-whisper from Hugging Face on first use. Audio and text never leave the machine.
- **Files it writes.** Only inside the plugin's own `scripts/` folder:
  `.voice-signal` (a one-word file, `toggle`/`send`/`cancel`, that the band buttons and
  `/dictate` write and the Python process reads and deletes) and `voice.log` (a plain
  text log of events for troubleshooting). It does not read or edit any project file,
  build file, settings file or instructions file.
- **Prompts it submits.** When you double-click the wheel, say a send word or press the
  *Send* button, the mod submits the transcribed text **as your own prompt**, verbatim,
  exactly as if you had typed it. It adds nothing to the text and submits nothing on its
  own. Cancelled dictations are discarded.
- **Hooks.** `session.start` registers `/dictate` and starts the process;
  `turn.complete` restarts the process if it is down; `command.run` handles `/dictate`;
  `ui.render` draws the band above the prompt with the recording state and buttons.
- **State.** Three in-memory values under the plugin's state: phase, partial text and
  the last submitted text. They are not persisted.

## Options

Open the plugin configuration menu (`/plugin` → *Voice Dictation* → *Configure*):

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

**Voice Dictation** é um plugin (*mod*) do [Claude Code](https://code.claude.com) que adiciona
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
/plugin install dictation@julu-plugins
```

Na primeira execução o modelo Whisper é baixado (cerca de 500 MB no `small`).
Quando a faixa mostrar **"Pronto"**, clique na rodinha e fale.

## O que este plugin faz na sua máquina

Este plugin é um *mod*: executa código dentro do Claude Code pelo módulo de hooks
`hooks/register.tsx`. Por transparência, aqui está tudo o que ele faz.

- **Programas que executa.** Ao abrir cada sessão interativa (e de novo ao fim de um
  turno, se o processo tiver morrido) inicia um processo Python:
  `python -X utf8 <plugin>/scripts/voiced.py --model ... --language ... --silence ...
  --send-words ... --cancel-words ... --signal <plugin>/scripts/.voice-signal`.
  Esse script importa `scripts/voice.py`, carrega o modelo faster-whisper, grava o
  microfone padrão com `sounddevice` e escuta o botão da rodinha com `pynput`.
  O comando `/dictate` inicia o mesmo processo se ele não estiver rodando. Nenhum outro
  programa, shell ou comando é executado.
- **Rede.** Nada. O único download é o modelo Whisper, baixado pelo faster-whisper do
  Hugging Face no primeiro uso. Áudio e texto nunca saem da máquina.
- **Arquivos que escreve.** Só dentro da pasta `scripts/` do próprio plugin:
  `.voice-signal` (arquivo de uma palavra, `toggle`/`send`/`cancel`, escrito pelos
  botões e pelo `/dictate` e lido e apagado pelo processo Python) e `voice.log`
  (log de eventos em texto). Não lê nem edita arquivos do projeto, de build, de
  configuração ou de instruções.
- **Prompts que envia.** Ao dar duplo clique, dizer uma palavra de envio ou apertar
  *Enviar*, o mod envia o texto transcrito **como seu próprio prompt**, sem alterações,
  como se você tivesse digitado. Não acrescenta nada e não envia nada por conta própria.
  Ditados cancelados são descartados.
- **Hooks.** `session.start` registra `/dictate` e inicia o processo; `turn.complete`
  reinicia o processo se caiu; `command.run` atende `/dictate`; `ui.render` desenha a
  faixa acima do prompt com o estado da gravação e os botões.
- **Estado.** Três valores em memória: fase, texto parcial e último texto enviado.
  Não são persistidos.

## Opções

No menu de configuração do plugin (`/plugin` → *Voice Dictation* → *Configure*):

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
