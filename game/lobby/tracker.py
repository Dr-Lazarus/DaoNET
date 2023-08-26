class Tracker():
    def __init__(self, tracker_list={}):
        self.tracker_list = tracker_list
        self.leader_list = []
        if tracker_list != {}:
            for player_id, value in tracker_list.items():
                self.leader_list.append(player_id)


    def get_tracker_list(self):
        return self.tracker_list

    def get_leader_list(self):
        return self.leader_list

    def add(self, player_id, ip_address, port):
        # save port number
        # print(f"I am adding here:{player_id}")
        self.tracker_list[player_id] = (ip_address, port)
        self.leader_list.append(player_id)

    def remove(self, player_id):
        # remove player from tracker
        self.tracker_list.pop(player_id)
        self.leader_list.remove(player_id)

    def get_ip_port(self, player_id):
        # return port number
        return self.tracker_list.get(player_id, (None, None))

    def is_ip_port_used(self, ip, port):
        return (ip, port) in [pair for pair in self.tracker_list.values()]

    def get_players(self):
        # return list of players
        return list(self.tracker_list.keys())

    def get_player_count(self):
        # return number of players
        return len(self.tracker_list)

    def __str__(self):
        return f"Current players: {str(list(self.tracker_list.keys()))}"
