<script lang="ts">
  /** Prompt variants shared by every selected suite; `variants` is what the run will evaluate. */
  let { options, variants = $bindable() }: { options: string[]; variants: string[] } = $props();
  const descriptions: Record<string, [string, string]> = {
    base: ['Base', 'Original prompt'],
    careful: ['Careful', 'Guided system note']
  };
  const COMPARE = '*';
  let choices = $derived([
    ...options.map((id) => ({ id, label: descriptions[id]?.[0] ?? id, sub: descriptions[id]?.[1] ?? 'Prompt variant' })),
    { id: COMPARE, label: 'Compare all', sub: 'Side by side' }
  ]);
  let current = $derived(variants.length > 1 ? COMPARE : variants[0]);
  function choose(id: string) { variants = id === COMPARE ? [...options] : [id]; }
</script>

<div class="field">
  <div class="field-head"><strong>Prompt treatment</strong><span>Same pinned questions</span></div>
  <div class="variant-grid" role="group" aria-label="Prompt treatment">
    {#each choices as choice (choice.id)}
      <button type="button" class:selected={current === choice.id} aria-pressed={current === choice.id} onclick={() => choose(choice.id)}>
        <strong>{choice.label}</strong><small>{choice.sub}</small>
      </button>
    {/each}
  </div>
</div>
