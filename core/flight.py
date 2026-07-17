"""
flight.py

Defines the Flight class used throughout the ATC (Air Traffic Control)
simulation framework.

Each Flight instance represents a single aircraft that "spawns" during a
trial and must be assigned by the participant to one of the available
runways (A, B, or C) before it runs out of time (see `eta`/`etd` logic
below). 
"""

import time


class Flight:
    """
    Represents a single flight (aircraft) that must be routed to a runway.

    Lifecycle of a Flight object:
        1. Created when the flight "spawns" in the simulation, with an
           initial estimated time of arrival (`eta`).
        2. While waiting (not yet assigned to a runway), `eta` counts down
           each simulation tick. If it reaches 0 before the flight is
           assigned, the flight is marked as `completed` without ever
           landing (i.e. it "timed out").
        3. Once assigned to a runway (`assigned_runway` is set elsewhere,
           e.g. by the simulation/controller logic), the countdown target
           switches to `etd` (estimated time of departure/occupation time),
           which represents how long the flight will keep the runway busy.

    Attributes:
        callsign (str): Unique identifier for the flight (e.g. "AB123"),
            used to display it in the UI/console and to match it to
            controller commands.
        eta (int/float): Estimated time (in simulation ticks/seconds)
            until the flight must be handled. Counts down while the
            flight has not yet been assigned a runway.
        etd (int/float): Estimated time the flight will occupy its
            assigned runway once landed/assigned. Initialized equal to
            `eta` at creation time.
        priority (bool): Whether this flight is a priority/emergency
            flight. Priority flights are expected to be handled with
            higher urgency by the participant.
        allowed_runways (list or None): Optional restriction on which
            runways (by name, e.g. ["A", "B"]) this flight may be
            assigned to. `None` means no restriction (any runway is
            valid).
        assigned_runway: Reference to the Runway object this flight has
            been assigned to. `None` while the flight is still waiting.
        completed (bool): True once the flight has finished its
            lifecycle in the simulation, either because it was
            successfully handled or because it timed out.
       required_runway: Runway identifier/name required for the flight 
            when it is subject to a runway constraint. This value is used 
            to associate the flight with a specific runway (e.g., in the ATC UI).
        is_priority (bool): Indicates whether the flight has priority handling.
        is_delayed (bool): Indicates whether the flight is currently delayed.
        spawn_time (float): Wall-clock timestamp (from `time.time()`)
            recording when this Flight object was created. Useful for
            logging/analysis of real elapsed time, independent of the
            simulation's internal tick counter.
    """

    def __init__(self, callsign, eta, priority=False, allowed_runways=None):
        self.callsign = callsign
        self.eta = eta
        self.etd = eta
        self.priority = priority
        self.allowed_runways = allowed_runways
        self.assigned_runway = None
        self.completed = False
        self.required_runway = None
        self.is_priority = False
        self.is_delayed = False
        self.spawn_time = time.time()

    def tick(self, speed=1):
        """
        Advance the flight's internal countdown by one simulation step.

        Called once per simulation tick (e.g. once per second, scaled by
        `speed`) for every active flight.

        Behavior:
            - If the flight has NOT yet been assigned a runway, `eta` is
              decremented. If `eta` drops to 0 or below, the flight is
              marked as `completed` (it timed out without being
              assigned).
            - If the flight HAS been assigned a runway, `etd` is
              decremented instead, representing the countdown until the
              flight finishes occupying the runway.

        Args:
            speed (int/float): Multiplier controlling how fast the
                countdown advances (e.g. to support fast-forwarding or
                slowing down the simulation). Defaults to 1 (normal
                speed).
        """
        if self.assigned_runway is None:
            self.eta -= speed
        else:
            self.etd -= speed

        if self.eta <= 0 and self.assigned_runway is None:
            self.completed = True