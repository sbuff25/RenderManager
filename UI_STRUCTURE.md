# UI Structure & Component Hierarchy

This document outlines the structural hierarchy of the Render Manager application for design reference.

---

## Application Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              HEADER                                     │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  [Logo] [Title + Subtitle]                [Settings] [Add Job]   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                              CONTENT                                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                         STATS ROW                                │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐              │   │
│  │  │Rendering│  │ Queued  │  │Completed│  │ Failed  │              │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Render Queue                                    X total jobs    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                       QUEUE LIST (scrollable)                    │   │
│  │  ┌────────────────────────────────────────────────────────────┐  │   │
│  │  │                        JobCard 1                           │  │   │
│  │  └────────────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────────────┐  │   │
│  │  │                        JobCard 2                           │  │   │
│  │  └────────────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────────────┐  │   │
│  │  │                        JobCard 3                           │  │   │
│  │  └────────────────────────────────────────────────────────────┘  │   │
│  │                            ...                                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                             LOG PANEL                                   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Log                                          [Clear] [Toggle]   │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │  [Scrollable log content]                                        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Tree

```
RenderManager (Root Window)
│
├── Header
│   ├── HeaderContent
│   │   ├── Left
│   │   │   ├── Logo (48x48 canvas/image)
│   │   │   └── Titles
│   │   │       ├── Title ("Render Manager")
│   │   │       └── Subtitle ("Manage and monitor...")
│   │   └── Right
│   │       ├── SettingsButton
│   │       └── AddJobButton
│   └── BorderLine
│
├── Content
│   ├── StatsRow
│   │   ├── StatsCard (rendering)
│   │   ├── StatsCard (queued)
│   │   ├── StatsCard (completed)
│   │   └── StatsCard (failed)
│   │
│   ├── QueueHeader
│   │   ├── Title ("Render Queue")
│   │   └── Count ("X total jobs")
│   │
│   └── QueueList (scrollable)
│       ├── JobCard
│       │   ├── Content
│       │   │   ├── TopRow
│       │   │   │   ├── Info
│       │   │   │   │   ├── NameRow
│       │   │   │   │   │   ├── JobName
│       │   │   │   │   │   └── StatusBadge
│       │   │   │   │   ├── FileName
│       │   │   │   │   └── Paths (optional)
│       │   │   │   │       ├── InputPath
│       │   │   │   │       └── OutputPath
│       │   │   │   └── Actions
│       │   │   │       ├── ActionButton (play/pause/retry)
│       │   │   │       ├── ExpandButton
│       │   │   │       └── DeleteButton
│       │   │   ├── ProgressSection (if not queued)
│       │   │   │   ├── ProgressHeader
│       │   │   │   │   ├── Label ("Progress")
│       │   │   │   │   └── Percentage ("65%")
│       │   │   │   └── ProgressBar
│       │   │   │       └── ProgressFill
│       │   │   ├── InfoRow
│       │   │   │   └── QuickInfo ("Frames • Resolution • Engine • Time")
│       │   │   └── DetailsSection (if expanded)
│       │   │       ├── Separator
│       │   │       └── DetailsGrid
│       │   │           ├── DetailCell (Priority)
│       │   │           ├── DetailCell (Camera)
│       │   │           ├── DetailCell (Engine)
│       │   │           ├── DetailCell (Resolution)
│       │   │           ├── DetailCell (Frames)
│       │   │           └── DetailCell (Format)
│       │   └── ...
│       ├── JobCard
│       └── ... (or EmptyState if no jobs)
│
└── LogPanel
    ├── LogHeader
    │   ├── Label ("Log")
    │   ├── ClearButton
    │   └── ToggleButton
    └── LogContainer (collapsible)
        └── LogText (scrollable, monospace)
```

---

## Modal Hierarchy

### AddJobModal

```
AddJobModal (Toplevel Window)
│
├── Overlay (black/70%)
│
└── ModalContainer
    ├── Header
    │   ├── Left
    │   │   ├── IconFrame (📤)
    │   │   └── Title ("Submit Render Job")
    │   └── CloseButton (✕)
    │
    ├── Separator
    │
    └── Form (scrollable)
        ├── TextField (Job Name)
        │   ├── Label
        │   └── Input
        │
        ├── FileField (Scene File)
        │   ├── Label
        │   ├── Input
        │   └── BrowseButton
        │
        ├── FileField (Output Directory)
        │   ├── Label
        │   ├── Input
        │   └── BrowseButton
        │
        ├── TextField (Frame Range)
        │   ├── Label
        │   ├── Input
        │   └── HintText
        │
        ├── SettingsGrid (2 columns)
        │   ├── Row1
        │   │   ├── Dropdown (Resolution)
        │   │   └── Dropdown (Priority)
        │   ├── Row2
        │   │   ├── Dropdown (Engine)
        │   │   └── Dropdown (Format)
        │   └── Row3
        │       ├── Dropdown (Camera)
        │       └── TextField (Estimated Time)
        │
        ├── CheckboxGroup
        │   ├── Checkbox (Enable GPU)
        │   └── Checkbox (Submit as Paused)
        │
        ├── Separator
        │
        └── ButtonRow
            ├── CancelButton
            └── SubmitButton
```

