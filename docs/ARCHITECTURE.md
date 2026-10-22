# Architecture

```text
Existing local Codex sign-in
       | documented account/rateLimits/read over stdio
       v
Python worker -> normalized quota snapshot -> OLED framebuffer
                                               | 1,024 bytes + sequence + CRC
                                               v
                                        USB -> ESP32 -> OLED
```

`bridge/codex.py` owns a read-only app-server subprocess. Its method allowlist permits initialization and account-rate-limit reads. Codex handles existing authentication and token renewal. No credential-file parsing is implemented.

`bridge/model.py` rejects missing/malformed usage, prefers multi-bucket responses when present, and preserves reported window/reset information. The worker keeps the last successful snapshot on errors and reconnects the source. Freshness is separate from the quota value.

`bridge/render.py` draws the exact 128×64 monochrome framebuffer using an original bitmap font. The same pixels are sent through USB and saved as a local PNG. The serial layer checks sequence/CRC acknowledgements and reconnects after errors.

The firmware accepts bounded `F sequence crc32 hex_pixels` and `PING` lines, rejects malformed frames, and applies a host-offline watchdog. It has no WiFi configuration or network listener. The OLED uses V2 pins. PRG events select windows or local display settings.

After a matching sequence/CRC acknowledgement, the bridge saves the exact frame and acknowledgement in its atomic local status record. `bridge/display.py` validates this record and displays it at integer pixel scales without independently re-rendering quota values. Missing acknowledgements never become live preview frames. The preview is a visible local Tk process, with no provider client, USB access, or network listener. Its 200 ms status refresh follows the monitor's 1 Hz frames. Hardware panel brightness/rotation and firmware watchdog screens are outside the host framebuffer.

`bridge/studio.py` edits a draft in an embedded frame of the display window and saves only validated layout data on Apply. Live/Design navigation preserves the editor instance, cancels interrupted transitions, and never creates another top-level window. `bridge/layout.py` enforces schema/version/type/size, geometry, no overlap, and one mandatory status widget. Invalid runtime changes retain the last valid layout. `bridge/widgets.py` exposes a clipped drawing canvas and fixed reviewed registry; JSON never resolves Python imports. The same renderer sends custom layouts to USB. The live mirror follows acknowledged output, while studio drafts use synthetic data. `bridge/ui.py` supplies rounded native controls, eased hover/view motion, an acknowledgement-status pulse respecting Windows' animation preference, and a Windows app identity set before UI creation.

Account reads occur every 60 seconds by default, with a minimum configured interval of 30 seconds. Frame updates occur at 1 Hz. Dependency versions are pinned. Upstream protocol changes should produce a visible source error; credential scraping is not an acceptable fallback.

Windows notification-area/startup scripts are the supported delivery path. Other operating systems and providers are contribution areas, not supported features.

`bridge/tray.py` registers an original multi-resolution icon with Windows using standard-library ctypes. Its message pump runs inside the bridge process; no separate supervisor or tray dependency is installed. Registration precedes account/USB access, Explorer restarts trigger re-registration, and an icon failure stops monitoring. Menu actions are queued to the main loop. Pause closes USB and signals the usage worker to exit. Resume waits for that worker to close before creating a fresh client, preventing overlapping provider subprocesses. Quit keeps the icon present during bounded client cleanup, then removes it. Windows owns notification overflow/pinning preferences.

## Guided setup and providers

`Run Quota Orb.cmd` invokes `scripts/Launch.ps1`, which creates the local environment and opens the native Tk desktop wizard. No HTTP listener is used. Provider login commands use fixed argument arrays and a visible vendor-owned console; Quota Orb does not capture their output. It verifies usable quota fields before enabling monitor start.

Codex retains the existing read-only app-server path. Claude's opt-in status line sends JSON through local stdin to `bridge/claude.py`; that adapter saves only whitelisted numeric five-hour/weekly quota fields and receipt time. `ClaudeFileClient` preserves the original event time on every cache read so idle data becomes stale. It never refreshes age merely by rereading a file. Events are not a guarantee of a new server quota query.

`bridge/providers.py` contains capability metadata, fixed login dispatch, and non-secret provider/port preferences. Gemini has no enabled authentication or quota client. The wizard changes no global execution policy, never overwrites another Claude status line, and requires explicit confirmation before installing its own status line or replacing firmware.
