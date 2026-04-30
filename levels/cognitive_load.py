class CognitiveLoadProfile:
    def __init__(self, level):
        self.level = level.upper()

        if self.level == "LOW":
            self.event_interval = 9.0
            self.decision_timeout = None
            self.time_speed = 1
            self.message_frequency = 0.3
            self.eta_range = (22, 30) 
            self.messages = [
                "System check completed.",
                "Weather nominal."
            ]
            self.dual_task = False


        elif self.level == "MEDIUM":
              self.event_interval = 6.5
              self.decision_timeout = 10
              self.time_speed = 1
              self.message_frequency = 0.5
              self.eta_range = (18, 26) 
              self.messages = [
                "Confirm radar contact.",
                "Acknowledge weather update.",
                "Check runway status."
              ]
              self.dual_task = False


        elif self.level == "HIGH":
              self.event_interval = 4.0
              self.decision_timeout = 5
              self.time_speed = 1
              self.message_frequency = 0.7
              self.eta_range = (14, 22) 
              self.messages = [
                "URGENT: Confirm separation.",
                "Acknowledge conflict alert.",
                "Immediate system response required."
            ]
              self.dual_task = True
