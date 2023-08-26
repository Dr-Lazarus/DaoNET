import json
from game.models.action import Action
from game.models.player import Player


# class Utils:
#     def transformPacketToAction(self, data: Packet) -> Action:
#         data = json.loads(data)
#         return Action(data.get("data"), Player(data.get("player").get("id")))
