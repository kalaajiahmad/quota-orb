# Verification scope

## Software and device

- The v1.1.1 validation passed 57 local checks covering parsing, quota freshness, transport, worker lifecycle, provider/security flows, tray failure and pause/resume cleanup, exact acknowledged mirror pixels at native/enlarged scales, bounded layout imports/rapid-save recovery, Windows file-sharing recovery, widget clipping, drag/drop, undo, apply preservation, same-window navigation/draft preservation, interrupted transitions, and Windows app identity.
- Firmware compiles for the pinned Heltec ESP32 target.
- The original device prototype passed frame acknowledgement, corrupt-CRC rejection, oversized/partial parser recovery, the offline watchdog, and serial close/reopen recovery.
- The physical OLED was confirmed readable and upright.

Windows notification registration/removal was checked in a desktop session. UI tests construct the actual Tk view/editor and inspect image pixels and interaction state; fixture tests do not prove a particular monitor's DPI/appearance or physical panel rotation. Live USB/custom-layout checks are reported separately from synthetic desktop tests.

For v1.1.1, the updated monitor was run against the connected V2 board: Windows confirmed notification registration, USB acknowledgements advanced, and a custom layout produced a valid sequence/CRC-confirmed mirror frame before classic mode was restored. Its user confirmed the live desktop window was readable, Live/Design stayed in the same window, and the taskbar displayed the correct Quota Orb icon. These checks did not reflash the board or validate a physical enclosure.

Original live diagnostics are deliberately excluded. A new build or fork must run its own checks; local checks do not imply remote CI success or validation on another board.

## v1.1.2 launcher regression checks

The release changes the manual Start launchers to open or focus the live mirror and adds Codex Peek compatibility launchers. Direct `scripts/Start.ps1` use without `-ShowWindow` and optional login startup retain notification-area-only behavior. The required regression scope includes visible startup, repeated-launch focus, one monitor/USB owner, notification registration, shutdown, and interpreter identification in Task Manager. Window identity does not rename `pythonw.exe`, and Windows controls notification overflow placement.

On 23 October 2026, 67 automated Windows checks passed, including ten launcher regressions. The launcher tests execute the real PowerShell/CMD entrypoints in isolated temporary trees and cover fresh startup, existing-monitor reuse, tray-only startup, older-monitor restart guidance, stale/future/dead-process rejection, argument forwarding, startup failure cleanup, repeated desktop requests, and retrying a Windows sharing lock without interrupting frame acknowledgements. Provider/USB launches are mocked in these regressions. Desktop tests release and collect Tk objects on their creating thread before later subprocess tests run. Python compilation and the pinned Heltec firmware build also passed.

Separate checks in a normal Windows desktop session verified that both Start names open a visible, unowned, non-tool **Quota Orb | Display studio** window with an application icon. Repeating either Start reused the same monitor PID and window handle while real V2 USB acknowledgements advanced. Stop cleared the running/tray flags and closed the mirror; the release's Codex Peek alias restarted the monitor and desktop. Live Codex data, a fresh heartbeat, registered tray, connected USB, and a CRC-valid acknowledged mirror were verified after restart. The local prototype's older shortcuts were also redirected to the maintained app after stopping its hidden bridge.

These checks inspect native window state and transport acknowledgements; they do not add a new physical OLED, button, cable-removal, enclosure-fit, or fresh provider sign-in observation. No firmware flash was performed. `-ShowWindow` submits an asynchronous desktop request after confirming monitor health; a desktop startup error is recorded in the local stderr log. The visible-window check above independently confirmed that the request succeeded on this machine. Remote PR/release checks are reported with their GitHub runs.

## Enclosure

Local CAD checks cover six valid single solids, watertight consistently wound meshes, nominal component and fastener clearances, 15 mm header allowance, left USB access, and six-object 3MF placement. Numerical reports and development harnesses remain in ignored local tooling.

The plate is checked in PrusaSlicer at 0.20 mm layers, 0.4 mm nozzle, four walls, 20% gyroid, and supports disabled. The USB tunnel has an 18 mm bridge, so inspect cooling and bridge performance in the actual printer profile. No printer-specific G-code is distributed.

The enclosure has not been physically printed or fit-tested. Required checks are fit-coupon alignment, actual header projection, cable-hood clearance, screw/nut fit, stand stability under cable pull, button access, and sustained operating temperature. Electronics in renders are illustrative proxies. All showcase quota values are simulated.

The assembly render is 13 seconds at 1920×1080 and 24 fps. Its camera path is baked with per-frame safe-framing checks and matching opening/closing poses. Media validation decodes all 312 frames and extracts a nine-frame storyboard for visual review.

The experimental Claude adapter has synthetic protocol/security checks only. No live Claude account or Gemini quota adapter was validated. Fresh Codex browser login was checked by fixed-argument dispatch tests; an existing signed-in Codex quota read was verified separately. No new sign-in or firmware flash is triggered by these checks.
