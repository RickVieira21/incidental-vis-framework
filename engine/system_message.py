"""
system_message.py

Defines SystemMessage, representing a single console message that the
participant must notice and acknowledge during a trial (separate from
the flight-routing task itself). These messages simulate the kind of
secondary alerts a real controller must attend to, and are one of the
sources of "errors" tracked for the study (missed/expired
acknowledgements).
"""

import time
import random


class SystemMessage:
    """
    Represents a single system message shown in the console that the
    participant must acknowledge before it expires.

    Attributes:
        text (str): The message content displayed to the participant.
        created_at (float): Wall-clock timestamp of when the message
            was created.
        acknowledged (bool): Whether the participant has acknowledged
            the message.
        cognitive: The cognitive_profile for the current trial,
            used to determine the message's timeout window
            (`eta_range`).
        ack_time (float or None): Wall-clock timestamp of when the
            message was acknowledged, or None if not yet acknowledged.
        expired (bool): Whether the message expired (timed out)
            without being acknowledged.
        expired_at (float or None): Wall-clock timestamp of when the
            message expired, or None if it hasn't expired.
        timeout (int): Number of seconds the participant has to
            acknowledge the message before it expires. Drawn randomly
            from `cognitive.eta_range` (the same range used for flight
            ETAs), so message urgency scales with the trial's
            cognitive-load level.
    """

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
        """
        Mark the message as acknowledged by the participant.

        No-op if the message has already expired (an expired message
        can no longer be acknowledged). Records the acknowledgement
        timestamp in `ack_time`, which is later used to compute
        `reaction_time`.
        """
        if self.expired:
            return 

        self.acknowledged = True
        self.ack_time = time.time()

    def check_expired(self):
        """
        Check whether the message's timeout has elapsed and, if so,
        mark it as expired.

        Intended to be called once per simulation tick (e.g. by
        EventScheduler) for every pending message.

        Returns:
            bool: True if the message just expired as a result of this
            call, False if it was already resolved (acknowledged or
            previously expired) or if it hasn't timed out yet.
        """
        if self.acknowledged or self.expired:
            return False

        if time.time() - self.created_at >= self.timeout:
            self.expired = True
            self.expired_at = time.time()
            return True

        return False

    @property
    def reaction_time(self):
        """
        float or None: Time in seconds between message creation and
        acknowledgement, used for analysis of participant response
        speed. None if the message hasn't been acknowledged yet.
        """
        if self.ack_time:
            return self.ack_time - self.created_at
        return None

    @property
    def time_left(self):
        """
        float: Seconds remaining before the message expires. Returns 0
        if the message has already been acknowledged or has expired.
        """
        if self.acknowledged or self.expired:
            return 0
        return max(0, self.timeout - (time.time() - self.created_at))