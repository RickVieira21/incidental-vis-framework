import time

class Flight:
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
        if self.assigned_runway is None:
            self.eta -= speed
        else:
            self.etd -= speed

        if self.eta <= 0 and self.assigned_runway is None:
            self.completed = True
