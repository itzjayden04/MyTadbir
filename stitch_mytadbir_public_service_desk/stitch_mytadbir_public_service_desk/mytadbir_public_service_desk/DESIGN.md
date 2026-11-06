---
name: MyTadbir Public Service Desk
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f3'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#47464a'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f0f1f1'
  outline: '#78767b'
  outline-variant: '#c8c5ca'
  surface-tint: '#5f5e60'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#1c1b1d'
  on-primary-container: '#858386'
  inverse-primary: '#c8c6c8'
  secondary: '#5f5e61'
  on-secondary: '#ffffff'
  secondary-container: '#e4e1e5'
  on-secondary-container: '#656467'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#1a1b22'
  on-tertiary-container: '#83838c'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e5e1e4'
  primary-fixed-dim: '#c8c6c8'
  on-primary-fixed: '#1c1b1d'
  on-primary-fixed-variant: '#474649'
  secondary-fixed: '#e4e1e5'
  secondary-fixed-dim: '#c8c6c9'
  on-secondary-fixed: '#1b1b1e'
  on-secondary-fixed-variant: '#47464a'
  tertiary-fixed: '#e3e1ec'
  tertiary-fixed-dim: '#c6c5cf'
  on-tertiary-fixed: '#1a1b22'
  on-tertiary-fixed-variant: '#46464e'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: IBM Plex Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-default:
    fontFamily: IBM Plex Sans
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  body-medium:
    fontFamily: IBM Plex Sans
    fontSize: 15px
    fontWeight: '500'
    lineHeight: 22px
  body-sm:
    fontFamily: IBM Plex Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm-medium:
    fontFamily: IBM Plex Sans
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  caption:
    fontFamily: IBM Plex Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-default:
    fontFamily: IBM Plex Sans
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-sm:
    fontFamily: IBM Plex Sans
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  data-mono-default:
    fontFamily: IBM Plex Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  data-mono-sm:
    fontFamily: IBM Plex Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-tablet: 1.5rem
  gutter-desktop: 2rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
---

## Brand & Style

This design system serves a mission-critical public service infrastructure. The design ethos is institutional, impartial, and exact. It reflects sovereign administrative authority through complete visual restraint and radical clarity.

The visual style is **Constructivist Institutional Minimalism**:
- **Monochrome Chrome**: The interface infrastructure is composed entirely of zinc-tinted neutral shades, absolute white, and carbon black. Chrome never competes with case data.
- **Semantic Exclusivity**: Color is deployed solely as an instrument of triage, status indication, geospatial routing, and departmental identity. It is never used decoratively, ambiently, or illustratively.
- **Zero Ornamentation**: Banned entirely are glassmorphic effects, backdrop blurs, glow rings, gradient fills, illustrative vignettes, purple tinting, novelty iconography, and artificial intelligence decorative metaphors.
- **Institutional Equality**: Complete bilingual parity across Bahasa Malaysia and English. Layouts, field labels, metadata containers, and actions accommodate text length fluctuations without layout reflow or ellipsis clipping.
- **Functional Linework**: Crisp 1px geometric boundaries replace drop shadows to structure hierarchy across all operational workflows.

## Colors

The system operates with a disciplined two-tier chromatic structure: an immutable neutral substrate for chrome and a strictly codified semantic registry for public sector workflows.

### Neutral Chrome Foundation
- **Base Ink (`--ink`)**: `#09090B` — Primary typography, critical headers, high-contrast actions.
- **Secondary Ink (`--ink-2`)**: `#3F3F46` — Body copy, field labels, operational descriptions.
- **Muted (`--muted`)**: `#71717A` — Supporting microcopy, helper text, inactive metadata.
- **Line Strong (`--line-strong`)**: `#D4D4D8` — Control borders, table dividers, active outlines.
- **Line (`--line`)**: `#E4E4E7` — Card boundaries, structural layout guides, grid dividers.
- **Surface 2 (`--surface-2`)**: `#F4F4F5` — Table headers, panel backgrounds, input inactive fills.
- **Surface (`--surface`)**: `#FAFAFA` — Canvas underlay, global viewport backdrop.
- **Canvas White (`--white`)**: `#FFFFFF` — Data cards, modal windows, raised sheets.

