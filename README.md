# AI-Assisted Disk Space Analysis and File Organisation Tool

**Optional AI-assisted disk organisation advice built on WinDirStat**

- **Course:** Contemporary Methods in Software Engineering
- **Project status:** Working prototype
- **Project type:** Student project based on an open-source application

This is an independent course project based on the open-source WinDirStat application for Windows.

## 1. Project Overview

WinDirStat scans drives and folders, visualizes storage usage, identifies large or duplicate files, and exports scan results in CSV or JSON format. This project adds a desktop assistant that summarizes a scan report and helps users decide what to inspect first. It runs locally by default and can optionally request disk organisation advice from DeepSeek.

## 2. Current Features

| Component | Features |
| --- | --- |
| WinDirStat | Scan drives or folders, visualize file and folder sizes, inspect large or duplicate files, and export reports as CSV or JSON |
| AI Analysis menu | Open the assistant with a completed scan report |
| Standalone assistant | Import a WinDirStat CSV or JSON report and view local statistics and general organisation guidance |
| Assistant settings | Switch between Simplified Chinese and English and set the minimum size for priority files |
| Optional DeepSeek advice | Generate a plain-text report with storage findings, review priorities, and cautions |

## 3. User Workflow

1. Scan a drive or folder using WinDirStat.
2. After the scan completes, open **Tools > AI Analysis** to pass the result to the assistant. To reuse a previous report, open the assistant directly and select the CSV or JSON file.
3. Set the priority file threshold if needed. The default is 100 MiB. Click **Analyze** or **开始分析** to generate the summary.
4. Review the file counts, sizes, and category breakdown. Enable DeepSeek before analyzing if you want AI-generated guidance.
5. Review the files in WinDirStat or File Explorer before taking any action.

## 4. Local Analysis and DeepSeek Advice

Local analysis uses the logical size of successfully scanned file records. The summary shows the total file count, logical size, priority file count, and storage usage by category. The threshold determines which files count as priority files. All eligible files contribute to the overall counts and sizes.

In local mode, the assistant shows general guidance alongside the statistics. With DeepSeek enabled, it requests findings based on the scan summary, suggested review steps, and cautions about system, application, and personal files. If the request fails or the response is unusable, the assistant displays an error and keeps the local statistics visible. Clear the DeepSeek checkbox and analyze again to see the local guidance.

## 5. System Design

| Component | Responsibility |
| --- | --- |
| [WinDirStat menu handler](windirstat/MainFrame.Commands.cpp) | Export the completed scan to a temporary JSON file and start the assistant with `pythonw.exe` |
| [`ai_pipeline/app.py`](ai_pipeline/app.py) | Provide the Tkinter interface, load the report, run analysis in the background, and display results or errors |
| [`ai_pipeline/report_parser.py`](ai_pipeline/report_parser.py) | Read and normalize WinDirStat CSV and JSON records |
| [`ai_pipeline/disk_analyzer.py`](ai_pipeline/disk_analyzer.py) | Aggregate file counts and sizes by type, extension, and size range |
| [`ai_pipeline/candidate_selector.py`](ai_pipeline/candidate_selector.py) | Classify extensions and provide a separate command-line candidate ranking |
| [`ai_pipeline/ai_advisor.py`](ai_pipeline/ai_advisor.py) | Provide local guidance or request and check a DeepSeek text response |

## 6. Prototype Scope

The prototype covers the completed-scan workflow, report import, local statistics, optional DeepSeek advice, and visible API error handling. The assistant leaves cleanup decisions and file operations to the user. Per-file risk ratings, duplicate-aware recommendations, and estimates of recoverable space remain outside the current assistant workflow.

## 7. Privacy and Safety

- **Local by default.** The assistant sends scan-derived statistics to DeepSeek only when the user enables the DeepSeek option and runs analysis.
- **Data sent to DeepSeek.** The request includes file counts, sizes, the priority threshold, category summaries, up to 20 extension summaries, size-range totals, and up to 15 large-file records containing only size, category, and extension. File names, paths, and contents stay local.
- **API credentials.** The assistant reads the key from the Git-ignored `.env` file and uses it in the HTTPS authorization header.
- **Temporary report.** The menu flow writes a temporary JSON report. The assistant attempts to remove it after importing it or when the window closes. Reports selected manually remain available for reuse.

## 8. Getting Started

### A. Build and run the WinDirStat desktop application

