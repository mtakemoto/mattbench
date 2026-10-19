<script lang="ts">
  let { maxCalls, configured, paid, capUsd = $bindable(), capConfirmed = $bindable() }: {
    maxCalls: number; configured: boolean; paid: boolean; capUsd: number; capConfirmed: boolean;
  } = $props();
</script>

<div class="paid">
  {#if paid}
    <h3><span>$</span> Paid run guard</h3>
    <p>OpenRouter's workspace cap is the dollar stop. Up to {maxCalls} model calls; API and task retries are disabled. Each Home Assistant evaluation stops after 3 minutes; setup and cleanup have separate deadlines.</p>
    <label for="cap">Active workspace cap (USD)</label>
    <input id="cap" type="number" min="0.01" max="20" step="0.01" bind:value={capUsd} />
    <label class="check"><input type="checkbox" bind:checked={capConfirmed} /> I confirm this cap is active in OpenRouter.</label>
  {/if}
  {#if !configured}<p class="warning">Add OPENROUTER_API_KEY to the ignored .env to enable hosted runs.</p>{/if}
</div>
