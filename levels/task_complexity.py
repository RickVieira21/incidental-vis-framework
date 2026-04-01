class TaskComplexityProfile:
    def __init__(self, level):
        if level == "LOW":
            self.max_flights = 5
            self.runway_occupation_time = 8
            self.has_priorities = False
            self.has_constraints = False
            self.delay_probability = 0.0


        elif level == "MEDIUM":
            self.max_flights = 6
            self.runway_occupation_time = 12
            self.has_priorities = True
            self.has_constraints = False
            self.delay_probability = 0.2


        elif level == "HIGH":
            self.max_flights = 8
            self.runway_occupation_time = 16
            self.has_priorities = True
            self.has_constraints = True
            self.delay_probability = 0.4
