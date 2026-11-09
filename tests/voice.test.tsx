import { expect, test } from 'claude-code/testing'

const BAND = {
  plugin: 'voice',
  component: 'AbovePrompt',
  requestId: 'above-prompt',
  props: { hasSurvey: false, isWorking: false, bodyColumns: 80 },
} as const

type Script = { stdout: string[] }

// Stand-ins do engine: o processo residente e o que o mod chama em `$`.
function engine(on: Parameters<Parameters<typeof test>[1]>[1], script: Script) {
  const seen = {
    submitted: null as { text: string; asUser: boolean } | null,
    toasts: [] as string[],
    signals: [] as string[],
    spawns: 0,
  }
  on('process.spawn', async function* (_, e) {
    seen.spawns += 1
    expect(e.argv[0]).toBe('python')
    expect(e.argv.join(' ')).toContain('voiced.py')
    expect(e.argv.join(' ')).toContain('--signal')
    for (const text of script.stdout) yield { stream: 'stdout', text }
    return { value: { code: 0, signal: null } }
  })
  on('prompt.submit', (_, e) => {
    const asUser = e.origin?.kind === 'plugin' && e.origin.asUser === true
    seen.submitted = { text: e.text, asUser }
    return { text: e.text }
  })
  on('fs.write', (_, e) => {
    seen.signals.push(e.text)
    return { value: undefined }
  })
  on('ui.toast', (_, e) => {
    seen.toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.status', () => ({ value: undefined }))
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  return seen
}

const settle = () => new Promise(resolve => setTimeout(resolve, 50))

test('a sessão interativa inicia o processo residente e registra /dictate', async ($, on) => {
  const seen = engine(on, { stdout: ['{"status": "loading"}\n{"status": "ready"}\n'] })

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await settle()

  expect(seen.spawns).toBe(1)
})

test('o texto que o processo entrega com "send" vira um prompt do usuário', async ($, on) => {
  const seen = engine(on, {
    stdout: [
      '{"status": "ready"}\n{"status": "recording"}\n',
      '{"partial": "crie um arquivo de teste"}\n',
      '{"status": "transcribing"}\n{"text": "crie um arquivo de teste com a lista", "action": "send"}\n{"status": "ready"}\n',
    ],
  })

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await settle()

  expect(seen.submitted?.text).toBe('crie um arquivo de teste com a lista')
  expect(seen.submitted?.asUser).toBe(true)
})

test('um "cancel" não envia nada', async ($, on) => {
  const seen = engine(on, {
    stdout: ['{"status": "ready"}\n{"text": "", "action": "cancel"}\n{"status": "ready"}\n'],
  })

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await settle()

  expect(seen.submitted).toBe(null)
  expect(seen.toasts.some(t => t.includes('nothing to send'))).toBe(true)
})

test('os botões da faixa escrevem o sinal para o processo', async ($, on) => {
  const seen = engine(on, { stdout: ['{"status": "ready"}\n'] })
  // O processo "fica vivo": o estado ready precisa estar valendo na faixa.
  on('state.get', (_, e) => (e.key === 'phase' ? { value: { value: 'ready', version: 1 } } : { value: { value: '', version: 1 } }))

  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  await ui.press({ plugin: 'voice', key: 'gravar' })
  await ui.unmount()

  expect(seen.signals).toEqual(['toggle'])
})

test('a faixa oferece iniciar a voz quando o processo não roda', async ($, on) => {
  engine(on, { stdout: [] })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    expect(await ui.find({ type: 'Button', key: 'iniciar' })).toBeTruthy()
    await ui.unmount()
  }
})
