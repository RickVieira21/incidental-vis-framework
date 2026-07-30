# ATC Cognitive Load Simulation Framework

> A detailed step-by-step **User Manual (PDF)** is included in this
> repository (`docs/User_Manual.pdf`) and covers installation,
> hardware setup, running a session, and the full data output format.
> This README is a quick-start summary.

---

## Requirements

- **Windows** (the session controller uses `pywin32` to manage the
  OpenFace preview window; it has not been tested on macOS/Linux)
- Python 3.9+
- Python packages: `pyaudio`, `pywin32`, `bitalino` (see
  `requirements.txt`)
- [OpenFace 2.2.0](https://github.com/TadasBaltrusaitis/OpenFace) for
  eye/face tracking (optional but expected by default — see
  **Configuration** below)
- A BITalino device for EEG (optional, **disabled by default**)
- A working microphone

## Installation

```bash
git clone <repo-url>
cd <repo-folder>
pip install -r requirements.txt
```

## Configuration (before first run)

This framework was built for a specific lab setup. Before running it
on a different machine, update the following hardcoded values:

| What | Where | Notes |
|---|---|---|
| Path to `FeatureExtraction.exe` (OpenFace) | `engine/experimentalSession.py`, `start_openface_recording()` | Absolute path, must point to your OpenFace install |
| BITalino MAC address | `engine/experimentalSession.py`, `start_eeg_recording()` | Only relevant if you set `use_eeg = True` in `__init__` |
| Microphone device index | `engine/experimentalSession.py`, `start_audio_recording()` | Defaults to index `0`; use the commented-out device-listing snippet to find yours |

By default, **audio recording is ON** and **EEG recording is OFF**
(`use_audio = True`, `use_eeg = False` in `ExperimentalSession.__init__`).

## Running

```bash
python main.py
```

The start menu lets you pick a **Participant ID** (1–30) and either:
- **START** - runs the real 9-condition session for that participant
- **PRACTICE** - runs a single, looping practice condition (fixed at
  LOW cognitive load / HIGH complexity) with no data saved

Press **Esc** at any time to abort and return to the start menu.




