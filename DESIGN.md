---
name: mattbench
description: A bright operator board for traceable model benchmark runs.
colors:
  signal-lime: "#d8ee6b"
  signal-lime-hover: "#edfa9b"
  coral-miss: "#ba553e"
  dark-canvas: "#161a19"
  dark-rail: "#111614"
  dark-header: "#1b231e"
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
  highlighted-choice-border: "#81945d"
  control-muted: "#70866d"
  pass-signal: "#70a344"
  score-fill: "#8fad38"
  paid-border: "#896c48"
  paid-input-border: "#a88b61"
  paid-accent: "#ddb871"
  paid-title: "#ffe4ac"
  paid-copy: "#eed5ad"
  paid-warning: "#ffc1ad"
  paid-input: "#211f1a"
  error-background: "#51312d"
  detail-background: "#e5ead9"
  badge-background: "#dce6c5"
  link-hover: "#25481d"
typography:
  display:
    fontFamily: "Bricolage Grotesque Variable, sans-serif"
    fontSize: "32px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-.03em"
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
  nano:
    fontFamily: "JetBrains Mono Variable, monospace"
    fontSize: "8px"
  micro:
    fontFamily: "JetBrains Mono Variable, monospace"
    fontSize: "9px"
  compact-body:
    fontFamily: "DM Sans Variable, sans-serif"
    fontSize: "11px"
  empty-title:
    fontFamily: "DM Sans Variable, sans-serif"
    fontSize: "14px"
  control:
    fontFamily: "DM Sans Variable, sans-serif"
    fontSize: "13px"
  mobile-brand:
    fontFamily: "Bricolage Grotesque Variable, sans-serif"
    fontSize: "21px"
  mobile-headline:
    fontFamily: "Bricolage Grotesque Variable, sans-serif"
    fontSize: "26px"
  mobile-display:
    fontFamily: "Bricolage Grotesque Variable, sans-serif"
    fontSize: "25px"
  empty-symbol:
    fontFamily: "Bricolage Grotesque Variable, sans-serif"
    fontSize: "42px"
rounded:
  mark-cut: "1px"
  badge: "4px"
  tiny-control: "5px"
  input: "6px"
  small-container: "7px"
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

The console pairs a dark control surface with a warm paper report surface. Lime marks active work, while the paper area keeps task outcomes and measurements easy to scan. A compact header shows the workspace name and live counts, placing controls and results near the top of the page.

This is the first code-led visual direction, not an owner-approved brand identity. Its reusable character is a bright, instrument-like working surface with visible run identity and task-level evidence. The owner’s direction is “form and function, not sacrificing one for another”: visual character should serve the task without taking space from it.

**Key Characteristics:**

- Dark operation area beside a cream result sheet.
- Strong display type for short declarations; compact monospace for measurements and system labels.
- Lime for selection and action; coral and green for distinct result meanings.
- Thin boundaries and surface tone carry most of the hierarchy.

## Colors

The palette is warm black and cream with a sharp lime signal.

### Primary

- **Signal Lime** (`{colors.signal-lime}`) marks the active source, selected controls, run action, small status lights, and the header period. **Signal Lime Hover** (`{colors.signal-lime-hover}`) is the brighter interactive state.
- **Highlighted Choice Border** (`{colors.highlighted-choice-border}`) outlines the default all-cases choice. **Control Muted** (`{colors.control-muted}`) serves quiet control edges and icons.

### Secondary

- **Coral Miss** (`{colors.coral-miss}`) marks the report heading accent; the related **Miss Text** (`{colors.miss-text}`) marks failed task results. Their uses are distinct from the green pass text (`{colors.pass-text}`).
- **Pass Signal and Score Fill** (`{colors.pass-signal}`, `{colors.score-fill}`) distinguish activity dots and compact score bars from result text.
- **Paid Guard Accents** (`{colors.paid-border}`, `{colors.paid-input-border}`, `{colors.paid-accent}`, `{colors.paid-title}`, `{colors.paid-copy}`, `{colors.paid-warning}`) keep spending controls and warnings legible on their warm inset.

### Neutral

