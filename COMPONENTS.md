# UI Components Reference

This document describes all UI components in the Render Manager application. Use this as a reference for visual design updates.

---

## Overview

The application consists of these main components:

| Component | Purpose |
|-----------|---------|
| **Header** | App branding, navigation, primary actions |
| **StatsCard** | Display render job statistics |
| **JobCard** | Individual render job with controls |
| **AddJobModal** | Form to submit new render jobs |
| **SettingsPanel** | Application configuration |
| **LogPanel** | Real-time render output display |

---

## Header

**Purpose:** Top navigation bar with branding and primary actions.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│  [Logo]  Render Manager                    [Settings] [Add Job] │
│          Manage and monitor your render queue                   │
└─────────────────────────────────────────────────────────────────┘
```

**Elements:**
| Element | Type | Description |
|---------|------|-------------|
| Logo | 48x48 image/canvas | Gradient blue→purple with "RM" text |
| Title | Text (bold, xl) | "Render Manager" |
| Subtitle | Text (muted) | "Manage and monitor your render queue" |
| Settings Button | Button (secondary) | Opens SettingsPanel |
| Add Job Button | Button (primary) | Opens AddJobModal |

**Visual Notes:**
- Background: slightly elevated from base (zinc-900)
- Bottom border: 1px separator
- Sticky positioning at top

---

## StatsCard

**Purpose:** Display count of jobs in each status category.

**Layout:**
```
┌──────────────────────────┐
│  [Icon]  Rendering       │
│          3               │
└──────────────────────────┘
```

**Variants:**
| Type | Icon | Color | Background Tint |
|------|------|-------|-----------------|
| Rendering | ▶ (play) | blue-400 | blue-900/20 |
| Queued | ⏱ (clock) | yellow-400 | yellow-900/20 |
| Completed | ✓ (check) | green-400 | green-900/20 |
| Failed | ✕ (x) | red-400 | red-900/20 |

**Elements:**
| Element | Type | Description |
|---------|------|-------------|
| Icon Container | 40x40 frame | Rounded, tinted background |
| Icon | Text/Symbol | Status-specific icon |
| Label | Text (small, muted) | "Rendering", "Queued", etc. |
| Value | Text (3xl, bold) | Numeric count |

**Visual Notes:**
- Card background: zinc-900
- Border: 1px zinc-800
- 4 cards in a row, equal width
- Gap between cards: 12px

---

## JobCard

**Purpose:** Display individual render job with status, progress, and controls.

**Layout (Collapsed):**
```
┌────────────────────────────────────────────────────────────────────┐
│  Scene_01_FinalRender  [RENDERING]              [⏸] [▼] [🗑]      │
│  project_main.blend                                                │
│  Input: /path/to/file.blend                                        │
│  Output: /path/to/output/                                          │
│                                                                    │
│  Progress                                               65%        │
│  ████████████████████████░░░░░░░░░░░░                              │
│                                                                    │
│  Frames: 1-250  •  1920x1080  •  Cycles  •  ~2h 15m                │
└────────────────────────────────────────────────────────────────────┘
```

**Layout (Expanded):**
```
┌────────────────────────────────────────────────────────────────────┐
│  [Collapsed content above]                                         │
│  ──────────────────────────────────────────────────────────────    │
│  Priority        Camera          Render Engine    Resolution       │
│  3               Scene Default   Cycles           1920×1080        │
│                                                                    │
│  Frame Range     Format          Start Time       End Time         │
│  1-250           PNG             10:23 AM         --               │
└────────────────────────────────────────────────────────────────────┘
```

**Status Badge Styles:**
| Status | Text Color | Background | Border |
|--------|------------|------------|--------|
| RENDERING | blue-400 | blue-900/20 | blue-600/30 |
| QUEUED | yellow-400 | yellow-900/20 | yellow-600/30 |
| COMPLETED | green-400 | green-900/20 | green-600/30 |
| FAILED | red-400 | red-900/20 | red-600/30 |
| PAUSED | zinc-400 | zinc-600/20 | zinc-600/30 |

**Action Buttons:**
| Status | Available Actions |
|--------|-------------------|
| Rendering | Pause ⏸, Expand ▼, Delete 🗑 |
| Queued | Start ▶, Expand ▼, Delete 🗑 |
| Paused | Start ▶, Expand ▼, Delete 🗑 |
| Completed | Expand ▼, Delete 🗑 |
| Failed | Retry ↻, Expand ▼, Delete 🗑 |

**Progress Bar:**
| Status | Bar Color |
|--------|-----------|
| Rendering | blue-500 |
| Paused | orange-500 |
| Completed | green-500 |
| Failed | red-500 |

**Visual Notes:**
- Card background: zinc-900
- Border: 1px zinc-800, hover: zinc-700
- Progress bar track: zinc-800
- Progress bar height: 8px
- Quick info uses "•" as separator

---

## AddJobModal

**Purpose:** Form dialog to submit new render jobs.

**Layout:**
```
┌────────────────────────────────────────────────────────────────┐
│  [📤] Submit Render Job                                    [✕] │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Job Name *                                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Scene_01_FinalRender                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  Scene File *                                                  │
│  ┌────────────────────────────────────────────────┐ [Browse]   │
│  │ /path/to/project_main.blend                    │            │
│  └────────────────────────────────────────────────┘            │
│                                                                │
│  Output Directory *                                            │
│  ┌────────────────────────────────────────────────┐ [Browse]   │
│  │ /path/to/output/                               │            │
│  └────────────────────────────────────────────────┘            │
│                                                                │
│  Frame Range *                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1-250                                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│  Example: 1-250 or 1,5,10-20                                   │
│                                                                │
│  ┌─────────────────────────┐  ┌─────────────────────────┐      │
│  │ Resolution          ▼  │  │ Priority            ▼  │      │
│  │ 1920x1080              │  │ 3 (Normal)             │      │
│  └─────────────────────────┘  └─────────────────────────┘      │
│                                                                │
│  ┌─────────────────────────┐  ┌─────────────────────────┐      │
│  │ Render Engine       ▼  │  │ Output Format       ▼  │      │
│  │ Cycles                 │  │ PNG                    │      │
│  └─────────────────────────┘  └─────────────────────────┘      │
│                                                                │
│  ┌─────────────────────────┐  ┌─────────────────────────┐      │
│  │ Camera              ▼  │  │ Estimated Time          │      │
│  │ Scene Default          │  │ 2h 30m                  │      │
│  └─────────────────────────┘  └─────────────────────────┘      │
│                                                                │
│  ☑ Enable GPU Rendering                                        │
│  ☐ Submit as Paused                                            │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│  [    Cancel    ]              [  📤 Submit Job  ]             │
└────────────────────────────────────────────────────────────────┘
```

**Form Fields:**
| Field | Type | Required | Options/Validation |
|-------|------|----------|-------------------|
| Job Name | Text input | Yes | Auto-fills from filename |
| Scene File | File picker | Yes | .blend files only |
| Output Directory | Folder picker | Yes | - |
| Frame Range | Text input | Yes | e.g., "1-250" or "1,5,10-20" |
| Resolution | Dropdown | No | 1920x1080, 2560x1440, 3840x2160, 7680x4320 |
| Priority | Dropdown | No | 1 (Highest) to 5 (Lowest) |
| Render Engine | Dropdown | No | Cycles, Eevee, Workbench |
| Output Format | Dropdown | No | PNG, JPEG, OpenEXR, TIFF |
| Camera | Dropdown | No | Scene Default + detected cameras |
| Estimated Time | Text input | No | e.g., "2h 30m" |
| Enable GPU | Checkbox | No | Default: checked |
| Submit as Paused | Checkbox | No | Default: unchecked |

**Visual Notes:**
- Modal overlay: black/70% opacity
- Modal background: zinc-900
- Max width: 600px
- Scrollable content area
- Two-column grid for dropdowns
- Primary button: blue-600
- Cancel button: zinc-800

---

## SettingsPanel

**Purpose:** Configure application defaults and Blender installations.

**Layout:**
```
┌────────────────────────────────────────────────────────────────┐
│  Render Settings                                           [✕] │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Blender Installations                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ [4.2.0] C:\Program Files\Blender Foundation\Blender 4.2  │  │
│  │ [4.1.0] C:\Program Files\Blender Foundation\Blender 4.1  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  [+ Add Custom]  [🔄 Rescan]                                   │
│                                                                │
│  ──────────────────────────────────────────────────────────    │
│                                                                │
│  Default Job Settings                                          │
│                                                                │
│  Default Render Engine                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Cycles                                                ▼  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  Default rendering engine for new jobs                         │
│                                                                │
│  Default Resolution                                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1920x1080                                             ▼  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  [... more dropdowns ...]                                      │
│                                                                │
│  ☑ Enable GPU by Default                                       │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│  [    Cancel    ]              [  💾 Save Settings  ]          │
└────────────────────────────────────────────────────────────────┘
```

**Settings Fields:**
| Field | Type | Options |
|-------|------|---------|
| Default Render Engine | Dropdown | Cycles, Eevee, Workbench |
| Default Resolution | Dropdown | 1920x1080, 2560x1440, 3840x2160, 7680x4320 |
| Default Output Format | Dropdown | PNG, JPEG, OpenEXR, TIFF |
| Default Render Quality | Dropdown | Low, Medium, High, Ultra |
| Max Concurrent Jobs | Dropdown | 1-5 |
| Default Samples Count | Dropdown | 32, 64, 128, 256, 512, 1024 |
| Enable GPU by Default | Checkbox | - |

**Blender Version Badge:**
- Background: green-500
- Text: white, bold
- Shows version number (e.g., "4.2.0")

**Visual Notes:**
- Same modal styling as AddJobModal
- Version list shows installed Blender versions with paths
- Hint text below some dropdowns (muted, small)

---

## LogPanel

**Purpose:** Display real-time Blender render output.

**Layout:**
```
┌────────────────────────────────────────────────────────────────┐
│  Log                                          [Clear]  [▲]     │
├────────────────────────────────────────────────────────────────┤
│  [10:23:45] ✓ Found 2 Blender version(s): 4.2.0, 4.1.0        │
│  [10:23:45] Loaded 3 jobs                                      │
│  [10:24:01] Starting: Scene_01_FinalRender                     │
│  [10:24:02] Using Blender 4.2.0: C:\Program Files\...          │
│  [10:24:15] Fra:1 Mem:256.45M (Peak 312.22M) | Time:00:12.34   │
│  [10:24:18] Fra:2 Mem:256.45M (Peak 312.22M) | Time:00:11.22   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Elements:**
| Element | Description |
|---------|-------------|
| Header | "Log" label, Clear button, Toggle button |
| Log area | Monospace text, scrollable |
| Timestamp | [HH:MM:SS] prefix for each line |

