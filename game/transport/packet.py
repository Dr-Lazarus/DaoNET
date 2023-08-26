from game.models.player import Player
import json
import time
import sys


class Packet:
    """
    We enclose all data to be sent over the network in a packet.

    Accepted data:
    - Action
    - PeeringCompleted
    - SyncReq
    - SyncAck
    - SyncUpdate
    - LobbyRegister
    - LobbyLeave
    - LobbyStart
    - LobbySaveTracker
    - ss_nak
    - ss_ack
    - vote
    - sat_down
    - end_game
    """

    def __init__(self, data, player: Player, packet_type: str):
        self.data = data
        self.player = player
        self.packet_type = packet_type
        self.createdAt = int(time.time())

    def get_data(self):
        return self.data

    def get_player(self):
        return self.player

    def get_packet_type(self):
        return self.packet_type

    def get_created_at(self):
        return self.createdAt

    def __hash__(self):
        return hash(self.packet_type + self.player.name + (str(hash(self.data)) if self.data else ""))

    def json(self) -> str:
        """Return a json representation of the packet."""
        return json.dumps(dict(
            data=self.data,
            player=self.player.dict(),
            packet_type=self.packet_type,
            created_at=self.createdAt
        ))

    def from_json(d):
        """Return a packet from a json representation."""
        return Packet(
            d["data"],
            Player(d["player"].get("name")),
            d["packet_type"]
        )

    def __str__(self):
        return f"Packet: {str(self.data)}"

    def __len__(self):
        """Used for the calculation of the throughput"""
        return sys.getsizeof(self)


class Action(Packet):
    def __init__(self, data: str, player: Player):
        super().__init__(data, player, "action")

    def __str__(self):
        return f"Action: {super().get_packet_type()}"

    def __hash__(self):
        # frame sync packets are unique for keypress, createdat
        return hash(self.packet_type + self.player.get_name() + self.data + str(self.get_created_at()))


class Ack(Packet):
    """Acknowledge a seat selection."""

    def __init__(self, player: Player):
        super().__init__(None, player, "ack")

    def __hash__(self):
        return hash(self.packet_type + self.player.get_name() + str(self.get_created_at()))


class Nak(Packet):
    """Nack seat selection."""

    def __init__(self, player: Player):
        super().__init__(None, player, "nak")

    def __hash__(self):
        return hash(self.packet_type + self.player.get_name() + str(self.get_created_at()))


class PeeringCompleted(Packet):
    """Peering has been completed."""

    def __init__(self, player: Player):
        super().__init__(None, player, "peering_completed")

    def __hash__(self):
        return hash(self.packet_type + self.player.get_name() + str(self.get_created_at()))

# Timer Packets


class SyncReq(Packet):
    """Send a Sync packet"""

    def __init__(self, round_number, player: Player):
        super().__init__(round_number, player, "sync_req")


class SyncAck(Packet):
    """Send a Sync packet."""

    def __init__(self, data, player: Player, round_number):
        super().__init__(data, player, "sync_ack")
        self.round_number = round_number

    def __hash__(self):
        return hash(self.packet_type + self.player.get_name() + str(self.round_number))


class PeerSyncAck(Packet):
    """Send peer their delay measurement."""

    def __init__(self, data, player: Player, round_number):
        super().__init__(data, player, "peer_sync_ack")
        self.round_number = round_number

    def __hash__(self):
        return hash(self.packet_type + self.player.get_name() + str(self.round_number))


class UpdateLeader(Packet):
    """Update the leader of syncing."""

    def __init__(self, data, player: Player):
        super().__init__(data, player, "update_leader")


# End of Timer Packets


class ReadyToStart(Packet):
    """Ready to start game"""

    def __init__(self, player: Player):
        super().__init__(None, player, "ready_to_start")


class AckStart(Packet):
    """AckReady and Start"""

    def __init__(self, player: Player):
        super().__init__(None, player, "ack_start")


class SatDown(Packet):
    """Player has sat down."""

    def __init__(self, seat, player: Player):
        super().__init__(seat, player, "sat_down")

    def __hash__(self):
        # frame sync packets are unique for keypress, createdat
        return hash(self.packet_type + self.player.get_name() + self.data + str(self.get_created_at()))


class FrameSync(Packet):
    """FrameSync"""

    def __init__(self, frame, player: Player):
        super().__init__(frame, player, "frame_sync")

    def __hash__(self):
        # frame sync packets are unique for (frame, createdAt)
        return hash(self.packet_type + self.player.name + str(self.data) + str(self.get_created_at()))


class AcquireMaster(Packet):
    def __init__(self, player: Player):
        super().__init__(None, player, "acquire_master")

    def __hash__(self):
        # frame sync packets are unique for (frame, createdAt)
        return hash(self.packet_type + self.player.name + str(self.data) + str(self.get_created_at()))


class UpdateMaster(Packet):
    def __init__(self, new_master_id: str, player: Player):
        super().__init__(new_master_id, player, "update_master")

    def __hash__(self):
        # frame sync packets are unique for (frame, createdAt)
        return hash(self.packet_type + self.player.name + str(self.data) + str(self.get_created_at()))


# initial transport layer initiation
class ConnectionRequest(Packet):
    """Initial request to connect"""

    def __init__(self, player: Player):
        super().__init__(None, player, "connection_req")


class ConnectionEstab(Packet):
    """Connection has been established."""

    def __init__(self, player: Player):
        super().__init__(None, player, "connection_estab")


class EndGame(Packet):
    """Inform everyone to end the game."""

    def __init__(self, player: Player):
        super().__init__(None, player, "end_game")


class Vote(Packet):
    def __init__(self, playerid: str, player: Player):
        super().__init__(playerid, player, "vote")

    def __hash__(self):
        return hash(self.packet_type + self.player.get_name() + self.data + str(self.get_created_at()))
