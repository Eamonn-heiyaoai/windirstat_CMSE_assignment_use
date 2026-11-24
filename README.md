# AI-Assisted Disk Space Analysis and File Organisation Tool

A course-project extension of [WinDirStat](https://github.com/windirstat/windirstat) for Windows. It combines WinDirStat's existing scanner with a local Python analysis interface and optional DeepSeek-generated **review advice**. It does **not** delete or move files automatically.

> Independent student project for Contemporary Methods in Software Engineering (AUT–CJLU BCIS Cycle 13). Not an official WinDirStat release.

## Features

- Scan drives or selected folders with the existing WinDirStat desktop interface.
- Open **Tools → AI Analysis** after a scan, or open an existing WinDirStat CSV or JSON report in the Python interface.
- Review file counts, logical sizes, file types and size ranges. The minimum size setting controls which files count as priority files.
- Get offline suggestions for Edge, Chrome and Firefox caches, user temporary files, and caches for pip, VS Code, VS Code Insiders, Discord, npm and NuGet.
- After a fresh WinDirStat scan, review registered desktop apps whose installation directories were fully scanned and occupy at least 1 GiB. Windows Settings provides the uninstall option.
- Optionally use DeepSeek to identify unfamiliar AppData directories and request step-by-step guidance for an individual result. Each request requires confirmation.
- Browse suggestions 10 at a time or expand the complete list. The interface supports **中文** and **English**.

## Requirements

- Windows 11 development/test environment (other Windows versions have not been verified by this team).
- Visual Studio with the **Desktop development with C++** workload, the **v145** toolset configured in the project, and a Windows SDK.
- Python **3.11** with Tkinter. Use `python` from the terminal and make `pythonw.exe` available to the WinDirStat launcher.
- Internet access and a valid DeepSeek API key with usable credits **only** for optional AI advice.

The Python pipeline uses the Python standard library.

## Clone and build

```powershell
git clone https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use.git
cd windirstat_CMSE_assignment_use
```

Open `windirstat.sln` in Visual Studio, select **x64**, and choose **Build → Build Solution**. Use **Debug → Start Without Debugging (Ctrl+F5)** to run the build from this repository.

The C++ launcher searches upward from the executable directory for `ai_pipeline/app.py`, so keep the build output inside the cloned repository's directory tree. The launcher assumes `pythonw.exe` is discoverable via Windows. If it cannot be found, install Python 3.11 and verify Python is available from a fresh terminal.

## Configure DeepSeek (optional)

**The API key is never required for local analysis.** To enable external advice:

1. Get an API key from [DeepSeek Platform](https://platform.deepseek.com/) and ensure the account has usable credits.
2. In the repository root, create `.env` from the template if you do not already have it.
   ```powershell
   if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
   ```
3. Open `.env` and set the key.
   ```dotenv
   DEEPSEEK_API_KEY=YOUR_OWN_KEY
   ```

The app reads the key when it is ready to send a confirmed request. Keep real keys in the ignored `.env` file. The repository template contains an empty key field.

## Run the application

### Option A: Integrated WinDirStat workflow

1. Start the locally built WinDirStat executable.
2. Scan a drive or folder and allow the scan to finish.
3. Select **Tools → AI Analysis**.
4. Choose **中文 / English**, set the priority-file threshold and choose whether to enable DeepSeek. Leave the box unchecked for offline suggestions.
5. Click **开始分析 / Analyze**. If DeepSeek is enabled, review the data-sharing prompt. Declining continues locally. The app also shows local suggestions if it receives no usable online findings.
6. Select an item in **清理建议 / Cleanup suggestions** to read its details. For a DeepSeek result, click **查看清理步骤 / View cleanup steps** and confirm. The steps and possible effects appear in the details pane. For uncertain directories, the guide explains what to check before clearing anything. Reopening an already generated guide in the same language reuses it until you start a new analysis.

The integrated workflow attempts to remove its temporary JSON report after reading it or closing the window. Parsed data stays in memory for repeat analysis while the window is open.

### Option B: Open a saved report directly

From the repository root:

```powershell
python -m ai_pipeline.app
```

Use **选择文件 / Choose file** to select an existing WinDirStat `.csv` or `.json` report. Keep private exports in the ignored `scan-reports/` directory if you store them inside the workspace. Imported reports support cache suggestions. Installed-app matching is available for fresh scans opened from WinDirStat.

To pre-fill a report path:

```powershell
python -m ai_pipeline.app "C:\path\to\scan.json"
```

For command-line aggregate inspection:

```powershell
python -m ai_pipeline.disk_analyzer "C:\path\to\scan.json" --min-mb 100
```

For command-line cleanup advice:

```powershell
python -m ai_pipeline.ai_advisor "C:\path\to\scan.json" --language en
```

Add `--api` for online detection. The CLI requires an interactive terminal and an explicit `yes` before sending directory summaries.

## Testing and continuous integration

Run the included Python unit tests from the repository root:

```powershell
python -m unittest ai_pipeline.test_pipeline -v
```

The Python unit tests cover report parsing, cleanup grouping and pagination, installed-app matching, and consent and payload checks for both DeepSeek requests. GitHub Actions runs the same command on Python 3.11 for pushes to the configured branches and pull requests targeting `master`. [.github/workflows/python-tests.yml](.github/workflows/python-tests.yml)

The full Windows interface, live DeepSeek responses, and the temporary report lifecycle require separate integration testing.

## Architecture and privacy

```text
WinDirStat C++ scanning/UI
    └── Tools → AI Analysis
          └── temporary JSON export (WinDirStat SaveResults)
                └── ai_pipeline/report_parser.py
                      └── Tkinter interface (ai_pipeline/app.py)
                            ├── Local statistics and cache rules (disk_analyzer.py)
                            ├── Local installed-app matching (installed_apps.py)
                            └── Confirmed online requests
                                  ├── Redacted directory summaries (directory_summary.py)
                                  └── Detection and per-item guidance (ai_advisor.py)
```

- **Offline analysis** uses scan metadata and, for fresh WinDirStat scans, reads the local Windows uninstall registry. All processing stays on the device.
- **Online detection** sends IDs, redacted labels and scanned sizes for up to 24 selected AppData directories. Displayed sizes come from the scan.
- **Per-item guidance** sends the selected directory label, scanned size and whether its purpose needs verification. Both requests omit the drive, Windows profile folder, filenames, file contents and registry values. Remaining directory labels can reveal software or personal information.

DeepSeek can misidentify folders or give inaccurate instructions. Confirm a folder's purpose and check the steps before making changes. Displayed sizes reflect scanned usage and can differ from the amount a cleanup frees. Files that could not be scanned may be absent from the results.

## Project evidence

- [Iteration 1 issue and acceptance criteria](https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use/issues/7)
- [Parser PR #8](https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use/pull/8)
- [Privacy-aware candidate selector PR #9](https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use/pull/9)
- [Automated tests PR #10](https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use/pull/10)
- [GitHub Actions PR #11](https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use/pull/11)
- [First successful automated run](https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use/actions/runs/45342164570)
- [Detailed analysis and AI extension commit](https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use/commit/081a99eebcb27883376097f0ca8805598717e977)

## Team

- Mao Lingyun (Eamonn)
- Chen Zihan (Han)
- Dong Yuzhe (Dylan)
- Fang Letian (Lamelo)

## Attribution and licensing

Based on [WinDirStat](https://github.com/windirstat/windirstat), an open-source application distributed under GPL-3.0-or-later terms, with additional notices and licence terms in the upstream repository. Preserve applicable notices when reusing or distributing the application. This project is not affiliated with, endorsed by, or maintained by the WinDirStat team.
