import tkinter as tk

from ui.atc_ui import ATCApp
from levels.cognitive_load import CognitiveLoadProfile
from levels.task_complexity import TaskComplexityProfile
from engine.simulation_engine import SimulationEngine
from engine.event_scheduler import EventScheduler

root = tk.Tk()

cognitive = CognitiveLoadProfile("LOW")
complexity = TaskComplexityProfile("LOW")

engine = SimulationEngine(cognitive, complexity)
app = ATCApp(root)

scheduler = EventScheduler(root, engine, app)
scheduler.start()

root.mainloop()
