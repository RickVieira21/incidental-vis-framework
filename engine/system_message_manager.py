import random

class SystemMessageManager:
    def __init__(self, cognitive_profile):
        self.cognitive = cognitive_profile

    def should_send_message(self):
        return random.random() < self.cognitive.message_frequency

    def generate_message(self):
        messages = self.cognitive.messages
        return random.choice(messages)
