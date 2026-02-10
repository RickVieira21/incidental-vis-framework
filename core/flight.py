class Flight:
    def __init__(self, callsign, eta, priority=False, allowed_runways=None):
        self.callsign = callsign
        self.eta = eta
        self.priority = priority
        self.allowed_runways = allowed_runways  # None = qualquer
        self.assigned_runway = None
