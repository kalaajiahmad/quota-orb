# Setup: from download to desk

The app requires **Python 3.10+ with Tcl/Tk** and supports the **Heltec WiFi Kit 32 V2, classic ESP32, 8 MB flash, 128×64 OLED**. Other board revisions and capacities need a separately verified firmware target. A ChatGPT/Claude/Gemini browser session does not, by itself, connect a local CLI.

## 1. Download and launch

Download this repository's ZIP and extract it, or clone it using Git. Keep it in a folder where your user can create files. Install Python 3.10+ with Tcl/Tk and ensure it is on PATH. On Linux, your distribution may package Tk and venv separately.

On Windows, double-click **`Run Quota Orb.cmd`**. On macOS or Linux, open a terminal in the extracted folder and run:

```sh
sh scripts/launch.sh
```

The launcher creates a local `.venv` when needed and installs the pinned runtime dependencies. The first launch opens setup. After you complete setup, the same launcher starts the monitor and opens or focuses the desktop display. An internet connection is needed for first-time dependencies, provider installation/sign-in, and quota reads. No Quota Orb cloud account or web server is required.

macOS and Linux paths have not yet been verified on physical machines; serial permissions and window behavior depend on the operating system and desktop environment. The guided firmware installer currently supports Windows only. On Windows, inspect the source and use the normal trust/unblock workflow if a downloaded launcher is blocked.

## 2. Choose a provider

The wizard lists provider capability explicitly:

| Provider | Connection | What is supported |
|---|---|---|
| **Codex** | Official Codex CLI browser sign-in | Documented account-quota polling every 60 seconds |
| **Claude Code** | Official Claude Code sign-in + opt-in local status line | Experimental five-hour/weekly quota events, when the CLI supplies them |
| **Gemini** | No connection enabled | No verified read-only account-quota adapter in this release |

**Install provider CLI** opens the provider's official installation documentation. Install its trusted native CLI for your operating system, then reopen the wizard if PATH changed. Quota Orb does not download or install an AI client for you. It detects Codex on PATH or in the desktop app's usual local bin folder; Claude Code must be installed as a native executable on PATH or in its usual local bin folder.

**Preview demo** shows synthetic output without an account or a board. It never signs in, contacts a model, or opens USB.

## 3. Connect and verify account access

### Codex

1. Select **Codex** and click **Check connection**. If its CLI is already signed into an eligible ChatGPT account, the wizard verifies the returned quota fields without another login.
2. If it is not connected, click **Sign in with provider**. This runs the fixed command `codex login` in the official CLI and opens its browser sign-in. Complete that flow in the provider's window.
3. Return and click **Check connection** again. Continue only when the wizard says **quota access verified**.

The app does not ask for a password, API key, cookie, access token, or authorization code. Authentication output is not captured by Quota Orb. The official CLI stores and renews its own credentials according to its configuration. A browser ChatGPT session may make the vendor's login quicker, but it is not used as an integration credential. API-key-only sign-in cannot supply ChatGPT subscription allowance. Organization policies may restrict available authentication or quota access.

### Claude Code — experimental

