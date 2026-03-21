# Design System — Research Publication Style

**Date**: 2026-03-21
**Status**: Approved
**Scope**: CSS design system + page restructuring. No pipeline changes.

## Goal

Replace 100+ inline styles across all pages with a single CSS design system that gives the dashboard the feel of a well-designed research publication (Our World in Data, The Lancet data pages) rather than a generic AI-generated dashboard.

## Principles

1. **Colour carries information, not decoration.** No coloured card borders, no tinted backgrounds, no alert-style boxes. Colour appears only in charts where it encodes data.
2. **Typography creates hierarchy.** Size and weight differences do the work that colour and borders currently do.
3. **Work within Observable's theme.** Keep the sidebar, dark mode, table styling. Add a CSS layer on top, don't fight the framework.
4. **Less is more.** Fewer component classes, fewer visual patterns, fewer decisions.

## Colour System

### Data colours (charts only)

```css
--color-adverse: #c4391d;     /* warm red — gaps, off-track, high travel time */
--color-favourable: #2166ac;  /* blue — favourable gaps, good access */
--color-neutral: #969696;     /* grey — neutral, no data, baseline */
```

### Ethnicity (Wong colorblind palette)

```css
--color-maori: #e69f00;
--color-pacific: #56b4e9;
--color-asian: #009e73;
--color-european: #0072b2;
--color-total: #555555;
```

### Status (scorecard only)

```css
--color-on-track: #2d8a4e;
--color-at-risk: #e5850b;
--color-off-track: #c4391d;   /* same as adverse — intentional */
```

### Facility markers (access page)

```css
--color-gp: #2d8a4e;          /* green — same as on-track */
--color-hospital: #7b3294;    /* purple — distinct from all other uses */
```

### UI chrome

No custom colours. Use Observable's theme variables exclusively:
- `var(--theme-foreground)` for text
- `var(--theme-foreground-muted)` for secondary text
- `var(--theme-foreground-faint)` for tertiary text
- `var(--theme-foreground-faintest)` for borders
- `var(--theme-background)` for backgrounds
- `var(--theme-background-alt)` for subtle card backgrounds (only when needed for grouping)

**Rule**: If you're writing `color: #` or `background: #` in a `.md` file for a UI element (not a chart), you're doing it wrong. Use a CSS class instead.

## Typography

```css
--text-xs: 0.75rem;      /* footnotes, source attributions, badges */
--text-sm: 0.875rem;     /* secondary labels, methodology notes, table captions */
--text-base: 1rem;       /* body text */
--text-lg: 1.125rem;     /* lead paragraphs, section intros */
--text-stat: 1.75rem;    /* stat card numbers */

--weight-normal: 400;
--weight-medium: 500;
--weight-bold: 600;       /* not 700 — more refined */

--leading-tight: 1.25;
--leading-normal: 1.5;
--leading-relaxed: 1.75;
```

## Spacing

```css
--space-xs: 0.25rem;
--space-sm: 0.5rem;
--space-md: 1rem;
--space-lg: 1.5rem;
--space-xl: 2rem;
--space-2xl: 3rem;
```

## Component Classes

### `.stat-grid`

Container for stat cards. 4 columns on desktop, 2 on mobile.

```css
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--space-md);
  margin: var(--space-lg) 0;
}
```

### `.stat-card`

Individual metric card. Thin border, no background, no coloured accent.

```css
.stat-card {
  padding: var(--space-md);
  border: 1px solid var(--theme-foreground-faintest);
  border-radius: 4px;
}
.stat-card .stat-label {
  font-size: var(--text-xs);
  color: var(--theme-foreground-faint);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: var(--space-xs);
}
.stat-card .stat-value {
  font-size: var(--text-stat);
  font-weight: var(--weight-bold);
  color: var(--theme-foreground);
  line-height: var(--leading-tight);
}
.stat-card .stat-unit {
  font-size: var(--text-sm);
  font-weight: var(--weight-normal);
  color: var(--theme-foreground-faint);
}
.stat-card .stat-sub {
  font-size: var(--text-xs);
  color: var(--theme-foreground-faint);
  margin-top: var(--space-xs);
}
```

