---
name: mattbench
description: A bright operator board for traceable model benchmark runs.
colors:
  signal-lime: "#d8ee6b"
  signal-lime-hover: "#edfa9b"
  coral-miss: "#ba553e"
  dark-canvas: "#161a19"
  dark-rail: "#111614"
  dark-masthead: "#1b231e"
  dark-panel: "#202922"
  dark-control: "#2c382e"
  dark-field: "#121b15"
  dark-selected: "#40543d"
  light-panel: "#f0eee4"
  light-sheet: "#fbfaf2"
  light-text: "#f4f0e6"
  dark-text: "#18231a"
  dark-muted-text: "#b3c2b2"
  light-muted-text: "#596b5c"
  dark-border: "#343d35"
  light-border: "#d0d5c4"
  pass-text: "#366e37"
  miss-text: "#b64430"
  paid-guard: "#362f26"
typography:
  display:
    fontFamily: "Bricolage Grotesque Variable, sans-serif"
    fontSize: "clamp(2.7rem, 4vw, 4.6rem)"
    fontWeight: 800
    lineHeight: 0.97
    letterSpacing: "-.038em"
  headline:
    fontFamily: "Bricolage Grotesque Variable, sans-serif"
    fontSize: "29px"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-.033em"
  body:
    fontFamily: "DM Sans Variable, sans-serif"
    fontSize: "12px"
    lineHeight: 1.45
  label:
    fontFamily: "JetBrains Mono Variable, monospace"
    fontSize: "10px"
    fontWeight: 700
    letterSpacing: ".1em"
  measure:
    fontFamily: "JetBrains Mono Variable, monospace"
    fontSize: "10px"
    fontWeight: 700
rounded:
  badge: "4px"
  field: "8px"
  control: "9px"
  guard: "10px"
spacing:
  choice-gap: "7px"
  compact: "10px"
  guard-inset: "16px"
  mobile-panel-inset: "17px"
  desktop-panel-inset: "40px"
components:
  run-button:
    backgroundColor: "{colors.signal-lime}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.control}"
    padding: "0 16px"
  run-button-hover:
    backgroundColor: "{colors.signal-lime-hover}"
  source-choice:
    backgroundColor: "{colors.dark-control}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.control}"
    padding: "12px 9px"
  source-choice-selected:
    backgroundColor: "{colors.dark-selected}"
  model-search:
    backgroundColor: "{colors.dark-field}"
    textColor: "{colors.light-text}"
    rounded: "{rounded.field}"
    padding: "0 12px"
    height: "43px"
  scorecard:
    backgroundColor: "{colors.light-sheet}"
    textColor: "{colors.dark-text}"
    rounded: "{rounded.field}"
  paid-guard:
    backgroundColor: "{colors.paid-guard}"
    rounded: "{rounded.guard}"
    padding: "16px"
---

# Design System: mattbench

## Overview

**Creative North Star: "The Operator Board"**

The current console pairs a dark control surface with a warm paper report surface. Lime marks the active path through a run, while the paper area keeps task outcomes and measurements easy to scan. The masthead is loud and graphic; the controls and results are dense, explicit, and restrained.

This is the first code-led visual direction, not an owner-approved brand identity. Its reusable character is a bright, instrument-like working surface with visible run identity and task-level evidence. The circular masthead dial reads as a timing mark; it does not encode benchmark progress.

**Key Characteristics:**

- Dark operation area beside a cream result sheet.
- Strong display type for short declarations; compact monospace for measurements and system labels.
- Lime for selection and action; coral and green for distinct result meanings.
- Thin boundaries and surface tone carry most of the hierarchy.

## Colors

The palette is warm black and cream with a sharp lime signal.

### Primary

- **Signal Lime** (`{colors.signal-lime}`) marks the active source, selected controls, run action, small status lights, and masthead emphasis. **Signal Lime Hover** (`{colors.signal-lime-hover}`) is the brighter interactive state.

### Secondary

- **Coral Miss** (`{colors.coral-miss}`) marks the report heading accent; the related **Miss Text** (`{colors.miss-text}`) marks failed task results. Their uses are distinct from the green pass text (`{colors.pass-text}`).

### Neutral

- **Dark Canvas, Rail, Masthead, and Panel** (`{colors.dark-canvas}`, `{colors.dark-rail}`, `{colors.dark-masthead}`, `{colors.dark-panel}`) separate the frame, navigation, introduction, and work area by tone.
- **Dark Control, Field, and Selected** (`{colors.dark-control}`, `{colors.dark-field}`, `{colors.dark-selected}`) differentiate interactive states within the work area.
- **Light Panel and Sheet** (`{colors.light-panel}`, `{colors.light-sheet}`) make the report feel like an inserted paper record.
- **Light and Dark Text** (`{colors.light-text}`, `{colors.dark-text}`), their muted counterparts, and the two border colors support readable hierarchy on each surface.
- **Paid Guard** (`{colors.paid-guard}`) gives hosted-run spending controls a separate warm brown zone.

