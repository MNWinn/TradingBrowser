# Minimal UI Research + Applied Direction (Palantir/Anduril-Inspired)

Date: 2026-03-18

## Research signals used

### Palantir
- Palantir Foundry docs emphasize reusable interfaces and consistency across complex workflows.
- Blueprint (Palantir open-source UI toolkit) describes itself as optimized for **complex, data-dense desktop interfaces**.

### Anduril
- Public Lattice command-and-control materials describe a human-machine interface built for high-complexity operations.
- Product/team materials consistently indicate mission workflows where speed, clarity, and reduced cognitive load matter.

### Cross-enterprise dashboard best practices
Common recommendations across enterprise dashboard references:
- prioritize primary workflows over decorative UI
- minimize color use, reserve color for status/severity only
- use progressive disclosure for advanced controls
- keep layout modular and predictable

## Design principles adopted for TradingBrowser

1. **Monochrome first**
   - white/black/gray base
   - color only for alerts/severity

2. **Low decoration, high structure**
   - flat surfaces, subtle borders, small radius
   - reduced motion and effects

3. **Progressive disclosure**
   - collapse advanced controls behind “View controls”
   - show critical actions by default

4. **Operational status in one line**
   - global status strip includes mode, bias, compliance open/overdue

5. **Density + consistency**
   - compact spacing and repeated interaction patterns

## What was implemented in this pass

### Minimal style refinement
- Updated global style tokens and components to a flatter, cleaner look.
- Reduced border radii and motion.

File:
- `frontend/app/globals.css`

### Dashboard simplification
- Replaced always-visible advanced toggles with a compact top bar + collapsible controls (`details/summary`).
- Kept only immediate actions visible.

File:
- `frontend/app/dashboard/page.tsx`

### Compliance operations continuation (Phase 2.5 direction)
- Added assignee filtering support in compliance list/export APIs.
- Added ownership assignment in compliance console.
- Added per-violation timeline panel.
- Added dashboard SLA overdue alert strip.

Files:
- `backend/app/routers/compliance.py`
- `frontend/lib/api.ts`
- `frontend/app/compliance/page.tsx`
- `frontend/app/dashboard/page.tsx`

## Next UI step (recommended)

To move even closer to a Palantir/Anduril operational feel:
- remove emoji/iconography entirely where present
- enforce one typography scale (12/14/16)
- convert page-level cards to 2-column split layouts with fixed left nav rail
- introduce keyboard-first quick command palette (⌘K / Ctrl+K)
