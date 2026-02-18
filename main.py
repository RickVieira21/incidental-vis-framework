import tkinter as tk

from ui.atc_ui import ATCApp
from ui.atc_ui import StartMenu
from levels.cognitive_load import CognitiveLoadProfile
from levels.task_complexity import TaskComplexityProfile
from engine.simulation_engine import SimulationEngine
from engine.event_scheduler import EventScheduler
from engine.experimentalSession import ExperimentalSession

def main():
    root = tk.Tk()
    root.geometry("1450x820")
    root.title("ATC Experiment")

    def start_experiment(participant_id):

        # Limpar tudo da janela
        for widget in root.winfo_children():
            widget.destroy()

        # Criar sessão
        session = ExperimentalSession(root, participant_id)

        # Perfis iniciais (serão alterados pela sessão)
        cognitive = CognitiveLoadProfile("LOW")
        complexity = TaskComplexityProfile("LOW")

        engine = SimulationEngine(cognitive, complexity)
        app = ATCApp(root, engine)

        scheduler = EventScheduler(root, engine, app)
        scheduler.start()

        session.attach(engine, app, scheduler)
        session.start()

    # Mostrar menu inicial
    StartMenu(root, start_experiment)

    root.mainloop()


if __name__ == "__main__":
    main()