- **Dark Canvas, Rail, Header, and Panel** (`{colors.dark-canvas}`, `{colors.dark-rail}`, `{colors.dark-header}`, `{colors.dark-panel}`) separate the frame, navigation, workspace summary, and work area by tone.
- **Dark Control, Field, and Selected** (`{colors.dark-control}`, `{colors.dark-field}`, `{colors.dark-selected}`) differentiate interactive states within the work area.
- **Light Panel and Sheet** (`{colors.light-panel}`, `{colors.light-sheet}`) make the report feel like an inserted paper record.
- **Light and Dark Text** (`{colors.light-text}`, `{colors.dark-text}`), their muted counterparts, and the two border colors support readable hierarchy on each surface.
- **Paid Guard** (`{colors.paid-guard}`) gives hosted-run spending controls a separate warm brown zone.
- **Paid Input, Error Background, Detail Background, and Badge Background** (`{colors.paid-input}`, `{colors.error-background}`, `{colors.detail-background}`, `{colors.badge-background}`) preserve the distinct nested surfaces used by forms, feedback, run metadata, and compact labels.
- **Link Hover** (`{colors.link-hover}`) deepens the interactive run-detail link without changing its underline cue.

**The Signal Rule.** Reserve lime for active work, selection, and the main action; keep outcome words explicit so color never carries the result alone.

## Typography

**Display Font:** Bricolage Grotesque Variable (sans-serif fallback). **Body Font:** DM Sans Variable (sans-serif fallback). **Measurement Font:** JetBrains Mono Variable (monospace fallback).

The broad, tightly spaced display face gives the board its voice. The simpler body face carries control copy; the mono face distinguishes system labels, IDs, numbers, and timing.

### Hierarchy

- **Display** (`{typography.display}`): compact workspace title with a lime period.
- **Headline** (`{typography.headline}`): work and report section headings; the small colored period is an accent, not a substitute for the title.
- **Body** (`{typography.body}`): compact explanations around controls and the scorecard.
- **Label** (`{typography.label}`): uppercase system labels and status tags.
- **Measure** (`{typography.measure}`): tabular scores, times, tokens, and cost. Numeric cells use tabular figures.
- **Small control and mobile steps** (`{typography.nano}`, `{typography.micro}`, `{typography.compact-body}`, `{typography.control}`, `{typography.empty-title}`, `{typography.mobile-brand}`, `{typography.mobile-headline}`, `{typography.mobile-display}`, `{typography.empty-symbol}`): the actual compact labels, empty-state title, phone headings, and empty-state mark. These are component-specific steps, not interchangeable body sizes.

**The Measurement Rule.** Put exact values in a mono treatment near the task or run they describe; keep explanatory prose in DM Sans.

## Layout

The desktop shell uses a 220px navigation rail and a flexible main column. At 1350px and below, the rail contracts to 68px. The compact workspace header is about 92px tall and presents task and run counts. The work area places a 390–430px dark setup panel beside a flexible light report panel; at 900px and below, those panels stack. At 620px and below, navigation becomes a 61px top strip, the header wraps with a 25px title, and the panels use a 17px horizontal inset. The page has a 320px minimum width.

The source and prompt options use three equal columns with a 7px gap. Fields have a 27px bottom rhythm. The scorecard table keeps a 680px minimum width inside its own horizontal scroll container, protecting the page from horizontal overflow at phone width. The compact header puts the case menu and scorecard much higher in the first viewport.

## Elevation & Depth

The board is mostly flat. Tonal surfaces and 1px borders separate major areas and controls. Status lights have a restrained glow, and the primary button lifts by 2px with a shadow on hover. The search field gets a 2px lime focus halo. These effects communicate interaction rather than decoration.

**The Flat Record Rule.** Keep report data on the cream plane; use borders and spacing to separate rows before adding lift.

## Shapes

Controls use compact rounded rectangles: 8px fields and report containers, 9px navigation and choice controls, and a 10px paid guard. Badges have 4px corners; small filter buttons, nested inputs, and message trays use the documented 5px, 6px, and 7px steps. Model selection dots and status lights are circular. The brand mark is three tilted lime bars with uneven heights and a 1px lower cut. Report rows stay rectangular and rule-separated.

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
- **Workspace header:** a compact title with counts of pinned cases and recorded runs. It uses the same dark surface and display type as the rest of the console.

## Do's and Don'ts

### Do:

- **Do** give run setup and task evidence distinct dark and light surfaces.
- **Do** show outcome words alongside pass and miss colors.
- **Do** keep long identifiers and wide result tables contained within their component boundaries.
- **Do** use the established 1350px, 900px, and 620px transitions when extending this console shell.

### Don't:

- **Don't** add a large decorative hero above the run controls and results.
- **Don't** imply model superiority from a tiny smoke suite.
- **Don't** rely on shadows to structure the report surface.
