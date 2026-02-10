class CognitiveLoadProfile:
    def __init__(self, level):
        self.level = level.upper()

        if self.level == "LOW":
            self.event_rate = 10.0
            self.decision_timeout = None
            self.message_frequency = 0.1
            self.messages = [
                "System check completed.",
                "Weather nominal."
            ]
            self.dual_task = False


        elif self.level == "MEDIUM":
              self.event_rate = 6.0
              self.decision_timeout = 10
              self.message_frequency = 0.3
              self.messages = [
                "Confirm radar contact.",
                "Acknowledge weather update.",
                "Check runway status."
              ]
              self.dual_task = False


        elif self.level == "HIGH":
              self.event_rate = 3.0
              self.decision_timeout = 5
              self.message_frequency = 0.6
              self.messages = [
                "URGENT: Confirm separation.",
                "Acknowledge conflict alert.",
                "Immediate system response required."
            ]
              self.dual_task = True
