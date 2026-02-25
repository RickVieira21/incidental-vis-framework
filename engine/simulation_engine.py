import random
import time

from core.flight import Flight
from core.runway import Runway

class SimulationEngine:
    def __init__(self, cognitive_profile, complexity_profile):
        self.cognitive = cognitive_profile
        self.complexity = complexity_profile
        self.system_messages = []

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
        for runway in self.runways:
            if runway.name == name:
                return runway
        return None
    

    def assign_flight_to_runway(self, flight, runway):

        # pista ocupada
        if not runway.available:
            #self.total_errors += 1
            return False

        # constraint violation
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
        if len(self.flights) >= self.complexity.max_flights:
            return None

        # Exemplo  
        flight = Flight(
            callsign="TAP" + str(len(self.flights) + 100),
            eta=30,
            priority=self.complexity.has_priorities
        )

        if self.complexity.has_constraints:
            # probabilidade de ter constraint 
            if random.random() < 0.4:
                flight.required_runway = random.choice(self.runways).name
                
        self.flights.append(flight)

        return flight
    

    # ------------------- Delays e Priorities -----------------------

    def maybe_modify_flight(self):

        if not self.complexity.has_priorities:
            return

        if not self.flights:
            return

        current_time = time.time()

        # ainda não chegou o próximo momento de modificar
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

        # ordenar por ETA
        self.flights.sort(key=lambda f: f.eta)

        # atualizar controlo temporal
        self.last_modification_time = current_time
        self.next_modification_interval = random.randint(15, 25)



    def apply_delay(self, flight):

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

        if flight.is_priority or flight.is_delayed:
            return
        
        if flight.assigned_runway is not None:
            return

        max_reduction = flight.eta - 10

        # se não há margem suficiente, não aplicar prioridade
        if max_reduction < 5:
            return

        reduction = random.randint(5, min(10, max_reduction))

        flight.eta -= reduction
        flight.is_priority = True