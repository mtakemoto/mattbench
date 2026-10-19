<script lang="ts">
  import { Bell, BellDot, X } from '@lucide/svelte';
  import type { Notice } from './notices';

  /** Bell in the header with a right-side fly-out; notices never push the page content around. */
  let { notices }: { notices: Notice[] } = $props();
  let open = $state(false);
  let errors = $derived(notices.filter((notice) => notice.tone === 'error').length);
  function closeOnEscape(event: KeyboardEvent) { if (open && event.key === 'Escape') open = false; }
</script>

<svelte:window onkeydown={closeOnEscape} />

<button class="bell" class:alert={errors} type="button" aria-expanded={open} aria-controls="notice-panel"
  aria-label={notices.length ? `Notifications: ${notices.length}` : 'Notifications: none'} onclick={() => open = !open}>
  {#if notices.length}<BellDot size={19} aria-hidden="true" />{:else}<Bell size={19} aria-hidden="true" />{/if}
  {#if notices.length}<span class="count">{notices.length}</span>{/if}
</button>

{#if open}
  <button class="scrim" type="button" aria-label="Close notifications" onclick={() => open = false}></button>
  <aside id="notice-panel" class="panel" aria-label="Notifications">
    <header><h2>Notifications</h2><button type="button" aria-label="Close notifications" onclick={() => open = false}><X size={17} aria-hidden="true" /></button></header>
    {#each notices as notice (notice.id)}
      <article class={notice.tone}><strong>{notice.title}</strong><p>{notice.body}</p></article>
    {:else}
      <p class="none">Nothing needs attention.</p>
    {/each}
  </aside>
{/if}

<style>
  .bell { position: relative; width: 40px; height: 40px; display: grid; place-items: center; border: 1px solid #596b5c; border-radius: 10px; background: #2c382e; color: #b3c2b2; }
  .bell:hover, .bell[aria-expanded='true'] { background: #40543d; color: #edfa9b; }
  .bell.alert { color: #ffc1ad; border-color: #ba553e; }
  .count { position: absolute; top: -6px; right: -6px; min-width: 18px; height: 18px; padding: 0 4px; border-radius: 9px; display: grid; place-items: center; background: #40543d; color: #f4f0e6; font: 800 9px 'JetBrains Mono Variable', monospace; }
  .alert .count { background: #ba553e; color: #fbfaf2; }
  .scrim { position: fixed; inset: 0; z-index: 20; border: 0; background: #11161466; cursor: default; }
  .panel { position: fixed; top: 0; right: 0; bottom: 0; z-index: 21; width: min(380px, 100vw); overflow: auto; background: #fbfaf2; color: #18231a; font: 400 12px/1.45 'DM Sans Variable', sans-serif; letter-spacing: 0; white-space: normal; padding: 22px 20px; box-shadow: -12px 0 32px #11161459; animation: slide-in .26s cubic-bezier(.16, 1, .3, 1); }
  header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  h2 { margin: 0; font: 800 22px 'Bricolage Grotesque Variable', sans-serif; letter-spacing: -.03em; }
  header button { border: 0; background: transparent; color: #596b5c; width: 32px; height: 32px; display: grid; place-items: center; border-radius: 7px; }
  header button:hover { background: #e5ead9; color: #18231a; }
  article { padding: 12px 13px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #d0d5c4; background: #f0eee4; }
  article.error { background: #f4d6cd; border-color: #e3b3a5; }
  article strong { display: block; font-size: 12px; font-weight: 800; color: #18231a; }
  article p { margin: 5px 0 0; font-size: 11px; line-height: 1.5; color: #40543d; }
  article.error p { color: #5c1f14; }
  .none { font-size: 12px; color: #596b5c; }
  @keyframes slide-in { from { transform: translateX(24px); opacity: .6; } }
  @media (prefers-reduced-motion: reduce) { .panel { animation: none; } }
</style>
