"""
experimentalSession.py

Defines ExperimentalSession, the top-level controller for running a
full experimental session with a participant: sequencing the 9 trial
conditions (in a counterbalanced order via a Latin square), starting
and stopping physiological/behavioural recordings (eye-tracking via
OpenFace, EEG via a BITalino device, and microphone audio), scheduling
the incidental visualizations that are the focus of the study, logging
all timestamped events to CSV, and managing the rest-baseline periods
between conditions.

IMPORTANT — platform & hardware dependencies:
    This module is Windows-specific (uses `win32gui`/`win32con` from
    pywin32) and depends on external hardware/software that other
    users of the framework will need to configure for their own setup:
        - OpenFace 2.2.0 (eye-tracking), invoked via a **hardcoded
          absolute path** to `FeatureExtraction.exe`
          (`start_openface_recording`). This path MUST be changed to
          match the OpenFace installation location on any other
          machine.
        - A BITalino EEG device, addressed via a **hardcoded Bluetooth
          MAC address** (`start_eeg_recording`). EEG recording is
          disabled by default (`self.use_eeg = False` in `__init__`)
          and must be explicitly enabled and reconfigured to use a
          different device.
        - A microphone, addressed via a **hardcoded input device
          index** (`input_device_index=0` in `start_audio_recording`).
          This may need to be changed depending on the machine's audio
          devices.
    These are exactly the kind of setup-specific details that should
    be called out prominently in the README/user manual, since other
    researchers reusing this framework will need to adapt them.
"""
from levels.cognitive_load import CognitiveLoadProfile
from levels.task_complexity import TaskComplexityProfile
from ui.atc_ui import ATCApp
from engine.simulation_engine import SimulationEngine
from engine.event_scheduler import EventScheduler
import tkinter as tk
import subprocess
import time
import os
import csv
import pyaudio
import wave
import win32gui
import win32con
import time
from bitalino import BITalino


