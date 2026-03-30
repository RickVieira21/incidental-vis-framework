import time
import random

class SystemMessage:
    def __init__(self, text, cognitive):
        self.text = text
        self.created_at = time.time()
        self.acknowledged = False
        self.cognitive = cognitive
        self.ack_time = None

        self.expired = False
        self.expired_at = None

        eta_min, eta_max = self.cognitive.eta_range
        self.timeout = random.randint(eta_min, eta_max)


    def acknowledge(self):

        if self.expired:
            return  # ou log de erro
    
        self.acknowledged = True
        self.ack_time = time.time()


    def check_expired(self):

        if self.acknowledged or self.expired:
            return False

        if time.time() - self.created_at >= self.timeout:
            self.expired = True
            self.expired_at = time.time()
            return True

        return False
    

    @property
    def reaction_time(self):
        if self.ack_time:
            return self.ack_time - self.created_at
        return None
    
    @property
    def time_left(self):
        if self.acknowledged or self.expired:
            return 0
        return max(0, self.timeout - (time.time() - self.created_at))
