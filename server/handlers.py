import time
from threading import Thread, Event


class QueueHandler(Thread):
    def __init__(self, event, function, int_time):
        Thread.__init__(self, daemon=True)
        self.stop_ev = event
        self.func = function
        self.t = int_time

    def run(self):
        while not self.stop_ev.wait(self.t):
            self.func()


class LoginHandler(Thread):
    def __init__(self, func, sock, addr):
        Thread.__init__(self, daemon=True)
        self.func = func
        self.sock = sock
        self.addr = addr

    def run(self):
        self.func(self.sock, self.addr)


class GameHandler(Thread):
    def __init__(self, function, game_dict):
        Thread.__init__(self, daemon=True)
        self.func = function
        self.gd = game_dict

    def run(self):
        self.func(self.gd)


class PlayerInGameHandler(Thread):
    def __init__(self, function, game_dict, player_socket):
        Thread.__init__(self, daemon=True)
        self.func = function
        self.gd = game_dict
        self.sock = player_socket

    def run(self):
        self.func(self.gd, self.sock)