class ExperimentalSession:
    """
    Orchestrates a full experimental session for one participant,
    covering all 9 trial conditions plus rest-baseline periods,
    hardware recordings, and event logging.

    A session is built around two counterbalanced orderings, both
    looked up by `participant_id`:
        - `self.conditions`: the order in which the 9 condition
          letters (A-I, each mapping to a cognitive-load x
          task-complexity combination — see `apply_condition`) are
          presented to this participant (Latin square across
          participants).
        - `self.iv_order`: the order in which the 36 possible
          incidental-visualization images (numbered 1-36) are shown
          across the whole session, also counterbalanced per
          participant via a separate Latin square.

    Attributes:
        root: The Tkinter root window.
        participant_id (int): Numeric ID used to look up this
            participant's counterbalancing orders.
        condition_duration (int): Length of each trial condition in
            seconds (120s = 2 minutes, matching the study design).
        baseline_duration (int): Length of the rest/baseline period
            shown between conditions, in seconds.
        is_practice (bool): Whether this session is a practice run
            (uses a fixed practice condition/IV order and loops
            indefinitely instead of ending).
        on_start_callback: Callback used to return to the start menu
            (e.g. after pressing Escape).
        trial_already_counted (bool): Guards against double-counting
            errors/logging if `start_baseline` is somehow triggered
            more than once for the same trial.
        total_errors_overall / constraint_errors_overall /
        expiration_errors_overall / system_ack_errors_overall (int):
            Running totals across the whole session. 
        events (list[tuple[float, str]]): Timestamped event log for
            the CURRENT trial, written to a CSV file at the end of
            each condition via `start_baseline`.
        current_index (int): Index of the current condition within
            `self.conditions`.
        conditions (list[str]): This participant's condition-letter
            order, from `load_conditions`.
        iv_order (list[int]): This participant's incidental-image
            order, from `load_iv_latin_square`.
        use_audio (bool): Whether microphone recording is enabled.
        audio, audio_stream, audio_frames, audio_recording: PyAudio
            recording state (see the PYAUDIO section below).
        incidental_image: A preloaded Tkinter PhotoImage
            ("incidental.png").
        use_eeg (bool): Whether EEG recording is enabled. False by
            default.
    """

    def __init__(self, root, participant_id, on_start_callback, practice=False):
        self.root = root
        self.participant_id = participant_id
        self.condition_duration = 120
        self.baseline_duration = 10
        self.is_practice = practice
        self.on_start_callback = on_start_callback

        #Errors
        self.trial_already_counted = False
        self.total_errors_overall = 0
        self.constraint_errors_overall = 0
        self.expiration_errors_overall = 0
        self.system_ack_errors_overall = 0
        self.events = []

        self.current_index = 0
        self.conditions = self.load_conditions(participant_id)
        self.iv_order = self.load_iv_latin_square()

        #PyAudio
        self.use_audio = True  # flag audio
        self.audio = None
        self.audio_stream = None
        self.audio_frames = []
        self.audio_recording = False

        self.incidental_image = tk.PhotoImage(file="incidental.png")
        self.use_eeg = False  # flag eeg
        self.root.bind("<Escape>", self.on_escape)

    def attach(self, engine, ui, scheduler):
        """
        Wire this session to the currently active SimulationEngine, UI
        controller, and EventScheduler.

        Also sets `engine.session = self`, so the engine and its
        scheduler can call back into `self.log_event(...)` when
        flights/messages expire (see engine/event_scheduler.py).

        Args:
            engine (SimulationEngine): The active engine for the
                current trial.
            ui: The active UI controller (ATCApp instance).
            scheduler (EventScheduler): The active scheduler for the
                current trial.
        """
        self.engine = engine
        self.engine.session = self
        self.ui = ui
        self.scheduler = scheduler

    def load_conditions(self, participant_id):
        """
        Look up this participant's Latin-square-ordered sequence of
        the 9 condition letters (A-I).

        Each letter corresponds to one cognitive-load x
        task-complexity combination (see `apply_condition` for the
        mapping). The table below is a fixed, precomputed Latin square
        assignment for up to 30 participants, ensuring that across the
        whole sample, each condition appears equally often in each
        serial position (counterbalancing order effects).

        Args:
            participant_id (int): The participant's numeric ID
                (expected range: 1-30, based on the table below).

        Returns:
            list[str]: The 9 condition letters in presentation order
            for this participant, or an empty list if the ID isn't
            found in the table.
        """
        LATIN_SQUARE = {
            1:  ["A","B","I","C","H","D","G","E","F"],
            2:  ["G","F","H","E","I","D","A","C","B"],
            3:  ["C","D","B","E","A","F","I","G","H"],
            4:  ["I","H","A","G","B","F","C","E","D"],
            5:  ["E","F","D","G","C","H","B","I","A"],
            6:  ["B","A","C","I","D","H","E","G","F"],
            7:  ["G","H","F","I","E","A","D","B","C"],
            8:  ["D","C","E","B","F","A","G","I","H"],
            9:  ["I","A","H","B","G","C","F","D","E"],
            10: ["F","E","G","D","H","C","I","B","A"],
            11: ["B","C","A","D","I","E","H","F","G"],
            12: ["H","G","I","F","A","E","B","D","C"],
            13: ["D","E","C","F","B","G","A","H","I"],
            14: ["A","I","B","H","C","G","D","F","E"],
            15: ["F","G","E","H","D","I","C","A","B"],
            16: ["C","B","D","A","E","I","F","H","G"],
            17: ["H","I","G","A","F","B","E","C","D"],
            18: ["E","D","F","C","G","B","H","A","I"],
            19: ["A","B","I","C","H","D","G","E","F"],
            20: ["G","F","H","E","I","D","A","C","B"],
            21: ["C","D","B","E","A","F","I","G","H"],
            22: ["I","H","A","G","B","F","C","E","D"],
            23: ["E","F","D","G","C","H","B","I","A"],
            24: ["B","A","C","I","D","H","E","G","F"],
            25: ["G","H","F","I","E","A","D","B","C"],
            26: ["D","C","E","B","F","A","G","I","H"],
            27: ["I","A","H","B","G","C","F","D","E"],
            28: ["F","E","G","D","H","C","I","B","A"],
            29: ["B","C","A","D","I","E","H","F","G"],
            30: ["H","G","I","F","A","E","B","D","C"],
        }

        return LATIN_SQUARE.get(participant_id, [])

    def load_iv_latin_square(self):
        """
        Look up this participant's Latin-square-ordered sequence of
        incidental-visualization image numbers (1-36).

        Each trial condition shows exactly 4 incidental images (at
        25s, 50s, 75s, and 100s into the 120s trial — see
        `start_condition`), so across the 9 conditions of a full
        session, 36 image "slots" need to be filled. This table
        assigns, for each participant, which of the 36 possible images
        goes into each of those 36 slots, again to counterbalance
        which images appear at which position/condition across the
        sample.

        If `self.is_practice` is True, the fixed practice ordering
        (key 31) is used regardless of `participant_id`.

        Returns:
            list[int]: 36 image numbers in presentation order (to be
            sliced into groups of 4, one group per condition — see
            `start_condition`), or an empty list if the ID isn't found
            in the table (and this isn't a practice session).
        """
        LATIN_IV = {
            1:  [1,2,36,3,35,4,34,5,33,6,32,7,31,8,30,9,29,10,28,11,27,12,26,13,25,14,24,15,23,16,22,17,21,18,20,19],
            2:  [2,3,1,4,36,5,35,6,34,7,33,8,32,9,31,10,30,11,29,12,28,13,27,14,26,15,25,16,24,17,23,18,22,19,21,20],
            3:  [3,4,2,5,1,6,36,7,35,8,34,9,33,10,32,11,31,12,30,13,29,14,28,15,27,16,26,17,25,18,24,19,23,20,22,21],
            4:  [4,5,3,6,2,7,1,8,36,9,35,10,34,11,33,12,32,13,31,14,30,15,29,16,28,17,27,18,26,19,25,20,24,21,23,22],
            5:  [5,6,4,7,3,8,2,9,1,10,36,11,35,12,34,13,33,14,32,15,31,16,30,17,29,18,28,19,27,20,26,21,25,22,24,23],
            6:  [6,7,5,8,4,9,3,10,2,11,1,12,36,13,35,14,34,15,33,16,32,17,31,18,30,19,29,20,28,21,27,22,26,23,25,24],
            7:  [7,8,6,9,5,10,4,11,3,12,2,13,1,14,36,15,35,16,34,17,33,18,32,19,31,20,30,21,29,22,28,23,27,24,26,25],
            8:  [8,9,7,10,6,11,5,12,4,13,3,14,2,15,1,16,36,17,35,18,34,19,33,20,32,21,31,22,30,23,29,24,28,25,27,26],
            9:  [9,10,8,11,7,12,6,13,5,14,4,15,3,16,2,17,1,18,36,19,35,20,34,21,33,22,32,23,31,24,30,25,29,26,28,27],
            10: [10,11,9,12,8,13,7,14,6,15,5,16,4,17,3,18,2,19,1,20,36,21,35,22,34,23,33,24,32,25,31,26,30,27,29,28],
            11: [11,12,10,13,9,14,8,15,7,16,6,17,5,18,4,19,3,20,2,21,1,22,36,23,35,24,34,25,33,26,32,27,31,28,30,29],
            12: [12,13,11,14,10,15,9,16,8,17,7,18,6,19,5,20,4,21,3,22,2,23,1,24,36,25,35,26,34,27,33,28,32,29,31,30],
            13: [13,14,12,15,11,16,10,17,9,18,8,19,7,20,6,21,5,22,4,23,3,24,2,25,1,26,36,27,35,28,34,29,33,30,32,31],
            14: [14,15,13,16,12,17,11,18,10,19,9,20,8,21,7,22,6,23,5,24,4,25,3,26,2,27,1,28,36,29,35,30,34,31,33,32],
            15: [15,16,14,17,13,18,12,19,11,20,10,21,9,22,8,23,7,24,6,25,5,26,4,27,3,28,2,29,1,30,36,31,35,32,34,33],
            16: [16,17,15,18,14,19,13,20,12,21,11,22,10,23,9,24,8,25,7,26,6,27,5,28,4,29,3,30,2,31,1,32,36,33,35,34],
            17: [17,18,16,19,15,20,14,21,13,22,12,23,11,24,10,25,9,26,8,27,7,28,6,29,5,30,4,31,3,32,2,33,1,34,36,35],
            18: [18,19,17,20,16,21,15,22,14,23,13,24,12,25,11,26,10,27,9,28,8,29,7,30,6,31,5,32,4,33,3,34,2,35,1,36],
            19: [19,20,18,21,17,22,16,23,15,24,14,25,13,26,12,27,11,28,10,29,9,30,8,31,7,32,6,33,5,34,4,35,3,36,2,1],
            20: [20,21,19,22,18,23,17,24,16,25,15,26,14,27,13,28,12,29,11,30,10,31,9,32,8,33,7,34,6,35,5,36,4,1,3,2],
            21: [21,22,20,23,19,24,18,25,17,26,16,27,15,28,14,29,13,30,12,31,11,32,10,33,9,34,8,35,7,36,6,1,5,2,4,3],
            22: [22,23,21,24,20,25,19,26,18,27,17,28,16,29,15,30,14,31,13,32,12,33,11,34,10,35,9,36,8,1,7,2,6,3,5,4],
            23: [23,24,22,25,21,26,20,27,19,28,18,29,17,30,16,31,15,32,14,33,13,34,12,35,11,36,10,1,9,2,8,3,7,4,6,5],
            24: [24,25,23,26,22,27,21,28,20,29,19,30,18,31,17,32,16,33,15,34,14,35,13,36,12,1,11,2,10,3,9,4,8,5,7,6],
            25: [25,26,24,27,23,28,22,29,21,30,20,31,19,32,18,33,17,34,16,35,15,36,14,1,13,2,12,3,11,4,10,5,9,6,8,7],
            26: [26,27,25,28,24,29,23,30,22,31,21,32,20,33,19,34,18,35,17,36,16,1,15,2,14,3,13,4,12,5,11,6,10,7,9,8],
            27: [27,28,26,29,25,30,24,31,23,32,22,33,21,34,20,35,19,36,18,1,17,2,16,3,15,4,14,5,13,6,12,7,11,8,10,9],
            28: [28,29,27,30,26,31,25,32,24,33,23,34,22,35,21,36,20,1,19,2,18,3,17,4,16,5,15,6,14,7,13,8,12,9,11,10],
            29: [29,30,28,31,27,32,26,33,25,34,24,35,23,36,22,1,21,2,20,3,19,4,18,5,17,6,16,7,15,8,14,9,13,10,12,11],
            30: [30,31,29,32,28,33,27,34,26,35,25,36,24,1,23,2,22,3,21,4,20,5,19,6,18,7,17,8,16,9,15,10,14,11,13,12],
            31: [31,32,30,33,29,34,28,35,27,36,26,1,25,2,24,3,23,4,22,5,21,6,20,7,19,8,18,9,17,10,16,11,15,12,14,13],
        }

        if self.is_practice:
            return LATIN_IV[31]

        return LATIN_IV.get(self.participant_id, [])

    # ---------------- OPENFACE -----------------
    # Eye-tracking recording via the external OpenFace 2.2.0 tool,
    # run as a separate subprocess for the duration of each trial.

    def hide_openface_window(self):
        """
        Find and hide OpenFace's own "tracking result" preview window
        (which it opens automatically), so it doesn't visually
        interfere with the task UI or distract the participant.

        Uses `win32gui.EnumWindows` to scan all open top-level windows
        and hide any whose title contains "tracking result".

        Windows-only (depends on pywin32).
        """
        def enum_handler(hwnd, ctx):
            if "tracking result" in win32gui.GetWindowText(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

        win32gui.EnumWindows(enum_handler, None)

    def start_openface_recording(self):
        """
        Launch OpenFace's FeatureExtraction.exe as a background
        subprocess to record webcam-based eye/face tracking data for
        the upcoming trial.

        Output files are named `P<participant_id>_[PRACTICE_]Openface
        <condition_index>` and written under
        `eye_data/<filename>/P<participant_id>/`.

        NOTE FOR OTHER USERS: the path to `FeatureExtraction.exe` is
        currently hardcoded to a specific machine.
        This MUST be updated to point to your own OpenFace
        installation before this function will work.

        Side effects:
            - Stores the subprocess handle in `self.openface_process`.
            - Records `self.trial_start_unix` (recording start time).
            - Logs an "OPENFACE_START" event.
        """
        prefix = "PRACTICE_" if self.is_practice else ""
        filename = f"P{self.participant_id}_{prefix}Openface{self.current_index}"

        base_dir = os.path.join("eye_data", filename)

        participant_dir = os.path.join(base_dir, f"P{self.participant_id}")

        os.makedirs(participant_dir, exist_ok=True)

        self.trial_start_unix = time.time()

        self.openface_process = subprocess.Popen( 
        [
            
            #r"yourPath",
            "-device", "0",
            "-out_dir", participant_dir,
            "-of", filename,
            "-q",
            "-novisualise"
        ],
        creationflags=subprocess.CREATE_NO_WINDOW
        )

        self.log_event("OPENFACE_START")
        print("OpenFace started")

    def stop_openface_recording(self):
        """
        Terminate the OpenFace subprocess started by
        `start_openface_recording`, if one is currently running.

        Side effects:
            - Terminates `self.openface_process` and clears the
              reference.
            - Logs an "OPENFACE_STOP" event.
        """
        if hasattr(self, "openface_process") and self.openface_process:
            self.openface_process.terminate()
            self.openface_process = None
            self.log_event("OPENFACE_STOP")
            print("OpenFace stopped")

    # -------------------- EEG ----------------------
    # EEG recording via a BITalino device over Bluetooth. Disabled by
    # default (`self.use_eeg = False`); every method below is a no-op
    # unless `use_eeg` has been explicitly set to True (and a matching
    # device is available at the configured MAC address).

    def start_eeg_recording(self):
        """
        Connect to a BITalino EEG device over Bluetooth and start
        streaming samples, retrying a few times if the connection
        fails (Bluetooth connections to these devices can be flaky).

        No-op if `self.use_eeg` is False.

        NOTE FOR OTHER USERS: the Bluetooth MAC address
        (`self.mac_address`), sampling rate, and channel list are
        hardcoded here and specific to the original BITalino device
        used in this study. Update these to match your own device
        before enabling EEG recording.

        Behavior:
            - Attempts up to 5 connection attempts (1.5s apart) before
              giving up.
            - On success: initializes `self.eeg_data` (buffer for
              incoming samples), sets `self.eeg_recording = True`,
              records `self.eeg_start_time`, and logs "EEG_START".
            - On failure after all retries: disables EEG for the rest
              of the session (`self.use_eeg = False`) and logs
              "EEG_FAILED".
        """
        if not self.use_eeg:
            print("EEG disabled (no device)")
            return

        self.mac_address = "" #yourAddress
        self.sampling_rate = 1000
        self.channels = [0]

        max_attempts = 5
        attempt = 0
        connected = False

        while attempt < max_attempts and not connected:
            try:
                print(f"EEG connection attempt {attempt + 1}")

                self.eeg_device = BITalino(self.mac_address)
                self.eeg_device.start(self.sampling_rate, self.channels)

                connected = True

            except Exception as e:
                print(f"EEG connection failed: {e}")
                attempt += 1
                time.sleep(1.5)  

        if not connected:
            print("EEG connection failed after retries")
            self.use_eeg = False
            self.log_event("EEG_FAILED")
            return

        self.eeg_data = []
        self.eeg_recording = True
        self.eeg_start_time = time.time()

        self.log_event("EEG_START")
        print("EEG recording started")

    def stop_eeg_recording(self):
        """
        Stop EEG streaming, close the device connection, and save all
        buffered samples to a CSV file.

        No-op if `self.use_eeg` is False.

        Output file: `eeg_data/P<participant_id>_[PRACTICE_]EEG_trial
        <condition_index>.csv`, containing the recording start
        timestamp, sampling rate, and all raw samples collected during
        the trial.
        """
        if not self.use_eeg:
           return

        if hasattr(self, "eeg_device"):

            self.eeg_recording = False

            self.eeg_device.stop()
            self.eeg_device.close()
            self.eeg_device = None
            self.log_event("EEG_STOP")

            prefix = "PRACTICE_" if self.is_practice else ""
            filename = f"P{self.participant_id}_{prefix}EEG_trial{self.current_index}.csv"

            filepath = os.path.join("eeg_data", filename)

            os.makedirs("eeg_data", exist_ok=True)

            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["start_timestamp", self.eeg_start_time])
                writer.writerow(["sampling_rate", self.sampling_rate])
                writer.writerow([])
                writer.writerows(self.eeg_data)

            print("EEG recording saved")

    def read_eeg_data(self):
        """
        Poll the BITalino device for new samples and append them to
        the in-memory buffer, then reschedule itself.

        No-op if EEG is disabled, not connected, or not currently
        recording. Runs roughly 10 times per second (every 100ms),
        reading 100 samples per call. If the device reports a
        "CONTACTING_DEVICE" error (typically a Bluetooth dropout),
        logs an "EEG_DISCONNECT" event.

        This method reschedules itself via `root.after(100, ...)`
        every time it runs (even after errors), so once started it
        keeps polling until `eeg_recording`/`use_eeg` become False.
        """
        if not self.use_eeg:
           return

        if not hasattr(self, "eeg_device"):
            return
        
        if not getattr(self, "eeg_recording", False):
            return

        try:
            samples = self.eeg_device.read(100) # 100 samples 
            self.eeg_data.extend(samples)

        except Exception as e:
                if "CONTACTING_DEVICE" in str(e):
                    self.log_event("EEG_DISCONNECT")

                print("EEG read warning:", e)
 
        self.root.after(100, self.read_eeg_data) 

    # -------------------- PYAUDIO ----------------------
    # Microphone audio recording, used to capture verbal
    # acknowledgements/think-aloud data (or similar) during the trial.

    def start_audio_recording(self):
            """
            Open the microphone input stream and start recording audio
            for the upcoming trial.

            No-op if `self.use_audio` is False.

            NOTE FOR OTHER USERS: `input_device_index=0` hardcodes
            which microphone is used. The commented-out lines above
            (querying `p.get_device_count()` /
            `get_device_info_by_index`) show how to list available
            devices and find the correct index for a different
            machine.

            Side effects:
                - Initializes `self.audio` (PyAudio instance) and
                  `self.audio_stream` (open input stream).
                - Resets `self.audio_frames` and sets
                  `self.audio_recording = True`.
                - Records `self.audio_start_time`.
                - Logs an "AUDIO_START" event.
                - Kicks off the polling loop via `read_audio_data()`.
            """
            #show mics
            #p = pyaudio.PyAudio()

            #for i in range(p.get_device_count()):
            #    dev = p.get_device_info_by_index(i)
            #    print(i, dev["name"])

            if not self.use_audio:
                print("Audio disabled")
                return

            self.audio = pyaudio.PyAudio()

            self.audio_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=0, #mic index
                frames_per_buffer=1024
            )

            self.audio_frames = []
            self.audio_recording = True

            self.audio_start_time = time.time()

            self.log_event("AUDIO_START")

            print("Audio recording started")

            self.read_audio_data()

    def read_audio_data(self):
        """
        Read one buffer's worth of audio samples from the open stream
        and append them to the in-memory frame list, then reschedule
        itself.

        No-op if audio is disabled or the stream isn't open/recording.
        Runs roughly 20 times per second (every 50ms). Logs an
        "AUDIO_ERROR" event if reading the stream raises an exception
        (e.g. a buffer overflow not otherwise suppressed).
        """
        if not self.use_audio:
            return

        if not self.audio_recording or not self.audio_stream:
            return

        try:
            data = self.audio_stream.read(1024, exception_on_overflow=False)
            self.audio_frames.append(data)

        except Exception as e:
            print("Audio read warning:", e)
            self.log_event("AUDIO_ERROR")

        self.root.after(50, self.read_audio_data)

    def stop_audio_recording(self):
        """
        Stop and close the audio stream, terminate PyAudio, and save
        all recorded frames to a WAV file.

        No-op if `self.use_audio` is False.

        Output file: `audio_data/P<participant_id>_[PRACTICE_]
        audio_trial<condition_index>.wav` (mono, 16-bit, 16kHz, matching
        the stream's recording parameters).
        """
        if not self.use_audio:
            return

        if self.audio_stream:

            self.audio_recording = False

            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.audio.terminate()

            self.log_event("AUDIO_STOP")

            prefix = "PRACTICE_" if self.is_practice else ""
            filename = f"P{self.participant_id}_{prefix}audio_trial{self.current_index}.wav"

            filepath = os.path.join("audio_data", filename)

            os.makedirs("audio_data", exist_ok=True)

            wf = wave.open(filepath, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(self.audio_frames))
            wf.close()

            print("Audio saved")

    # ------------------ LOGS --------------------

    def log_event(self, event_name):
        """
        Append a timestamped event to the current trial's in-memory
        event log (`self.events`), later flushed to a CSV file by
        `start_baseline`.

        Used throughout the session/engine/scheduler to record
        discrete, analyzable events (e.g. "TRIAL_START",
        "FLIGHT_EXPIRED_...", "IV_APPEAR_<n>", hardware start/stop
        events, etc.), each paired with a Unix timestamp.

        Args:
            event_name (str): A short, descriptive event identifier.
        """
        timestamp = time.time()
        self.events.append((timestamp, event_name))

    # --------------- MAIN CODE ------------------

    def start(self):
        """Begin the session by starting its first trial condition."""
        self.start_condition()

    def start_condition(self):
        """
        Set up and run one full trial condition (2 minutes): start all
        hardware recordings, apply the condition's cognitive-load and
        task-complexity levels, display the on-screen trial timer,
        schedule the 4 incidental-visualization appearances, and
        schedule the automatic transition to the rest-baseline period.

        Sequence:
            1. Reset the event log and start OpenFace recording
               (with a short sleep to let it initialize).
            2. Start EEG recording and its polling loop (with a short
               sleep).
            3. Start audio recording and log "TRIAL_START".
            4. If all conditions have already been run, print a
               message and stop (session finished).
            5. Otherwise, look up the current condition letter and
               apply it via `apply_condition` (sets cognitive/
               complexity profiles on the engine).
            6. Create/update the on-screen condition/timer label
               (bottom-right corner) and start its per-second update
               loop (`update_trial_timer`).
            7. Slice this condition's 4 incidental-visualization image
               numbers out of `self.iv_order` (4 per condition, in
               order), and schedule each one to appear at a fixed
               offset (25s, 50s, 75s, 100s) into the trial via
               `root.after(...)`, storing the resulting `after` IDs so
               they can be cancelled later if needed (e.g. on Escape).
            8. Unless this is a practice session, schedule the
               automatic transition to `start_baseline` after
               `condition_duration` (120s).

        Note: `time.sleep(...)` calls here briefly block the Tkinter
        main loop while hardware recordings initialize — this is a
        deliberate (if slightly UI-blocking) trade-off to ensure
        recordings are running before the trial officially starts.
        """
        self.events = []
        
        self.start_openface_recording()
        time.sleep(2.5)

        self.start_eeg_recording()
        self.read_eeg_data()
        time.sleep(0.5)

        self.start_audio_recording()
        self.events.append((time.time(), "TRIAL_START"))

        self.trial_already_counted = False
        if self.current_index >= len(self.conditions):
            print("Experiment finished")
            return

        condition = self.conditions[self.current_index]
        print("Starting condition:", condition)

        self.apply_condition(condition)

        self.trial_time_left = self.condition_duration

        self.condition_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 12, "bold"),
            bg="#f0f0f0",
            anchor="e",
            justify="right"
        )

        self.condition_label.place(
            relx=1.0,
            rely=1.0,
            anchor="se",
            x=-20,
            y=-20
        )

        self.update_trial_timer()

        start_index = self.current_index * 4
        end_index = start_index + 4

        self.current_trial_ivs = self.iv_order[start_index:end_index]

        self.incidental_times = [25, 50, 75, 100]
        self.incidental_after_ids = []

        for t, iv_number in zip(self.incidental_times, self.current_trial_ivs):

            after_id = self.root.after(
                t * 1000,
                lambda n=iv_number: self.show_incidental_visualization(n)
            )

            self.incidental_after_ids.append(after_id)

        if not self.is_practice:
            self.root.after(self.condition_duration * 1000, self.start_baseline)

    def update_trial_timer(self):
        """
        Update the on-screen condition/timer label once per second
        and reschedule itself, counting down `self.trial_time_left`.

        In practice mode, the timer loops back to
        `condition_duration` instead of stopping once it reaches
        zero, so practice can run indefinitely. In normal (non-
        practice) mode, once time runs out this method simply stops
        rescheduling itself (the actual transition to baseline is
        driven separately by the `root.after` call scheduled in
        `start_condition`).

        Also calls `hide_openface_window()` on every tick, to
        continuously suppress OpenFace's preview window in case it
        reappears.
        """
        if not hasattr(self, "condition_label"):
            return

        if not self.condition_label.winfo_exists():
            return

        if self.trial_time_left < 0:
            if self.is_practice:
                self.trial_time_left = self.condition_duration 
            else:
                return
        
        self.hide_openface_window()

        minutes = self.trial_time_left // 60
        seconds = self.trial_time_left % 60

        if self.is_practice:
            self.condition_label.config(
                text=f"Practice Mode\nTime: {minutes:02d}:{seconds:02d}"
            )
        else:
            self.condition_label.config(
                text=f"Condition {self.current_index + 1} / {len(self.conditions)}\n"
                    f"Time left: {minutes:02d}:{seconds:02d}"
            )
            
        self.trial_time_left -= 1

        if self.trial_time_left >= 0:
            self.timer_after_id = self.root.after(1000, self.update_trial_timer)

    def on_escape(self, event=None):
        """
        Handle the participant/experimenter pressing Escape: abort the
        current trial early, stop all recordings, and return to the
        start menu.

        Side effects:
            - Cancels all pending incidental-visualization
              `after` callbacks.
            - Stops audio, OpenFace, and EEG recording.
            - Stops the event scheduler, if attached.
            - Destroys all current UI widgets.
            - Recreates the `StartMenu` (imported locally to avoid a
              circular import with `ui.atc_ui`).

        Note: this does NOT save the partial trial's events to CSV or
        log a corresponding event!
        """
        if hasattr(self, "incidental_after_ids"):
            for after_id in self.incidental_after_ids:
                try:
                    self.root.after_cancel(after_id)
                except:
                    pass

        print("ESC pressed - returning to menu")

        self.stop_audio_recording()
        self.stop_openface_recording()
        self.stop_eeg_recording()

        if hasattr(self, "scheduler"):
            self.scheduler.stop()

        for widget in self.root.winfo_children():
            widget.destroy()

        from ui.atc_ui import StartMenu
        StartMenu(self.root, self.on_start_callback)

    # ------------- BASELINE -----------------

    def show_end_screen(self):
        """
        Display a simple "Thank you for your participation!" end
        screen once all conditions have been completed.

        Clears all existing widgets from the root window first.
        """
        print("Experiment finished")

        # limpar UI
        for widget in self.root.winfo_children():
            widget.destroy()

        # frame final
        end_frame = tk.Frame(self.root, bg="white")
        end_frame.pack(fill="both", expand=True)

        label = tk.Label(
            end_frame,
            text="Thank you for your participation!",
            font=("Arial", 28, "bold"),
            bg="white",
            justify="center"
        )
        label.pack(expand=True)

    def start_baseline(self):
        """
        End the current trial condition: stop all recordings, log and
        save per-trial summary statistics and the full event log to
        CSV, reset the engine, and show a rest/baseline countdown
        screen before moving on to the next condition.

        Sequence:
            1. Log "TRIAL_END" and stop audio/OpenFace/EEG recording.
            2. If this is a practice session, just print a message and
               return (practice doesn't count toward results and
               loops instead — see `update_trial_timer`).
            3. Guard against running this twice for the same trial via
               `trial_already_counted`.
            4. Log summary counters for this trial (total errors,
               constraint errors, expiration errors, total flights
               generated, total messages generated, total constrained
               flights). 
            5. Cancel the trial timer and any remaining incidental-
               visualization callbacks; destroy the condition label and
               any open incidental-visualization window.
            6. Save the full per-trial event log to
               `events_data/P<participant_id>_[PRACTICE_]
               events_trial<condition_index>.csv`.
            7. Stop the scheduler and clear the engine's flight list.
            8. Destroy the current UI and show a white "Take some time
               to rest!" overlay with a countdown
               (`update_baseline_countdown`), lasting
               `baseline_duration` seconds.
        """
        self.log_event("TRIAL_END")
        self.stop_audio_recording()
        self.stop_openface_recording()
        self.stop_eeg_recording()


        if self.is_practice:
            print("Practice finished")
            #self.root.destroy()  
            return

        if self.trial_already_counted:
           return

        self.trial_already_counted = True

        # --------- SYSTEM ACK ERRORS ----------

        '''unacked = [
            msg for msg in self.engine.system_messages
            if not msg.acknowledged
        ]

        num_unacked = len(unacked)

        self.engine.system_ack_errors += num_unacked
        self.engine.total_errors += num_unacked

        
        #PER TRIAL
        print("")
        print("Trial errors:", self.engine.total_errors)
        print("Constraint errors:", self.engine.constraint_errors)
        print("Expiration errors:", self.engine.expiration_errors)
        print("Ack errors:", self.engine.system_ack_errors)
        print("------------------")

        #OVERALL
        print("Overall before:", self.total_errors_overall)
        self.total_errors_overall += self.engine.total_errors
        self.constraint_errors_overall += self.engine.constraint_errors
        self.expiration_errors_overall += self.engine.expiration_errors
        self.system_ack_errors_overall += self.engine.system_ack_errors

        print("Overall after:", self.total_errors_overall)
        print("")
        '''

        print("Baseline period")

        self.log_event(f"ERROR_TOTAL_{self.engine.total_errors}")
        self.log_event(f"ERROR_CONSTRAINT_{self.engine.constraint_errors}")
        self.log_event(f"ERROR_EXPIRATION_{self.engine.expiration_errors}")
        #self.log_event(f"ERROR_ACK_{self.engine.system_ack_errors}")       
        self.log_event(f"FLIGHTS_TOTAL_{self.engine.total_flights_generated}")
        self.log_event(f"MESSAGES_TOTAL_{self.scheduler.message_manager.total_messages_generated}")
        self.log_event(f"FLIGHTS_CONSTRAINED_{self.engine.total_constrained_flights}")

        if hasattr(self, "timer_after_id"):
            self.root.after_cancel(self.timer_after_id)

        if hasattr(self, "condition_label") and self.condition_label.winfo_exists():
            self.condition_label.destroy()

        if hasattr(self, "incidental_after_ids"):
            for after_id in self.incidental_after_ids:
                self.root.after_cancel(after_id)

        if hasattr(self, "incidental_window") and self.incidental_window.winfo_exists():
            self.incidental_window.destroy()

        # --------- SAVE EVENTS CSV ----------

        prefix = "PRACTICE_" if self.is_practice else ""
        filename = f"P{self.participant_id}_{prefix}events_trial{self.current_index}.csv"
        
        filepath = os.path.join("events_data", filename)

        os.makedirs("events_data", exist_ok=True)

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)

            writer.writerow(["timestamp", "event"])

            for event in self.events:
                writer.writerow(event)

        print("Events saved")

        self.scheduler.stop()

        self.engine.flights.clear()

        for widget in self.root.winfo_children():
            widget.destroy()

        self.baseline_frame = tk.Frame(self.root, bg="white")
        self.baseline_frame.pack(fill="both", expand=True)

        self.countdown = self.baseline_duration

        self.baseline_label = tk.Label(
            self.baseline_frame,
            text=f"Take some time to rest!\n\n{self.countdown}",
            font=("Arial", 32, "bold"),
            bg="white"
        )
        self.baseline_label.pack(expand=True)

        self.update_baseline_countdown()

    def update_baseline_countdown(self):
        """
        Count down the rest/baseline period once per second. Once it
        reaches zero, briefly shows "Loading...", tears down the
        baseline overlay, and advances to the next condition via
        `next_condition()`.
        """
        if self.countdown <= 0:
            self.baseline_label.config(
                text="Loading...",
                font=("Arial", 36, "bold")
            )
            self.root.update()
            self.baseline_frame.destroy()
            self.next_condition()
            return

        self.baseline_label.config(
            text=f"Take some time to rest!\n\n{self.countdown}"
        )

        self.countdown -= 1
        self.root.after(1000, self.update_baseline_countdown)

    # --------------------------------------------

    def next_condition(self):
        """
        Advance to the next trial condition, or show the end screen if
        all conditions have been completed.

        Rebuilds the SimulationEngine, UI (ATCApp), and EventScheduler
        from scratch for the new condition (rather than reusing the
        previous ones), reusing the previous engine's cognitive/
        complexity profiles only as placeholders — they get
        overwritten immediately afterward by `start_condition` ->
        `apply_condition` based on the new condition letter.
        """
        self.current_index += 1

        if self.current_index >= len(self.conditions):
            self.show_end_screen()
            return

        cognitive = self.engine.cognitive
        complexity = self.engine.complexity

        self.engine = SimulationEngine(cognitive, complexity)
        self.engine.session = self
        self.app = ATCApp(self.root, self.engine)
        self.ui = self.app   
        self.scheduler = EventScheduler(self.root, self.engine, self.app)

        self.start_condition()
        self.scheduler.start()

    def apply_condition(self, letter):
        """
        Translate a condition letter (A-I) into concrete
        CognitiveLoadProfile and TaskComplexityProfile instances, and
        install them on the current engine.

        Mapping (cognitive level, complexity level):
            A: LOW/LOW      D: LOW/MEDIUM    G: LOW/HIGH
            B: MEDIUM/LOW   E: MEDIUM/MEDIUM H: MEDIUM/HIGH
            C: HIGH/LOW     F: HIGH/MEDIUM   I: HIGH/HIGH

        If `self.is_practice` is True, the levels are overridden to a
        fixed LOW cognitive / HIGH complexity combination regardless
        of the letter passed in, so practice always uses a consistent
        (and presumably representative/challenging) configuration.

        Args:
            letter (str): One of "A".."I", identifying the trial
                condition.
        """
        mapping = {
            "A": ("LOW", "LOW"),
            "B": ("MEDIUM", "LOW"),
            "C": ("HIGH", "LOW"),
            "D": ("LOW", "MEDIUM"),
            "E": ("MEDIUM", "MEDIUM"),
            "F": ("HIGH", "MEDIUM"),
            "G": ("LOW", "HIGH"),
            "H": ("MEDIUM", "HIGH"),
            "I": ("HIGH", "HIGH"),
        }

        cog_level, comp_level = mapping[letter]

        if self.is_practice:
            cog_level = "LOW"
            comp_level = "HIGH"

        self.engine.cognitive = CognitiveLoadProfile(cog_level)
        self.engine.complexity = TaskComplexityProfile(comp_level)

        print(f"Condition {letter} → Cognitive: {cog_level}, Complexity: {comp_level}")

    def trigger_critical_events(self):
        """
        Inject a small burst of extra task events (2 extra flights and
        1 extra system message) into the running trial.

        Called right before each incidental-visualization appearance
        (see `show_incidental_visualization`), to ensure
        there is always meaningful task activity happening around the
        time the incidental image appears — relevant for studying
        whether/when participants notice it amid ongoing task demands.
        """
       
        for _ in range(2):
            flight = self.engine.generate_flight()
            if flight:
                self.ui.add_flight(flight)

        msg = self.scheduler.message_manager.generate_message()
        if msg:
            self.ui.add_system_message(msg)

    # ---------------- INCIDENTAL VIS -----------------

    def show_incidental_visualization(self, iv_number):
        """
        Display one incidental-visualization image as a borderless,
        always-on-top popup window for a short, fixed duration.

        This is the core mechanism for the study's independent
        interest: incidental visualizations appear briefly, outside
        the main task UI, and their visibility/noticing is what's
        being measured. Each trial condition triggers this method 4
        times (scheduled from `start_condition`, at 25s/50s/75s/100s
        into the 2-minute trial).

        Sequence:
            1. Bails out if the UI isn't attached or the root window
               no longer exists (e.g. session was aborted).
            2. Calls `trigger_critical_events()` to inject extra task
               activity at the same time the image appears.
            3. Loads the image for this `iv_number` from
               `imgs/iv_<iv_number>.png`.
            4. Creates a borderless (`overrideredirect(True)`),
               always-on-top (`-topmost`) Toplevel window sized
               483x588px, positioned flush against the right edge of
               the screen and vertically centered.
            5. Logs an "IV_APPEAR_<iv_number>" event (timestamped,
               used later to align this with eye-tracking/EEG/audio
               data for analysis).
            6. Displays the image in the popup.
            7. Schedules the popup to automatically close after 1
               second (`hide_incidental_visualization`) — i.e. the
               image is shown for exactly 1 second before
               disappearing.

        Args:
            iv_number (int): Which of the 36 possible incidental
                images to show (determines the file
                `imgs/iv_<iv_number>.png`), as determined by this
                participant's counterbalanced `iv_order`.
        """
        if not hasattr(self, "ui") or not self.ui:
            return

        if not self.root.winfo_exists():
            return

        self.trigger_critical_events()

        image_path = os.path.join("imgs", f"iv_{iv_number}.png")
        image = tk.PhotoImage(file=image_path)

        self.incidental_window = tk.Toplevel(self.root)
        self.incidental_window.overrideredirect(True) 
        self.incidental_window.attributes("-topmost", True)

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        width = 483
        height = 588

        x = screen_width - width 
        y = (screen_height // 2) - (height // 2)  

        self.incidental_window.geometry(f"{width}x{height}+{x}+{y}")
        self.log_event(f"IV_APPEAR_{iv_number}")

        label = tk.Label(self.incidental_window, image=image)
        label.image = image
        label.pack(expand=True)

        self.root.after(1000, self.hide_incidental_visualization)

    def hide_incidental_visualization(self):
        """
        Close the currently displayed incidental-visualization popup
        window, if one exists and is still open.

        Called automatically 1 second after
        `show_incidental_visualization` opens the popup.
        """
        if hasattr(self, "incidental_window") and self.incidental_window.winfo_exists():
            self.incidental_window.destroy()