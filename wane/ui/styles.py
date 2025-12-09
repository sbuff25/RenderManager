"""
Wane UI Styles
==============

CSS styles and JavaScript for the Wane application.
Includes dark theme, custom title bar, progress bars, and notification suppression.
"""


def get_main_css() -> str:
    """
    Get the main CSS styles for the application.
    
    Includes:
    - Global box-sizing and layout fixes
    - Custom title bar styling
    - Desaturated theme colors
    - Scrollbar styling
    - Progress bar animations
    - Form element styles
    """
    return '''
    <style>
        /* Global box-sizing for proper layout */
        *, *::before, *::after {
            box-sizing: border-box;
        }
        
        /* Responsive container */
        .responsive-container {
            width: 100%;
            max-width: 100%;
            padding: 1rem;
            box-sizing: border-box;
            overflow-x: hidden;
        }
        @media (min-width: 1024px) {
            .responsive-container {
                padding: 1.5rem;
            }
        }
        .stat-card {
            min-width: 150px;
            flex: 1 1 200px;
        }
        .job-card {
            width: 100%;
        }
        
        /* ========== CUSTOM TITLE BAR (Frameless Window) ========== */
        
        .custom-titlebar {
            height: 32px;
            background: #0a0a0a;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 8px;
            user-select: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 9999;
            border-bottom: 1px solid #27272a;  /* Subtle separator */
            cursor: default;  /* Standard cursor for draggable area */
        }
        
        .titlebar-left {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: default;
        }
        
        .titlebar-icon {
            width: 16px;
            height: 16px;
            object-fit: contain;
            filter: invert(1);  /* Invert for dark theme */
            border-radius: 3px;
        }
        
        .titlebar-title {
            font-size: 12px;
            font-weight: 500;
            color: #a1a1aa;
            letter-spacing: 0.02em;
        }
        
        .titlebar-controls {
            display: flex;
            align-items: center;
            -webkit-app-region: no-drag;  /* Buttons not draggable */
        }
        
        .titlebar-btn {
            width: 46px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: transparent;
            border: none;
            cursor: pointer;
            transition: background-color 0.15s ease;
            color: #a1a1aa;  /* For stroke="currentColor" */
        }
        
        .titlebar-btn svg {
            width: 10px;
            height: 10px;
            fill: #a1a1aa;
            stroke: #a1a1aa;
            transition: fill 0.15s ease, stroke 0.15s ease;
        }
        
        .titlebar-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
        }
        
        .titlebar-btn:hover svg {
            fill: #ffffff;
            stroke: #ffffff;
        }
        
        .titlebar-btn:active {
            background: rgba(255, 255, 255, 0.05);
        }
        
        /* Close button - red on hover */
        .titlebar-btn-close:hover {
            background: #e81123;
        }
        
        .titlebar-btn-close:hover svg {
            fill: #ffffff;
        }
        
        .titlebar-btn-close:active {
            background: #c42b1c;
        }
        
        /* Adjust layout for custom titlebar - only when titlebar is visible */
        /* The titlebar is 32px fixed at top, so we need to push everything down */
        html, body {
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            overflow-x: hidden !important;
        }
        
        body.has-custom-titlebar {
            padding-top: 0 !important;
        }
        
        /* Push the NiceGUI header down by titlebar height */
        body.has-custom-titlebar .q-header {
            top: 32px !important;
            left: 0 !important;
            right: 0 !important;
            width: 100% !important;
        }
        
        /* The q-layout needs margin-top for the titlebar, not padding */
        /* NiceGUI's q-page-container already has padding for the q-header */
        body.has-custom-titlebar .q-layout {
            margin-top: 32px !important;
            padding-top: 0 !important;
            min-height: calc(100vh - 32px) !important;
            width: 100% !important;
            max-width: 100% !important;
            overflow-x: hidden !important;
        }
        
        /* Main content area - this is where scrollbar should appear */
        body.has-custom-titlebar .q-page-container {
            width: 100% !important;
            max-width: 100% !important;
        }
        
        /* Ensure scrollbar appears inside the content area, not at window edge */
        body.has-custom-titlebar .q-page {
            width: 100% !important;
            max-width: 100% !important;
        }
        
        /* ========== MAIN WINDOW DESATURATED THEME ========== */
        /* Header buttons - white/gray desaturated style */
        .header-btn,
        .header-btn.q-btn {
            color: #a1a1aa !important;
            background-color: transparent !important;
            transition: all 0.2s ease !important;
        }
        .header-btn .q-icon,
        .header-btn.q-btn .q-icon {
            color: #a1a1aa !important;
        }
        .header-btn:hover,
        .header-btn.q-btn:hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        .header-btn:hover .q-icon,
        .header-btn.q-btn:hover .q-icon {
            color: #ffffff !important;
        }
        
        .header-btn-primary,
        .header-btn-primary.q-btn {
            background-color: #3f3f46 !important;
            color: #ffffff !important;
            transition: all 0.2s ease !important;
        }
        .header-btn-primary .q-icon,
        .header-btn-primary.q-btn .q-icon {
            color: #ffffff !important;
        }
        .header-btn-primary:hover,
        .header-btn-primary.q-btn:hover {
            background-color: #52525b !important;
        }
        .header-btn-primary:active {
            background-color: #3f3f46 !important;
        }
        
        /* Job action buttons - desaturated with hover effects */
        .job-action-btn {
            transition: all 0.2s ease !important;
        }
        .job-action-btn:hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        
        .job-action-btn-danger {
            transition: all 0.2s ease !important;
        }
        .job-action-btn-danger:hover {
            color: #f87171 !important;
            background-color: rgba(239, 68, 68, 0.15) !important;
        }
        
        /* Engine-specific action buttons (when rendering) */
        .job-action-btn-engine {
            color: #a1a1aa !important;
            transition: all 0.2s ease !important;
        }
        
        /* Blender themed buttons */
        .job-action-btn-engine-blender {
            color: #ea7600 !important;
        }
        .job-action-btn-engine-blender:hover {
            color: #ffffff !important;
            background-color: rgba(234, 118, 0, 0.2) !important;
        }
        
        /* Marmoset themed buttons */
        .job-action-btn-engine-marmoset {
            color: #ef0343 !important;
        }
        .job-action-btn-engine-marmoset:hover {
            color: #ffffff !important;
            background-color: rgba(239, 3, 67, 0.2) !important;
        }
        
        /* Status badge - no hover */
        .status-badge {
            /* Static - no hover effect */
        }
        
        /* Job cards - no hover effect on the card itself */
        /* Hover effects are only on action buttons within */
        
        /* Settings dialog cards (engine sections) */
        .settings-engine-card,
        .settings-engine-card.q-card {
            transition: all 0.2s ease;
            background-color: #18181b !important;
        }
        .settings-engine-card:hover,
        .settings-engine-card.q-card:hover {
            background-color: #27272a !important;
        }
        
        /* Settings dialog - fully desaturated */
        .settings-dialog,
        .settings-dialog .q-card {
            background-color: #18181b !important;
        }
        
        /* Settings dialog buttons */
        .settings-action-btn,
        .settings-action-btn.q-btn {
            color: #a1a1aa !important;
            background-color: transparent !important;
            transition: all 0.2s ease !important;
        }
        .settings-action-btn:hover,
        .settings-action-btn.q-btn:hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        
        .settings-close-btn,
        .settings-close-btn.q-btn {
            color: #71717a !important;
            transition: all 0.2s ease !important;
        }
        .settings-close-btn:hover,
        .settings-close-btn.q-btn:hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        
        .settings-close-btn-footer,
        .settings-close-btn-footer.q-btn {
            color: #a1a1aa !important;
            background-color: #3f3f46 !important;
            transition: all 0.2s ease !important;
        }
        .settings-close-btn-footer:hover,
        .settings-close-btn-footer.q-btn:hover {
            color: #ffffff !important;
            background-color: #52525b !important;
        }
        
        /* Settings dialog input fields - gray focus */
        .settings-dialog .q-field--focused .q-field__control:after {
            border-color: #71717a !important;
        }
        .settings-dialog .q-field:hover .q-field__control:before {
            border-color: #52525b !important;
        }
        
        /* Version badge styling */
        .version-badge .q-badge,
        .settings-dialog .q-badge {
            background-color: #3f3f46 !important;
            color: #e4e4e7 !important;
        }
        
        /* ========== EXPANSION PANELS ========== */
        .log-expansion .q-expansion-item__container {
            background-color: #18181b !important;
            transition: all 0.2s ease;
        }
        .log-expansion .q-item {
            color: #a1a1aa !important;
            transition: all 0.2s ease;
        }
        .log-expansion .q-item:hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.05) !important;
        }
        .log-expansion .q-item__section--avatar {
            color: #71717a !important;
        }
        
        /* ========== GLOBAL INTERACTIVE HOVER ========== */
        /* All flat buttons in main window */
        .q-btn--flat:not(.accent-dialog .q-btn--flat):not(.header-btn):not(.header-btn-primary):not(.job-action-btn):not(.job-action-btn-danger):not(.settings-action-btn):not(.settings-close-btn):not(.settings-close-btn-footer) {
            color: #a1a1aa !important;
            transition: all 0.2s ease !important;
        }
        .q-btn--flat:not(.accent-dialog .q-btn--flat):not(.header-btn):not(.header-btn-primary):not(.job-action-btn):not(.job-action-btn-danger):not(.settings-action-btn):not(.settings-close-btn):not(.settings-close-btn-footer):hover {
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        
        /* Input fields in main window - desaturated focus */
        .q-field:not(.accent-dialog .q-field) .q-field__control:after {
            border-color: #52525b !important;
        }
        .q-field:not(.accent-dialog .q-field):hover .q-field__control:before {
            border-color: #71717a !important;
        }
        .q-field--focused:not(.accent-dialog .q-field--focused) .q-field__control:after {
            border-color: #a1a1aa !important;
        }
        
        /* ========== ENGINE LOGO STYLING ========== */
        /* Invert dark logos for visibility on dark theme */
        /* Note: marmoset_logo is already white, only invert wain_logo if needed */
        img[src*="wain_logo"] {
            filter: invert(1);
        }
        
        /* Marmoset logo is white - no invert needed */
        img[src*="marmoset_logo"] {
            /* Already white on dark background */
        }
        
        /* Rounded corners for wain logo in header */
        .header img[src*="wain_logo"],
        img[src*="wain_logo"].rounded-lg {
            border-radius: 8px;
            overflow: hidden;
        }
        
        /* ========== SCROLLBAR STYLING ========== */
        /* Global scrollbar - applies everywhere including dialogs */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #18181b;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb {
            background: #3f3f46;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #52525b;
        }
        ::-webkit-scrollbar-corner {
            background: #18181b;
        }
        
        /* Quasar scroll area scrollbar */
        .q-scrollarea__thumb {
            background: #3f3f46 !important;
            border-radius: 4px !important;
            width: 8px !important;
            right: 2px !important;
        }
        .q-scrollarea__thumb:hover {
            background: #52525b !important;
        }
        .q-scrollarea__bar {
            background: #18181b !important;
            border-radius: 4px !important;
            width: 8px !important;
            right: 2px !important;
            opacity: 1 !important;
        }
        
        /* Layout stability - prevent content shifts during updates */
        .q-expansion-item__content {
            contain: layout;
        }
        
        /* Job cards should maintain stable layout */
        .q-card {
            contain: layout style;
            transform: translateZ(0); /* Force GPU layer for smoother updates */
        }
        
        /* Dialog styling */
        .q-dialog .q-card {
            max-height: 90vh;
        }
        
        /* Resizable dialog card */
        .q-card[style*="resize"] {
            resize: both !important;
            overflow: hidden !important;
            display: flex !important;
            flex-direction: column !important;
        }
        .q-card[style*="resize"]::-webkit-resizer {
            background: linear-gradient(135deg, transparent 50%, #3f3f46 50%);
            border-radius: 0 0 4px 0;
            width: 16px;
            height: 16px;
        }
        
        /* Ensure scroll area grows within resizable dialog */
        .q-card .q-scrollarea {
            flex: 1 1 auto !important;
            min-height: 100px;
        }
        
        /* Keep header and footer fixed size */
        .q-card > .row:first-child,
        .q-card > .row:last-child {
            flex-shrink: 0 !important;
        }
        
        /* ========== HIDE ALL NOTIFICATIONS ========== */
        /* This is a desktop app - no need for connection notifications */
        .q-notification,
        .q-notification--standard,
        .q-notifications,
        .q-notifications__list {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        
        /* ========== CHECKBOX/RADIO/TOGGLE FIXES ========== */
        /* Completely disable ripple/focus circle that gets stuck */
        .q-checkbox .q-checkbox__inner::before,
        .q-radio .q-radio__inner::before,
        .q-toggle .q-toggle__inner::before,
        .q-checkbox__bg::before,
        .q-radio__bg::before,
        .q-focus-helper,
        .q-checkbox .q-focus-helper,
        .q-radio .q-focus-helper,
        .q-toggle .q-focus-helper,
        .q-checkbox__focus-helper,
        .q-radio__focus-helper,
        .q-toggle__focus-helper {
            display: none !important;
            opacity: 0 !important;
            visibility: hidden !important;
            background: transparent !important;
            box-shadow: none !important;
            transform: scale(0) !important;
            width: 0 !important;
            height: 0 !important;
        }
        
        /* Remove the circular highlight/ripple on all states */
        .q-checkbox__inner,
        .q-radio__inner,
        .q-toggle__inner {
            background: transparent !important;
        }
        
        /* Kill all pseudo-elements that could show the circle */
        .q-checkbox__inner::before,
        .q-checkbox__inner::after,
        .q-radio__inner::before,
        .q-radio__inner::after,
        .q-toggle__inner::before,
        .q-toggle__inner::after,
        .q-checkbox__bg::after,
        .q-radio__bg::after {
            display: none !important;
            content: none !important;
            opacity: 0 !important;
            visibility: hidden !important;
            background: transparent !important;
            transform: scale(0) !important;
        }
        
        /* Disable all transitions to prevent stuck states */
        .q-checkbox__bg,
        .q-radio__bg,
        .q-toggle__inner,
        .q-checkbox__svg,
        .q-radio__check,
        .q-toggle__track,
        .q-toggle__thumb {
            transition: none !important;
        }
        
        /* Style the checkbox box itself */
        .q-checkbox__bg {
            border-radius: 4px !important;
            border: 2px solid #71717a !important;
            background: transparent !important;
        }
        
        /* Checked state */
        .q-checkbox--truthy .q-checkbox__bg {
            border-color: #3b82f6 !important;
            background: #3b82f6 !important;
        }
        
        /* Hover effect on checkbox */
        .q-checkbox:hover .q-checkbox__bg {
            border-color: #a1a1aa !important;
        }
        
        .q-checkbox--truthy:hover .q-checkbox__bg {
            border-color: #60a5fa !important;
            background: #60a5fa !important;
        }
        
        /* Checkmark color */
        .q-checkbox__svg {
            color: white !important;
        }
        
        /* Button toggle group */
        .q-btn-toggle .q-btn {
            transition: background-color 0.1s ease, color 0.1s ease !important;
        }
        
        /* Ripple effect - completely disable everywhere */
        .q-ripple,
        [class*="q-ripple"],
        .q-btn .q-ripple,
        .q-checkbox .q-ripple,
        .q-radio .q-ripple,
        .q-toggle .q-ripple {
            display: none !important;
            opacity: 0 !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }
        
        /* ===== NUKE THE FOCUS CIRCLE COMPLETELY ===== */
        /* This is the semi-transparent circle that gets stuck */
        .q-checkbox__inner--truthy::before,
        .q-checkbox__inner--falsy::before,
        .q-checkbox__inner::before,
        .q-checkbox .q-checkbox__inner::before,
        .q-radio__inner--truthy::before,
        .q-radio__inner--falsy::before,
        .q-radio__inner::before,
        .q-toggle__inner--truthy::before,
        .q-toggle__inner--falsy::before,
        .q-toggle__inner::before {
            display: none !important;
            content: '' !important;
            opacity: 0 !important;
            visibility: hidden !important;
            background: transparent !important;
            background-color: transparent !important;
            transform: scale(0) !important;
            width: 0 !important;
            height: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }
        
        /* ========== CUSTOM PROGRESS BAR ========== */
        .custom-progress-container {
            width: 100%;
            display: flex;
            flex-direction: column;
            gap: 4px;
            /* Prevent layout shift */
            min-height: 28px;
        }
        
        .custom-progress-track {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.15);
            border-radius: 4px;
            overflow: hidden;
            position: relative;
            /* Ensure track is always visible */
            min-height: 8px;
        }
        
        .custom-progress-fill {
            height: 100%;
            border-radius: 4px;
            position: relative;
            /* Default color if status class doesn't apply */
            background: #3b82f6;
            /* Smooth width changes */
            will-change: width;
        }
        
        .custom-progress-label {
            text-align: center;
            font-size: 14px;
            color: #a1a1aa;
        }
        
        /* ===== RENDERING - Blue with shimmer ===== */
        /* ===== RENDERING - Engine-specific colors ===== */
        .custom-progress-rendering .custom-progress-fill {
            background: #a1a1aa;  /* Default gray if no engine match */
            transition: background 0.3s ease;
        }
        
        /* Blender - Orange */
        .custom-progress-rendering.custom-progress-engine-blender .custom-progress-fill {
            background: #ea7600;
        }
        .custom-progress-rendering.custom-progress-engine-blender .custom-progress-track {
            box-shadow: 0 0 8px rgba(234, 118, 0, 0.4);
            animation: render-glow-blender 2s ease-in-out infinite;
        }
        @keyframes render-glow-blender {
            0%, 100% { box-shadow: 0 0 4px rgba(234, 118, 0, 0.3); }
            50% { box-shadow: 0 0 12px rgba(234, 118, 0, 0.6); }
        }
        
        /* Marmoset - Red/Pink */
        .custom-progress-rendering.custom-progress-engine-marmoset .custom-progress-fill {
            background: #ef0343;
        }
        .custom-progress-rendering.custom-progress-engine-marmoset .custom-progress-track {
            box-shadow: 0 0 8px rgba(239, 3, 67, 0.4);
            animation: render-glow-marmoset 2s ease-in-out infinite;
        }
        @keyframes render-glow-marmoset {
            0%, 100% { box-shadow: 0 0 4px rgba(239, 3, 67, 0.3); }
            50% { box-shadow: 0 0 12px rgba(239, 3, 67, 0.6); }
        }
        
        .custom-progress-rendering .custom-progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255, 255, 255, 0.4) 50%,
                transparent 100%
            );
            animation: shimmer 2s ease-in-out infinite;
        }
        
        @keyframes shimmer {
            0% { transform: translateX(-100%); opacity: 0; }
            50% { opacity: 1; }
            100% { transform: translateX(200%); opacity: 0; }
        }
        
        /* ===== QUEUED - Neutral gray ===== */
        .custom-progress-queued .custom-progress-fill {
            background: #52525b;
        }
        
        /* ===== PAUSED - Neutral white/gray with subtle glow ===== */
        .custom-progress-paused .custom-progress-fill {
            background: #a1a1aa;
        }
        
        .custom-progress-paused .custom-progress-track {
            box-shadow: 0 0 8px rgba(161, 161, 170, 0.3);
            animation: paused-glow 2s ease-in-out infinite;
        }
        
        @keyframes paused-glow {
            0%, 100% { box-shadow: 0 0 4px rgba(161, 161, 170, 0.2); }
            50% { box-shadow: 0 0 10px rgba(161, 161, 170, 0.4); }
        }
        
        /* ===== COMPLETED - Green with shine ===== */
        .custom-progress-completed .custom-progress-fill {
            background: #22c55e;
        }
        
        .custom-progress-completed .custom-progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255, 255, 255, 0.3) 50%,
                transparent 100%
            );
            animation: success-shine 3s ease-in-out infinite;
        }
        
        @keyframes success-shine {
            0%, 70%, 100% { transform: translateX(-100%); }
            35% { transform: translateX(200%); }
        }
        
        /* ===== FAILED - Red ===== */
        .custom-progress-failed .custom-progress-fill {
            background: #ef4444;
        }
        
        .custom-progress-failed .custom-progress-track {
            animation: failed-pulse 2s ease-in-out infinite;
        }
        
        @keyframes failed-pulse {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 1; }
        }
        
        /* ========== OLD PROGRESS BAR (hidden/disabled) ========== */
        .q-linear-progress__track,
        .q-linear-progress__model {
            transition: none !important;
        }
        
        /* Hide ALL text/labels inside and around progress bar - very aggressive */
        .q-linear-progress *:not(.q-linear-progress__track):not(.q-linear-progress__model),
        .q-linear-progress__string,
        .q-linear-progress > div:not(.q-linear-progress__track):not(.q-linear-progress__model),
        .q-linear-progress span,
        .q-linear-progress div[class*="string"],
        .q-linear-progress div[class*="label"],
        .q-linear-progress__track span,
        .q-linear-progress__model span,
        .progress-bar-no-label span,
        .q-linear-progress > span,
        .nicegui-linear-progress span,
        /* Target value display elements */
        .q-linear-progress__value,
        .q-linear-progress [class*="value"],
        .q-linear-progress [class*="Value"],
        .q-linear-progress__stripe + span,
        .q-linear-progress + span,
        /* Any floating/absolute positioned text near progress */
        .q-linear-progress [style*="position: absolute"],
        .q-linear-progress [style*="position:absolute"] {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            font-size: 0 !important;
            color: transparent !important;
            width: 0 !important;
            height: 0 !important;
            overflow: hidden !important;
        }
        
        /* Make progress bar taller and always visible */
        .q-linear-progress {
            height: 8px !important;
            min-height: 8px !important;
            border-radius: 4px !important;
            overflow: hidden !important;
            background: rgba(255, 255, 255, 0.15) !important;
            font-size: 0 !important;
            color: transparent !important;
        }
        
        .q-linear-progress__track {
            border-radius: 4px !important;
            opacity: 1 !important;
            background: rgba(255, 255, 255, 0.15) !important;
            height: 100% !important;
        }
        
        .q-linear-progress__model {
            border-radius: 4px !important;
            opacity: 1 !important;
            min-width: 0 !important;
            height: 100% !important;
        }
        
        /* Ensure track is always visible even at 0% */
        .q-linear-progress__track--dark {
            background: rgba(255, 255, 255, 0.15) !important;
        }
        
    </style>
    '''


