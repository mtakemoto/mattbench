<script lang="ts">
	import '../app.css';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();
</script>

<svelte:head>
	<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
	<title>mattbench — make models prove it</title>
	<meta name="description" content="Run small, reproducible model benchmarks and inspect every task result." />
</svelte:head>

<!--
THESIS: Make every benchmark result traceable to a task; refuse a generic model leaderboard.
OWN-WORLD: Warm black operator board, cream scorecard, lime actions, coral misses, precise data type.
STORY: Choose source, model, and prompt; make a bounded run; inspect each task and its run settings.
FIRST VIEWPORT: Compact rail, large measurement masthead, dark run controls beside the cream result matrix; primary action follows the form.
FORM: Code-led operator board, assigned direction 7, concept seed 0ce90ca4. Owner requested autonomous execution and a bold, fun start.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
-->
{@render children()}
