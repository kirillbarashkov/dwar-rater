---
name: Dwar Rater
version: alpha
description: Dark gaming-inspired UI for character analysis from Legend: Legacy of the Dragons (dwar.ru). Cyberpunk/fantasy aesthetic with teal accent, glow effects, and gradient backgrounds.
colors:
  bg-primary: "#0a0e14"
  bg-secondary: "#121824"
  bg-card: "#1a2235"
  bg-card-hover: "#243050"
  text-primary: "#e8edf5"
  text-secondary: "#8899b0"
  text-muted: "#556677"
  accent: "#00d4aa"
  accent-hover: "#00ffcc"
  accent-subtle: "rgba(0, 212, 170, 0.15)"
  accent-glow: "rgba(0, 212, 170, 0.4)"
  border: "#2a3548"
  border-light: "#1e2a3d"
  gold: "#ffc857"
  green: "#50fa7b"
  red: "#ff5555"
  purple: "#bd93f9"
  orange: "#ffb86c"
  blue: "#8be9fd"
  chart-1: "#00d4aa"
  chart-2: "#8be9fd"
  chart-3: "#bd93f9"
  chart-4: "#ffb86c"
  chart-5: "#ffc857"
  chart-6: "#50fa7b"
  chart-7: "#ff5555"
typography:
  display:
    fontFamily: Rajdhani
    fontSize: 1.5rem
    fontWeight: 700
  h1:
    fontFamily: Rajdhani
    fontSize: 2rem
    fontWeight: 700
    letterSpacing: 1px
  h2:
    fontFamily: Rajdhani
    fontSize: 1.2rem
    fontWeight: 700
    letterSpacing: 0.5px
  section-title:
    fontFamily: Rajdhani
    fontSize: 0.8rem
    fontWeight: 600
    letterSpacing: 2px
  body-md:
    fontFamily: IBM Plex Sans
    fontSize: 1rem
    fontWeight: 400
  body-sm:
    fontFamily: IBM Plex Sans
    fontSize: 0.85rem
    fontWeight: 500
  label-sm:
    fontFamily: IBM Plex Sans
    fontSize: 0.8rem
    fontWeight: 500
rounded:
  sm: 6px
  md: 10px
  lg: 16px
  xl: 24px
spacing:
  xs: 8px
  sm: 12px
  md: 16px
  lg: 20px
  xl: 24px
  xxl: 28px
  section: 40px
components:
  card-standard:
    backgroundColor: "{colors.bg-card}"
    rounded: "{rounded.xl}"
    padding: "{spacing.xxl}"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.bg-primary}"
    rounded: "{rounded.md}"
  button-secondary:
    backgroundColor: transparent
    textColor: "{colors.accent}"
    rounded: "{rounded.md}"
  button-danger:
    backgroundColor: "{colors.red}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
  input-field:
    backgroundColor: "{colors.bg-secondary}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm}"
  badge-status:
    rounded: "{rounded.sm}"
    padding: "{spacing.xs}"
---

## Brand & Style

Dwar Rater is a character analysis tool for the browser MMORPG "Legend: Legacy of the Dragons" (dwar.ru). The visual identity is dark, gaming-inspired, with a cyberpunk/fantasy aesthetic.

The UI uses a teal/mint green accent (`#00d4aa`) against deep navy backgrounds, with gradient effects, glow animations, and two custom fonts: Rajdhani for display/headings and IBM Plex Sans for body text.

The emotional response is intended to feel premium, tactical, and immersive — like a command center for analyzing game characters.

## Colors

The palette is anchored in deep navy and dark blue tones with a single vibrant accent.

- **Primary Background (#0a0e14):** Near-black navy foundation for the entire application.
- **Secondary Background (#121824):** Slightly lighter navy for sidebar, secondary surfaces.
- **Card Surface (#1a2235):** Gradient card backgrounds with subtle blue tint.
- **Accent (#00d4aa):** Teal/mint green — the sole driver for primary actions, active states, and highlights.
- **Accent Hover (#00ffcc):** Brighter teal for hover states.
- **Gold (#ffc857):** Used for leader badges, rank highlights, and prestige indicators.
- **Green (#50fa7b):** Success states, buffs, positive values.
- **Red (#ff5555):** Errors, danger actions, debuffs, negative values.
- **Purple (#bd93f9):** Secondary accent for decorative gradients and special states.
- **Orange (#ffb86c):** Warning states, highlights.
- **Blue (#8be9fd):** Tertiary accent, elixirs, informational elements.

## Typography

The design system uses a dual-font strategy:

- **Rajdhani** for all headings, section titles, and display text. Its squared, technical geometry evokes a HUD-like, tactical feel.
- **IBM Plex Sans** for body text, labels, and metadata. Its neutral clarity ensures readability for dense data tables.

Headlines use bold weights (600-700) with tight letter spacing. Section titles are uppercase with generous letter-spacing (2px). Body text uses regular weight with comfortable line height (1.6).

## Layout & Spacing

The layout follows a **Fixed Sidebar + Fluid Content** model:

- Sidebar: 280px fixed left navigation
- Main content: flex: 1, padding 40px 48px, max-width 1600px centered
- Grid utilities: `.grid-2`, `.grid-3`, `.grid-4` for responsive card layouts
- Spacing scale: 8px base unit (xs=8, sm=12, md=16, lg=20, xl=24, xxl=28)

## Elevation & Depth

Depth is achieved through layered gradients, borders, and glow effects rather than traditional shadows:

- **Level 1 (Base):** Multi-layered background with radial gradients (teal top-left, purple bottom-right)
- **Level 2 (Cards):** Gradient background (bg-card to bg-secondary), 1px border, subtle bottom accent line via `::after`
- **Level 3 (Hover):** Border transitions to accent color, shadow-glow effect, translateY(-2px)
- **Header:** Sticky with backdrop blur

## Shapes

The shape language uses rounded corners throughout:

- **sm (6px):** Badges, small inline elements
- **md (10px):** Buttons, input fields
- **lg (16px):** Section containers
- **xl (24px):** Cards, modals, major containers

## Components

### Cards

Standard cards use a gradient background, 1px border, rounded-xl corners, and a subtle accent gradient line at the bottom. On hover, the border transitions to the accent color with a glow effect.

### Buttons

Four variants: primary (accent fill), secondary (accent outline), danger (red fill), ghost (transparent). Three sizes: small, medium, large.

### Inputs

Dark background with accent border on focus. Error state uses red border.

### Badges

Small inline labels with quality-colored variants (green for success, red for error, blue for info, gold for prestige).

## Do's and Don'ts

- Do use the accent color only for the single most important action per screen
- Do maintain the dark theme as the primary experience
- Don't mix rounded and sharp corners — all elements use the defined radius scale
- Do use Rajdhani exclusively for headings, IBM Plex Sans for body text
- Don't introduce new colors outside the defined palette without justification
- Do use glow effects sparingly — they should highlight, not overwhelm
