# Setup: from download to desk

The guided app supports **Windows**, **Python 3.10+ with Tcl/Tk**, and the **Heltec WiFi Kit 32 V2, classic ESP32, 8 MB flash, 128×64 OLED**. Other board revisions and capacities need a separately verified firmware target. A ChatGPT/Claude/Gemini browser session does not, by itself, connect a local CLI.

## 1. Download and launch

Download this repository's ZIP and extract it, or clone it using Git. Keep it in a folder where the current Windows user can create files. Install Python from [python.org](https://www.python.org/downloads/windows/) with **Tcl/Tk** and **Add Python to PATH** enabled. Restart the terminal after installing Python.

Double-click **`Run Quota Orb.cmd`**. On first launch it creates a local `.venv` and installs the pinned serial dependency from PyPI. It then opens the local desktop wizard. Later launches reuse that environment. No administrator access, cloud account for Quota Orb, or web server is required. An internet connection is needed for first-time dependencies, provider installation/sign-in, and quota reads.

If Windows blocks an untrusted downloaded file, inspect its source and use Windows' normal trust/unblock workflow. Do not disable Windows security protections.

## 2. Choose a provider

The wizard lists provider capability explicitly:

| Provider | Connection | What is supported |
|---|---|---|
| **Codex** | Official Codex CLI browser sign-in | Documented account-quota polling every 60 seconds |
| **Claude Code** | Official Claude Code sign-in + opt-in local status line | Experimental five-hour/weekly quota events, when the CLI supplies them |
| **Gemini** | No connection enabled | No verified read-only account-quota adapter in this release |

**Install provider CLI** opens the provider's official installation documentation. Install its trusted native Windows CLI, then reopen the wizard if PATH changed. Quota Orb does not download or install an AI client for you. It detects Codex on PATH or in the desktop app's usual local bin folder; Claude Code must be the native `.exe` on PATH or in its usual local bin folder.

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

## 4. Connect and prepare the board

Connect the Heltec through a **micro USB data cable**. Click **Find board**, select the correct CP210x serial port, then click **Check USB**. Install the Silicon Labs CP210x driver if Windows does not expose a serial port. With several CP210x devices, verify the physical board before selecting one. A CP210x adapter alone does not identify its board revision.

**Check USB** performs the Quota Orb firmware handshake and checks that the OLED acknowledged on I2C. It does not flash the board. Stop any running monitor before checking the port. A successful handshake does not prove the physical pixels are upright; inspect the actual OLED.

If the board needs Quota Orb firmware, click **Install V2 firmware**:

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

Once **quota access** and **USB** are verified, click **Start monitor**. The wizard saves only the selected provider and serial port under ignored `.runtime/` preferences. It starts the background bridge and shows source state, USB state, and acknowledged frame count. A launch message alone is not proof that the device is working: wait for the acknowledged count to increase and check the OLED.

The display shows the selected provider, remaining percentage, reported window, reset countdown, and freshness. Codex polls every 60 seconds; the OLED redraws every second. Claude follows status-line events. Both retain a last good reading as **STALE** on failures. Expired reset timers wait for confirmation rather than inventing replenishment.

Closing the wizard **leaves a started monitor running** while the PC is awake. Use **Stop monitor** or `Stop Quota Orb.cmd` to stop it. The board shows **USB OFFLINE** within six seconds. To change provider/account/board, stop, update the provider's official client if needed, then repeat account and USB checks. A named mutex prevents duplicate Quota Orb monitors.

For subsequent use, `Run Quota Orb.cmd` reopens the wizard; `Start Quota Orb.cmd` starts directly using saved preferences. **Login startup is off by default**. Advanced users can run `scripts/Enable-Startup.ps1` to create a launcher in their own Startup folder, or `scripts/Disable-Startup.ps1` to remove it. The project must remain in its chosen location.

| PRG press, applied on release | Action |
|---|---|
| Under 0.6 seconds | Next reported quota window |
| 0.6–1.8 seconds | Cycle brightness |
| Over 1.8 seconds | Flip the OLED 180 degrees |

Do not hold PRG during reset/connection: it selects the ESP32 bootloader. Display settings reset after power loss.

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

Quota Orb does not automatically chain arbitrary shell commands. To preserve a custom status line, an experienced user can adapt that script to send the same stdin JSON to `scripts/Claude-Statusline.ps1` while keeping the original stdout. Do not write the raw JSON to disk or forward it to a network service. Alternatively, remove the existing status line yourself before opting into Quota Orb's integration. No existing configuration is overwritten automatically.

## Advanced command line

```powershell
.\scripts\Setup.ps1             # includes PlatformIO and firmware build
.\scripts\Start.ps1 -Provider codex
.\scripts\Stop.ps1
# Claude, after its status-line integration is installed:
.\scripts\Start.ps1 -Provider claude
```

To build manually: `python -m platformio run` in the project environment. Runtime-only dependencies are in `requirements-bridge.txt`; firmware build dependencies are in `requirements.txt`. The ignored local `tooling/` folder is for development only and is not required or distributed.

## Official interface references

- [Codex sign-in and credential ownership](https://learn.chatgpt.com/docs/auth)
- [Codex app-server and account rate limits](https://learn.chatgpt.com/docs/app-server)
- [Claude Code authentication commands](https://code.claude.com/docs/en/cli-reference)
- [Claude Code status-line quota fields and availability](https://code.claude.com/docs/en/statusline)
- [Gemini authentication](https://geminicli.com/docs/get-started/authentication/) and [structured CLI output](https://geminicli.com/docs/cli/headless/)
