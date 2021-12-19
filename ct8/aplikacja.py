from flask import Flask

app = Flask(__name__)

import psutil
import subprocess
from threading import Thread, Event


class KeepAliveHandler(Thread):
    def __init__(self, event, function, check_name, start_name, int_time):
        Thread.__init__(self, daemon=True)
        self.stop_ev = event
        self.func = function
        self.cn = check_name
        self.sn = start_name
        self.t = int_time

    def run(self):
        while not self.stop_ev.wait(self.t):
            self.func(self.cn, self.sn)


def checkIfProcessRunning(processName):
    """
    Check if there is any running process that contains the given name processName.
    """
    # Iterate over the all the running process
    p_list = []
    for proc in psutil.process_iter():
        try:
            # Check if process name contains the given name string.
            name = map(lambda x: x.lower(), proc.cmdline())
            if processName.lower() in name:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def f_keepalive(search, start):
    if not checkIfProcessRunning(search):
        subprocess.call(start, shell=True)


e_stop_keepalive = Event()
t_keepalive = KeepAliveHandler(e_stop_keepalive, f_keepalive, "sysop-srv", "./start.sh", 0.5)
t_keepalive.start()


@app.route("/")
def hello():
    return "Hello World!"


@app.route("/is_running")
def is_running():
    if checkIfProcessRunning("sysop-srv"):
        return "running"
    else:
        return "not running"


if __name__ == "__main__":
    app.run()
