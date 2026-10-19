<script lang="ts">
  let { connectionError, historyError, warnings }: { connectionError: string; historyError: string; warnings: string[] } = $props();
</script>

{#if connectionError}
  <div class="message error" role="status">Console connection lost: {connectionError} Retrying with backoff; the worker continues independently.</div>
{/if}
{#if historyError}
  <div class="message error" role="status">Results unavailable: {historyError} The last valid view is preserved.</div>
{/if}
{#if warnings.length}
  <div class="note" role="status">
    <div><strong>Incomplete report</strong>{#each warnings as warning (warning)}<p>{warning}</p>{/each}</div>
  </div>
{/if}
