from threading import Thread, Event

class QueueHandler(Thread):
    def __init__(self, event, function, int_time):
        Thread.__init__(self)
        self.stop_ev = event
        self.func = function
        self.t = int_time

    def run(self):
        while not self.stop_ev.wait(self.t):
            self.func()

class GameHandler(Thread):
    def __init__(self, event, function, game_dict, int_time):
        Thread.__init__(self)
        self.stop_ev = event
        self.func = function
        self.t = int_time

    def run(self):
        while not self.stop_ev.wait(self.t):
            self.func()