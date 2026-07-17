"""
main.py

Entry point for the ATC Cognitive Load Simulation Framework.

Creates the single Tkinter root window used throughout the
application's lifetime, shows the initial StartMenu, and wires up
`start_experiment` as the callback that builds a fresh
SimulationEngine + ATCApp (UI) + EventScheduler + ExperimentalSession
each time a participant (or practice) session is started.

Run with:
    python main.py
"""

import tkinter as tk

from ui.atc_ui import ATCApp
from ui.atc_ui import StartMenu
from levels.cognitive_load import CognitiveLoadProfile
from levels.task_complexity import TaskComplexityProfile
from engine.simulation_engine import SimulationEngine
from engine.event_scheduler import EventScheduler
from engine.experimentalSession import ExperimentalSession


def main():
    """
    Set up the Tkinter root window and show the start menu.

    Defines and passes in `start_experiment` as the callback used both
    by StartMenu (on START/PRACTICE) and by ExperimentalSession itself
    (passed through as `on_start_callback`, used e.g. when the
    participant presses Escape and StartMenu is recreated — see
    ExperimentalSession.on_escape).
    """
    root = tk.Tk()
    root.geometry("1450x820")
    root.title("ATC Experiment")

    def start_experiment(participant_id, practice=False):
        """
        (Re)build and start a full simulation stack for one session:
        engine, UI, scheduler, and experimental session controller.

        This is called once per session start (from StartMenu's START
        or PRACTICE buttons), and is also passed into
        ExperimentalSession as `on_start_callback` so a fresh session
        can be started again if the participant returns to the start
        menu (e.g. via Escape) and picks a session again.

        Sequence:
            1. Destroy any existing widgets on the root window (clears
               whatever was shown before, e.g. the StartMenu or a
               previous session's UI).
            2. Create the ExperimentalSession for this participant,
               passing `start_experiment` itself back in so the
               session can restart the flow later if needed.
            3. Create placeholder LOW/LOW cognitive and complexity
               profiles and use them to build a new SimulationEngine.
               These initial values don't matter much: they are
               immediately overwritten once the session applies the
               first real trial condition (see
               ExperimentalSession.start_condition ->
               apply_condition).
            4. Create the ATCApp (UI) bound to this engine, and the
               EventScheduler bound to both, then start the
               scheduler's update loops.
            5. Attach the engine/UI/scheduler to the session
               (`session.attach(...)`) so the session can log events
               and read counters from them, and finally call
               `session.start()` to begin the first trial condition.

        Args:
            participant_id (int): The participant ID selected in
                StartMenu (1-30).
            practice (bool): Whether this is a practice run (passed
                straight through to ExperimentalSession).
        """
        
        for widget in root.winfo_children():
            widget.destroy()

        session = ExperimentalSession(root, participant_id, start_experiment, practice)

        cognitive = CognitiveLoadProfile("LOW")
        complexity = TaskComplexityProfile("LOW")

        engine = SimulationEngine(cognitive, complexity)
        app = ATCApp(root, engine)

        scheduler = EventScheduler(root, engine, app)
        scheduler.start()

        session.attach(engine, app, scheduler)
        session.start()

    StartMenu(root, start_experiment)

    root.mainloop()


if __name__ == "__main__":
    main()