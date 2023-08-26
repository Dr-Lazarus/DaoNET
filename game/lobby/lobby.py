import socket
from game.lobby.tracker import Tracker
import json
import keyboard
from game.thread_manager import ThreadManager
import threading
import logging


class Lobby():
    """
    Lobby state helps initialize connections and shift to game state once max number 
    of players have been reached.
    """

    def __init__(self, logger):
        self.game_started = False
        self.lobby_host_exited = False
        self.chunksize = 1024
        self.logger = logger

        self.lock = threading.Lock()
        self.game_start_lock = threading.Lock()

    def start(self, host_ip="127.0.0.1", host_port=9999, player_name="Host"):
        """
        Hosting a lobby
        """
        self.player_name = player_name

        self.tracker = Tracker()
        self.thread_mgr = ThreadManager()

        self.player_ip = host_ip
        self.host_port = host_port

        # initialize host socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", host_port))
        sock.listen(7)
        sock.settimeout(0.5)
        self.mysocket = sock

        # register myself
        self.tracker.add(player_name, host_ip, self.host_port)

        self.connections = {}

        # bind keypress listener
        keyboard.add_hotkey('space', self.attempt_start)

        try:
            while not self.game_started:
                try:
                    connection, _ = self.mysocket.accept()
                    if connection:
                        # start a thread to handle incoming data
                        t = threading.Thread(target=self.thread_handler, args=(
                            connection, ), daemon=True)
                        t.start()
                        self.thread_mgr.add_thread(t)
                except socket.timeout:
                    pass
            print("Exiting lobby, entering game")
            return self.mysocket, self.tracker
        except KeyboardInterrupt:
            self.thread_mgr.shutdown()
            print("\nExiting lobby")
        finally:
            for connection in self.connections.values():
                connection.close()
            keyboard.remove_all_hotkeys()

    def join(self, host_ip="127.0.0.1", player_ip="127.0.0.1", host_port=9999, player_port=9997, player_name="Player") -> Tracker:
        """
        Join an existing lobby.
        """
        self.player_name = player_name
        self.player_port = player_port
        self.player_ip = player_ip

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host_ip, host_port))

        self.send(self.lobby_register_pkt(), sock)

        try:
            while not self.game_started and not self.lobby_host_exited:
                buf = sock.recv(1024)
                if buf:
                    self.handle_player(buf.decode(
                        'utf-8').rstrip("\0"), sock)
            print("Exiting lobby, entering game")
            return None, self.tracker
        except KeyboardInterrupt:
            self.send(self.lobby_deregister_pkt(), sock)
            sock.close()
            print("\nExiting lobby")
            exit()
        finally:
            sock.close()

    # handler triggers

    def handle_player(self, packet, connection):
        """
        Handle incoming packets from players
        """
        req = json.loads(packet)
        packet_type = req.get("packet_type")

        if packet_type == "lobby_shutdown":
            connection.close()
            self.lobby_host_exited = True
            return

        if packet_type == "lobby_start":
            # game is starting, save tracker
            data = req.get("data")
            tracker = data.get("tracker")

            if tracker is None:
                self.send(self.nak("No tracker data provided"), connection)
                return

            self.tracker = Tracker(tracker)
            print(self.tracker.get_players())
            self.game_started = True

    def handle_host(self, packet, connection):
        req = json.loads(packet)

        # read packet
        packet_type = req.get("packet_type")

        if (packet_type == "lobby_register"):
            data = req.get("data")
            self.lobby_register(data, connection)
        elif (packet_type == "lobby_deregister"):
            data = req.get("data")
            self.lobby_deregister(data, connection)
        else:
            self.send(self.nak("Unknown payload type: " +
                      packet_type), connection)

    # state handlers

    def attempt_start(self):
        if self.tracker.get_player_count() >= 2:
            self.lobby_start_game()
        else:
            print("Not enough players to start game.")
            self.logger.info(
                f"Attempted to start with {self.tracker.get_player_count()} players.")
            print("Current players: " + str(self.tracker.get_players()))

    def lobby_register(self, data, connection):
        player_id = data.get("player_id")
        player_ip = data.get("ip_address")
        player_port = data.get("port")

        if not player_id:
            print("No player id")
            return
        if not player_port:
            print("No player port")
            return

        if self.tracker.is_ip_port_used(player_ip, player_port):
            print("[lobby_register] ip port used")
            self.send(self.nak("ip + port in use by another player"), connection)
            return

        self.lock.acquire()
        self.connections[player_id] = connection
        self.tracker.add(player_id, player_ip, player_port)
        self.lock.release()

        self.send(self.ack(), connection)

        print("Player registered: " + player_id)
        print("Current players: " + str(self.tracker.get_players()))

    def lobby_deregister(self, data, connection):
        player_id = data.get("player_id")
        player_ip = data.get("ip_address")
        player_port = data.get("port")

        if not player_id:
            print("No player id")
            return
        if not player_port or not player_ip:
            print("No player port or IP address")
            return

        self.lock.acquire()
        self.connections.pop(player_id)
        self.tracker.remove(player_id)
        self.lock.release()

        connection.close()
        print("Player left the lobby: " + player_id)
        print("Current players: " + str(self.tracker.get_players()))

    def lobby_start_game(self):
        for connection in self.connections.values():
            self.send(self.start_pkt(), connection)
        print("All clients notified of game start.")
        self.logger.info("All clients notified of game start.")
        keyboard.remove_hotkey('space')

        self.game_started = True

    # handler threads
    def thread_handler(self, connection):
        while not self.game_started:
            try:
                buf = connection.recv(1024)
                if buf:
                    self.handle_host(buf.decode(
                        'utf-8').rstrip("\0"), connection)
            except:
                pass

    # helper method to send packets
    def send(self, packet: bytes, connection):
        connection.sendall(packet.ljust(self.chunksize, b"\0"))

    # packets

    def start_pkt(self):
        return json.dumps(dict(
            data=dict(
                players=self.tracker.get_players(),
                tracker=self.tracker.get_tracker_list()
            ),
            packet_type="lobby_start",
        )).encode('utf-8')

    def lobby_register_pkt(self):
        return json.dumps(dict(
            data=dict(
                player_id=self.player_name,
                ip_address=self.player_ip,
                port=self.player_port,
            ),
            packet_type="lobby_register",
        )).encode('utf-8')

    def lobby_deregister_pkt(self):
        return json.dumps(dict(
            data=dict(
                player_id=self.player_name,
                ip_address=self.player_ip,
                port=self.player_port,
            ),
            packet_type="lobby_deregister",
        )).encode('utf-8')

    def nak(self, error_msg="Error"):
        return json.dumps(dict(
            data=dict(
                message=error_msg
            ),
            packet_type="lobby_nak",
        )).encode('utf-8')

    def ack(self):
        return json.dumps(dict(
            data=dict(
                message="Success"
            ),
            packet_type="lobby_ack",
        )).encode('utf-8')
