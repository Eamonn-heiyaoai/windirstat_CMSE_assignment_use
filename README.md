# AI-Assisted Disk Space Analysis and File Organisation Tool

A course-project extension of [WinDirStat](https://github.com/windirstat/windirstat) for Windows. It combines WinDirStat's existing scanner with a local Python analysis interface and optional DeepSeek-generated **review advice**. It does **not** delete or move files automatically.

> Independent student project for Contemporary Methods in Software Engineering (AUT–CJLU BCIS Cycle 13). Not an official WinDirStat release.

## Features

- Scan drives or selected folders with the existing WinDirStat desktop interface.
- Open **Tools → AI Analysis** after a scan; the modified WinDirStat exports a temporary JSON report and passes it to the AI window automatically.
- Alternatively, launch the Python interface independently and select an existing CSV or JSON WinDirStat report.
- Analyse all successfully scanned regular-file metadata locally: total logical size, file counts, category totals, top extensions, size bands and large-file summaries.
- Choose a minimum size threshold for priority-file review. All qualifying file records still contribute to overall statistics.
- Switch the interface between **中文** and **English**.
- Use local, generic advice without an API key, or explicitly enable **DeepSeek AI** for detailed suggestions.
- Send only aggregate statistics and anonymous type/size information to DeepSeek; no raw file names, paths or file contents are sent in the API request.
- Cache parsed records in the current window for repeat analyses and attempt to remove temporary JSON reports created by the WinDirStat-to-Python workflow.

**Limitations:** Advice is based on metadata, not file contents, actual application usage or verified deletion safety. Scans may have inaccessible records; logical file-size totals are not necessarily physical space recoverable. The AI interface does not locate or delete individual files, and it does not validate specific files as safe to remove.

## Requirements

- Windows 11 development/test environment (other Windows versions have not been verified by this team).
- Visual Studio with the **Desktop development with C++** workload, the build tools and Windows SDK required by this WinDirStat fork.
- Python **3.11** available as `python` and `pythonw.exe` (the C++ launcher starts the GUI using `pythonw.exe`).
- Internet access and a valid DeepSeek API key with usable credits **only** for optional AI advice.

The Python pipeline uses Python standard-library modules including `tkinter`, `unittest`, `json` and `urllib`; no third-party Python packages are required by these modules. Visual Studio C++ build prerequisites and toolset versions should be checked against the repository's solution and upstream WinDirStat build guidance.

## Clone and build

```powershell
git clone https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use.git
cd windirstat_CMSE_assignment_use
```

Open the repository's `windirstat.sln` in Visual Studio, select the appropriate **x64** configuration, and choose **Build → Build Solution**. Use **Debug → Start Without Debugging (Ctrl+F5)** to run the *modified* WinDirStat, rather than an independently installed official WinDirStat.

The C++ launcher searches upward from the executable directory for `ai_pipeline/app.py`, so keep the build output inside the cloned repository's directory tree. The launcher assumes `pythonw.exe` is discoverable via Windows. If it cannot be found, install Python 3.11 and verify Python is available from a fresh terminal.

## Configure DeepSeek (optional)

**The API key is never required for local analysis.** To enable external advice:

1. Get an API key from [DeepSeek Platform](https://platform.deepseek.com/) and ensure the account has usable credits.
2. In the repository root, copy the committed template to a local file:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Open `.env` and fill in the key:
   ```dotenv
   DEEPSEEK_API_KEY=YOUR_OWN_KEY
   ```
4. Save `.env`. The application reads this file **each time** AI advice is requested.

The `.env` file is excluded by `.gitignore`; only the empty `.env.example` is committed. **Never commit real keys, paste them into issues, or share them publicly.** For a shared course-demo key, distribute it privately; any user of that key consumes the same account's credits. This local file is not encrypted, so protect access to the computer and rotate a shared key if it may have been exposed.

## Run the application

### Option A: Integrated WinDirStat workflow

1. Start the locally built WinDirStat executable.
2. Scan a drive or folder and allow the scan to finish.
3. Select **Tools → AI Analysis**.
4. In the AI window, choose **中文 / English**, set the minimum priority-file size and choose whether to use DeepSeek.
5. Click **开始分析 / Analyze**. Review the space statistics and organization advice. Scroll to read longer answers.
6. Change settings and click Analyze again as needed. The Python window can reuse its in-memory parsed report; enabling AI for another run makes another API call.

The automatically created temporary report is intended for the integrated workflow. It is removed after reading, or when the window closes before analysis; previously parsed data can remain in memory until the window closes.

### Option B: Open a saved report directly

From the repository root:

```powershell
python -m ai_pipeline.app
```

Use **选择报告 / Choose Report** to select an existing WinDirStat `.csv` or `.json` file. The application does **not** intentionally delete ordinary user-selected reports.

To pre-fill a report path:

```powershell
python -m ai_pipeline.app "C:\path\to\scan.json"
```

For command-line aggregate inspection:

```powershell
python -m ai_pipeline.disk_analyzer "C:\path\to\scan.json" --min-mb 100
```

## Testing and continuous integration

Run the included Python unit tests from the repository root:

```powershell
python -m unittest ai_pipeline.test_pipeline -v
```

The repository contains 10 Python unit tests for report parsing and candidate selection. The GitHub Actions workflow at `.github/workflows/python-tests.yml` runs the same test command on Python 3.11 for pushes and pull requests. [Example successful workflow run](https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use/actions/runs/45379180634).

These unit tests do **not** constitute automated coverage of the full native C++ GUI, DeepSeek network responses, or temporary-file lifecycle. End-to-end behavior was also exercised manually; further automated integration and failure-path tests are future work.

## Architecture and privacy

```text
WinDirStat C++ scanning/UI
    └── Tools → AI Analysis
          └── temporary JSON export (WinDirStat SaveResults)
                └── ai_pipeline/report_parser.py
                      └── ai_pipeline/disk_analyzer.py
                            ├── Local statistics / generic advice
                            └── Optional DeepSeek API (ai_advisor.py)
                                  └── Suggestions in the Tkinter GUI (app.py)
```

The Python report parser operates on exported file-system **metadata**, not file contents. Its in-memory normalized records retain basenames, while the outgoing AI payload is explicitly constructed from aggregated counts, sizes, file extensions and anonymous large-file metadata. DeepSeek output is advisory text; no AI-generated instructions automatically perform file-system changes.

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
