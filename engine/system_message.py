import time

class SystemMessage:
    def __init__(self, text):
        self.text = text
        self.created_at = time.time()
        self.acknowledged = False
        self.ack_time = None

        self.expired = False
        self.expired_at = None


    def acknowledge(self):

        if self.expired:
            return  # ou log de erro
    
        self.acknowledged = True
        self.ack_time = time.time()


    def check_expired(self):

        if self.acknowledged or self.expired:
            return False

        timeout = getattr(self, "timeout", 10)  # default 10s

        if time.time() - self.created_at >= timeout:
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
