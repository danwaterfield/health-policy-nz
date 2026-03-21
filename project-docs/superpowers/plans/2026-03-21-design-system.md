# Design System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all inline styles with a CSS design system and restructure the access page to put the map first.

**Architecture:** Add CSS custom properties and component classes to `src/style.css`. Then sweep each `.md` page to replace inline `style="..."` with CSS classes. The access page also gets reordered. No pipeline or JS changes.

**Tech Stack:** CSS custom properties, Observable Framework theme variables.

**Spec:** `project-docs/superpowers/specs/2026-03-21-design-system.md`

---

## File Structure

### Modified files
- `src/style.css` — expand from 47 lines (print-only) to ~130 lines (design tokens + component classes)
- `src/access.md` — restructure section order + replace inline styles with classes
- `src/index.md` — replace inline styles with classes
- `src/equity.md` — replace inline styles with classes
- `src/scorecard.md` — replace inline styles with classes
- `src/explorer.md` — replace inline styles with classes
- `src/forecast.md` — replace inline styles with classes
- `src/trends.md` — replace inline styles with classes
- `src/workforce.md` — replace inline styles with classes
- `src/blind-spots.md` — replace inline styles with classes
- `src/autoresearch.md` — replace inline styles with classes

### No new files, no deleted files.

---

## Task 1: Build the CSS design system

**Files:**
- Modify: `src/style.css`

- [ ] **Step 1: Add design tokens (custom properties)**

Add the following BEFORE the existing `@media print` block in `src/style.css`:

```css
:root {
  /* Data colours — charts only */
  --color-adverse: #c4391d;
  --color-favourable: #2166ac;
  --color-neutral: #969696;

  /* Ethnicity (Wong colorblind palette) */
  --color-maori: #e69f00;
  --color-pacific: #56b4e9;
  --color-asian: #009e73;
  --color-european: #0072b2;
  --color-total: #555;

  /* Status */
  --color-on-track: #2d8a4e;
  --color-at-risk: #e5850b;
  --color-off-track: #c4391d;

  /* Facilities */
  --color-gp: #2d8a4e;
  --color-hospital: #7b3294;

  /* Typography */
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-stat: 1.75rem;
  --weight-normal: 400;
  --weight-medium: 500;
  --weight-bold: 600;
  --leading-tight: 1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.75;

  /* Spacing */
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2rem;
  --space-2xl: 3rem;
}
```

- [ ] **Step 2: Add component classes**

Add after the design tokens:

```css
/* Stat cards */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--space-md);
  margin: var(--space-lg) 0;
}

.stat-card {
  padding: var(--space-md);
  border: 1px solid var(--theme-foreground-faintest, #e0e0e0);
  border-radius: 4px;
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--theme-foreground-faint, #999);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: var(--space-xs);
}

.stat-value {
  font-size: var(--text-stat);
  font-weight: var(--weight-bold);
  color: var(--theme-foreground, #222);
  line-height: var(--leading-tight);
}

.stat-unit {
  font-size: var(--text-sm);
  font-weight: var(--weight-normal);
  color: var(--theme-foreground-faint, #999);
}

.stat-sub {
  font-size: var(--text-xs);
  color: var(--theme-foreground-faint, #999);
  margin-top: var(--space-xs);
}

/* Note / callout — replaces all alert boxes */
.note {
  font-size: var(--text-sm);
  color: var(--theme-foreground-muted, #666);
  line-height: var(--leading-relaxed);
  padding-left: var(--space-md);
  border-left: 2px solid var(--theme-foreground-faintest, #e0e0e0);
  margin: var(--space-lg) 0;
}

.note strong {
  color: var(--theme-foreground, #222);
}

/* Methodology footer */
.methodology {
  font-size: var(--text-sm);
  color: var(--theme-foreground-faint, #999);
  line-height: var(--leading-relaxed);
  margin-top: var(--space-2xl);
  padding-top: var(--space-lg);
  border-top: 1px solid var(--theme-foreground-faintest, #e0e0e0);
}

.methodology p {
  margin: var(--space-sm) 0;
}

.methodology strong {
  color: var(--theme-foreground-muted, #666);
}

/* Collapsible panels */
.details-panel {
  border: 1px solid var(--theme-foreground-faintest, #e0e0e0);
  border-radius: 4px;
  padding: var(--space-sm) var(--space-md);
  margin: var(--space-md) 0;
}

.details-panel summary {
  cursor: pointer;
  font-weight: var(--weight-medium);
  padding: var(--space-xs) 0;
  color: var(--theme-foreground, #222);
}

/* Scenario impact panel */
.scenario-impact {
  border: 1px solid var(--theme-foreground-faintest, #e0e0e0);
  border-radius: 4px;
  padding: var(--space-md);
  margin: var(--space-md) 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--space-md);
}

.impact-label {
  font-size: var(--text-xs);
  color: var(--theme-foreground-faint, #999);
}

.impact-value {
  font-size: var(--text-lg);
  font-weight: var(--weight-bold);
  color: var(--theme-foreground, #222);
}

/* Lead paragraph — intro text for pages */
.lead {
  font-size: var(--text-lg);
  line-height: var(--leading-relaxed);
  color: var(--theme-foreground-muted, #666);
  margin-bottom: var(--space-lg);
}
```

- [ ] **Step 3: Verify build**

```bash
npm run build 2>&1 | tail -3
```
Expected: `ok (no errors)` or similar success.

- [ ] **Step 4: Commit**