def get_notification_suppression_js() -> str:
    """
    Get JavaScript to suppress NiceGUI/Quasar notifications.
    
    This is a desktop app - connection notifications are unnecessary.
    """
    return '''
    <script>
        // Completely disable Quasar notifications for desktop app
        (function() {
            // Immediately hide any notification container
            const style = document.createElement('style');
            style.textContent = `
                .q-notification,
                .q-notification--standard,
                .q-notifications,
                .q-notifications__list,
                .q-notification__wrapper,
                [class*="q-notification"] {
                    display: none !important;
                    visibility: hidden !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                    position: absolute !important;
                    left: -9999px !important;
                }
            `;
            document.head.appendChild(style);
        })();
        
        document.addEventListener('DOMContentLoaded', function() {
            // Override Quasar Notify plugin
            if (window.Quasar && window.Quasar.Notify) {
                window.Quasar.Notify.create = function() { return { dismiss: function() {} }; };
                window.Quasar.Notify.setDefaults = function() {};
            }
            
            // Also try to override it on the Vue instance
            setTimeout(function() {
                if (window.Quasar && window.Quasar.Notify) {
                    window.Quasar.Notify.create = function() { return { dismiss: function() {} }; };
                }
            }, 100);
            
            // MutationObserver to immediately remove any notifications and stuck checkbox effects
            const observer = new MutationObserver(function(mutations) {
                // Remove notifications
                const notifications = document.querySelectorAll(
                    '.q-notification, .q-notifications, [class*="q-notification"]'
                );
                notifications.forEach(n => {
                    n.style.display = 'none';
                    n.remove();
                });
                
                // Clean up stuck checkbox/radio/toggle ripple and focus effects
                document.querySelectorAll('.q-focus-helper, .q-ripple, [class*="focus-helper"]').forEach(el => {
                    el.style.cssText = 'display:none!important;opacity:0!important;visibility:hidden!important;transform:scale(0)!important;';
                    try { el.remove(); } catch(e) {}
                });
            });
            
            observer.observe(document.body, { childList: true, subtree: true });
            
            // Clean up checkbox/toggle stuck states on any click
            document.addEventListener('click', function(e) {
                // Immediate cleanup
                cleanupCheckboxEffects();
                // Also cleanup after Quasar animations
                setTimeout(cleanupCheckboxEffects, 50);
                setTimeout(cleanupCheckboxEffects, 150);
                setTimeout(cleanupCheckboxEffects, 300);
            }, true);
            
            // Clean up on mouseup too (catches drag releases)
            document.addEventListener('mouseup', function(e) {
                setTimeout(cleanupCheckboxEffects, 50);
            }, true);
            
            // Aggressive cleanup function
            function cleanupCheckboxEffects() {
                // Hide all focus helpers and ripples
                document.querySelectorAll('.q-focus-helper, .q-ripple, [class*="focus-helper"]').forEach(el => {
                    el.style.cssText = 'display:none!important;opacity:0!important;visibility:hidden!important;transform:scale(0)!important;';
                });
                // Reset inner element backgrounds
                document.querySelectorAll('.q-checkbox__inner, .q-radio__inner, .q-toggle__inner').forEach(el => {
                    el.style.background = 'transparent';
                });
                // Force hide any pseudo-element circles by setting the parent overflow
                document.querySelectorAll('.q-checkbox, .q-radio, .q-toggle').forEach(el => {
                    el.style.overflow = 'visible';
                });
            }
            
            // Run cleanup periodically as a safety net
            setInterval(cleanupCheckboxEffects, 500);
            
            // ========== SMOOTH PROGRESS BAR ANIMATION ==========
            // Track current animated widths for each progress bar
            const progressState = {};
            const ANIMATION_SPEED = 0.06; // Easing factor (0-1, lower = smoother)
            const MIN_STEP = 0.15; // Minimum step per frame for visible movement
            
            // Global function to update progress without UI refresh
            window.updateJobProgress = function(jobId, progress, elapsed, framesDisplay, samplesDisplay, passDisplay) {
                const fill = document.getElementById('progress-fill-' + jobId);
                const label = document.getElementById('progress-label-' + jobId);
                const info = document.getElementById('job-info-' + jobId);
                const renderProgress = document.getElementById('job-render-progress-' + jobId);
                
                if (fill) {
                    fill.dataset.target = progress;
                }
                if (label) {
                    label.textContent = progress + '%';
                }
                if (info && elapsed) {
                    // Get the base text without the render progress span
                    var baseText = info.textContent;
                    if (renderProgress) {
                        baseText = baseText.replace(renderProgress.textContent, '').trim();
                    }
                    
                    // Update elapsed time
                    if (baseText.includes('Time:')) {
                        baseText = baseText.replace(/Time: [0-9:]+/, 'Time: ' + elapsed);
                    } else {
                        baseText = baseText + ' | Time: ' + elapsed;
                    }
                    
                    // Build render progress string (pass/frame/samples)
                    var progressParts = [];
                    // Show pass info for multi-pass renders
                    if (passDisplay && passDisplay.length > 0) {
                        progressParts.push(passDisplay);
                    }
                    // For animations, show current/total frame
                    if (framesDisplay && framesDisplay.includes('/')) {
                        progressParts.push('Frame ' + framesDisplay);
                    }
                    if (samplesDisplay) {
                        progressParts.push('Sample ' + samplesDisplay);
                    }
                    var progressText = progressParts.length > 0 ? ' | ' + progressParts.join(' | ') : '';
                    
                    // Reconstruct the HTML (same gray color, no special styling)
                    info.innerHTML = baseText + '<span id="job-render-progress-' + jobId + '">' + progressText + '</span>';
                }
            };
            
            function animateProgressBars() {
                document.querySelectorAll('.custom-progress-fill[data-target]').forEach(function(fill) {
                    const id = fill.id;
                    if (!id) return;
                    
                    const target = parseFloat(fill.dataset.target) || 0;
                    
                    // If element is new (not in state), set it directly without animation
                    // This prevents the "animate from 0" flash on UI refresh
                    if (!(id in progressState)) {
                        // Check if element has inline width already set
                        const inlineWidth = parseFloat(fill.style.width) || 0;
                        if (inlineWidth > 0) {
                            // Element was created with correct width, sync state to it
                            progressState[id] = inlineWidth;
                        } else {
                            // No inline width, set directly to target (no animation)
                            progressState[id] = target;
                            fill.style.width = target + '%';
                        }
                        return; // Skip animation this frame
                    }
                    
                    const current = progressState[id];
                    const diff = target - current;
                    
                    // Only animate if there's a meaningful difference
                    if (Math.abs(diff) > 0.1) {
                        // Calculate step with easing
                        let step = diff * ANIMATION_SPEED;
                        if (Math.abs(step) < MIN_STEP && Math.abs(diff) > MIN_STEP) {
                            step = diff > 0 ? MIN_STEP : -MIN_STEP;
                        }
                        progressState[id] = current + step;
                        fill.style.width = progressState[id] + '%';
                    } else if (Math.abs(diff) > 0.01) {
                        // Snap to target when very close
                        progressState[id] = target;
                        fill.style.width = target + '%';
                    }
                });
                
                requestAnimationFrame(animateProgressBars);
            }
            
            // Start animation loop
            requestAnimationFrame(animateProgressBars);
        });
        
        // Suppress console errors about connection
        const originalError = console.error;
        const originalWarn = console.warn;
        console.error = function(...args) {
            const msg = args.join(' ');
            if (msg.includes('WebSocket') || msg.includes('connection') || 
                msg.includes('reconnect') || msg.includes('socket')) {
                return;
            }
            originalError.apply(console, args);
        };
        console.warn = function(...args) {
            const msg = args.join(' ');
            if (msg.includes('WebSocket') || msg.includes('connection') || 
                msg.includes('reconnect') || msg.includes('socket')) {
                return;
            }
            originalWarn.apply(console, args);
        };
    </script>
    '''


