from random import randrange
import time
from game.lobby.tracker import Tracker


class Delay:
    """
    Synchronizes game actions.
    """

    def __init__(self, myself: str, tracker: Tracker):
        print("Delay Initiated")
        self.myself = myself
        self._delay_to_peers = {}
        self.leader_list = tracker.get_leader_list()

        self.generate_delays()

    def generate_delays(self):
        for player_id in self.leader_list:
            if player_id == self.myself:
                continue
            self._delay_to_peers[player_id] = 0.01 * randrange(1, 9)

    def delay(self, player_id):
        sleep_time = self._delay_to_peers[player_id]
        time.sleep(sleep_time)
