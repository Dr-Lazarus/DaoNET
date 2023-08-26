import json
import threading
from platform import system
from game.clock.clock import Clock
from game.models.player import Player
from game.lobby.tracker import Tracker
from game.thread_manager import ThreadManager
from game.transport.transport import Transport
from game.transport.packet import AckStart, EndGame, Nak, Ack, PeerSyncAck, PeeringCompleted, Packet, ReadyToStart, SatDown, FrameSync, SyncAck, UpdateLeader, Action, Vote
import keyboard
import game.clock.sync as sync
from time import time, sleep
import logging


class Client():
    """
    Game FSM
    """

    def __init__(self, my_name: str, tracker: Tracker, logger, host_socket=None, ):
        super().__init__()

        self._state: str = "PEERING"
        self._myself = Player(name=my_name)
        self.game_over = False
        self.tracker = tracker
        self.host_socket = host_socket  # for testing only
        self.my_ip, self.my_port_number = self.tracker.get_ip_port(
            self._myself.get_name())  # for testing only

        self._tracker_list = self.tracker.get_tracker_list()
        self._total_players = self.tracker.get_player_count()

        self.lock = threading.Lock()
        self.logger = logger

        self._players: dict[str, Player] = {
            self._myself.get_name(): self._myself}
        self._votekick: dict[str, int] = {}

        self.os_name = system()

        self.loop_interval = 0.5

        # INITIALIZE ROUND INPUTS #
        LETTERS = ["Q", "W", "E", "R", "T", "Y"]
        KEYBOARD_MAPPING_MAC = [12, 13, 14, 15, 17, 16]  # Q W E R T Y
        KEYBOARD_MAPPING_WDW = [81, 87, 69, 82, 84, 89]  # Q W E R T Y

        self.key_to_letter = {}
        self.letter_to_key = {}

        mapping = KEYBOARD_MAPPING_MAC
        if self.os_name == "Windows":
            mapping = KEYBOARD_MAPPING_WDW

        for i in range(len(LETTERS)):
            self.key_to_letter[mapping[i]] = LETTERS[i]
            self.letter_to_key[LETTERS[i]] = mapping[i]

        self._round_inputs = {k: None for k in [
            self.key_to_letter[mapping[i]] for i in range(self._total_players - 1)]}

        self.hotkeys_added = False
        self._round_started = False
        self._round_ready = {}
        self._round_ackstart = {}
        self._sat_down_count = 0

        self._vote_tied = False

        self._my_keypress = None
        self._my_keypress_time = None
        self.init_send_time = None
        self.init_ack_start = None

        # selecting seats algo
        self._nak_count = 0
        self._ack_count = 0
        self._is_selecting_seat = False
        self._done_voting = False

        # transport layer stuff
        self._transportLayer = Transport(my_name,
                                         self.tracker.get_ip_port(my_name)[1],
                                         ThreadManager(),
                                         logger,
                                         tracker=self.tracker,
                                         host_socket=host_socket)
        self.is_peering_completed = False
        # print(f"Tracker_List Before Sync:{self.tracker.get_tracker_list()}")
        # print(
        #     f"Leader List Before Sync Initialisation:{self.tracker.get_leader_list()}")

        self._frameSync = Clock(
            self._myself, self._transportLayer, self._myself if host_socket else None)
        self.frame_delta_threshold = 2
        self.frame_count = 0
        self.alpha = 0.1

        self.is_peering_completed = False
        self.is_sync_complete = False

        self.round_number = 1
        self._am_spectator = False

    def _state(self):
        return self._state

    def start(self):
        try:
            while not self.game_over:
                sleep(self.loop_interval)  # slow down game loop
                temporary_logger_dict = json.dumps(
                    {"Logger Name": "FRAME COUNT", "Logging Data": self.frame_count, "Player Name": self._myself.get_name(), "Time": time()})
                self.logger.info(f'{temporary_logger_dict}')
                self.frame_count += 1
                if self._frameSync.get_master() == self._myself and self.frame_count % 10 == 0:
                    self._transportLayer.sendall(
                        FrameSync(self.frame_count, self._myself))
                self.trigger_handler(self._state)

        except KeyboardInterrupt:
            print("Exiting game")
            self._transportLayer.shutdown()

    def trigger_handler(self, state):
        if state == "PEERING":
            self.peering()

        if state == "SYNCHRONIZE_CLOCK":
            self.sync_clock()

        if state == "AWAIT_SYNC_END":
            self.await_sync_end()

        if state == "INIT":
            self.init()

        elif state == "AWAIT_KEYPRESS":
            self.await_keypress()

        elif state == "AWAIT_ROUND_END":
            self.await_round_end()

        elif state == "END_ROUND":
            self.end_round()

        elif state == "END_GAME":
            self.end_game()

        elif state == "SPECTATOR":
            self.spectator()

        elif state == "RESET_SYNC":
            self.reset_sync()

    def peering(self):
        if self._transportLayer.all_connected() and not self.is_peering_completed:
            self._transportLayer.sendall(PeeringCompleted(player=self._myself))
            self.is_peering_completed = True

            self._state = "RESET_SYNC"

    def reset_sync(self):
        self._transportLayer.reset_sync()
        self._state = "SYNCHRONIZE_CLOCK"

    def sync_clock(self):
        self._checkTransportLayerForIncomingData()
        if not self._transportLayer.sync.done():
            self.is_sync_complete = self._transportLayer.syncing(
                self.round_number)
            return
        else:
            print(f"[DELAYS FILLED]: {self._transportLayer.sync._delay_dict}")
            temporary_logger_dict = json.dumps(
                {"Logger Name": "UNORDERED DELAYLIST", "Round Number": self.round_number, "Logging Data": self._transportLayer.sync._delay_dict})
            self.logger.info(f'{temporary_logger_dict}')
            temporary_logger_dict = json.dumps({"Logger Name": "ORDERED DELAYLIST", "Round Number": self.round_number, "Logging Data": sorted(
                self._transportLayer.sync._delay_dict, key=lambda x: x[1], reverse=True)})
            self.logger.info(f'{temporary_logger_dict}')
            temporary_logger_dict = json.dumps(
                {"Logger Name": "WAIT LIST", "Round Number": self.round_number, "Logging Data": self._transportLayer.sync.get_wait_times()})
            self.logger.info(f'{temporary_logger_dict}')
            update_leader_pkt = UpdateLeader(self.round_number, self._myself)
            self._transportLayer.sendall(update_leader_pkt)
            self._transportLayer.sync.next_leader()
            self._state = "AWAIT_SYNC_END"

    def await_sync_end(self):
        self._checkTransportLayerForIncomingData()
        if self._transportLayer.sync.no_more_leader():
            self._transportLayer.stop_timers()
            print(f"[SYNC COMPLETE]")
            self._state = "INIT" if self.round_number == 1 else "AWAIT_KEYPRESS"

    def init(self):
        # we only reach here once peering is completed
        # everybody sends ok start to everyone else
        self._checkTransportLayerForIncomingData()

        if len(self._round_ready.keys()) < self._total_players - 1:
            if self.init_send_time is None:
                print(f"[SYSTEM] Sending Ready to Start...")
                self.init_send_time = time()
                temporary_logger_dict = json.dumps(
                    {"Logger Name": "FRAME SYNCING", "Frame Count": self.frame_count, "Player Name": self._myself.get_name(), "Time": time()})
                self.logger.info(f'{temporary_logger_dict}')
                self._frameSync.if_master_emit_new_master(self._myself)
                self._transportLayer.sendall(ReadyToStart(self._myself))
        else:
            if self.init_ack_start is None:
                self.init_ack_start = time()
                print("[SYSTEM] Voting to start now...")
                self._transportLayer.sendall(AckStart(self._myself))
                self._state = "AWAIT_KEYPRESS"

    def await_keypress(self):
        self._checkTransportLayerForIncomingData()

        if self._am_spectator:
            self._state = "SPECTATOR"
            return

        if not self._round_started:
            if self._all_voted_to_start():
                # waiting for everyone to ackstart
                print(f"[SYSTEM] STARTING GAME IN 3 SECONDS")
                sleep(1)

                print(f"[SYSTEM] STARTING GAME IN 2 SECONDS")
                sleep(1)

                print(f"[SYSTEM] STARTING GAME IN 1 SECONDS")
                sleep(1)
                
                self._round_started = True
                print(f"\n|-------- ROUND {self.round_number} --------|")
                print(f"[PLAYING AS] {self._myself.get_name()}")
                print(f"[CURRENT PLAYERS] {list(self._players.keys())}")
                print(f"[AVAILABLE SEATS] {self._round_inputs}")
                print("[SYSTEM] GRAB A SEAT NOW !!!")

        if self._round_started:
            # 1) Received local keypress
            if self._my_keypress is None:
                if not self.hotkeys_added:
                    for k in self._round_inputs.keys():
                        ## FOR TESTING ONLY ##
                        # player takes hotkey sequentially accordingly to port number
                        # port 9999 takes 12, 10000 takes 13...
                        # if not (k + 9987 == self.my_port_number):
                        #     continue
                        if self.os_name != "Windows":
                            translated_key: str = self.letter_to_key[k]
                        else:
                            translated_key = k.lower()
                        keyboard.add_hotkey(
                            translated_key, self._insert_input, args=(k,))
                        self.hotkeys_added = True

            elif not self._is_selecting_seat:
                # first time we've received a keypress, and have yet to enter selecting seat
                self._selecting_seats()

            if self._is_selecting_seat:
                thresh = len(self._players) // 2
                if (self._nak_count + self._ack_count) >= len(self._players)-1:
                    if self._nak_count >= thresh:
                        print("[ACTION] Failed to sit down, pick a new seat!")
                        # SelectingSeat failed
                        self._my_keypress = None
                        self._nak_count = 0
                        self._ack_count = 0
                        self._is_selecting_seat = False
                        self.hotkeys_added = False
                    else:
                        # SelectingSeat success
                        self.lock.acquire()
                        self._round_inputs[self._my_keypress] = self._myself.get_name(
                        )
                        self.lock.release()
                        self._transportLayer.sendall(
                            SatDown(self._my_keypress, self._myself))
                        self._sat_down_count += 1
                        print("[ACTION] I have sat down successfully!")
                        print(f"[SEATS] {self._round_inputs}")
                        self._state = "AWAIT_ROUND_END"
                        return

            # if everyone else has sat down, move onto next state
            elif all(self._round_inputs.values()):
                self._state = "AWAIT_ROUND_END"

    def await_round_end(self):
        self._checkTransportLayerForIncomingData()
        if all(self._round_inputs.values()):
            # everyone is ready to vote
            if not self._done_voting:
                # choosing who to kick
                player_to_kick = None
                for playerid in self._players.keys():
                    if playerid not in self._round_inputs.values():
                        player_to_kick = playerid
                        print(
                            f"[VOTE] Voting to kick: {self._players[playerid].get_name()}")
                        packet = Vote(player_to_kick, self._myself)
                        self._transportLayer.sendall(packet)
                        # my own vote
                        numvotes = self._votekick.get(player_to_kick, 0)
                        self._votekick[player_to_kick] = numvotes + 1
                        break  # break after the first player to kick
                self._done_voting = True

                if player_to_kick == None:
                    print(
                        "[SYSTEM] Cannot find player to kick, moving to next round")
                    self._state = "END_ROUND"
                    return

            # tallying votes
            else:
                # print(f"Waiting for votes... Current votes: {self._votekick}")
                if sum(self._votekick.values()) >= len(self._players):
                    print("\n ---- ALL VOTES IN ----")
                    max_vote = max(self._votekick.values())
                    # in case there is a tie
                    to_be_kicked = [key for key,
                                    value in self._votekick.items() if value == max_vote]

                    # 1) if only one voted, remove from player_list
                    if len(to_be_kicked) == 1:
                        print(
                            f"[KICKING LOSER] Kicking player: {to_be_kicked[0]}")
                        self._players.pop(to_be_kicked[0])

                    else:
                        self._vote_tied = True
                        print(
                            "[SYSTEM] Vote tied; moving onto the next round with nobody kicked")

                    self._state = "END_ROUND"

    def end_round(self):
        # clear all variables
        print(
            f"\n---- Round has ended. Players left: {list(self._players.keys())} ----")
        self._reset_round()

        # player has lost the game
        if not self._players.get(self._myself.get_name(), None):
            if self._total_players == 2:
                self._state = "END_GAME"
                return
            print("\n[SYSTEM] You lost! Enjoy spectating the game!")
            self._total_players -= 1
            self._am_spectator = True
            temp_dict = json.dumps({"Logger Name": "SPECTATE BEGIN", "Name": self._myself.get_name(
            ), "Logging Data": self.frame_count})
            self.logger.info(f"{temp_dict}")
            self._state = "AWAIT_KEYPRESS"

        # if no chairs left, end the game, else reset
        elif len(self._round_inputs.keys()) < 1:
            winner = list(self._players.keys())[0]
            print('[SYSTEM] No more seats left, game over.')
            print(
                f"\n--- {'Congrats! You have' if winner == self._myself.get_name() else winner + ' has'} won the game! ---\n")
            self._transportLayer.sendall(EndGame(self._myself))
            self._state = "END_GAME"

        else:
            # must wait for everyone to signal end round before moving on to next round
            self._total_players -= 1
            self._state = "AWAIT_KEYPRESS"

    def end_game(self):
        # terminate all connectionsidk
        self._transportLayer.shutdown()
        self.game_over = True

    def spectator(self):
        # for player who last lost game
        self._checkTransportLayerForIncomingData()


