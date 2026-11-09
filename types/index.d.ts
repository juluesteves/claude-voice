export type VoicePhase = 'idle' | 'loading' | 'ready' | 'recording' | 'paused' | 'transcribing'

declare module 'claude-code' {
  interface PluginState {
    dictation: { phase: VoicePhase; partial: string; lastText: string; lang: string }
  }
}
