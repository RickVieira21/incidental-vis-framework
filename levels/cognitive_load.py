"""
cognitive_load.py

Defines CognitiveLoadProfile, which encodes the "cognitive load"
independent variable of the study as one of three fixed levels: LOW,
MEDIUM, or HIGH. This profile controls everything related to timing
pressure and message handling that the participant experiences during
a trial (how fast events happen, how urgent messages are, how much
time flights/messages give before timing out, and — at the HIGH level
— whether a secondary/dual task is active).

Each participant experiences all 3 cognitive-load levels crossed with
all 3 task-complexity levels (see task_complexity.py), giving the 9
trial combinations described in the study design.
"""


class CognitiveLoadProfile:
    """
    Holds all parameters that define a single cognitive-load level
    (LOW, MEDIUM, or HIGH) for a trial.

    Attributes:
        level (str): Normalized (uppercase) level name: "LOW",
            "MEDIUM", or "HIGH".
        event_interval (float): Mean interval (in seconds) between
            new-flight generation cycles (used as the mean of an
            exponential distribution in EventScheduler). Lower values
            mean flights arrive more frequently, increasing pressure.
        time_speed (int): Multiplier applied to flight countdown ticks
            (passed to `Flight.tick(speed)`). Currently 1 at every
            level, so it doesn't yet vary cognitive load on its own,
            but is available to accelerate the simulation clock if
            needed.
        message_frequency (float): Probability (0-1) that a new system
            message is generated on each flight-generation cycle (see
            SystemMessageManager.should_send_message). Higher values
            mean more frequent interruptions to acknowledge.
        eta_range (tuple[int, int]): (min, max) range in seconds used
            to randomly draw both flight ETAs and system message
            timeouts. Narrower/lower ranges at higher levels mean less
            time to react.
        messages (list[str]): Pool of possible texts for system
            messages at this level. Wording escalates in urgency from
            LOW ("routine" tone) to HIGH ("URGENT"/conflict alerts),
            which may also serve as a manipulation check for perceived
            urgency.
    """

    def __init__(self, level):
        self.level = level.upper()

        if self.level == "LOW":
            self.event_interval = 9.0
            self.time_speed = 1
            self.message_frequency = 0.3
            self.eta_range = (22, 30)
            self.messages = [
                "System check completed.",
                "Weather nominal."
            ]
  

        elif self.level == "MEDIUM":
              self.event_interval = 6.625
              self.time_speed = 1
              self.message_frequency = 0.5
              self.eta_range = (18, 26)
              self.messages = [
                "Confirm radar contact.",
                "Acknowledge weather update.",
                "Check runway status."
              ]


        elif self.level == "HIGH":
              self.event_interval = 4.25
              self.time_speed = 1
              self.message_frequency = 0.7
              self.eta_range = (14, 22)
              self.messages = [
                "URGENT: Confirm separation.",
                "Acknowledge conflict alert.",
                "Immediate system response required."
            ]