**The Signal Rule.** Reserve lime for active work, selection, and the main action; keep outcome words explicit so color never carries the result alone.

## Typography

**Display Font:** Bricolage Grotesque Variable (sans-serif fallback). **Body Font:** DM Sans Variable (sans-serif fallback). **Measurement Font:** JetBrains Mono Variable (monospace fallback).

The broad, tightly spaced display face gives the board its voice. The simpler body face carries control copy; the mono face distinguishes system labels, IDs, numbers, and timing.

### Hierarchy

- **Display** (`{typography.display}`): short masthead statement, with one lime phrase.
- **Headline** (`{typography.headline}`): work and report section headings; the small colored period is an accent, not a substitute for the title.
- **Body** (`{typography.body}`): compact explanations around controls and the scorecard. The masthead paragraph is larger (14px, line-height 1.55).
- **Label** (`{typography.label}`): uppercase system labels and status tags.
- **Measure** (`{typography.measure}`): tabular scores, times, tokens, and cost. Numeric cells use tabular figures.

**The Measurement Rule.** Put exact values in a mono treatment near the task or run they describe; keep explanatory prose in DM Sans.

## Layout

The desktop shell uses a 220px navigation rail and a flexible main column. At 1350px and below, the rail contracts to 68px. The work area places a 390–430px dark setup panel beside a flexible light report panel; at 900px and below, those panels stack. At 620px and below, navigation becomes a 61px top strip, the panels use a 17px horizontal inset, and the header type reduces to 2.65rem. The page has a 320px minimum width.

The source and prompt options use three equal columns with a 7px gap. Fields have a 27px bottom rhythm. The scorecard table keeps a 680px minimum width inside its own horizontal scroll container, protecting the page from horizontal overflow at phone width. The desktop and 390px review captures show the rail, masthead, and control stack following these shifts.

## Elevation & Depth

The board is mostly flat. Tonal surfaces and 1px borders separate major areas and controls. The dial has two inset rings, status lights have a restrained glow, and the primary button lifts by 2px with a shadow on hover. The search field gets a 2px lime focus halo. These effects communicate interaction or instrument detail rather than a floating-card hierarchy.

**The Flat Record Rule.** Keep report data on the cream plane; use borders and spacing to separate rows before adding lift.

## Shapes

Controls use compact rounded rectangles: 8px fields and report containers, 9px navigation and choice controls, and a 10px paid guard. Badges have 4px corners. Model selection dots, status lights, and the masthead dial are circular. The brand mark is three tilted lime bars with uneven heights and partially rounded tops. Report rows stay rectangular and rule-separated.

## Components

### Buttons and choices

- **Run action:** a full lime button (`{components.run-button}`) beside the model-call counter. Hover brightens, rises 2px, and adds a shadow; disabled state reduces opacity to .44. Keyboard focus uses the global 3px lime outline.
- **Source and prompt choices:** dark, left-aligned controls (`{components.source-choice}`) with a lighter selected fill (`{components.source-choice-selected}`) and lime border. Hover lifts 1px. Source options include a lime icon above compact title and helper copy.
- **Report filter:** small segmented buttons on a pale tray. The selected segment turns dark with light text.

### Inputs and selection

- **Search and endpoint field:** dark inset field (`{components.model-search}`) with a muted border. Focus shifts the border to lime and adds the 2px halo. The endpoint variant has an attached lime Connect button.
- **Model list:** bordered rows with a circular radio indicator; selected rows turn green and the indicator gets a thick lime ring. Long names and IDs truncate within the row.

### Containers and reporting

- **Scorecard:** a light sheet (`{components.scorecard}`) with a thin border, small mono column labels, row rules, explicit PASS/MISS/UNSCORED/NOT RUN words, and tabular measurements. Each row offers Run details; the detail panel opens below the table and displays exact run metadata.
- **Paid guard:** warm brown inset panel (`{components.paid-guard}`) for hosted cap and call-limit controls.
- **Navigation:** dark rail with icon and text links. The active item uses a green fill and pale lime text. At compact widths, the rail shows icons; at phone width, it becomes a top strip.
- **Masthead dial:** an ornamental circular timing mark with inset rings. It has no data or progress semantics and is hidden from assistive technology.

## Do's and Don'ts

### Do:

- **Do** give run setup and task evidence distinct dark and light surfaces.
- **Do** show outcome words alongside pass and miss colors.
- **Do** keep long identifiers and wide result tables contained within their component boundaries.
- **Do** use the established 1350px, 900px, and 620px transitions when extending this console shell.

### Don't:

- **Don't** turn the dial into a progress or quality score without a real data definition.
- **Don't** imply model superiority from a tiny smoke suite.
- **Don't** rely on shadows to structure the report surface.
