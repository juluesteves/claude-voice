export type VoicePhase = 'idle' | 'loading' | 'ready' | 'recording' | 'paused' | 'transcribing'

declare module 'claude-code' {
  interface PluginState {
    voice: { phase: VoicePhase; partial: string; lastText: string }
  }
}
