"""
task_complexity.py

Defines TaskComplexityProfile, which encodes the "task complexity"
independent variable of the study as one of three fixed levels: LOW,
MEDIUM, or HIGH. This profile controls the structural difficulty of
the flight-routing task itself: how many flights can be active at
once, how long runways stay occupied, and whether priority flights
and/or runway constraints are part of the trial.

Crossed with the 3 levels of CognitiveLoadProfile (see
cognitive_load.py), this produces the 9 trial combinations each
participant completes.
"""


class TaskComplexityProfile:
    """
    Holds all parameters that define a single task-complexity level
    (LOW, MEDIUM, or HIGH) for a trial.

    Attributes:
        max_flights (int): Maximum number of flights allowed to be
            active (waiting or assigned) at the same time. Higher
            values increase the participant's workload by requiring
            more flights to be tracked simultaneously.
        runway_occupation_time (int): Number of ticks a runway stays
            occupied after a flight is assigned to it (passed to
            `Runway.occupy`). Currently the same (7) at every level,
            so it doesn't vary complexity on its own in the current
            configuration.
        has_priorities (bool): Whether flights can be dynamically
            promoted to priority or delayed during the trial (enables
            `SimulationEngine.maybe_modify_flight` logic). False only
            at LOW; True at MEDIUM and HIGH.
        has_constraints (bool): Whether generated flights can carry a
            `required_runway` constraint that must be respected when
            assigning them (see `SimulationEngine.generate_flight` /
            `assign_flight_to_runway`). Only True at HIGH.
        delay_probability (float): Reserved parameter representing the
            probability of a flight being delayed. Not currently read
            by SimulationEngine (which instead uses a fixed 50/50 to
            choose between delay and priority inside
            `maybe_modify_flight`).
    """

    def __init__(self, level):
        if level == "LOW":
            self.max_flights = 5
            self.runway_occupation_time = 7
            self.has_priorities = False
            self.has_constraints = False
            self.delay_probability = 0.0

        elif level == "MEDIUM":
            self.max_flights = 6
            self.runway_occupation_time = 7
            self.has_priorities = True
            self.has_constraints = False
            self.delay_probability = 0.2

        elif level == "HIGH":
            self.max_flights = 8
            self.runway_occupation_time = 7
            self.has_priorities = True
            self.has_constraints = True
            self.delay_probability = 0.4