### `.note`

Replaces all alert/info/callout boxes. No background colour. Subtle left border.

```css
.note {
  font-size: var(--text-sm);
  color: var(--theme-foreground-muted);
  line-height: var(--leading-relaxed);
  padding-left: var(--space-md);
  border-left: 2px solid var(--theme-foreground-faintest);
  margin: var(--space-lg) 0;
}
.note strong {
  color: var(--theme-foreground);
}
```

### `.methodology`

Footer sections with sources, caveats, methodology.

```css
.methodology {
  font-size: var(--text-sm);
  color: var(--theme-foreground-faint);
  line-height: var(--leading-relaxed);
  margin-top: var(--space-2xl);
  padding-top: var(--space-lg);
  border-top: 1px solid var(--theme-foreground-faintest);
}
.methodology p {
  margin: var(--space-sm) 0;
}
.methodology strong {
  color: var(--theme-foreground-muted);
}
```

### `.details-panel`

Styled `<details>` for collapsible sections.

```css
.details-panel {
  border: 1px solid var(--theme-foreground-faintest);
  border-radius: 4px;
  padding: var(--space-sm) var(--space-md);
  margin: var(--space-md) 0;
}
.details-panel summary {
  cursor: pointer;
  font-weight: var(--weight-medium);
  padding: var(--space-xs) 0;
  color: var(--theme-foreground);
}
```

### `.scenario-impact`

The before/after comparison panel when a scenario is active. No yellow/amber background.

```css
.scenario-impact {
  border: 1px solid var(--theme-foreground-faintest);
  border-radius: 4px;
  padding: var(--space-md);
  margin: var(--space-md) 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--space-md);
}
.scenario-impact .impact-label {
  font-size: var(--text-xs);
  color: var(--theme-foreground-faint);
}
.scenario-impact .impact-value {
  font-size: var(--text-lg);
  font-weight: var(--weight-bold);
  color: var(--theme-foreground);
}
```

### No other classes.

Charts, tables, inputs, and the map use their respective library defaults (Plot, Inputs.table, Leaflet). The fewer custom components, the more it feels like research rather than a product.

## Access Page Restructure

Current order: title → controls → scenarios → stats → map → charts → tables → methodology

New order:
```
1. Title + one-line description
2. Map (hero — first thing visible)
3. Controls bar: [Facility type ▾] [LISA toggle] [Autoresearch toggle]
4. Stat cards (4-across)
5. Note: equity narrative ("Q5 median is low because...")
6. Scenario controls (visible section, not hidden <details>)
7. Scenario impact (if active)
8. Deprivation vs access (scatter + quintile bars)
9. Facility deserts table
10. Analyst tools (<details>: CSV export, summary stats, cross-tab, spatial stats)
11. Facility distribution charts
12. Methodology footer
```

The map moves from position ~6 to position 2. This is the single biggest UX improvement.

## Implementation Approach

1. **Expand `src/style.css`** with all CSS variables and component classes defined above.
2. **Restructure `src/access.md`** — reorder sections, replace all inline styles with CSS classes.
3. **Update remaining pages** (`equity.md`, `index.md`, `scorecard.md`, etc.) — replace inline styles with CSS classes. Don't restructure content, just restyle.
4. **Consolidate colour palettes** — ensure all charts across all pages use the same colour constants.

## What NOT to do

- Don't add a CSS framework (Tailwind, Bootstrap). The design system is 80 lines of CSS.
- Don't change the Observable Framework theme. Keep `air` + `near-midnight`.
- Don't add custom fonts. Observable's default (Source Serif 4) is excellent for research.
- Don't restructure any page except access.md. The other pages just need restyling.
- Don't touch chart configurations beyond standardising colours.