1. Install the native Claude Code CLI. Select **Claude Code**. If needed, use **Sign in with provider**, which runs `claude auth login`. Complete its normal browser flow.
2. Click **Enable Claude events** and read the confirmation. This adds only Quota Orb's `statusLine` entry to the current user's Claude Code settings, respecting `CLAUDE_CONFIG_DIR` when set. It does not read authentication files. Existing unrelated settings are preserved.
3. If another status line is already configured, setup **refuses to overwrite it**. Keep that configuration and follow the [manual integration note](#existing-claude-status-line) below.
4. Open/use Claude Code normally in an eligible subscription session. Its quota fields appear only when the CLI supplies them after a response. Quota Orb never sends a model request to obtain a reading.
5. Return to the wizard and click **Check connection**. It waits until valid recent quota events exist. Missing fields are unavailable, never assumed to mean zero usage.

Only five-hour and weekly numeric percentages/reset times are retained. Raw event input can include workspace paths and session identifiers; those fields are discarded in memory and are neither logged nor saved. The adapter does not read transcripts. Gateway spending, API billing, and every model-specific quota are not supported.

Claude updates are **event-driven**. A recent event does not prove a new server quota read. Idle/closed sessions become **STALE**; reopening Quota Orb cannot force a refresh. Managed hook policies or project settings can prevent the status line from running. This adapter has fixture-based checks; it has not been validated against a live Claude subscription in this project.

**Remove Claude link** removes only the exact status-line configuration installed by this copy of Quota Orb. It refuses if that setting was changed by another tool. It does not sign out or remove unrelated settings. Stop the monitor separately.

### Gemini

The wizard labels Gemini **unavailable** and starts no login or model request for it. Successful Google sign-in alone would not establish reliable remaining account quota. Gemini's interactive statistics and token usage should not be presented as verified remaining allowance. A supported adapter is future work.

## 4. Connect and prepare the board (optional)

Skip this section for desktop-only use. To use the physical OLED, connect the Heltec through a **micro USB data cable**. Click **Find board**, select the correct CP210x serial port, then click **Check USB**. Install the Silicon Labs CP210x driver if Windows does not expose a serial port. With several CP210x devices, verify the physical board before selecting one. A CP210x adapter alone does not identify its board revision.

**Check USB** performs the Quota Orb firmware handshake and checks that the OLED acknowledged on I2C. It does not flash the board. Stop any running monitor before checking the port. A successful handshake does not prove the physical pixels are upright; inspect the actual OLED.

On Windows, if the board needs Quota Orb firmware, click **Install V2 firmware**. Guided installation is Windows-only:

1. Confirm that the connected board is the specified V2/8 MB target. The installer runs in a visible console.
2. It stops this project's monitor, installs the pinned PlatformIO build dependencies, and compiles firmware.
3. It checks detected flash capacity. If it cannot confirm **8 MB**, it aborts without upload. Do not bypass this check for another board.
4. It reads a complete **8 MB flash backup** into the ignored local `backups/` folder, verifies its length, and records a SHA-256 checksum. If backup fails, upload does not proceed.
5. It uploads the firmware. Keep the board connected until it finishes, then return and **Check USB** again.

Flashing replaces the previous firmware. Keep the backup private: old firmware can contain network credentials or other secrets. No backup or prebuilt firmware image is part of the public repository. Restoring a backup is an advanced operation using the matching esptool and detected flash capacity; preserve the file and checksum before attempting recovery.

| V2 signal | GPIO |
|---|---:|
| OLED SDA / SCL | 4 / 15 |
| OLED reset | 16 |
| OLED address | 0x3C |
| PRG button | 0 |

## 5. Start and check the result

Once **quota access** is verified, click **Start monitor**. USB verification is required only when a board is selected. The wizard saves the selected provider and optional serial port under ignored `.runtime/` preferences. On Windows, the monitor registers a notification icon. If using the board, wait for the acknowledged frame count to increase and check the OLED.

The display shows the selected provider, remaining percentage, reported window, reset countdown, and freshness. Codex polls every 60 seconds; the OLED redraws every second. Claude follows status-line events. Both retain a last good reading as **STALE** on failures. Expired reset timers wait for confirmation rather than inventing replenishment.

On Windows, closing setup leaves the monitor running with its notification icon. Look beside the clock or under the taskbar overflow arrow. Windows controls its placement. On macOS and Linux, there is no notification icon: use the app window to manage the monitor. Closing the last display/widget window stops it.

For normal use after setup, use the same launcher from step 1. It starts monitoring with saved preferences and opens the live display. If the monitor is already running, it opens or focuses the existing display without creating another monitor. To change provider or board, stop monitoring and open setup from the application.

**Upgrading an older Codex Peek or Quota Orb copy:** stop the old copy, then use the launcher inside the new release. Older extracted folders remain separate installations. Quit the old monitor using its notification icon before opening the new copy.

On Windows, the notification icon controls are:

| Icon / control | Meaning |
|---|---|
| Green status dot | Live provider data and connected USB |
| Amber status dot | USB disconnected, stale data, or waiting for a refresh |
| Red status dot | USB connected, but quota data unavailable or blocked |
| Grey status dot | Paused, pausing/resuming, or stopping |
| Click icon / **Open live display** | Open the live, acknowledged OLED mirror; **Edit layout** opens the studio |
| Right-click → **Open setup** | Reopen provider and USB setup |
| Right-click → **Show status** | Provider/source state, USB state, acknowledged frames |
| Right-click → **Pause monitoring** | Close USB and stop this monitor's quota polling; keep the icon visible |
| Right-click → **Resume monitoring** | Start a fresh provider client after the previous client has closed; reconnect USB |
| Right-click → **Quit Quota Orb** | Stop the monitor, close its provider client, and remove the icon |

An in-flight provider request may need time to finish. The icon shows **Pausing** or **Stopping** during cleanup; allow up to 40 seconds. The board shows **USB OFFLINE** within six seconds of frame updates stopping. Claude's separately configured status line remains active in Claude Code after Pause/Quit: use **Remove Claude link** in setup to stop that event cache. Quitting the monitor does not log out of a provider or close its independently opened windows.

The live window reads the atomic local status record every 200 ms and displays only frames whose sequence/CRC were acknowledged by the board. OLED frames update at 1 Hz. **1×** maps one OLED pixel to one image pixel; **2×/4×/6×** enlarge without smoothing. If USB disconnects or monitoring pauses, the last confirmed frame remains clearly labeled; the board can independently show its offline watchdog screen. Brightness and the board's hardware rotation are panel settings, not framebuffer pixels, and are not reproduced by the mirror. On Windows, closing the live window leaves monitoring and its icon running; Quit closes the mirror after shutdown. On macOS and Linux, closing the last display/widget window stops the monitor.

On Windows, **Quit Quota Orb** from the notification menu stops the monitor. If Windows refuses icon registration or the icon thread fails, monitoring stops. On macOS and Linux, close the last display/widget window or use **Stop monitor** in setup.

In **Task Manager → Details**, enable the **Command line** column to distinguish the local environment's `pythonw.exe` processes: the monitor runs `-m bridge`, and the live window runs `-m bridge.display`. Codex monitoring also owns a `codex.exe app-server` child. A branded taskbar icon and Windows app identity do not rename the executable to `Quota Orb.exe` or `Codex Peek.exe`. No Windows service or scheduled task is installed.

To change provider/account/board, stop, update the provider's official client if needed, then repeat the account check and, if using a board, the USB check.

**Login startup is off by default**. Advanced users can run `scripts/Enable-Startup.ps1` to create a launcher in their own Startup folder, or `scripts/Disable-Startup.ps1` to remove it. Optional login startup opens only the notification-area monitor; open its live window from the icon when needed. The project must remain in its chosen location.

| PRG press, applied on release | Action |
|---|---|
| Under 0.6 seconds | Next reported quota window |
| 0.6–1.8 seconds | Cycle brightness |
| Over 1.8 seconds | Flip the OLED 180 degrees |

Do not hold PRG during reset/connection: it selects the ESP32 bootloader. Display settings reset after power loss.

## 6. Add a desktop widget

In the display window, click **Add widget**. A compact movable application window shows the locally rendered quota frame and its source state, even without a connected board. Its position and enabled state are saved locally and it reopens when you next open the display. Close the widget to disable it; use **Add widget** again to restore it. If the main display is closed while the widget is open, it stays available. This is an app window rather than a native macOS, Windows, or Linux widget panel integration.

## 7. Design your OLED

1. Open the live display, then choose **Edit layout**. The **same window** transitions into Design with the active custom layout or a starter arrangement. **← Live display** switches back; your draft remains intact across view changes. Its preview is explicitly **simulated draft data**; it does not request account usage or send frames while you edit. Windows identifies the app as Quota Orb with its own icon rather than grouping its window under Python.
2. Drag a widget from the palette onto the canvas, or double-click its palette card to place it. Select an existing widget and drag to move it. Movement follows the pointer, then snaps to a **2 px position grid** on release. Enter exact integer **X / Y / width / height** in the inspector and choose **Update size / position** for precise placement.
3. Add **Custom text** and use **Update text** to change its label. Text uses the OLED's original 5×7 alphabet and clips at its widget bounds. Remove components or **Undo** changes. The renderer clips every widget to its own rectangle.
4. Keep exactly one **Source status** widget. All widgets must fit inside **128×64** without overlap. Invalid drafts show a reason and disable **Apply to OLED**. This prevents a large reading from hiding freshness/error state.
5. Choose **Apply to OLED**. Only the validated layout is saved under ignored `.runtime/layout.json`. A running monitor uses it on the next frame; resume first if paused. Return to the live mirror to confirm the exact board-acknowledged result. Applying while stopped saves the layout for next start.
6. Choose **Use classic display** to restore the original renderer immediately. The editor retains your draft until closed, so Apply can switch back.
7. **Export JSON** saves geometry, widget IDs, and any custom text you entered. It includes no live quota snapshot, account identifiers, credentials, or machine paths. Review your own custom text before sharing it. **Import JSON** accepts only a supported, valid data-only layout up to 16 KiB; unknown widget IDs, fields, executable/plugin directives, invalid geometry, and overlaps are refused. Import opens a draft; it does not automatically apply it.

Example layouts are in [`layouts/`](../layouts). Provider/window/remaining/progress/reset widgets use the same selected quota window; short PRG presses still cycle available windows. The source-status widget exposes unavailable, stale, blocked, and expired-reset states. Missing quota stays unavailable, never zero.

Community widgets are reviewed source changes, with a small drawing API and required tests. Layout files cannot install Python modules, run shell commands, or fetch code. Read the [widget contribution guide](WIDGETS.md) before adding a widget or sharing a layout.

## Security and local data

- **Credentials stay with the official provider CLI.** Quota Orb never opens credential caches, browser cookies, or transcripts. It has no credential entry fields, remote backend, telemetry, or local HTTP server.
- Vendor login may create its own logs/cache outside this project. Manage those through the vendor's documentation. Stopping Quota Orb does not revoke a provider session; use the provider's logout/revocation controls when needed.
- Quota Orb creates local aggregate usage logs/status/previews under ignored `.runtime/` and `artifacts/`. Claude's cache contains only numeric quota fields and receipt time. These files can reveal usage patterns; do not post them publicly.
- The board receives only a 1,024-byte rendered framebuffer, sequence, and CRC over USB. It never receives provider tokens or account identifiers.
- Flash backups remain under ignored `backups/`. The public README uses synthetic data throughout.
- To clear Quota Orb's local history, stop it first, then remove its local `.runtime/` and generated `artifacts/` files manually. Keep `artifacts/demo.png` if you want the demo. This does not log out of the provider. Disable startup before moving/removing the project.

## Troubleshooting

| Symptom | Action |
|---|---|
| Launcher reports missing Python/Tk | Install Python 3.10+ with Tcl/Tk and PATH enabled; reopen the terminal |
| Dependency installation fails | Check internet/proxy access to PyPI; rerun the launcher |
| No taskbar window after starting | Use `Run Quota Orb.cmd` from the current extracted release. Stop an older Codex Peek copy first; its old launcher may still run hidden |
| Cannot find the running notification icon | Check the taskbar overflow arrow; rerun the current launcher to open the live window. Start fails if Windows cannot register an icon |
| Cannot find Quota Orb in Task Manager | Use Details and enable Command line; look for `pythonw.exe` with `-m bridge` or `-m bridge.display` |
| Icon is grey / board is offline | Resume monitoring from the icon's right-click menu; pausing intentionally stops frames |
| Provider CLI missing | Use the official installation link, install its native CLI, reopen the wizard |
| Browser signed in but quota check fails | Complete the official CLI sign-in; browser authentication alone is insufficient |
| Codex returns no quota windows | Check subscription/account/workspace and compare with the provider's usage display |
| Claude waits for events | Enable its status line, use an eligible session normally, check project/managed policies |
| Claude existing status line refused | Preserve it; use the manual integration note below |
| Serial port busy | Stop this and other serial monitors before Check USB or flashing |
| No firmware handshake | Verify data cable, V2 hardware, firmware install, and OLED connection |
| Capacity check rejects board | Stop; this release's installer supports the specified 8 MB target only |
| Display is STALE | Check provider connectivity or event freshness; a stale reading is retained intentionally |
| USB OFFLINE | Start the bridge and wait for acknowledged frames; verify PC is awake |

### Existing Claude status line

Quota Orb does not automatically chain arbitrary shell commands. To preserve a custom status line, an experienced user can adapt that script to send the same stdin JSON to the Quota Orb status-line command while keeping the original stdout. Do not write the raw JSON to disk or forward it to a network service. Alternatively, remove the existing status line yourself before opting into Quota Orb's integration. No existing configuration is overwritten automatically.

## Advanced development

Run the automated tests from the project environment with `python -m unittest discover -s tests -v`. The firmware build uses `python -m platformio run` with the dependencies in `requirements.txt`. Runtime dependencies are listed separately in `requirements-bridge.txt`.

## Official interface references

- [Codex sign-in and credential ownership](https://learn.chatgpt.com/docs/auth)
- [Codex app-server and account rate limits](https://learn.chatgpt.com/docs/app-server)
- [Claude Code authentication commands](https://code.claude.com/docs/en/cli-reference)
- [Claude Code status-line quota fields and availability](https://code.claude.com/docs/en/statusline)
- [Gemini authentication](https://geminicli.com/docs/get-started/authentication/) and [structured CLI output](https://geminicli.com/docs/cli/headless/)
