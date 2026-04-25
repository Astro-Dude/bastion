---
name: Citadel Command Center
colors:
  surface: '#10141a'
  surface-dim: '#10141a'
  surface-bright: '#353940'
  surface-container-lowest: '#0a0e14'
  surface-container-low: '#181c22'
  surface-container: '#1c2026'
  surface-container-high: '#262a31'
  surface-container-highest: '#31353c'
  on-surface: '#dfe2eb'
  on-surface-variant: '#c0c7d4'
  inverse-surface: '#dfe2eb'
  inverse-on-surface: '#2d3137'
  outline: '#8b919d'
  outline-variant: '#414752'
  surface-tint: '#a2c9ff'
  primary: '#a2c9ff'
  on-primary: '#00315c'
  primary-container: '#58a6ff'
  on-primary-container: '#003a6b'
  inverse-primary: '#0060aa'
  secondary: '#d8baff'
  on-secondary: '#430882'
  secondary-container: '#5d2d9c'
  on-secondary-container: '#cda8ff'
  tertiary: '#4be260'
  on-tertiary: '#00390c'
  tertiary-container: '#10bc3f'
  on-tertiary-container: '#004310'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d3e4ff'
  primary-fixed-dim: '#a2c9ff'
  on-primary-fixed: '#001c38'
  on-primary-fixed-variant: '#004882'
  secondary-fixed: '#eddcff'
  secondary-fixed-dim: '#d8baff'
  on-secondary-fixed: '#290055'
  on-secondary-fixed-variant: '#5b2b9a'
  tertiary-fixed: '#6fff7b'
  tertiary-fixed-dim: '#4be260'
  on-tertiary-fixed: '#002205'
  on-tertiary-fixed-variant: '#005316'
  background: '#10141a'
  on-background: '#dfe2eb'
  surface-variant: '#31353c'
typography:
  h1:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  h2:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  data-lg:
    fontFamily: JetBrains Mono
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
  data-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  data-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 16px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
  margin: 24px
---

## Brand & Style

The design system is engineered for high-stakes cybersecurity environments where speed of cognition and tactical authority are paramount. The brand personality is **vigilant, authoritative, and precise**, evoking the feeling of a digital fortress.

The aesthetic direction combines **Minimalism** with **High-Tech Tactical** influences. It utilizes a deep-space background to minimize eye strain during long shifts, while employing "glow-state" indicators to direct attention to critical anomalies. Layouts are strictly organized on a grid to reflect the order and control required in a Security Operations Center (SOC).

## Colors

The color palette of this design system is rooted in functional utility. The **Background (#0d1117)** and **Surface (#161b22)** provide a low-luminance foundation that makes data visualizations pop. 

The primary action color, **Commander Blue**, is used for interactive elements and primary navigation. **Oversight Purple** is reserved for high-level governance and administrative tasks. Semantic colors are strictly enforced: **Threat Red** is used sparingly to signify active breaches, while **Escalation Orange** indicates a rising priority level. 

**Glow Effects:** When a system status is "Threat" or "Escalation," use a 15-20% opacity glow (drop shadow) of the respective color to create a "breathing" emergency state.

## Typography

This design system utilizes a dual-font strategy to separate human-readable prose from machine-generated data.

- **Inter** is the workhorse for the UI shell, navigation, and descriptions. It provides maximum legibility for administrative oversight.
- **JetBrains Mono** (or Fira Code) is used exclusively for technical data points, including IP addresses, timestamps, hash values, and terminal feeds. This monospace choice ensures that character alignment is maintained in log tables, making it easier for analysts to spot patterns in strings.

Headlines should be kept compact. Use `label-caps` for section headers to create a "military-spec" aesthetic.

## Layout & Spacing

The layout philosophy follows a **Fluid Grid** model with a preference for high-density information display. The interface is divided into functional zones: a global navigation sidebar, a header for high-level "Citadel" metrics, and a main content area for dashboard widgets.

A strict 4px baseline grid ensures vertical rhythm. Widgets and cards should utilize `md (16px)` padding for internal content, while logs can drop to `sm (8px)` to maximize the amount of data visible on a single screen. Gutters are fixed at 16px to maintain a cohesive structure even when the viewport is resized.

## Elevation & Depth

In this design system, depth is communicated through **Tonal Layering** and **Subtle Outlines** rather than heavy shadows.

- **Level 0 (Background):** The foundation (#0d1117).
- **Level 1 (Surface):** Standard cards and containers (#161b22) with a 1px border (#30363d).
- **Level 2 (Active/Hover):** When an element is focused, the background shifts slightly lighter, and a primary color glow is applied to the border.

Shadows are rarely used, except for modals or "Threat" alerts, where a color-tinted ambient glow is used to suggest the element is "projecting" light onto the dashboard.

## Shapes

The design system employs a **Soft (0.25rem)** roundedness to maintain a modern, sleek feel without losing the structural "hardness" of a secure system. 

- **Cards & Widgets:** Use `rounded-sm` (4px) to keep a tight, technical look.
- **Buttons & Inputs:** Follow the same 4px radius for consistency.
- **Status Indicators:** Small dots and pips should be perfectly circular to distinguish them from interactive buttons.

## Components

### Buttons & Inputs
Buttons use a solid fill for primary actions (Commander Blue) and a ghost style (border only) for secondary actions. Input fields should resemble terminal prompts, using the `Surface` color with a `Border` stroke, transitioning to a `Primary` stroke on focus.

### Cards
Cards are the primary container. They must have a header section with a `label-caps` title and an optional "Status Glow" on the left edge to indicate the health of the system the card represents.

### Terminal Log Feeds
Logs should use a true black (#000000) or deep surface background to differentiate them from the standard UI. Text must be `data-sm` (JetBrains Mono). Highlight syntax (IPs in Blue, Threats in Red) within the feed for rapid scanning.

### Health Pips & Gauges
Use circular "Pips" for system status. A "Safe" pip is Green (#3fb950); an "Infected" pip uses Red (#f85149) with an outer glow animation to simulate a pulse.

### Navigation
The sidebar should be collapsed by default to maximize the data workspace, using high-contrast icons that light up in `Commander Blue` when active.