import functools
import time
import socket
import json
import logging
from random import randrange

from game.models.player import Player
from game.lobby.tracker import Tracker
from game.transport.packet import UpdateLeader, Packet
# TODO Modify Sync Function Based on New FSM


class Sync:
    """
    Synchronizes game actions.
    """

    def __init__(self, myself: str, tracker: Tracker, logger: logging.Logger):
        print("Sync Initiated")
        self.myself = myself
        self._delay_dict = {}
        self.logger = logger

        self.leader_idx = 0
        self.leader_list = tracker.get_leader_list()

    def next_leader(self):
        if self.leader_idx < len(self.leader_list) - 1:
            self.leader_idx += 1
            self.leader = self.leader_list[self.leader_idx]

    def no_more_leader(self):
        return self.leader_idx == len(self.leader_list) - 1

    def is_leader_myself(self):
        # If you are the leader
        return self.myself == self.leader_list[self.leader_idx]

    def update_delay_dict(self, pkt: Packet):
        peer_player_id = pkt.get_player().get_name()
        self._delay_dict[peer_player_id] = pkt.get_data()

    def done(self):
        return len(self._delay_dict) == len(self.leader_list) - 1

    def add_delay(self, player_id):
        """
        Adds a random delay at first and second hops of the measure delay.
        This value returned by this function + measured difference will serve
        as the sample RTT on the game client.
        """
        if len(self._delay_dict) != len(self.leader_list) - 1:
            return
        else:
            delay = self._delay_dict[player_id]
            time.sleep(delay)
        return

    def get_ordered_delays(self):
        return sorted(self._delay_dict.items(), key=lambda x:x[1], reverse=True)
    
    def get_wait_times(self):
        self.logger.info(f"DELAYLIST\n{self.myself} | Actual delays: {self._delay_dict.items()}")
        ordered_delays = self.get_ordered_delays()
        self.logger.info(f"DELAYLIST_ORDERED\n{self.myself} | Ordered delays: {self._delay_dict.items()}")
        wait_times = {}
        if len(ordered_delays) == len(self.leader_list) - 1:
            for i in range(len(ordered_delays)-1):
                player_id = ordered_delays[i+1][0]
                wait_times[player_id] = ordered_delays[0][1] - ordered_delays[i+1][1] # diff between slowest player and this player
            
            wait_times[ordered_delays[0][0]] = 0 

            return wait_times
        return None
    
    def reset_sync(self):
        self._delay_dict = {}
        self.leader_idx = 0
