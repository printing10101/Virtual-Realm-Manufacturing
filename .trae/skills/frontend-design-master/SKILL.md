---
name: "frontend-design-master"
description: "Applies brand-grade DESIGN.md systems to frontend UI generation. Invoke when designing web pages, creating frontend components, building landing pages, or when user mentions brand names like Stripe, Apple, Notion, Vercel, etc."
---

# Frontend Design Master

## Overview

This skill integrates the **awesome-design-md** collection into Trae, providing 73+ brand-grade DESIGN.md files for pixel-perfect frontend generation. It serves two purposes:

1. **AI Context**: Guides the AI agent to generate UI that matches specific brand aesthetics
2. **File Copy**: Copies the selected DESIGN.md to the user's project root for persistent reference

## Core Capabilities

### 1. Brand Catalog Display

Show available design systems organized by category:

**AI & LLM Platforms**: Claude, Cohere, ElevenLabs, Minimax, Mistral AI, Ollama, OpenCode AI, Replicate, Runway, Together AI, VoltAgent, xAI

**Developer Tools & IDEs**: Cursor, Expo, Lovable, Raycast, Superhuman, Vercel, Warp

**Backend, Database & DevOps**: ClickHouse, Composio, HashiCorp, MongoDB, PostHog, Sanity, Sentry, Supabase

**Productivity & SaaS**: Cal.com, Intercom, Linear, Mintlify, Notion, Resend, Zapier

**Design & Creative Tools**: Airtable, Clay, Figma, Framer, Miro, Webflow

**Fintech & Crypto**: Binance, Coinbase, Kraken, Mastercard, Revolut, Stripe, Wise

**E-commerce & Retail**: Airbnb, Meta, Nike, Shopify, Starbucks

**Media & Consumer Tech**: Apple, HP, IBM, NVIDIA, Pinterest, PlayStation, SpaceX, Spotify, The Verge, Uber, Vodafone, WIRED

**Automotive**: BMW, BMW M, Bugatti, Ferrari, Lamborghini, Renault, Tesla

### 2. DESIGN.md Application

When user selects a brand:

1. **Copy DESIGN.md** to project root: `skills/awesome-design-md-main/design-md/<brand>/DESIGN.md` → project root
2. **Read the DESIGN.md** and apply its specifications during code generation:
   - Color palette and semantic roles
   - Typography rules (font families, hierarchy)
   - Component stylings (buttons, cards, inputs, navigation)
   - Layout principles (spacing, grid, whitespace)
   - Depth & elevation (shadows, surfaces)
   - Responsive behavior (breakpoints, touch targets)

### 3. Code Generation Integration

When generating frontend code, ALWAYS:

1. Check if DESIGN.md exists in project root
2. If yes, strictly follow its design specifications
3. If no, offer to apply a brand from the catalog
4. Generate production-grade code with the brand's visual identity

### 4. Custom DESIGN.md Support

Users can add custom designs:

1. Create new directory: `c:\Users\Lenovo\Desktop\灵境制造（上线版）\skills\awesome-design-md-main\design-md\<custom-name>\`
2. Add DESIGN.md following [Stitch DESIGN.md format](https://stitch.withgoogle.com/docs/design-md/format/)
3. Custom designs are automatically included in the brand catalog

## Usage Workflow

### Scenario 1: User asks to design a page

**User**: "帮我设计一个登录页面"

**Response**:
1. Show brand catalog organized by category
2. Ask: "你想应用哪个品牌的设计风格？也可以输入自定义名称"
3. After selection:
   - Copy DESIGN.md to project root
   - Read DESIGN.md specifications
   - Generate login page following the design system

### Scenario 2: User specifies a brand

**User**: "用 Stripe 的风格设计支付页面"

**Response**:
1. Locate `design-md/stripe/DESIGN.md`
2. Copy to project root
3. Read and apply Stripe's design specs:
   - Signature purple gradients
   - Weight-300 typography
   - Premium spacing and elevation
4. Generate payment page

### Scenario 3: User wants to see design tokens

**User**: "看看 Notion 的设计系统"

**Response**:
1. Read `design-md/notion/DESIGN.md`
2. Display:
   - Color palette with hex values
   - Typography hierarchy
   - Component examples
   - Layout principles
3. Ask: "要应用到你的项目吗？"

### Scenario 4: User adds custom design

**User**: "我想添加自己的设计系统"

**Response**:
1. Guide user to create `design-md/<name>/DESIGN.md`
2. Provide DESIGN.md template structure:
   ```markdown
   ---
   # 1. Visual Theme & Atmosphere
   # 2. Color Palette & Roles
   # 3. Typography Rules
   # 4. Component Stylings
   # 5. Layout Principles
   # 6. Depth & Elevation
   # 7. Do's and Don'ts
   # 8. Responsive Behavior
   # 9. Agent Prompt Guide
   ---
   ```
3. After creation, make it available in catalog

## DESIGN.md Location

All design files are stored at:
`c:\Users\Lenovo\Desktop\灵境制造（上线版）\skills\awesome-design-md-main\design-md\`

Each brand directory contains:
- `DESIGN.md` - The complete design system
- `README.md` - Brand description and preview links

## Integration with Frontend Skills

This skill works alongside existing frontend skills:

- **When to use this skill**: User needs brand-specific design guidance
- **When to use frontend-design**: Generic UI creation without brand requirements
- **When to use web-dev**: Building complete websites from scratch

## Best Practices

1. **Always copy DESIGN.md** to project root before generating code
2. **Never mix design systems** - use one brand per page/component
3. **Follow typography rules strictly** - font families, weights, sizes matter
4. **Respect color semantics** - primary, accent, surface colors have specific roles
5. **Maintain spacing scale** - don't invent arbitrary margins/padding
6. **Preview with preview.html** if user wants to see design tokens visually

## Quick Reference

Common triggers for this skill:
- "设计前端页面" / "Design frontend page"
- "创建登录页" / "Create login page"
- "用 XX 风格" / "In the style of XX"
- "应用品牌设计" / "Apply brand design"
- "看看 XX 的设计系统" / "Show me XX's design system"
- "复制 DESIGN.md" / "Copy DESIGN.md"
- Brand names: Stripe, Apple, Notion, Vercel, Linear, Figma, etc.