def get_custom_titlebar_html() -> str:
    """
    Get custom title bar HTML and JavaScript for frameless window mode.
    
    Uses pywebview's JavaScript API for window controls (minimize, maximize, close).
    """
    return '''
    <div id="custom-titlebar" class="custom-titlebar" style="display: none;">
        <div class="titlebar-left">
            <img src="/logos/wain_logo.png" class="titlebar-icon" alt="">
            <span class="titlebar-title">Wain</span>
        </div>
        <div class="titlebar-controls">
            <!-- Minimize button -->
            <button class="titlebar-btn" id="titlebar-minimize" title="Minimize">
                <svg viewBox="0 0 10 10">
                    <rect x="0" y="4.5" width="10" height="1"/>
                </svg>
            </button>
            <!-- Maximize/Restore button -->
            <button class="titlebar-btn" id="titlebar-maximize" title="Maximize">
                <svg viewBox="0 0 10 10" id="maximize-icon">
                    <rect x="0.5" y="0.5" width="9" height="9" fill="none" stroke="currentColor" stroke-width="1"/>
                </svg>
                <svg viewBox="0 0 10 10" id="restore-icon" style="display: none;">
                    <!-- Restore icon (two overlapping windows) -->
                    <path d="M2,0.5 L9.5,0.5 L9.5,7" fill="none" stroke="currentColor" stroke-width="1"/>
                    <rect x="0.5" y="2.5" width="7" height="7" fill="none" stroke="currentColor" stroke-width="1"/>
                </svg>
            </button>
            <!-- Close button -->
            <button class="titlebar-btn titlebar-btn-close" id="titlebar-close" title="Close">
                <svg viewBox="0 0 10 10">
                    <line x1="0" y1="0" x2="10" y2="10" stroke="currentColor" stroke-width="1.2"/>
                    <line x1="10" y1="0" x2="0" y2="10" stroke="currentColor" stroke-width="1.2"/>
                </svg>
            </button>
        </div>
    </div>
    <script>
        // Show title bar only in native pywebview mode
        document.addEventListener('DOMContentLoaded', function() {
            // Check if we're in pywebview (native mode)
            function checkPywebview() {
                if (window.pywebview && window.pywebview.api) {
                    // Add body class for CSS layout adjustments
                    document.body.classList.add('has-custom-titlebar');
                    
                    // Show the custom title bar
                    const titlebar = document.getElementById('custom-titlebar');
                    if (titlebar) {
                        titlebar.style.display = 'flex';
                    }
                    
                    // Enable dragging on titlebar and titlebar-left
                    // This calls the Python API to start native Windows drag
                    const titlebarLeft = document.querySelector('.titlebar-left');
                    if (titlebarLeft) {
                        titlebarLeft.addEventListener('mousedown', function(e) {
                            // Don't start drag if clicking on a button
                            if (e.target.closest('button')) return;
                            // Start native drag
                            window.pywebview.api.start_drag();
                        });
                    }
                    
                    // Also make the titlebar itself draggable (empty space)
                    if (titlebar) {
                        titlebar.addEventListener('mousedown', function(e) {
                            // Only drag if clicking directly on titlebar, not children (except titlebar-left)
                            if (e.target === titlebar || e.target.closest('.titlebar-left')) {
                                if (!e.target.closest('button') && !e.target.closest('.titlebar-controls')) {
                                    window.pywebview.api.start_drag();
                                }
                            }
                        });
                    }
                    
                    // Wire up the window control buttons
                    document.getElementById('titlebar-minimize').addEventListener('click', function() {
                        window.pywebview.api.minimize();
                    });
                    
                    const maxBtn = document.getElementById('titlebar-maximize');
                    const maxIcon = document.getElementById('maximize-icon');
                    const restoreIcon = document.getElementById('restore-icon');
                    let isMaximized = false;
                    
                    function setMaximizedState(maximized) {
                        isMaximized = maximized;
                        if (maximized) {
                            maxIcon.style.display = 'none';
                            restoreIcon.style.display = 'block';
                            maxBtn.title = 'Restore';
                        } else {
                            maxIcon.style.display = 'block';
                            restoreIcon.style.display = 'none';
                            maxBtn.title = 'Maximize';
                        }
                    }
                    
                    maxBtn.addEventListener('click', function() {
                        if (isMaximized) {
                            window.pywebview.api.restore();
                            setMaximizedState(false);
                        } else {
                            window.pywebview.api.maximize();
                            setMaximizedState(true);
                        }
                    });
                    
                    // Double-click title bar to maximize (standard Windows behavior)
                    document.querySelector('.titlebar-left').addEventListener('dblclick', function() {
                        if (isMaximized) {
                            window.pywebview.api.restore();
                            setMaximizedState(false);
                        } else {
                            window.pywebview.api.maximize();
                            setMaximizedState(true);
                        }
                    });
                    
                    document.getElementById('titlebar-close').addEventListener('click', function() {
                        window.pywebview.api.close();
                    });
                    
                    console.log('Custom title bar initialized for native mode');
                } else {
                    // Not in pywebview, hide title bar
                    document.body.classList.remove('has-custom-titlebar');
                    const titlebar = document.getElementById('custom-titlebar');
                    if (titlebar) titlebar.style.display = 'none';
                }
            }
            
            // pywebview API might not be ready immediately
            if (window.pywebview && window.pywebview.api) {
                checkPywebview();
            } else {
                // Wait for pywebview to be ready
                window.addEventListener('pywebviewready', checkPywebview);
                // Also try after a short delay as fallback
                setTimeout(checkPywebview, 500);
            }
        });
    </script>
'''