### Semantic Triage Tokens
- **Success (`--status-success`)**: `#15803D` (Surface Tint: `#F0FDF4`, Border Tint: `#BBF7D0`) — Verified, approved, dished, resolved.
- **Warning (`--status-warning`)**: `#B45309` (Surface Tint: `#FFFBEB`, Border Tint: `#FDE68A`) — Under inquiry, pending citizen action, review overdue.
- **Danger (`--status-danger`)**: `#B91C1C` (Surface Tint: `#FEF2F2`, Border Tint: `#FECACA`) — Escalated, rejected, breached SLA, critical violation.
- **Info (`--status-info`)**: `#1D4ED8` (Surface Tint: `#EFF6FF`, Border Tint: `#BFDBFE`) — In process, routed, general update.
- **Neutral (`--status-neutral`)**: `#52525B` (Surface Tint: `#F4F4F5`, Border Tint: `#E4E4E7`) — Closed, archived, draft status.

### Ministerial & Agency Identifiers
Color is used solely as a dot/indicator pip (`8px`) or structured taxonomy tag:
- **Kementerian Kesihatan Malaysia (Health)**: `#DC2626`
- **Kementerian Pendidikan (Education)**: `#2563EB`
- **Pihak Berkuasa Tempatan (Local Government)**: `#0F766E`
- **Jabatan Imigresen Malaysia (Immigration)**: `#7C3AED`
- **Jabatan Pengangkutan Jalan (JPJ)**: `#EA580C`
- **Lembaga Hasil Dalam Negeri (LHDN)**: `#CA8A04`
- **Jabatan Kebajikan Masyarakat (JKM)**: `#DB2777`
- **Polis Diraja Malaysia / KDN (Police/Home Affairs)**: `#1E3A8A`
- **Pertanian & Alam Sekitar (Agriculture/Environment)**: `#16A34A`
- **Lintas Agensi (Cross-Agency Tasks)**: `#475569`

## Typography

The typographic hierarchy distinguishes governance authority from high-density data parsing:

- **Executive Structural Headings**: Rendered in `Plus Jakarta Sans` with weights strictly constrained to SemiBold (600) and Bold (700). Negative letter spacing (-0.01em to -0.02em) provides an authoritative, compact footprint suitable for bilingual headers.
- **Administrative Interface**: Built upon `IBM Plex Sans` with an operational base size of `15px`. This non-standard base balances scanability with data density, providing legibility for prolonged officer screen exposure.
- **Identifiers & Numeric Precision**: All case reference numbers (e.g., `MY-TR-2024-89912`), MyKad identity representations, passport numbers, currency values, dates, and SLA timers strictly mandate `IBM Plex Mono` with tabular numeral sizing enabled (`font-variant-numeric: tabular-nums`).
- **Language Alignment**: All typographic tokens are tested for dual-language layout equivalence. Text components must avoid truncation; BM descriptive terms (e.g., *Pengesahan Dokumen Sokongan*) expand vertically without horizontal rupture.

## Layout & Spacing

The layout is built upon an 8px atomic grid (`0.5rem = 8px`), supporting high-density desks, search registries, and application flows.

### Grid & Responsive Rules
- **Desktop (≥ 1280px)**: 12-column responsive fluid grid. `2rem` (32px) margins and gutters. Global layout splits into an operational fixed sidebar (260px) and a fluid dynamic workbench workspace (capped at 1600px).
- **Tablet (768px – 1279px)**: 8-column layout. `1.5rem` (24px) gutters and margins. Sidebar collapses to an icon rail (64px) or off-canvas drawer. Data grids support horizontal scrolling on structural sub-panes.
- **Mobile (< 768px)**: 4-column layout. `1rem` (16px) margins and gutters. Single-column stacked triage workflows. Secondary table data cascades into key-value summary disclosure panels.

### Rhythm & Densities
- `space-xs` (4px): Fine alignment between agency badge icons, dot indicators, and linked metadata.
- `space-sm` (8px): Internal gaps within form field clusters, tag groups, and list items.
- `space-md` (16px): Structural padding within table cells, list containers, and compact cards.
- `space-lg` (24px): Standard card body padding, multi-column form gaps, and section intervals.
- `space-xl` (32px): Separation between unrelated administrative modules or master summary panels.

## Elevation & Depth

This system rejects ambient shadows and blur filters. Visual depth is established through **Structural Tonal Layering and Precision Outlines**:

- **No Drop Shadows**: Standard UI components (cards, filters, inputs, splitters) use zero shadow (`box-shadow: none`).
- **Surface Elevation Hierarchy**:
  - *Layer 0 (Canvas)*: `#FAFAFA` — The underlying workspace desk floor.
  - *Layer 1 (Card/Container)*: `#FFFFFF` bounded by a 1px border of `#E4E4E7`.
  - *Layer 2 (Header / Table Row Focus / Grouping)*: `#F4F4F5` inset fill without borders.
  - *Layer 3 (Floating Overlays / Modals / Command Palette)*: `#FFFFFF` bounded by a 1px border of `#D4D4D8`, backed by a flat translucent veil of `rgba(9, 9, 11, 0.4)` without backdrop blur.
