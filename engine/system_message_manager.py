"""
system_message_manager.py

Defines SystemMessageManager, a small helper responsible for deciding
when a new SystemMessage should be generated during a trial, and for
creating it with the correct content/timeout parameters.
"""

import random
from engine.system_message import SystemMessage


class SystemMessageManager:
    """
    Decides when to generate new SystemMessage instances for a trial,
    based on the cognitive_profile's configured message frequency.

    Attributes:
        engine (SimulationEngine): Reference to the parent simulation
            engine, used to read `cognitive.message_frequency` and
            `cognitive.messages`.
        total_messages_generated (int): Running count of messages
            generated so far in the trial (for analysis/logging).
    """

    def __init__(self, engine):
        self.engine = engine
        self.total_messages_generated = 0

    def should_send_message(self):
        """
        Randomly decide whether a new system message should be
        generated on this scheduling cycle.

        Draws a random number in [0, 1) and compares it against the
        current trial's `cognitive.message_frequency`, so higher
        frequency values make messages more likely to appear.

        Returns:
            bool: True if a message should be generated now.
        """
        r = random.random()
        #print(r)
        return r < self.engine.cognitive.message_frequency

    def generate_message(self):
        """
        Create a new SystemMessage with a random text drawn from the
        trial's configured message pool.

        Returns:
            SystemMessage: The newly created message, already carrying
            the current trial's `cognitive` profile (so its timeout
            is drawn from the correct ETA range).
        """
        messages = self.engine.cognitive.messages
        text = random.choice(messages)
        self.total_messages_generated += 1
        #print(self.total_messages_generated)
        return SystemMessage(text, self.engine.cognitive)