from levels.cognitive_load import CognitiveLoadProfile
from levels.task_complexity import TaskComplexityProfile

class ExperimentalSession:

    def __init__(self, root, participant_id):
        self.root = root
        self.participant_id = participant_id

        self.condition_duration = 120
        self.baseline_duration = 10

        self.current_index = 0
        self.conditions = self.load_conditions(participant_id)

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

        # timer 120s
        self.root.after(self.condition_duration * 1000, self.start_baseline)

    def start_baseline(self):
        print("Baseline period")

        # parar simulação
        self.scheduler.running = False

        # ecrã branco
        self.ui.root.configure(bg="white")

        self.root.after(self.baseline_duration * 1000, self.next_condition)

    def next_condition(self):
        # restaurar cor normal
        self.ui.root.configure(bg="#f0f0f0")

        self.scheduler.running = True

        self.current_index += 1
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