```bash
git add src/style.css
git commit -m "feat: add CSS design system — tokens, stat cards, notes, methodology"
```

---

## Task 2: Restructure and restyle the access page

**Files:**
- Modify: `src/access.md`

This is the largest task. The page needs two changes:
1. **Reorder sections** so the map comes first
2. **Replace all inline styles** with CSS classes

- [ ] **Step 1: Read the current file**

Read `src/access.md` in its entirety. Understand the current section order and identify all inline `style="..."` attributes on UI elements (not charts).

- [ ] **Step 2: Reorder sections**

Move code blocks to achieve this order:
1. Title + one-line description (keep as-is)
2. Data loading blocks (DuckDB, FileAttachments — keep grouped at top)
3. Leaflet CSS + style block
4. **Map** (move the entire Leaflet map block up — currently around line 350-480)
5. Controls bar: facility type selector, LISA toggle, autoresearch toggle (move above map or just below)
6. Autoresearch summary card (if toggled)
7. Stat cards (the 4-across grid)
8. Note: equity narrative
9. Scenario section (make it a visible `## What-if scenarios` with controls, NOT hidden in `<details>`)
10. Scenario impact (if active)
11. Scatter + quintile bar charts
12. Facility deserts table
13. Analyst tools (CSV export, summary stats, cross-tab — can stay in `<details>`)
14. Facility distribution charts
15. Methodology footer

- [ ] **Step 3: Replace inline styles with CSS classes**

For every stat card: replace the inline `style="..."` div soup with:
```html
<div class="stat-grid">
  <div class="stat-card">
    <div class="stat-label">Q1 (least deprived)</div>
    <div class="stat-value">4<span class="stat-unit"> min</span></div>
    <div class="stat-sub">pop-weighted median</div>
  </div>
  ...
</div>
```

For narrative notes: replace inline-styled paragraphs with `<p class="note">`.

For methodology footer: replace the inline-styled `<div>` with `<div class="methodology">`.

For the scenario details panel: replace inline-styled `<details>` with `<details class="details-panel">`.

For the scenario impact box: replace inline-styled grid with `<div class="scenario-impact">`.

- [ ] **Step 4: Verify build**

```bash
npm run build 2>&1 | tail -3
```

- [ ] **Step 5: Visual check**

```bash
npm run dev
```
Open http://127.0.0.1:3000/access. Verify:
- Map appears near the top
- Stat cards have thin borders, no coloured accents
- Notes have subtle left border
- Methodology footer is visually separated
- Dark mode works (toggle in bottom-left)

- [ ] **Step 6: Commit**

```bash
git add src/access.md
git commit -m "feat: restructure access page — map first, CSS classes replace inline styles"
```

---

## Task 3: Restyle index page

**Files:**
- Modify: `src/index.md`

- [ ] **Step 1: Read the file, identify inline styles**
- [ ] **Step 2: Replace stat cards with `.stat-grid` + `.stat-card` classes**
- [ ] **Step 3: Replace info boxes with `.note` class**
- [ ] **Step 4: Replace methodology/source text with `.methodology` class**
- [ ] **Step 5: Build and verify**
```bash
npm run build 2>&1 | tail -3
```
- [ ] **Step 6: Commit**
```bash
git add src/index.md
git commit -m "feat: restyle index page with design system classes"
```

---

## Task 4: Restyle equity page

**Files:**
- Modify: `src/equity.md`

- [ ] **Step 1: Read the file, identify inline styles on UI elements** (not chart configs)
- [ ] **Step 2: Replace stat cards, info boxes, bias estimate panels with CSS classes**
- [ ] **Step 3: Replace methodology/source footer with `.methodology` class**
- [ ] **Step 4: Standardise data colours** — ensure gap colours use `--color-adverse` / `--color-favourable`, ethnicity colours use the Wong palette variables
- [ ] **Step 5: Build and verify**
- [ ] **Step 6: Commit**
```bash
git add src/equity.md
git commit -m "feat: restyle equity page with design system classes"
```

---

## Task 5: Restyle remaining pages

**Files:**
- Modify: `src/scorecard.md`, `src/explorer.md`, `src/forecast.md`, `src/trends.md`, `src/workforce.md`, `src/blind-spots.md`, `src/autoresearch.md`

- [ ] **Step 1: Read each file, identify inline styles**
- [ ] **Step 2: Replace all inline-styled cards/boxes/footers with CSS classes** across all 7 files
- [ ] **Step 3: Standardise data colours across all chart configs** — use CSS variable values where possible, or at minimum use consistent hex values from the spec
- [ ] **Step 4: Build and verify**
```bash
npm run build 2>&1 | tail -3
```
- [ ] **Step 5: Commit**
```bash
git add src/scorecard.md src/explorer.md src/forecast.md src/trends.md src/workforce.md src/blind-spots.md src/autoresearch.md
git commit -m "feat: restyle all remaining pages with design system classes"
```

---

## Task 6: Final verification and push

- [ ] **Step 1: Run full test suite**
```bash
python3.12 -m pytest tests/ -v
```

- [ ] **Step 2: Build**
```bash
npm run build
```

- [ ] **Step 3: Visual review of every page in dev server**
```bash
npm run dev
```
Check each page in both light and dark mode. Verify:
- No inline `style="..."` on UI elements (cards, notes, footers) — only on charts/maps
- Consistent typography — no random font sizes
- Stat cards look identical across pages
- Dark mode is legible everywhere
- Access page map is near the top

- [ ] **Step 4: Push**
```bash
git push origin main
gh workflow run "Refresh and Deploy"
```
