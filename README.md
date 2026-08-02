<p align="center">
  <img src="logo.png" alt="TRACE Banner" width="200">
</p>

<h1 align="center">TRACE</h1>

<p align="center">
  <strong>Toolkit for Reverse Analysis & Code Exploration</strong><br>
  Version 1.2.2
</p>

<p align="center">
  By <strong>TriCode Club Labs</strong>
</p>

---

## Overview

TRACE is a desktop application for exploring and understanding software projects. (Prototpye - not finished product)

Open a local project or clone a public GitHub repository, browse project files, inspect source code, preview images, review documentation, analyze dependencies, and understand repository structure from a modern desktop interface.

Originally built for **SFHS CODE Hack 7**, TRACE is now an active **TriCode Club Labs** project that will continue to evolve with new features and improvements.

---

## Credits

| Component | Credits |
|----------|---------|
| Python | https://python.org |
| CustomTkinter | https://customtkinter.tomschimansky.com |
| Pillow | https://python-pillow.org |
| Git | https://git-scm.com |
| GitHub REST API | https://docs.github.com/en/rest |
| Color Palette | https://coolors.co |
| Debugging & Brainstorm | https://chatgpt.com + https://github.com/features/copilot |

---

## Features

- Local & GitHub repository support
- Repository exploration
- Source code viewer
- Project documentation viewer
- Repository insights
- Image preview
- Dependency analysis
- Modern desktop interface

### AI Analysis (Digital Forensics & Repository Intelligence)

Built for **AI for Smart Forensics & Public Safety**. Available from the new
**AI Analysis** section of the sidebar once a project is opened:

| Feature | What it does |
|---|---|
| 🧠 Repository Summary | Gemini-powered overview: purpose, framework, languages, entry point, architecture, folder structure, key files, dependencies. |
| 📄 Explain File | Explains the currently selected file's purpose, functions, classes, execution flow, bugs, and possible improvements. |
| 💬 Repository Chat | Ask questions about the codebase ("What starts the application?", "Where is auth handled?"). Only relevant files are sent to Gemini, never the whole repo. |
| 🛡️ Threat Scan | Static regex scan for dangerous APIs (`eval`, `exec`, `os.system`, `pickle.loads`, sockets, PowerShell invocation, registry access, etc.), optionally paired with an AI analyst summary. |
| 🔑 Secret Scan | Static regex scan for exposed credentials (AWS/Google/Gemini keys, JWTs, private keys, passwords, bearer tokens, DB connection strings). |
| 📋 Generate Report | Combines the summary, risk score (0-100), and both scans into a Markdown forensic report you can export. |

**Setup:** the AI features need a Gemini API key. Kindly make a file called "gemini_key.txt" in base-dir and paste your api-key there

## Screenshots

### Loading Screen

<p align="center">
  <img src="assets/loading.png" alt="Loading Screen" width="400">
</p>

### Project Selection

<p align="center">
  <img src="assets/selection.png" alt="Project Selection" width="500">
</p>

### Project Analysis

<p align="center">
  <img src="assets/analysis.png" alt="Analysis Window" width="700">
</p>

> Screenshots will be updated as TRACE evolves.

---

## Project Team

| Name | Role |
|------|------|
| Akshat Jain | Developer |
| Mridul Thakur | Developer |

Maintained by **TriCode Club Labs**.

---

## Roadmap

| Status | Feature |
|:------:|---------|
| ⏳ | GTK4 desktop version |
| ⏳ | Official TRACE website |
| ⏳ | Cloud-based repository analysis |
| ⏳ | Cross-platform support (Linux, Windows & macOS) |
| ⏳ | Integration with the TriCode Development Suite |
| ⏳ | Rich Markdown rendering |
| ⏳ | Better repository statistics & insights |
| ⏳ | Faster analysis engine |

---

## Repository Structure

```text
TRACE/
├── assets/
│   ├── banner.png
│   ├── loading.png
│   ├── project-selection.png
│   └── analysis.png
├── projects/
├── main.py
├── text_style.py
├── theme.json
├── requirements.txt
├── LICENSE
└── README.md
```

---

## License

TRACE is distributed as **freeware**.

You may use the software for personal, educational, and non-commercial purposes.

Redistribution, modification, or commercial distribution without permission is prohibited.

The developers and TriCode Club Labs are not responsible for any misuse, damages, or data loss resulting from the use of this software.

---

<p align="center">
Made with ❤️ by <strong>TriCode Club Labs</strong>
</p>