- **Border Hierarchy**: 
  - Standard containment: 1px `#E4E4E7` (`--line`).
  - Active selection, focused states, or structural demarcations: 1px `#D4D4D8` (`--line-strong`).
  - Active focused input ring: 2px `#09090B` (`--ink`) offset by 1px white margin.

## Shapes

Shapes communicate institutional precision and functional boundaries. Radii are locked to three exact geometric standards:

- **Cards & Data Modules**: Fixed at `10px`. Provides subtle refinement while maintaining structural stability alongside adjacent modules.
- **Form Inputs, Buttons, & Interactive Controls**: Fixed at `8px`. Aligns directly with the 8px baseline grid.
- **Metadata Badges, Status Chips, & Filter Pills**: Fixed at `999px` (fully rounded capsule). Differentiates clickable or informational tags from interactive form fields and structural content containers.
- **Tables, Nested Insets, and Panel Splitters**: Zero radius (`0px`) on internal divider lines to preserve column geometry.

## Components

### Buttons
- **Primary**: Background `#09090B`, text `#FFFFFF`, border 1px solid `#09090B`, radius 8px, height 40px (32px for compact tables). Hover: `#27272A`. Active: `#3F3F46`. Focus: 2px `#09090B` offset 2px.
- **Secondary / Outline**: Background `#FFFFFF`, text `#09090B`, border 1px solid `#D4D4D8`, radius 8px. Hover: `#F4F4F5`, border `#09090B`.
- **Tertiary / Ghost**: Background transparent, text `#3F3F46`, border 1px solid transparent. Hover: `#F4F4F5`, text `#09090B`.
- **Destructive**: Background `#B91C1C`, text `#FFFFFF`, border 1px solid `#B91C1C`. Hover: `#991B1B`.

### Status Badges & Chips
- **Geometry**: Height 24px, radius 999px, padding 0 10px. Typographic rule: `label-sm` (12px, 600 weight).
- **Semantics**:
  - Neutral / Unassigned: Surface `#F4F4F5`, border 1px solid `#E4E4E7`, text `#52525B`.
  - Approved / Aktif: Surface `#F0FDF4`, border 1px solid `#BBF7D0`, text `#15803D`.
  - Perhatian / Pending: Surface `#FFFBEB`, border 1px solid `#FDE68A`, text `#B45309`.
  - Tindakan Segera / Critical: Surface `#FEF2F2`, border 1px solid `#FECACA`, text `#B91C1C`.
- **Agency Dot Chips**: Surface `#FFFFFF`, border 1px solid `#E4E4E7`, text `#09090B`. Includes a left-aligned 8px solid circular dot displaying the designated departmental hex value.

### Form Inputs & Selectors
- **Input Fields**: Background `#FFFFFF`, border 1px solid `#D4D4D8`, radius 8px, height 40px, padding 0 12px. Text `#09090B`, placeholder `#71717A`.
- **Focus State**: Border `#09090B`, outline 1px solid `#09090B`. No drop glow.
- **Error State**: Border `#B91C1C`, error helper text in `#B91C1C` using `caption` (12px).
- **Checkboxes & Radios**: 16px × 16px, 1px solid `#D4D4D8`. Checked state: Background `#09090B`, checkmark `#FFFFFF` (1.5px stroke). Radios use 999px radius; checkboxes use 4px radius.

### Cards & Data Containers
- **Master Data Card**: Background `#FFFFFF`, border 1px solid `#E4E4E7`, radius 10px, padding 24px.
- **Card Header**: Border-bottom 1px solid `#E4E4E7`, padding-bottom 16px, margin-bottom 16px. Includes bilingual label grouping (`BM` in primary `headline-sm`, `EN` equivalent in `body-sm` muted directly beneath or parenthesized).

### Tables & Data Lists
- **Header**: Background `#F4F4F5`, text `#71717A`, uppercase, `label-sm`, height 40px, border-bottom 1px solid `#D4D4D8`.
- **Rows**: Background `#FFFFFF`, height 48px (dense) or 56px (standard), border-bottom 1px solid `#E4E4E7`. Hover: `#FAFAFA`. Selected: `#F4F4F5`.
- **Numeric / Case Identifier Columns**: Right-aligned or mono-spaced using `IBM Plex Mono` tabular figures.

### Iconography
- **System**: Lucide line icon suite. Stroke width strictly locked to `1.5px`. Size baseline: 16px (inline labels), 20px (action buttons/headers). Color: `currentColor`, resolving to the active text or semantic token.