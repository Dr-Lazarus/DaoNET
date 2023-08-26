from game.models.player import Player
from game.transport.packet import AcquireMaster, UpdateMaster
from game.transport.transport import Transport


class Clock:
    def __init__(self, myself: Player, transportLayer: Transport, initial_master=None):
        self.indiv_clocks = {}
        self.master: Player = initial_master
        self.myself: Player = myself
        self.transportLayer = transportLayer

    def update_frame(self, player_id, frame):
        self.indiv_clocks[player_id] = frame

    def get_frame(self, player_id):
        return self.indiv_clocks[player_id]

    def get_master(self) -> Player:
        return self.master

    def acquire_master(self):
        self.transportLayer.send(AcquireMaster(
            self.myself), self.get_master().get_name())

    def if_master_emit_new_master(self, new_master: Player):
        if self.master == self.myself:
            self.transportLayer.sendall(UpdateMaster(
                new_master.get_name(), self.myself))

    def update_master(self, new_master: Player, _from: Player):
        if self.master is None or _from.get_name() == self.master.get_name():
            self.master = new_master
