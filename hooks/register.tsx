import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { VoicePhase } from '../types'

const phase = atom({ plugin: 'dictation', key: 'phase' } as const, 'idle' as VoicePhase)
const partial = atom({ plugin: 'dictation', key: 'partial' } as const, '')
const lastText = atom({ plugin: 'dictation', key: 'lastText' } as const, '')

type Strings = {
  labels: Record<VoicePhase, string>
  start: string
  notRunning: string
  speak: string
  speakHint: string
  stop: string
  resume: string
  send: string
  cancel: string
  placeholder: string
  starting: string
  pausedMsg: string
  recordingMsg: string
  stillLoading: string
  cancelled: string
  nothing: string
  processStopped: string
  pythonFailed: string
  commandDescription: string
}

const STRINGS: Record<'en' | 'pt', Strings> = {
  en: {
    labels: {
      idle: '🎤 voice stopped',
      loading: '🎤 Preparing voice (loading the model)…',
      ready: '🎤 Ready. Click the mouse wheel to talk.',
      recording: '🔴 Recording… wheel: stop · double-click: send',
      paused: '⏸ Paused. Wheel: resume · double-click: send',
      transcribing: '🎤 Transcribing segment…',
    },
    start: '🎤 Start voice',
    notRunning: ' the voice process is not running',
    speak: '🎤 Talk',
    speakHint: ' or click the mouse wheel · double-click sends',
    stop: 'Stop',
    resume: 'Resume',
    send: 'Send',
    cancel: 'Cancel',
    placeholder: '(recognized text shows up here)',
    starting: 'Starting voice… once ready, click the mouse wheel to talk.',
    pausedMsg: 'Recording paused.',
    recordingMsg: 'Recording… click the wheel (or /dictate) to stop; double-click sends.',
    stillLoading: 'Voice: still loading…',
    cancelled: 'Voice: dictation discarded.',
    nothing: 'Voice: nothing to send.',
    processStopped: 'Voice: the voice process stopped.',
    pythonFailed: 'could not start Python',
    commandDescription: 'Voice: start the dictation process or toggle recording (the mouse wheel does the same)',
  },
  pt: {
    labels: {
      idle: '🎤 voz parada',
      loading: '🎤 Preparando a voz (carregando o modelo)…',
      ready: '🎤 Pronto. Clique na rodinha do mouse para falar.',
      recording: '🔴 Gravando… rodinha: parar · duplo clique: enviar',
      paused: '⏸ Pausado. Rodinha: continuar · duplo clique: enviar',
      transcribing: '🎤 Transcrevendo o trecho…',
    },
    start: '🎤 Iniciar voz',
    notRunning: ' o processo de voz não está rodando',
    speak: '🎤 Falar',
    speakHint: ' ou clique na rodinha do mouse · duplo clique envia',
    stop: 'Parar',
    resume: 'Continuar',
    send: 'Enviar',
    cancel: 'Cancelar',
    placeholder: '(o texto reconhecido aparece aqui)',
    starting: 'Iniciando a voz… quando ficar pronto, clique na rodinha do mouse para falar.',
    pausedMsg: 'Gravação pausada.',
    recordingMsg: 'Gravando… clique na rodinha (ou /dictate) para parar; duplo clique envia.',
    stillLoading: 'Voz: ainda carregando…',
    cancelled: 'Voz: ditado cancelado.',
    nothing: 'Voz: nada para enviar.',
    processStopped: 'Voz: o processo de voz parou.',
    pythonFailed: 'não consegui iniciar o Python',
    commandDescription: 'Voz: inicia o processo de ditado ou alterna gravar/parar (a rodinha do mouse faz o mesmo)',
  },
}

type Action = 'send' | 'cancel'
type Line =
  | { status: VoicePhase }
  | { partial: string }
  | { text: string; action: Action }
  | { error: string }
  | { log: string }

type Settings = {
  t: Strings
  model: string
  language: string
  silence: string
  sendWords: string
  cancelWords: string
}

function signalPath($: EngineInterface): string {
  return `${$.plugin.root}/scripts/.voice-signal`
}

async function setPhase($: EngineInterface, s: Settings, p: VoicePhase): Promise<void> {
  await update($, phase, () => p)
  $.ui.status(p === 'idle' || p === 'ready' ? undefined : s.t.labels[p])
}

async function signal($: EngineInterface, s: Settings, cmd: 'toggle' | 'send' | 'cancel'): Promise<void> {
  const p = await read($, phase)
  if (p === 'idle' || p === 'loading') {
    $.ui.toast(p === 'idle' ? s.t.labels.idle : s.t.stillLoading)
    return
  }
  await $.fs.write(signalPath($), cmd)
}

