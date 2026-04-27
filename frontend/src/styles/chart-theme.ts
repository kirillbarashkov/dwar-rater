/**
 * Chart theme configuration for Recharts.
 *
 * Colors are derived from the DESIGN.md token palette:
 *   chart-1: accent (#00d4aa)
 *   chart-2: blue (#8be9fd)
 *   chart-3: purple (#bd93f9)
 *   chart-4: orange (#ffb86c)
 *   chart-5: gold (#ffc857)
 *   chart-6: green (#50fa7b)
 *   chart-7: red (#ff5555)
 *
 * Recharts is installed (package.json) but not yet used in components.
 * This file is ready for when charts are added to TreasuryAnalytics,
 * TaxAnalytics, or other analytics views.
 */

export const chartColors = [
  '#00d4aa',
  '#8be9fd',
  '#bd93f9',
  '#ffb86c',
  '#ffc857',
  '#50fa7b',
  '#ff5555',
] as const;

export const chartTheme = {
  colors: chartColors,
  background: '#0a0e14',
  text: '#e8edf5',
  textSecondary: '#8899b0',
  grid: '#2a3548',
  tooltip: {
    background: '#1a2235',
    border: '#2a3548',
    text: '#e8edf5',
  },
} as const;

export const chartTypography = {
  fontFamily: "'IBM Plex Sans', sans-serif",
  fontSize: 12,
  fontWeight: 400,
} as const;