**Visual Notes:**
- Header background: zinc-800
- Log background: zinc-950
- Text: zinc-500 (muted)
- Font: Consolas or monospace, 10px
- Height: ~5 lines (collapsible)
- Toggle: ▲ (expanded) / ▼ (collapsed)

---

## Empty State

**Purpose:** Shown when no jobs exist in the queue.

**Layout:**
```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│                       No render jobs                           │
│                  Click "Add Job" to start                      │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Visual Notes:**
- Card background: zinc-900
- Border: 1px zinc-800
- Text centered vertically and horizontally
- Primary text: zinc-400
- Secondary text: zinc-500

---

## Color Palette (Tailwind Zinc)

| Token | Hex | Usage |
|-------|-----|-------|
| zinc-950 | #09090b | Base background |
| zinc-900 | #18181b | Card backgrounds |
| zinc-800 | #27272a | Elevated surfaces, borders, inputs |
| zinc-700 | #3f3f46 | Hover states, light borders |
| zinc-600 | #52525b | Dim text |
| zinc-500 | #71717a | Muted text |
| zinc-400 | #a1a1aa | Secondary text |
| zinc-100 | #fafafa | Primary text |
| blue-600 | #2563eb | Primary buttons, active states |
| blue-500 | #3b82f6 | Progress bars |
| blue-400 | #60a5fa | Icons, light accents |
| green-500 | #22c55e | Success states |
| green-400 | #4ade80 | Success icons |
| yellow-400 | #facc15 | Warning/queued states |
| orange-500 | #f97316 | Paused states |
| red-500 | #ef4444 | Error/failed states |
| red-400 | #f87171 | Error icons |

---

## Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| App Title | Segoe UI | 20px | Bold |
| Section Headers | Segoe UI | 16px | Bold |
| Card Titles | Segoe UI | 14px | Bold |
| Body Text | Segoe UI | 12px | Normal |
| Small Text | Segoe UI | 11px | Normal |
| Labels | Segoe UI | 11px | Normal |
| Muted/Hints | Segoe UI | 10px | Normal |
| Log Text | Consolas | 10px | Normal |
| Stat Values | Segoe UI | 28px | Bold |

---

## Spacing

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Tight spacing |
| sm | 8px | Between related elements |
| md | 12px | Card padding, gaps |
| lg | 16px | Section spacing |
| xl | 20px | Modal padding |
| 2xl | 24px | Page margins |

---

## Interactive States

| State | Style Change |
|-------|--------------|
| Hover (card) | Border: zinc-800 → zinc-700 |
| Hover (button) | Background darkens/lightens |
| Focus (input) | Border: zinc-700 → blue-500 |
| Active (button) | Slight scale or color shift |
| Disabled | Opacity: 50% |
