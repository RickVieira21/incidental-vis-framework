"""
experimentalSession.py

Defines ExperimentalSession, the top-level controller for running a
full experimental session with a participant: sequencing the 9 trial
conditions (in a counterbalanced order via a Latin square), starting
and stopping physiological/behavioural recordings (eye-tracking via
OpenFace, EEG via a BITalino device, and microphone audio), logging
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
"""

import tkinter as tk
from levels.cognitive_load import CognitiveLoadProfile
from levels.task_complexity import TaskComplexityProfile
from ui.atc_ui import ATCApp
from engine.simulation_engine import SimulationEngine
from engine.event_scheduler import EventScheduler
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

    A session is built around a counterbalanced ordering, looked up by
    `participant_id`:
        - `self.conditions`: the order in which the 9 condition
          letters (A-I, each mapping to a cognitive-load x
          task-complexity combination — see `apply_condition`) are
          presented to this participant (Latin square across
          participants).

    Attributes:
        root: The Tkinter root window.
        participant_id (int): Numeric ID used to look up this
            participant's counterbalancing orders.
        condition_duration (int): Length of each trial condition in
            seconds (120s = 2 minutes, matching the study design).
        baseline_duration (int): Length of the rest/baseline period
            shown between conditions, in seconds.
        is_practice (bool): Whether this session is a practice run
            (uses a fixed practice condition and loops indefinitely
            instead of ending).
        on_start_callback: Callback used to return to the start menu
            (e.g. after pressing Escape).
        trial_already_counted (bool): Guards against double-counting
            errors/logging if `start_baseline` is somehow triggered
            more than once for the same trial.
        events (list[tuple[float, str]]): Timestamped event log for
            the CURRENT trial, written to a CSV file at the end of
            each condition via `start_baseline`.
        current_index (int): Index of the current condition within
            `self.conditions`.
        conditions (list[str]): This participant's condition-letter
            order, from `load_conditions`.
        use_audio (bool): Whether microphone recording is enabled.
        audio, audio_stream, audio_frames, audio_recording: PyAudio
            recording state (see the PYAUDIO section below).
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

        self.trial_already_counted = False
        self.total_errors_overall = 0
        self.constraint_errors_overall = 0
        self.expiration_errors_overall = 0
        self.system_ack_errors_overall = 0
        self.events = []

        self.current_index = 0
        self.conditions = self.load_conditions(participant_id)

        self.use_audio = True  
        self.audio = None
        self.audio_stream = None
        self.audio_frames = []
        self.audio_recording = False

        self.use_eeg = False  
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

        NOTE: The path to `FeatureExtraction.exe` 
        MUST be updated to point to your own OpenFace installation 

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

        self.mac_address = "your_MAC_Address"
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
            samples = self.eeg_device.read(100) 
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
        "FLIGHT_EXPIRED_...", hardware start/stop events, etc.), each
        paired with a Unix timestamp.

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
        and schedule the automatic transition to the rest-baseline
        period.

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
            7. Unless this is a practice session, schedule the
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
            - Stops audio, OpenFace, and EEG recording.
            - Stops the event scheduler, if attached.
            - Destroys all current UI widgets.
            - Recreates the `StartMenu` (imported locally to avoid a
              circular import with `ui.atc_ui`).
        """
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

        for widget in self.root.winfo_children():
            widget.destroy()

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
            5. Cancel the trial timer and destroy the condition label.
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

        print("Baseline period")

        self.log_event(f"ERROR_TOTAL_{self.engine.total_errors}")
        self.log_event(f"ERROR_CONSTRAINT_{self.engine.constraint_errors}")
        self.log_event(f"ERROR_EXPIRATION_{self.engine.expiration_errors}")   
        self.log_event(f"FLIGHTS_TOTAL_{self.engine.total_flights_generated}")
        self.log_event(f"MESSAGES_TOTAL_{self.scheduler.message_manager.total_messages_generated}")
        self.log_event(f"FLIGHTS_CONSTRAINED_{self.engine.total_constrained_flights}")

        if hasattr(self, "timer_after_id"):
            self.root.after_cancel(self.timer_after_id)

        if hasattr(self, "condition_label") and self.condition_label.winfo_exists():
            self.condition_label.destroy()

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