/**
 * Wain Mobile — Color palette
 *
 * Matches the desktop Wain color scheme from config.py
 */

export const Colors = {
  // Base dark theme
  bg: '#09090b',
  surface: '#18181b',
  card: '#1c1c1f',
  cardBorder: '#27272a',
  border: '#3f3f46',
  textPrimary: '#fafafa',
  textSecondary: '#a1a1aa',
  textTertiary: '#71717a',
  textMuted: '#52525b',

  // Engine accent colors (from config.py ENGINE_COLORS)
  blender: '#ea7600',
  marmoset: '#ef0343',
  vantage: '#77b22a',

  // Status colors (from config.py STATUS_CONFIG)
  rendering: '#3b82f6',  // blue
  queued: '#eab308',     // yellow
  paused: '#f97316',     // orange
  completed: '#22c55e',  // green
  failed: '#ef4444',     // red
  claimed: '#3b82f6',    // blue (same as rendering)

  // Worker status
  connected: '#3b82f6',
  idle: '#a1a1aa',
  offline: '#71717a',
  stale: '#ef4444',

  // Misc
  accent: '#a1a1aa',
  positive: '#22c55e',
  negative: '#ef4444',
  warning: '#f59e0b',
} as const;

export type EngineType = 'blender' | 'marmoset' | 'vantage';

export function engineColor(engine: string): string {
  switch (engine.toLowerCase()) {
    case 'blender': return Colors.blender;
    case 'marmoset': return Colors.marmoset;
    case 'vantage': return Colors.vantage;
    default: return Colors.accent;
  }
}

export function statusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'rendering': return Colors.rendering;
    case 'claimed': return Colors.claimed;
    case 'queued': return Colors.queued;
    case 'paused': return Colors.paused;
    case 'completed': return Colors.completed;
    case 'failed': return Colors.failed;
    default: return Colors.textTertiary;
  }
}
