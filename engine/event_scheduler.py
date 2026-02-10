from engine.system_message_manager import SystemMessageManager


class EventScheduler:
    def __init__(self, root, engine, ui):
        self.root = root
        self.engine = engine
        self.ui = ui
        self.running = False

        self.message_manager = SystemMessageManager(engine.cognitive)

    def start(self):
        self.running = True
        self.schedule_next_flight()

    def stop(self):
        self.running = False

    def schedule_next_flight(self):
        if not self.running:
            return

        flight = self.engine.generate_flight()
        if flight:
            self.ui.add_flight(flight)

        if self.message_manager.should_send_message():
            msg = self.message_manager.generate_message()
            self.ui.add_system_message(msg)

        delay = int(self.engine.cognitive.event_rate * 1000)
        self.root.after(delay, self.schedule_next_flight)
