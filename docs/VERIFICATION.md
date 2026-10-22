# Verification scope

## Software and device

- 27 local bridge/onboarding checks cover parsing, multi-window limits, freshness, reset handling, framebuffer encoding, serial acknowledgement validation, subprocess lifecycle, and worker failure recovery.
- Firmware compiles for the pinned Heltec ESP32 target.
- The original device prototype passed frame acknowledgement, corrupt-CRC rejection, oversized/partial parser recovery, the offline watchdog, and serial close/reopen recovery.
- The physical OLED was confirmed readable and upright.

Original live diagnostics are deliberately excluded. A new build or fork must run its own checks; local checks do not imply remote CI success or validation on another board.

## Enclosure

Local CAD checks cover six valid single solids, watertight consistently wound meshes, nominal component and fastener clearances, 15 mm header allowance, left USB access, and six-object 3MF placement. Numerical reports and development harnesses remain in ignored local tooling.

The plate is checked in PrusaSlicer at 0.20 mm layers, 0.4 mm nozzle, four walls, 20% gyroid, and supports disabled. The USB tunnel has an 18 mm bridge, so inspect cooling and bridge performance in the actual printer profile. No printer-specific G-code is distributed.

The enclosure has not been physically printed or fit-tested. Required checks are fit-coupon alignment, actual header projection, cable-hood clearance, screw/nut fit, stand stability under cable pull, button access, and sustained operating temperature. Electronics in renders are illustrative proxies. All showcase quota values are simulated.

The assembly render is 13 seconds at 1920×1080 and 24 fps. Its camera path is baked with per-frame safe-framing checks and matching opening/closing poses. Media validation decodes all 312 frames and extracts a nine-frame storyboard for visual review.

The experimental Claude adapter has synthetic protocol/security checks only. No live Claude account or Gemini quota adapter was validated. Fresh Codex browser login was checked by fixed-argument dispatch tests; an existing signed-in Codex quota read was verified separately. No new sign-in or firmware flash is triggered by these checks.
