"""
simulation_engine.py

Core orchestrator of a single simulation trial in the ATC framework.

The SimulationEngine ties together flights (Flight) and runways
(Runway), and applies the rules defined by the trial's independent
variables:
    - `cognitive_profile`: parameters related to the participant's
      cognitive load / message handling for this trial level.
    - `complexity_profile`: parameters related to task complexity for
      this trial level.

Each of the 9 trial levels a participant goes through corresponds to a
different combination of `cognitive_profile` and `complexity_profile`
(low/medium/high on each of the two independent variables).
"""

import random
import time

from core.flight import Flight
from core.runway import Runway


class SimulationEngine:
    """
    Holds and updates all state for one simulation trial: active
    flights, runways, generated system messages, and error/performance
    counters used later for analysis.

    Attributes:
        cognitive: The cognitive_profile object for this trial level.
        complexity: The complexity_profile object for this trial level.
        system_messages (list[SystemMessage]): Messages currently
            visible/pending acknowledgement in the console.
        total_flights_generated (int): Running count of flights
            created during the trial (for analysis/logging).
        total_constrained_flights (int): Running count of flights that
            were generated with a runway constraint
            (`required_runway` set).
        total_errors (int): Aggregate count of all error types below
            (constraint violations, expirations, missed
            acknowledgements).
        constraint_errors (int): Count of attempts to assign a flight
            to a runway that violates its `required_runway`.
        expiration_errors (int): Count of flights or system messages
            that expired (timed out) without being handled/
            acknowledged.
        system_ack_errors (int): Reserved counter for system-message
            acknowledgement errors. 
        last_modification_time (float): Timestamp of the last time a
            flight was modified (delayed or made priority) via
            `maybe_modify_flight`. Used to space out modifications
            over time.
        next_modification_interval (int): Number of seconds to wait
            before the next possible flight modification. Re-rolled
            randomly after each modification.
        flights (list[Flight]): Flights currently active in the trial
            (spawned but not yet completed/removed).
        runways (list[Runway]): The three fixed runways available in
            every trial ("A", "B", "C").
    """

    def __init__(self, cognitive_profile, complexity_profile):
        self.cognitive = cognitive_profile
        self.complexity = complexity_profile
        self.system_messages = []

        self.total_flights_generated = 0
        self.total_constrained_flights = 0

        self.total_errors = 0
        self.constraint_errors = 0
        self.expiration_errors = 0
        self.system_ack_errors = 0

        self.last_modification_time = 0
        self.next_modification_interval = random.randint(5, 10)

        self.flights = []
        self.runways = [
            Runway("A"),
            Runway("B"),
            Runway("C")
        ]

    def get_runway(self, name):
        """
        Look up a Runway object by its name (e.g. "A", "B", "C").

        Args:
            name (str): Runway name to search for.

        Returns:
            Runway or None: The matching Runway, or None if no runway
            with that name exists.
        """
        for runway in self.runways:
            if runway.name == name:
                return runway
        return None

    def assign_flight_to_runway(self, flight, runway):
        """
        Attempt to assign a flight to a runway, applying validation
        rules before committing the assignment.

        This is the main action triggered when the participant tries
        to route a flight to a specific runway.

        Validation order:
            1. If the runway is already occupied, the assignment is
               rejected (returns False). Note: this does NOT currently
               increment `total_errors`.
            2. If the flight has a `required_runway` constraint and
               the chosen runway doesn't match it, the assignment is
               rejected as a constraint violation, incrementing both
               `constraint_errors` and `total_errors`.
            3. Otherwise, the flight is occupied onto the runway for
               `complexity.runway_occupation_time` ticks, and the
               flight's `assigned_runway` is set to the runway's name
               (so its `tick()` logic switches to counting down `etd`
               — see core/flight.py).

        Args:
            flight (Flight): The flight being assigned.
            runway (Runway): The target runway.

        Returns:
            True: if the assignment succeeded.
            False: if the runway was already occupied.
            "CONSTRAINT_VIOLATION": if the flight has a required
                runway and this isn't it.
        """

        if not runway.available:
            #self.total_errors += 1
            return False

        if flight.required_runway is not None:
            if runway.name != flight.required_runway:
                self.constraint_errors += 1
                self.total_errors += 1
                return "CONSTRAINT_VIOLATION"

        duration = self.complexity.runway_occupation_time
        runway.occupy(flight, duration)
        flight.assigned_runway = runway.name

        return True

    def generate_flight(self):
        """
        Create and register a new Flight, if the trial hasn't reached
        its maximum simultaneous flight count.

        The flight's callsign is generated by combining a random
        airline code with a random 3-digit number. Its ETA is drawn
        uniformly from `cognitive.eta_range`. Whether it can be a
        priority flight is determined by `complexity.has_priorities`.

        If `complexity.has_constraints` is enabled, the flight has a
        40% chance of being assigned a `required_runway` (a runway
        constraint it must be routed to), and the constrained-flight
        counter is incremented accordingly.

        Returns:
            Flight or None: The newly created Flight, or None if the
            trial is already at its maximum flight capacity
            (`complexity.max_flights`).
        """
        if len(self.flights) >= self.complexity.max_flights:
            return None

        airlines = ["TAP", "EZY", "RYR", "QTR"]
        generatedCallsign = random.choice(airlines) + str(random.randint(100, 999))

        eta_min, eta_max = self.cognitive.eta_range
        generatedETA = random.randint(eta_min, eta_max)

        flight = Flight(
            callsign=generatedCallsign,
            eta=generatedETA,
            priority=self.complexity.has_priorities
        )

        if self.complexity.has_constraints:
            if random.random() < 0.4:
                flight.required_runway = random.choice(self.runways).name
                self.total_constrained_flights += 1

        self.total_flights_generated += 1
        self.flights.append(flight)

        return flight


    def maybe_modify_flight(self):
        """
        Periodically and randomly modify one eligible waiting flight,
        either delaying it or promoting it to priority.

        This introduces dynamic changes during the trial so that
        flights aren't purely static once spawned. It only runs when
        `complexity.has_priorities` is enabled, and only after at
        least `next_modification_interval` seconds have passed since
        the last modification.

        A flight is only eligible for modification if it:
            - has not yet been assigned to a runway,
            - is not already priority or already delayed,
            - has existed for more than 8 seconds since it spawned
              (gives the participant a minimum window to react before
              the flight's parameters can change).

        If any eligible flight exists, one is picked at random and,
        with 50/50 probability, either delayed (`apply_delay`) or
        promoted to priority (`apply_priority`). The modification
        timer is then reset with a new random interval (10-15s).
        """
        if not self.complexity.has_priorities:
            return

        if not self.flights:
            return

        current_time = time.time()

        if current_time - self.last_modification_time < self.next_modification_interval:
            return

        available_flights = [
            f for f in self.flights
            if f.assigned_runway is None
            and not f.is_priority
            and not f.is_delayed
            and current_time - f.spawn_time > 8
        ]

        if not available_flights:
            return

        flight = random.choice(available_flights)

        if random.random() < 0.5:
            self.apply_delay(flight)
        else:
            self.apply_priority(flight)

        # Sort by ETA
        #self.flights.sort(key=lambda f: f.eta)

        self.last_modification_time = current_time
        self.next_modification_interval = random.randint(10, 15)

    def apply_delay(self, flight):
        """
        Delay a waiting flight by adding extra time to its ETA.

        No-op if the flight is already priority/delayed or already
        assigned to a runway (defensive checks, since eligibility is
        normally already filtered in `maybe_modify_flight`).

        Args:
            flight (Flight): The flight to delay.

        Side effects:
            - Increases `flight.eta` by a random amount (5-10 ticks).
            - Sets `flight.is_delayed = True`.
            - Prints a log line to the console noting the delay
              (participant-visible feedback).
        """
        if flight.is_priority or flight.is_delayed:
            return

        if flight.assigned_runway is not None:
            return

        extra_time = random.randint(5, 10)

        flight.eta += extra_time
        flight.is_delayed = True
        flight.is_priority = False

        print(f"{flight.callsign} delayed +{extra_time}s")

    def apply_priority(self, flight):
        """
        Promote a waiting flight to priority status by reducing its
        remaining ETA, making it more urgent.

        No-op if the flight is already priority/delayed, already
        assigned to a runway, or doesn't have enough time margin left
        to safely reduce (at least 5 ticks of reduction with at least
        10 ticks of ETA remaining beforehand).

        Args:
            flight (Flight): The flight to promote to priority.

        Side effects:
            - Decreases `flight.eta` by a random amount (5-10 ticks,
              capped by the available margin).
            - Sets `flight.is_priority = True`.
        """
        if flight.is_priority or flight.is_delayed:
            return

        if flight.assigned_runway is not None:
            return

        max_reduction = flight.eta - 10

        if max_reduction < 5:
            return

        reduction = random.randint(5, min(10, max_reduction))

        flight.eta -= reduction
        flight.is_priority = True