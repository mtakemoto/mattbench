<script lang="ts">
  import { Circle, CircleCheck, CircleDashed, CircleSlash, CircleX, LoaderCircle, OctagonX, Scissors } from '@lucide/svelte';
  import { STATE_LABELS, type ProgressCase } from './progress';

  /** One case as a drawn mark; shape, colour and accessible name all carry the state. */
  let { entry }: { entry: ProgressCase } = $props();
  let label = $derived([
    entry.name, STATE_LABELS[entry.state], entry.truncated ? 'cut off at the token limit' : '',
    entry.calls != null ? `${entry.calls} ${entry.calls === 1 ? 'call' : 'calls'}` : '', entry.explanation ?? ''
  ].filter(Boolean).join(' · '));
  const icons = { queued: Circle, running: LoaderCircle, pass: CircleCheck, fail: CircleX, unscored: CircleDashed, error: OctagonX, not_run: CircleSlash };
  let Icon = $derived(entry.truncated && entry.state === 'fail' ? Scissors : icons[entry.state]);
</script>

<span class="mark {entry.state}" class:truncated={entry.truncated} role="img" aria-label={label} title={label}>
  <Icon size={14} strokeWidth={2.2} aria-hidden="true" />
</span>

<style>
  .mark { width: 22px; height: 22px; display: inline-grid; place-items: center; border-radius: 6px; color: var(--mark-muted); }
  .queued, .not_run { opacity: .7; }
  .running { color: var(--mark-accent); }
  .running :global(svg) { animation: mark-spin 1.1s linear infinite; }
  .pass { color: var(--mark-pass); background: var(--mark-pass-surface); }
  .fail, .error { color: var(--mark-miss); background: var(--mark-miss-surface); }
  .unscored { color: var(--mark-muted); }
  @keyframes mark-spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .running :global(svg) { animation: none; } }
</style>
