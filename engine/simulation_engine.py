from core.flight import Flight
from core.runway import Runway

class SimulationEngine:
    def __init__(self, cognitive_profile, complexity_profile):
        self.cognitive = cognitive_profile
        self.complexity = complexity_profile

        self.flights = []
        self.runways = [Runway("A"), Runway("B"), Runway("C")]

    def generate_flight(self):
        if len(self.flights) >= self.complexity.max_flights:
            return None

        # Exemplo simples (vamos enriquecer depois)
        flight = Flight(
            callsign="TAP" + str(len(self.flights) + 100),
            eta=30,
            priority=self.complexity.has_priorities
        )
        self.flights.append(flight)
        return flight
