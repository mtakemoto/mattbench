# Design hook triage — 2026-10-11 UTC

**Observed:** The active design-system scan of `web/src/routes/console.css` reproduced 82 cached findings: 66 color occurrences (64 distinct values), 4 radius values, and 12 font-size occurrences (11 distinct values). The Svelte package boundary hid the root design file from a standalone scan, so `web/DESIGN.md` and `web/.impeccable/design.json` now link to the root files. The same scan then reproduced all 82 findings before the fixes.

**Fixed:** Near-duplicate colors were consolidated into the documented palette. Distinct dial, status, paid-guard, feedback, and detail-surface colors were added as semantic tokens. Two unused icon font-size declarations were removed; the other flagged type and radius values were documented. The current design scan reports zero findings for the CSS file. Desktop and 390px mobile views were visually checked; mobile document width is 390px.

**Suppressed:** None. **Left standing:** None. No ignore rule, file, or value was added.

## Color values

Each source value below was either replaced by the listed palette value or, if equal, retained and documented. Repeated findings for `#3b493d` and `#70866d` share their value-level resolution.

| Final palette value | Original flagged values |
| --- | --- |
| `#18231a` | `#203624` |
| `#25481d` | `#25481d` |
| `#343d35` | `#3b493d` |
| `#366e37` | `#335d30`, `#496e37` |
| `#40543d` | `#394c3b`, `#3b4b3d` |
| `#51312d` | `#51312d` |
| `#596b5c` | `#4e604f`, `#4f6251`, `#506450`, `#526052`, `#526454`, `#526b52`, `#536651`, `#586f6c`, `#5d725f`, `#5f735d`, `#617561` |
| `#698749` | `#698749` |
| `#70866d` | `#667b65`, `#667b68`, `#6a796c`, `#6c8069`, `#70866d`, `#72846e`, `#738274` |
| `#70a344` | `#70a344` |
| `#81945d` | `#81945d` |
| `#896c48` | `#896c48` |
| `#8fad38` | `#8fad38` |
| `#a88b61` | `#a88b61` |
| `#b3c2b2` | `#a6b6a2`, `#a9b69a`, `#adb9af`, `#adbbaa`, `#afc19d`, `#afc29f`, `#bdcaba`, `#bdcdb9`, `#becbbd`, `#c1ceb9`, `#c1cebb`, `#c8d7c3`, `#c8d8bb` |
| `#ba553e` | `#c75d43` |
| `#d0d5c4` | `#bbc9b4`, `#c0d0b6`, `#c9d3c1`, `#d7dece`, `#dedfd1`, `#dee2d1`, `#e2e5d8` |
| `#dce6c5` | `#dce6c5` |
| `#ddb871` | `#ddb871` |
| `#e5ead9` | `#e5ead9` |
| `#eed5ad` | `#eed5ad`, `#f1dfbc` |
| `#f0eee4` | `#e9efe5` |
| `#ffc1ad` | `#ffc1ad`, `#ffd0c5` |
| `#ffe4ac` | `#ffe2c2`, `#ffe4ac`, `#fff4dc` |

## Radius values

| Flagged value | Resolution |
| --- | --- |
| `1px` | Added to the rounded scale in `DESIGN.md`. |
| `5px` | Added to the rounded scale in `DESIGN.md`. |
| `6px` | Added to the rounded scale in `DESIGN.md`. |
| `7px` | Added to the rounded scale in `DESIGN.md`. |

## Font-size values

| Flagged value | Resolution |
| --- | --- |
| `11px` | Added as a component-specific type step in `DESIGN.md`. |
| `13px` | Added as a component-specific type step in `DESIGN.md`. |
| `14px` | Added as a component-specific type step in `DESIGN.md`. |
| `19px` | Removed unused icon sizing declarations. |
| `2.65rem` | Added as a component-specific type step in `DESIGN.md`. |
| `21px` | Added as a component-specific type step in `DESIGN.md`. |
| `23px` | Removed unused icon sizing declarations. |
| `26px` | Added as a component-specific type step in `DESIGN.md`. |
| `42px` | Added as a component-specific type step in `DESIGN.md`. |
| `8px` | Added as a component-specific type step in `DESIGN.md`. |
| `9px` | Added as a component-specific type step in `DESIGN.md`. |
