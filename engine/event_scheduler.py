"""
event_scheduler.py

Defines EventScheduler, the component responsible for driving the
simulation forward over time using Tkinter's `root.after()` scheduling
(hence the `root` argument — the Tkinter root window). It repeatedly
reschedules itself to create the "game loop" of the trial: spawning
flights, ticking runways/flights, generating system messages, and
detecting expirations.
"""

import time

from engine.system_message_manager import SystemMessageManager
import random


class EventScheduler:
    """
    Drives the simulation loop for a single trial using Tkinter's
    `after()` scheduling mechanism (non-blocking timers).

    Three independent, self-rescheduling loops run concurrently once
    `start()` is called:
        1. `schedule_runway_update`: ticks every runway once per
           second and refreshes their UI representation.
        2. `schedule_flight_update`: ticks every active flight once
           per second (scaled by `cognitive.time_speed`), removes
           flights that expired (timed out) and logs the event, then
           also checks pending system messages for expiration and
           removes/logs those. Also triggers
           `engine.maybe_modify_flight()` each cycle.
        3. `schedule_next_flight`: generates new flights (and,
           probabilistically, new system messages) at random
           intervals drawn from an exponential distribution, so
           flights don't arrive at perfectly regular intervals.

    Attributes:
        root: The Tkinter root window, used to schedule callbacks via
            `root.after(ms, callback)`.
        engine (SimulationEngine): The simulation engine holding all
            trial state (flights, runways, messages, counters).
        ui: The UI controller object, responsible for rendering
            flights, runways, and messages, and for logging text to
            an on-screen log.
        running (bool): Whether the scheduler's loops are currently
            active. Sub loops check this flag on each cycle and stop
            rescheduling themselves once it's False.
        message_manager (SystemMessageManager): Helper that decides
            when to generate new system messages and creates them.
    """

    def __init__(self, root, engine, ui):
        self.root = root
        self.engine = engine
        self.ui = ui
        self.running = False

        self.message_manager = SystemMessageManager(engine)

    def start(self):
        """
        Begin the simulation trial: set `running` to True and kick off
        all three self-rescheduling update loops.
        """
        self.running = True
        self.schedule_next_flight()
        self.schedule_runway_update()
        self.schedule_flight_update()

    def stop(self):
        """
        Stop the simulation trial. Sets `running` to False; the next
        time each loop checks this flag it will stop rescheduling
        itself, ending the trial gracefully.
        """
        self.running = False

    def schedule_runway_update(self):
        """
        Tick every runway once and refresh its UI representation,
        then reschedule itself to run again in 1 second.

        Stops silently (without rescheduling) if `running` is False.
        """
        if not self.running:
            return

        for runway in self.engine.runways:
            runway.tick()
            self.ui.update_runway(runway)

        self.root.after(1000, self.schedule_runway_update)

    def schedule_flight_update(self):
        """
        Advance all active flights and pending system messages by one
        tick, handle expirations, and reschedule itself to run again
        in 1 second.

        For each flight:
            - Calls `flight.tick()` scaled by `cognitive.time_speed`.
            - If the flight expired (timed out while unassigned),
              increments error counters, removes it from the UI and
              from the engine's flight list, and logs a
              "FLIGHT_EXPIRED_<reaction_time>_<callsign>" event via
              the experimental session.
            - Otherwise, refreshes its UI representation.

        After processing flights, calls `engine.maybe_modify_flight()`
        to possibly delay/prioritize an eligible flight.

        For each pending system message:
            - Calls `msg.check_expired()`.
            - If it just expired, increments error counters, removes
              it from the UI and from the engine's message list, logs
              to the console/UI log, and (if the engine has a
              `session` attribute) logs a "MESSAGE_EXPIRED" event.

        Stops silently (without rescheduling) if `running` is False.
        """
        if not self.running:
            return

        for flight in list(self.engine.flights):
            flight.tick(self.engine.cognitive.time_speed)

            if flight.completed:
                self.engine.total_errors += 1
                self.engine.expiration_errors += 1
                self.ui.remove_flight(flight)
                self.engine.flights.remove(flight)
                decision_time = time.time() - flight.spawn_time
                self.engine.session.log_event(
                    f"FLIGHT_EXPIRED_{decision_time:.3f}_{flight.callsign}"
                )
            else:
                self.ui.update_flight(flight)

        self.engine.maybe_modify_flight()

        for msg in list(self.engine.system_messages):

            if msg.check_expired():

                self.engine.total_errors += 1
                self.engine.expiration_errors += 1

                self.ui.remove_system_message(msg)
                self.engine.system_messages.remove(msg)

                print(f"Message expired: {msg.text}")
                self.ui.add_log(f"Message expired: {msg.text}")

                if hasattr(self.engine, "session"):
                    self.engine.session.log_event(f"MESSAGE_EXPIRED")

        self.root.after(1000, self.schedule_flight_update)

    def schedule_next_flight(self):
        """
        Generate a new flight (if the trial isn't at capacity) and,
        probabilistically, a new system message, then reschedule
        itself after a randomly drawn interval.

        The interval between flight-generation cycles is drawn from
        an exponential distribution with mean
        `cognitive.event_interval`, giving irregular, more realistic
        flight arrival timing (as opposed to a fixed interval, which
        is left commented out below for reference).

        Stops silently (without rescheduling) if `running` is False.
        """
        if not self.running:
            return

        flight = self.engine.generate_flight()
        if flight:
            self.ui.add_flight(flight)

        if self.message_manager.should_send_message():
            msg = self.message_manager.generate_message()
            self.ui.add_system_message(msg)

        mean_interval = self.engine.cognitive.event_interval
        delay = int(random.expovariate(1 / mean_interval) * 1000) 
        self.root.after(delay, self.schedule_next_flight)