from engine.system_message_manager import SystemMessageManager


class EventScheduler:
    def __init__(self, root, engine, ui):
        self.root = root
        self.engine = engine
        self.ui = ui
        self.running = False

        self.message_manager = SystemMessageManager(engine)

    def start(self):
        self.running = True
        self.schedule_next_flight()
        self.schedule_runway_update()
        self.schedule_flight_update()

    def stop(self):
        self.running = False


# ---  UPDATE TICKS ---

    def schedule_runway_update(self):
        if not self.running:
            return

        for runway in self.engine.runways:
            runway.tick()
            self.ui.update_runway(runway)

        # tick a cada 1 segundo
        self.root.after(1000, self.schedule_runway_update)


    def schedule_flight_update(self):
        if not self.running:
            return

        for flight in list(self.engine.flights):
            flight.tick(self.engine.cognitive.time_speed)

            if flight.completed:
                self.engine.total_errors += 1
                self.engine.expiration_errors += 1
                self.ui.remove_flight(flight)
                self.engine.flights.remove(flight)
            else:
                self.ui.update_flight(flight)

        self.engine.maybe_modify_flight()
        self.ui.refresh_flight_list()
    
        self.root.after(1000, self.schedule_flight_update)



    def schedule_next_flight(self):
        if not self.running:
            return

        flight = self.engine.generate_flight()
        if flight:
            self.ui.add_flight(flight)

        if self.message_manager.should_send_message():
            #print("sendddddd")
            msg = self.message_manager.generate_message()
            self.ui.add_system_message(msg)

        delay = int(self.engine.cognitive.event_rate * 1000)
        self.root.after(delay, self.schedule_next_flight)
