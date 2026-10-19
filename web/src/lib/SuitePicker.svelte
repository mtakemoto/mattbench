<script lang="ts">
  import { ChevronDown, Check } from '@lucide/svelte';
  import { SELECT_ALL, type Suite } from './contracts';
  import { plural } from './format';

  /** `selection` is `['all']` or the IDs of the chosen suites. */
  let { suites, selection = $bindable() }: { suites: Suite[]; selection: string[] } = $props();
  let open = $state(false);
  let runAll = $derived(selection.includes(SELECT_ALL));
  let caseCount = $derived(suites.reduce((sum, suite) => sum + suite.cases.length, 0));
  let suiteNames = $derived(suites.map((suite) => suite.label).join(', '));

  function chooseAll() { selection = [SELECT_ALL]; }
  function toggle(id: string) {
    const current = runAll ? [] : selection;
    selection = current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id];
  }
</script>

<div class="field case-field">
  <div class="field-head">
    <strong>Choose a benchmark</strong>
    <span>{plural(caseCount, 'task')} across {plural(suites.length, 'category', 'categories')}</span>
  </div>
  <div class="case-selection-wrapper">
    <button class="case-option everything" class:selected={runAll} type="button" aria-pressed={runAll} onclick={chooseAll}>
      <span><strong>Run everything</strong><small>All {caseCount} tasks: {suiteNames}</small></span>
      <b>{caseCount} TASKS</b>
    </button>

    <div class="category-accordion-card">
      <button class="category-accordion-trigger" class:active={!runAll} type="button" aria-expanded={open} onclick={() => open = !open}>
        <div class="trigger-label">
          <span class="trigger-title">
            <strong>Select by category</strong>
            {#if !runAll && selection.length}<span class="active-pill">{selection.length} of {suites.length} SELECTED</span>{/if}
          </span>
          <small>{suiteNames}</small>
        </div>
        <div class="trigger-meta">
          <span class="mode-badge">{runAll ? 'CATEGORIES' : `${selection.length} ACTIVE`}</span>
          <span class="chevron" class:open aria-hidden="true"><ChevronDown size={18} /></span>
        </div>
      </button>

      {#if open}
        <div class="category-accordion-body" role="group" aria-label="Category multi-choice selection">
          <p class="category-note">Select one or more categories (replaces Run everything):</p>
          <div class="category-choices">
            {#each suites as suite (suite.id)}
              {@const checked = !runAll && selection.includes(suite.id)}
              <div class="category-card" class:checked>
                <label class="category-choice-header">
                  <input type="checkbox" {checked} onchange={() => toggle(suite.id)} />
                  <span class="choice-checkbox" aria-hidden="true">{#if checked}<Check size={14} />{/if}</span>
                  <div class="choice-text">
                    <div class="choice-title-row"><strong>{suite.label}</strong></div>
                    <small>{suite.description}</small>
                  </div>
                  <b class="task-count">{plural(suite.cases.length, 'TASK').toUpperCase()}</b>
                </label>
                <details class="category-subtasks">
                  <summary class="subtasks-label">Included tasks</summary>
                  <ul>
                    {#each suite.cases as entry (entry.id)}
                      <li><code>{entry.name}</code><span>{plural(entry.maxModelCalls, 'call')} max</span></li>
                    {/each}
                  </ul>
                </details>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </div>
  {#if !runAll && !selection.length}
    <p class="case-hint warning">No categories selected. Check at least one category above, or select "Run everything".</p>
  {/if}
</div>
