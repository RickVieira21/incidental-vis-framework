class TaskComplexityProfile:
    def __init__(self, level):
        if level == "LOW":
            self.max_flights = 5
            self.has_priorities = False
            self.has_constraints = False
            self.delay_probability = 0.0
            self.system_state_changes = False

        elif level == "MEDIUM":
            self.max_flights = 10
            self.has_priorities = True
            self.has_constraints = False
            self.delay_probability = 0.2
            self.system_state_changes = False

        elif level == "HIGH":
            self.max_flights = 20
            self.has_priorities = True
            self.has_constraints = True
            self.delay_probability = 0.4
            self.system_state_changes = True
