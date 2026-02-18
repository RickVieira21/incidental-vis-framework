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
            1: ["A","B","I","C","H","D","G","E","F"],
            2: ["G","F","H","E","I","D","A","C","B"],
            # continua...
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

        # Atualizar perfis
        self.engine.cognitive.set_level(cog_level)
        self.engine.complexity.set_level(comp_level)

        print(f"Condition {letter} → Cognitive: {cog_level}, Complexity: {comp_level}")