async function deliver($: EngineInterface, s: Settings, done: { text: string; action: Action }): Promise<void> {
  const text = done.text.trim()
  await update($, partial, () => '')
  if (done.action === 'cancel') {
    $.ui.toast(text ? s.t.cancelled : s.t.nothing)
    return
  }
  if (!text) {
    $.ui.toast(s.t.nothing)
    return
  }
  await update($, lastText, () => text)
  $.ui.toast(`🎤 ${text}`)
  void $.prompt.submit({ text, asUser: true })
}

/** Keeps the resident process alive; returns when it ends. */
async function runDaemon($: EngineInterface, s: Settings): Promise<void> {
  if ((await read($, phase)) !== 'idle') return
  await setPhase($, s, 'loading')
  await update($, partial, () => '')

  const script = `${$.plugin.root}/scripts/voiced.py`
  const child = $.process.spawn({
    argv: [
      'python', '-X', 'utf8', script,
      '--model', s.model,
      '--language', s.language,
      '--silence', s.silence,
      '--send-words', s.sendWords,
      '--cancel-words', s.cancelWords,
      '--signal', signalPath($),
    ],
    env: { PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
  })

  let buffer = ''
  let stderr = ''
  let failed: string | null = null

  const handle = async (line: string) => {
    if (!line.trim()) return
    let parsed: Line
    try {
      parsed = JSON.parse(line) as Line
    } catch {
      return
    }
    if ('status' in parsed) {
      await setPhase($, s, parsed.status)
    } else if ('partial' in parsed) {
      await update($, partial, () => parsed.partial)
    } else if ('text' in parsed) {
      await deliver($, s, parsed)
    } else if ('error' in parsed) {
      failed = parsed.error
    }
  }

  try {
    for await (const chunk of child) {
      if (chunk.stream === 'stderr') {
        stderr += chunk.text
        continue
      }
      buffer += chunk.text
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) await handle(line)
    }
    await handle(buffer)
  } catch (err) {
    failed = `${s.t.pythonFailed}: ${String(err)}`
  }

  await setPhase($, s, 'idle')
  await update($, partial, () => '')
  const reason: string | null = failed
  if (reason !== null) {
    $.ui.toast(`Voice: ${reason}`)
  } else if (stderr.trim()) {
    const tail = stderr.trim().split('\n').slice(-2).join(' ')
    $.ui.toast(`${s.t.processStopped} ${tail}`)
  }
}

export const register: Register = (on, options) => {
  const ui = options.ui === 'pt' ? 'pt' : 'en'
  const s: Settings = {
    t: STRINGS[ui],
    model: String(options.model ?? 'small'),
    language: String(options.language ?? 'auto'),
    silence: String(options.silence ?? '1.2'),
    sendWords: String(options.sendWords ?? ''),
    cancelWords: String(options.cancelWords ?? ''),
  }

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'dictate', description: s.t.commandDescription })
    const started = await next(e)
    if (e.isInteractive) void runDaemon($, s)
    return started
  })

  // After a reload the process may not have started with the session:
  // at the end of each turn, if it is down, bring it up again.
  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if ((await read($, phase)) === 'idle') void runDaemon($, s)
    return done
  })

  on('command.run', { command: 'dictate' }, async $ => {
    const p = await read($, phase)
    if (p === 'idle') {
      void runDaemon($, s)
      return { text: s.t.starting }
    }
    await signal($, s, 'toggle')
    return { text: p === 'recording' ? s.t.pausedMsg : s.t.recordingMsg }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)
    const p = await read($, phase)
    const t = s.t

    if (p === 'idle') {
      return (
        <Box>
          <Button key="iniciar" hotkey="0" label={t.start} onPress={() => void runDaemon($, s)} />
          <Text dimColor>{t.notRunning}</Text>
        </Box>
      )
    }
    if (p === 'loading') {
      return (
        <Box>
          <Text dimColor>{t.labels.loading}</Text>
        </Box>
      )
    }
    if (p === 'ready') {
      return (
        <Box>
          <Button key="gravar" hotkey="0" label={t.speak} onPress={() => void signal($, s, 'toggle')} />
          <Text dimColor>{t.speakHint}</Text>
        </Box>
      )
    }

    const sofar = await read($, partial)
    const width = Math.max(20, (e.props.bodyColumns ?? 80) - 4)
    const shown = sofar.length > width * 3 ? `…${sofar.slice(-(width * 3))}` : sofar

    return (
      <Box flexDirection="column">
        <Box>
          <Text color={p === 'recording' ? 'red' : 'yellow'}>{t.labels[p]} </Text>
          <Button key="alternar" hotkey="0" label={p === 'recording' ? t.stop : t.resume} onPress={() => void signal($, s, 'toggle')} />
          <Text> </Text>
          <Button key="enviar" hotkey="9" label={t.send} variant="primary" onPress={() => void signal($, s, 'send')} />
          <Text> </Text>
          <Button key="cancelar" hotkey="8" label={t.cancel} onPress={() => void signal($, s, 'cancel')} />
        </Box>
        {shown ? <Text>{shown}</Text> : <Text dimColor>{t.placeholder}</Text>}
      </Box>
    )
  })
}