On Windows, install Visual Studio 2026 with the **Desktop development with C++** workload. Ensure **MSVC Build Tools for x64/x86**, **C++ ATL for x64/x86**, and a **Windows SDK** are selected. The project uses the **v145** platform toolset and **C++23**. The first build can download xxHash if it is missing.

1. Open [`windirstat.sln`](windirstat.sln) in Visual Studio 2026.
2. Select **Release | x64** and choose **Build > Build Solution**.
3. From the repository root, run the built executable.

```powershell
.\build\WinDirStat_x64.exe
```

### B. Open the assistant from WinDirStat

Install Python 3 with Tcl/Tk support. Python 3.12 is a working option. The menu uses `pythonw.exe`, so make sure Windows can find it, for example by adding its Python installation directory to `PATH`. Keep the built WinDirStat executable in the repository's `build` directory so it can find `ai_pipeline`.

Scan a drive or folder, wait for the scan to complete, then choose **Tools > AI Analysis**. The report path is filled in automatically. Click **Analyze** to run local analysis.

### C. Run the assistant with an exported report

From the repository root, run the following command with a Python interpreter that includes Tkinter. The assistant uses the Python standard library, so there are no additional Python packages to install.

```powershell
python -m ai_pipeline.app
```

If your default Python has an incomplete Tcl/Tk installation, use the full path to a Python executable that has Tkinter. Run `python -m tkinter` to check the selected interpreter.

To create a report, use **File > Save Results To CSV/JSON** in WinDirStat. In the assistant, click **Choose file**, select the report, and click **Analyze**. If an older export is missing fields such as `ScanOutcome` or `ScanError`, export the scan again using the build from this repository.

### D. Enable DeepSeek advice

Create a file named `.env` in the repository root, next to `windirstat.sln`. Add this line with your own DeepSeek API key.

```dotenv
DEEPSEEK_API_KEY=your_key_here
```

In the assistant, select **Use DeepSeek AI** and click **Analyze**. The implementation calls DeepSeek using the `deepseek-flash` model. The API key and an internet connection are only needed for this mode.

## 9. Testing and Evaluation

Run the Python unit tests from the repository root.

```powershell
python -m unittest ai_pipeline.test_pipeline
```

The tests cover CSV and JSON parsing, file classification, candidate ranking and size thresholds, exclusion of failed scan records, and omission of file names and paths from candidate output.

For a manual demo, scan a small folder and open **Tools > AI Analysis**. Verify that the report is prefilled and local statistics appear after analysis. Export the same scan and import it into the standalone assistant to check the second launch path. With a configured key, enable DeepSeek and check that the advice appears alongside the local summary.

Evaluation focuses on whether the guidance is clear, relevant to the scan, and useful alongside the local statistics.

## 10. Known Limitations

- The totals reflect logical sizes from the successfully scanned files in the supplied report. Actual disk usage and recoverable space can differ due to allocation, hard links, deduplication, or incomplete scan coverage.
- Metadata and model-generated advice cannot establish a file's importance or whether it is safe to delete.
- The assistant expects the WinDirStat CSV or JSON report schema. Older or differently structured exports may be rejected.
- DeepSeek advice depends on the configured key, network access, service availability, and account balance.

## 11. Open-Source Attribution and Licenses

This student project builds on **WinDirStat**, created by the WinDirStat Team. The original software is available at:

- Source code: https://github.com/windirstat/windirstat
- Project website: https://windirstat.net/
- User documentation: https://github.com/windirstat/windirstat/wiki

WinDirStat is distributed under **GPL v3 or later**, while some portions of its source have more permissive terms. The original logo and derivatives are licensed under **CC BY 3.0**. Preserve applicable copyright notices and source-level license terms when reusing, modifying, or distributing the upstream code. Determine and document the licensing of the team's additional code and dependencies before distributing the project.

This repository and its AI functionality should not be presented as official WinDirStat software. For trusted upstream downloads, use the official sources linked above.

## 12. Team and Course Information


- **Course:** Contemporary Methods in Software Engineering
- **Team members:**
  - Mao Lingyun (Eamonn)
  - Chen Zihan (Han)
  - Dong Yuzhe (Dylan)
  - Fang Letian (Lamelo)
- **Project repository:** https://github.com/Eamonn-heiyaoai/windirstat_CMSE_assignment_use
- **Institution / programme:** Auckland University of Technology (AUT) – CJLU BCIS Cycle 13
- **Final demo / report:** Not publicly linked in this repository.
