import tkinter as tk
from levels.cognitive_load import CognitiveLoadProfile
from levels.task_complexity import TaskComplexityProfile
from ui.atc_ui import ATCApp
from engine.simulation_engine import SimulationEngine
from engine.event_scheduler import EventScheduler


class ExperimentalSession:

    def __init__(self, root, participant_id):
        self.root = root
        self.participant_id = participant_id

        self.condition_duration = 120
        self.baseline_duration = 10

        self.current_index = 0
        self.conditions = self.load_conditions(participant_id)

        self.incidental_image = tk.PhotoImage(file="incidental.png")

    def attach(self, engine, ui, scheduler):
        self.engine = engine
        self.ui = ui
        self.scheduler = scheduler

    def load_conditions(self, participant_id):

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


    def start(self):
        self.start_condition()

    def start_condition(self):
        if self.current_index >= len(self.conditions):
            print("Experiment finished")
            return

        condition = self.conditions[self.current_index]
        print("Starting condition:", condition)

        # aplicar condição ao engine aqui
        self.apply_condition(condition)

        # Criar indicador de condição no canto inferior direito
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

        self.incidental_after_ids = []

        # IVs - momentos em segundos (relativos ao início do trial)
        self.incidental_times = [25, 50, 75, 100]

        for t in self.incidental_times:
            after_id = self.root.after(
                t * 1000,
                self.show_incidental_visualization
            )
            self.incidental_after_ids.append(after_id)

        # timer 120s
        self.root.after(self.condition_duration * 1000, self.start_baseline)


    def update_trial_timer(self):

        if not hasattr(self, "condition_label"):
            return

        if not self.condition_label.winfo_exists():
            return

        if self.trial_time_left < 0:
            return

        minutes = self.trial_time_left // 60
        seconds = self.trial_time_left % 60

        self.condition_label.config(
            text=f"Condition {self.current_index + 1} / {len(self.conditions)}\n"
                f"Time left: {minutes:02d}:{seconds:02d}"
        )

        self.trial_time_left -= 1

        if self.trial_time_left >= 0:
            self.timer_after_id = self.root.after(1000, self.update_trial_timer)



# ------------- BASELINE -----------------

    def start_baseline(self):

        print("Baseline period")
        # Cancelar timer da condição
        if hasattr(self, "timer_after_id"):
            self.root.after_cancel(self.timer_after_id)

        # Remover label se existir
        if hasattr(self, "condition_label") and self.condition_label.winfo_exists():
            self.condition_label.destroy()

        # Cancelar visualizações agendadas
        if hasattr(self, "incidental_after_ids"):
            for after_id in self.incidental_after_ids:
                self.root.after_cancel(after_id)

        # Fechar janela se ainda estiver aberta
        if hasattr(self, "incidental_window") and self.incidental_window.winfo_exists():
            self.incidental_window.destroy()

        # Parar scheduler
        self.scheduler.stop()

        # Reset engine state
        self.engine.flights.clear()

        # Destruir UI atual
        for widget in self.root.winfo_children():
            widget.destroy()

        # Criar overlay branco
        self.baseline_frame = tk.Frame(self.root, bg="white")
        self.baseline_frame.pack(fill="both", expand=True)

        self.countdown = self.baseline_duration

        self.baseline_label = tk.Label(
            self.baseline_frame,
            text=f"Baseline Period\n\n{self.countdown}",
            font=("Arial", 32, "bold"),
            bg="white"
        )
        self.baseline_label.pack(expand=True)

        self.update_baseline_countdown()


    def update_baseline_countdown(self):

        if self.countdown <= 0:
            self.baseline_frame.destroy()
            self.next_condition()
            return

        self.baseline_label.config(
            text=f"Baseline Period\n\n{self.countdown}"
        )

        self.countdown -= 1
        self.root.after(1000, self.update_baseline_countdown)


# --------------------------------------------


    def next_condition(self):

        self.current_index += 1

        if self.current_index >= len(self.conditions):
            print("Experiment finished")
            return

        # Recriar engine e UI do zero
        cognitive = self.engine.cognitive
        complexity = self.engine.complexity

        self.engine = SimulationEngine(cognitive, complexity)
        self.app = ATCApp(self.root, self.engine)
        self.scheduler = EventScheduler(self.root, self.engine, self.app)

        self.scheduler.start()
        self.start_condition()



    def apply_condition(self, letter):

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

        self.engine.cognitive = CognitiveLoadProfile(cog_level)
        self.engine.complexity = TaskComplexityProfile(comp_level)

        print(f"Condition {letter} → Cognitive: {cog_level}, Complexity: {comp_level}")


# ---------------- INCIDENTAL VIS -----------------

    def show_incidental_visualization(self):

        self.incidental_window = tk.Toplevel(self.root)
        self.incidental_window.overrideredirect(True) #remover bordas
        self.incidental_window.attributes("-topmost", True)

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        width = 400
        height = 300

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        self.incidental_window.geometry(f"{width}x{height}+{x}+{y}")

        label = tk.Label(self.incidental_window, image=self.incidental_image)
        label.image = self.incidental_image
        label.pack(expand=True)

        self.root.after(1000, self.hide_incidental_visualization)


  
    def hide_incidental_visualization(self):

        if hasattr(self, "incidental_window") and self.incidental_window.winfo_exists():
            self.incidental_window.destroy()

