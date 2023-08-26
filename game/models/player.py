import json
import uuid


class Player:
    def __init__(self, name: str, ):
        self.name = name
        self.id = str(uuid.uuid4())

    def get_name(self):
        return self.name

    def id(self):
        return self.id

    def dict(self):
        return dict(
            name=self.name,
            id=self.id
        )

    def __str__(self):
        return f"{self.name}"
