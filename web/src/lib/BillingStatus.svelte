<script lang="ts">
  import type { Row } from './contracts';
  let { rows }: { rows: Row[] } = $props();
  let incomplete = $derived(rows.filter((row) => row.model.startsWith('openai-api/openrouter/') && row.billing?.complete !== true));
</script>

{#each incomplete as row (`${row.task}:${row.sample_id}`)}
  <p class="billing-note">
    <strong>{row.sample_id}: billing incomplete.</strong>
    {#if row.billing?.partial_cost_usd != null}
      Known charges: ${row.billing.partial_cost_usd.toFixed(6)} — a partial subtotal, not the total cost.
    {:else}
      Known charges unavailable; total cost unknown.
    {/if}
    {#if row.billing?.unknown_attempts != null}{row.billing.unknown_attempts} attempts have unknown charges.{/if}
    {#if row.billing?.lookup_failures != null}{row.billing.lookup_failures} billing lookups failed.{/if}
  </p>
{/each}

<style>
  .billing-note { margin: .75rem 0; padding: .6rem .8rem; border-radius: 7px; background: #fbfaf2; border: 1px solid #d0d5c4; color: #40543d; font-size: 11px; line-height: 1.5; }
</style>
