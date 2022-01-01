class Game:
    def __init__(self, gid):
        self.gid = gid
        self.players = {}
        self.word = None
        self.ended = False


class Player:
    def __init__(self, uid, address):
        self.uid = uid
        self.address = address
        self.queued = False
        self.ingame = False
        self.points = 0
        self.guesses = []


class GameLog:
    def __init__(self, timestamp, gid, message, pid=None):
        self.timestamp = timestamp
        self.gid = gid
        self.pid = pid
        self.message = message


class PlayerLog:
    def __init__(self, timestamp, gid, pid, points, attempts, result):
        self.timestamp = timestamp
        self.gid = gid
        self.pid = pid
        self.points = points
        self.attempts = attempts
        self.result = result


class QueueLog:
    def __init__(self, action, pid=None, gid=None):
        self.action = action
        self.pid = pid
        self.gid = gid
