# Web Design

Build modern, beautiful, accessible web interfaces that look professionally designed.

## Principles
- **Restraint over decoration.** One accent color, one neutral ramp, generous whitespace. Avoid gradients-on-everything and drop shadows everywhere.
- **Type scale.** Use a clear hierarchy (e.g. 12/14/16/20/28/40px). One display/serif for headings is optional; a clean sans (Inter, system-ui) for body. Line-height 1.5–1.7 for body.
- **Spacing system.** Use an 4px/8px grid. Consistent padding (16/24px) and gaps. Align everything to the grid.
- **Color.** Pick a neutral background (off-white #FAF9F5 or near-black), a single accent, and semantic colors (success/warn/error). Maintain WCAG AA contrast (≥4.5:1 for text).
- **Components.** Rounded corners (8–14px), 1px hairline borders in a soft neutral, subtle hover states. Buttons: clear primary vs ghost. Inputs: visible focus ring.
- **Motion.** Subtle, fast (150–250ms), ease-out. Animate opacity/transform only. Respect `prefers-reduced-motion`.
- **Responsive.** Mobile-first. Fluid containers, `max-width` ~1100px for reading. Test at 375 / 768 / 1280.

## Workflow
1. Define tokens first (colors, spacing, radius, type) as CSS variables.
2. Build layout with fl/grid; never hardcode magic numbers — use the scale.
3. Add states (hover/focus/active/disabled) and empty/loading/error states.
4. Verify contrast and keyboard navigation.
5. Polish: consistent icon set, aligned baselines, no orphaned elements.

## Stacks to prefer
- Static: semantic HTML + a single CSS file with variables.
- App: React + Vite + Tailwind, or plain HTML/CSS for small sites.
Always run/preview the result and iterate on the actual rendered output.
