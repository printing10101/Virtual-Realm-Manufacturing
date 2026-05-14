---
name: "frontend-unified"
description: "Create production-grade frontend interfaces with brand-level design. Invoke when building web pages, components, landing pages, apps, dashboards, or when user mentions design/frontend/UI."
---

# Frontend Unified

Create distinctive, production-grade frontend interfaces that avoid generic AI aesthetics. Implement working code with exceptional attention to visual design, composition, and creative choices.

## Design Thinking

Before coding, understand context and commit to a BOLD aesthetic direction:

- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme: brutally minimal, maximalist, retro-futuristic, organic, luxury, playful, editorial, brutalist, art deco, pastel, industrial, etc.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE?

Then define the working model:

- **Visual thesis**: One sentence describing mood, material, and energy
- **Content plan**: Hero, support, detail, final CTA
- **Interaction thesis**: 2-3 motion ideas that change the feel of the page

**CRITICAL**: Choose a clear conceptual direction and execute with precision.

## Aesthetic Guidelines

- **Typography**: Choose distinctive, beautiful fonts. Avoid generic fonts (Inter, Roboto, Arial). Pair a distinctive display font with a refined body font. Two typefaces max unless clear reason.
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables. Dominant colors with sharp accents outperform timid palettes. One accent color by default.
- **Motion**: Use CSS-only solutions for HTML, Motion library for React. Ship 2-3 intentional motions: one hero entrance, one scroll-linked/sticky effect, one hover/reveal transition. Fast, smooth, consistent. Remove if ornamental.
- **Spatial Composition**: Unexpected layouts, asymmetry, overlap, diagonal flow, grid-breaking, generous negative space OR controlled density.
- **Backgrounds**: Create atmosphere and depth. Gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows. Avoid solid default colors.
- **Copy**: Product language, not design commentary. Headlines carry meaning. Cut repetition. Every section has one responsibility: explain, prove, deepen, or convert.

## Beautiful Defaults

- Start with composition, not components.
- Prefer full-bleed hero or full-canvas visual anchor.
- Brand/product name is the loudest text.
- Copy scannable in seconds.
- Use whitespace, alignment, scale, cropping, contrast before adding chrome.
- Default to cardless layouts. Use sections, columns, dividers, media blocks.
- First viewport is a poster, not a document.

## Landing Pages

Default sequence:

1. **Hero**: Brand/product, promise, CTA, one dominant visual
2. **Support**: One concrete feature, offer, or proof point
3. **Detail**: Atmosphere, workflow, product depth, or story
4. **Final CTA**: Convert, start, visit, or contact

Hero rules:
- One composition only, full-bleed with no inherited gutters
- Brand first, headline second, body third, CTA fourth
- No hero cards, stat strips, logo clouds, pill soup, floating dashboards
- Headlines 2-3 lines desktop, readable in one glance mobile
- Text column narrow, anchored to calm image area
- Strong contrast, clear tap targets

Viewport budget:
- Sticky/fixed header counts against hero
- Combined header + hero fits initial viewport
- Overlay header instead of stacking in normal flow

## App UI

Default to Linear-style restraint:
- Calm surface hierarchy, strong typography, few colors
- Dense but readable information, minimal chrome
- Cards only when the card is the interaction

Organize around:
- Primary workspace
- Navigation
- Secondary context/inspector
- One clear accent for action/state

Avoid:
- Dashboard-card mosaics
- Thick borders on every region
- Decorative gradients behind routine UI
- Multiple competing accent colors
- Ornamental icons that don't improve scanning

If a panel can be plain layout without losing meaning, remove card treatment.

## Utility Copy for Product UI

For dashboards, admin tools, operational workspaces:

- Prioritize orientation, status, action over promise, mood, brand voice
- Start with working surface: KPIs, charts, filters, tables, status
- Section headings say what area is or what user can do
- Good: "Selected KPIs", "Plan status", "Search metrics", "Top segments"
- Avoid aspirational hero lines, metaphors, campaign language on product surfaces
- If deleting 30% of copy improves the page, keep deleting

## Imagery

- Use at least one strong, real-looking image for brands, venues, editorial, lifestyle
- Prefer in-situ photography over abstract gradients or fake 3D
- Choose/crop images with stable tonal area for text
- No embedded signage, logos, typographic clutter
- First viewport needs a real visual anchor; decorative texture is not enough

## Hard Rules

- No cards by default
- No hero cards by default
- No boxed/center-column hero when brief calls for full bleed
- No more than one dominant idea per section
- No section needs many tiny UI devices to explain itself
- No headline overpowers brand on branded pages
- No filler copy
- No split-screen hero unless text sits on calm, unified side
- No more than two typefaces without clear reason
- No more than one accent color unless product has strong system

## Reject These Failures

- Generic SaaS card grid as first impression
- Beautiful image with weak brand presence
- Strong headline with no clear action
- Busy imagery behind text
- Sections repeating same mood statement
- Carousel with no narrative purpose
- App UI of stacked cards instead of layout

## Litmus Checks

1. Is brand/product unmistakable in first screen?
2. Is there one strong visual anchor?
3. Can page be understood by scanning headlines only?
4. Does each section have one job?
5. Are cards actually necessary?
6. Does motion improve hierarchy or atmosphere?
7. Would design still feel premium if all decorative shadows removed?

**Implementation**: Match complexity to aesthetic vision. Maximalist needs elaborate code with animations. Minimalist needs restraint, precision, spacing, typography. Elegance = executing the vision well.