### SettingsPanel

```
SettingsPanel (Toplevel Window)
│
├── Header
│   ├── Title ("Render Settings")
│   └── CloseButton (✕)
│
├── Separator
│
└── Form (scrollable)
    ├── Section: Blender Installations
    │   ├── SectionTitle
    │   ├── VersionsList
    │   │   ├── VersionRow
    │   │   │   ├── VersionBadge ("4.2.0")
    │   │   │   └── PathText
    │   │   └── ...
    │   └── ButtonRow
    │       ├── AddCustomButton
    │       └── RescanButton
    │
    ├── Separator
    │
    ├── Section: Default Job Settings
    │   ├── SectionTitle
    │   ├── Dropdown (Default Engine)
    │   │   ├── Label
    │   │   ├── Select
    │   │   └── HintText (optional)
    │   ├── Dropdown (Default Resolution)
    │   ├── Dropdown (Default Format)
    │   ├── Dropdown (Render Quality)
    │   ├── Dropdown (Max Concurrent Jobs)
    │   ├── Dropdown (Default Samples)
    │   └── Checkbox (Enable GPU by Default)
    │
    ├── Separator
    │
    └── ButtonRow
        ├── CancelButton
        └── SaveButton
```

---

## Data Flow

### Job Data Structure
```
RenderJob {
  id: string              // Unique identifier
  name: string            // Display name
  file_path: string       // Input .blend file path
  output_folder: string   // Output directory
  output_name: string     // Output file prefix
  output_format: string   // PNG, JPEG, OpenEXR, TIFF
  
  status: string          // queued, rendering, completed, failed, paused
  progress: int           // 0-100
  
  is_animation: bool      // Single frame or animation
  frame_start: int        // Start frame
  frame_end: int          // End frame
  current_frame: int      // Current progress (for resume)
  
  res_width: int          // Resolution width
  res_height: int         // Resolution height
  engine: string          // Cycles, Eevee, Workbench
  samples: int            // Render samples
  camera: string          // Camera name or "Scene Default"
  
  use_gpu: bool           // GPU rendering enabled
  priority: int           // 1-5 (1 = highest)
  estimated_time: string  // User estimate
  elapsed_time: string    // Actual elapsed time
  
  start_time: string      // When render started
  end_time: string        // When render completed
  error_message: string   // Error details if failed
}
```

### Settings Data Structure
```
AppSettings {
  blender_paths: Dict     // version -> path mapping
  default_blender: string // Preferred version
  default_engine: string
  default_resolution: string
  default_format: string
  default_samples: int
  use_gpu: bool
  compute_device: string
  max_concurrent_jobs: int
  render_quality: string
}
```

---

## Responsive Behavior

### Minimum Window Size
- Width: 900px
- Height: 650px

### Stats Cards
- 4 columns on desktop (>900px)
- Could stack to 2x2 on smaller screens

### Job Cards
- Full width, stacked vertically
- 12px gap between cards

### Modals
- Max width: 600px
- Centered in viewport
- Scrollable content if overflow

---

## Z-Index Layers

| Layer | Z-Index | Content |
|-------|---------|---------|
| Base | 0 | Main content |
| Header | 10 | Sticky header |
| Modal Overlay | 50 | Dark backdrop |
| Modal | 51 | Modal dialogs |
| Tooltips | 100 | Hover tooltips (future) |

---

## Animation Notes

Currently using minimal animation:
- Hover transitions on buttons/cards
- Progress bar width transitions

Potential future animations:
- Modal fade-in/out
- Card expand/collapse
- Status badge pulse when rendering
- Progress bar shimmer effect

---

## Accessibility Considerations

- All interactive elements should have visible focus states
- Color is not the only indicator of status (icons used)
- Sufficient contrast ratios (dark theme)
- Keyboard navigation support
- Screen reader labels for icon-only buttons

---

## File Structure Reference

```
RenderManager/
├── render_manager_ITT03.py    # Main application (Python/tkinter)
├── RenderManager.bat          # Windows launcher
├── icon.ico                   # Window icon
├── icon.png                   # Alternate icon format
├── logo.png                   # App logo (48x48 recommended)
├── requirements.txt           # Python dependencies
├── COMPONENTS.md              # Component documentation (this file's sibling)
└── UI_STRUCTURE.md            # This file
```

---

## Version History

| Version | Changes |
|---------|---------|
| ITT01 | Initial Blender render manager |
| ITT02 | Added multi-engine support (Marmoset) |
| ITT03 | Figma-styled UI with Tailwind Zinc palette |
