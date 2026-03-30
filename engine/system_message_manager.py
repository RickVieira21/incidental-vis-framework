import random
from engine.system_message import SystemMessage  

class SystemMessageManager:
    def __init__(self, engine):
        self.engine = engine
        self.total_messages_generated = 0

    def should_send_message(self):
        r = random.random()
        #print(r)
        return r < self.engine.cognitive.message_frequency

    def generate_message(self):
        messages = self.engine.cognitive.messages
        text = random.choice(messages)
        self.total_messages_generated += 1
        #print(self.total_messages_generated)
        return SystemMessage(text, self.engine.cognitive)