######### helper functions #########

    def _checkTransportLayerForIncomingData(self):
        """handle data being received from transport layer"""
        pkt: Packet = self._transportLayer.receive()
        temporary_logger_dict = json.dumps(
            {"Logger Name": "GAME PLAY LIST", "Round Number": self.round_number, "Logging Data": self._round_inputs})
        self.logger.info(f'{temporary_logger_dict}')

        if pkt:
            if pkt.get_packet_type() == "action":
                # keypress
                packet = pkt
                length = len(packet)
                rtt = time() - packet.get_created_at()
                throughput = length / rtt
                if packet.get_packet_type() == "action":
                    temporary_logger_dict = json.dumps({"Logger Name": "ACTION PACKET INFO-RECEIVE", "Length": length,
                                                       "Packet Type": packet.get_packet_type(), "Data": packet.get_data(), "RTT": rtt, "Throughput": throughput})
                    self.logger.info(f'{temporary_logger_dict}')
                if not self._state == "SPECTATOR":
                    self._receiving_seats(pkt)

            elif pkt.get_packet_type() == "ss_nak":
                # drop the nak/ack if we've moved on
                if self._is_selecting_seat:
                    self._nak_count += 1

            elif pkt.get_packet_type() == "ss_ack":
                # drop the nak/ack if we've moved on
                if self._is_selecting_seat:
                    self._ack_count += 1

            elif pkt.get_packet_type() == "peering_completed" and not self._round_started:
                print(
                    f"[Peering Completed] {pkt.get_player().get_name()}")

            elif pkt.get_packet_type() == "ready_to_start" and not self._round_started:
                player_name = pkt.get_player().get_name()
                self._round_ready[player_name] = True
                self._players[player_name] = Player(player_name)
                print(f"[Ready to Start]{player_name}")

            elif pkt.get_packet_type() == "ack_start" and not self._round_started:
                player_name = pkt.get_player().get_name()
                self._round_ackstart[player_name] = True
                print(f"[Vote to Start] {player_name}")

            elif pkt.get_packet_type() == "ack":
                player_name = pkt.get_player().get_name()
                self._ack_count += 1
                # print(f"[ACK from] {player_name}")

            elif pkt.get_packet_type() == "nak":
                player_name = pkt.get_player().get_name()
                self._nak_count += 1
                # print(f"[NAK from] {player_name}")

            elif pkt.get_packet_type() == "sat_down":
                player_name = pkt.get_player().get_name()
                seat = pkt.get_data()
                self._sat_down_count += 1
                self.lock.acquire()
                self._round_inputs[seat] = player_name
                self.lock.release()
                print(f"[ACTION] {player_name} has sat down!")
                print(f"[SEATS] {self._round_inputs}")

            elif pkt.get_packet_type() == "vote":
                player_to_kick = pkt.get_data()
                print(f"[SYSTEM] Received vote to kick {player_to_kick}")
                if player_to_kick in self._votekick:
                    self._votekick[player_to_kick] += 1
                else:
                    self._votekick[player_to_kick] = 1

                # print(f"{self._votekick}")

            elif pkt.get_packet_type() == "update_master":
                player = pkt.get_player()
                new_master_name = pkt.get_data()
                if self._frameSync.get_master() is None or player.get_name() == self._frameSync.get_master().get_name():
                    print(f"[FRAME_SYNC] Updating master to {new_master_name}")
                    self._frameSync.update_master(
                        Player(new_master_name), player)
                    print(
                        f"[FRAME_SYNC] Master is now {self._frameSync.get_master().get_name()}")

            elif pkt.get_packet_type() == "acquire_master":
                playerRequestingForMaster = pkt.get_player()
                print(
                    f"[FRAME_SYNC] {playerRequestingForMaster} requested to acquire master")
                self._frameSync.if_master_emit_new_master(
                    playerRequestingForMaster)
                self._frameSync.update_master(
                    playerRequestingForMaster, self._myself)
                print(
                    f"[FRAME_SYNC] Master is now {self._frameSync.get_master().get_name()}")

            elif pkt.get_packet_type() == "frame_sync":
                frame = pkt.get_data()
                player = pkt.get_player()
                self._frameSync.update_frame(player.get_name(), frame)
                if self._frameSync.get_master():
                    if self._frameSync.get_master().get_name() == player.get_name():
                        if self.frame_count > frame + self.frame_delta_threshold:
                            print(
                                f"[FRAME_SYNC] Slowing down since I'm ahead by {self.frame_count - frame} frames")
                            temporary_logger_dict = json.dumps(
                                {"Logger Name": "FRAME SLOWING-BEFORE", "Frame Count": self.frame_count, "Player Name": self._myself.get_name(), "Time": time()})
                            self.logger.info(f'{temporary_logger_dict}')

                            sleep(self.loop_interval *
                                  (self.frame_count - frame)*self.alpha)
                            temporary_logger_dict = json.dumps(
                                {"Logger Name": "FRAME SLOWING-AFTER", "Frame Count": self.frame_count, "Player Name": self._myself.get_name(), "Time": time()})
                            self.logger.info(f'{temporary_logger_dict}')
                            # print(f"[FRAME_SYNC] Slowing down since I'm ahead")
                        elif frame > self.frame_count:
                            print(
                                f"[FRAME_SYNC] Requesting to be master since I'm behind by {self.frame_count - frame} frames")
                            self._frameSync.acquire_master()

            elif pkt.get_packet_type() == "end_game":
                winner = pkt.get_player()
                if self._state == "SPECTATOR":
                    print(
                        f"\n ---- [GAME ENDED] {winner} has won the game! ----")
                    self._state = "END_GAME"

            elif pkt.get_packet_type() == "sync_req":
                rcv_time = time()
                # print("rcv time: {}".format(rcv_time))
                leader_id = pkt.get_player().get_name()
                print(f"[SYNCING WITH LEADER] {leader_id}")
                delay_from_leader = float(
                    rcv_time) - float(pkt.get_created_at())
                # print("delay from leader {}".format(delay_from_leader))

                sync_ack_pkt = SyncAck(
                    delay_from_leader, self._myself, self.round_number)
                self._transportLayer.send(
                    packet=sync_ack_pkt, player_id=leader_id)

            elif pkt.get_packet_type() == "sync_ack":
                rcv_time = time()
                self._transportLayer.sync.update_delay_dict(pkt)

                print(self._transportLayer.sync._delay_dict)

                peer_id = pkt.get_player().get_name()
                self._transportLayer.sync_req_timers[peer_id].cancel()

                delay_from_peer = float(rcv_time) - float(pkt.get_created_at())

                peer_sync_ack_pkt = PeerSyncAck(
                    delay_from_peer, self._myself, self.round_number)
                self._transportLayer.send(
                    packet=peer_sync_ack_pkt, player_id=peer_id)

            elif pkt.get_packet_type() == "peer_sync_ack":
                self._transportLayer.sync.update_delay_dict(pkt)

            elif pkt.get_packet_type() == "update_leader":
                self._transportLayer.sync.next_leader()
                if self._transportLayer.sync.no_more_leader():
                    # print(self._transportLayer.sync._delay_dict)
                    self._transportLayer.is_sync_completed = True

    def _all_voted_to_start(self):
        return len(self._round_ackstart.keys()) >= len(self._round_inputs)

    def _selecting_seats(self):
        self._is_selecting_seat = True
        pkt = Action(self._my_keypress, self._myself)
        self._my_keypress_time = pkt.get_created_at()
        temporary_logger_dict = json.dumps(
            {"Logger Name": "KEYPRESS TIME", "Seat Selected": self._my_keypress, "Time": time()})
        self.logger.info(f'{temporary_logger_dict}')
        self._transportLayer.sendall(pkt)

    def _send_ack(self, player: Player):
        self._transportLayer.send(Ack(self._myself), player.get_name())

    def _send_nak(self, player: Player):
        self._transportLayer.send(Nak(self._myself), player.get_name())

    def _next(self):
        self._state = self.trigger_handler(self._state)
        return self._state

    def _insert_input(self, keypress):
        self._my_keypress = keypress
        print(f"[ACTION] I HAVE PRESSED {keypress}")
        keyboard.remove_all_hotkeys()

    def _receiving_seats(self, action: Packet):
        seat = action.get_data()
        player = action.get_player()
        created_at = action.get_created_at()
        if seat:
            # print(f"[ACTION] Received seat: {seat} from {player}")
            self.lock.acquire()
            if self._round_inputs[seat] is not None:
                self._send_nak(player)
                self.lock.release()
                return
            if len(self._round_inputs) == 1:
                # final round break deadlock
                if self._my_keypress_time is not None:
                    if created_at >= self._my_keypress_time:
                        # if their kp timing >= mine,
                        self._send_nak(player)
                        self._my_keypress_time = None  # reset
                        self.lock.release()
                        return
            self._send_ack(player)
            self._round_inputs[seat] = player.get_name()
            self.lock.release()
            return

    def _reset_round(self):
        self.round_number += 1
        self._round_ready = {}
        self._round_started = False

        # reset round inputs, num chairs - 1
        d = self._round_inputs
        d = {key: None for key in d}
        if not self._vote_tied:
            print("[SYSTEM] Reducing number of chairs...")
            d.popitem()

        self._round_inputs = d

        self._my_keypress = None
        self._nak_count = 0
        self._ack_count = 0
        self._is_selecting_seat = False
        self.hotkeys_added = False
        self._sat_down_count = 0
        self._votekick = {}
        self._done_voting = False

        self._vote_tied = False
        self.init_send_time = None
        self.init_ack_start = None
