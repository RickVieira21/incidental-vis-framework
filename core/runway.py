"""
runway.py

Defines the Runway class used throughout the ATC (Air Traffic Control)
simulation framework.

Each Runway instance represents one of the physical runways available
in the simulation (e.g. "A", "B", "C"). Participants assign incoming
Flight objects to runways; once occupied, a runway remains unavailable
for a set duration before it becomes free again.
"""


class Runway:
    """
    Represents a single runway that flights can be assigned to.

    A runway is either available (free) or occupied by exactly one
    flight at a time. While occupied, it counts down `remaining_time`
    on every simulation tick until it automatically releases itself.

    Attributes:
        name (str): Identifier for the runway (e.g. "A", "B", "C"),
            used for display and for matching participant commands
            (e.g. "assign flight X to runway A") to the correct
            Runway object.
        available (bool): Whether the runway is currently free to
            accept a new flight. Starts as True.
        current_flight: Reference to the Flight object currently
            occupying this runway. `None` when the runway is available.
        remaining_time (int/float): Number of simulation ticks left
            before the runway automatically becomes available again.
            0 while the runway is free.
    """

    def __init__(self, name):
        self.name = name
        self.available = True
        self.current_flight = None
        self.remaining_time = 0

    def occupy(self, flight, duration):
        """
        Assign a flight to this runway, marking it as occupied.

        Args:
            flight (Flight): The flight being assigned to this runway.
                The caller is responsible for also setting
                `flight.assigned_runway = self` so the Flight's own
                tick logic switches from counting down `eta` to `etd`.
            duration (int/float): Number of simulation ticks the
                runway should remain occupied before it is
                automatically released.
        """
        self.available = False
        self.current_flight = flight
        self.remaining_time = duration

    def tick(self):
        """
        Advance the runway's internal countdown by one simulation step.

        Called once per simulation tick for every runway. If the
        runway is occupied, decrements `remaining_time`; once it
        reaches 0 (or below), the runway is automatically released
        (see `release`).
        """
        if not self.available:
            self.remaining_time -= 1
            if self.remaining_time <= 0:
                self.release()

    def release(self):
        """
        Free the runway, making it available for a new flight.

        Resets `current_flight` to None and `remaining_time` to 0.
        Called automatically by `tick()` when the occupation duration
        elapses, but can also be called manually if the simulation
        needs to force a runway free (e.g. on trial end/reset).
        """
        self.available = True
        self.current_flight = None
        self.remaining_time = 0