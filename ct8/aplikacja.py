from flask import Flask, render_template

app = Flask(__name__)

import psutil
import sqlite3
import subprocess
from threading import Thread, Event

DB_CON = sqlite3.connect("./wordgame.db")
DB_CUR = DB_CON.cursor()


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
t_keepalive = KeepAliveHandler(
    e_stop_keepalive, f_keepalive, "sysop-srv", "./start.sh", 0.5
)
t_keepalive.start()


@app.route("/")
def hello():
    return "Hello World!"


@app.route("/games")
def games():
    DB_CUR.execute("SELECT * FROM games")
    data = DB_CUR.fetchall()

    dicts = []
    for entry in data:
        new_dict = {}
        new_dict["timestamp"] = entry[1]
        new_dict["gid"] = entry[2]
        new_dict["pid"] = entry[3]
        new_dict["message"] = entry[4]
        dicts.append(new_dict)

    return render_template("games.html", games=dicts)


@app.route("/game/<gameid>")
def game(gameid):
    DB_CUR.execute("SELECT * FROM games WHERE gid = ?", [gameid])
    data = DB_CUR.fetchall()

    games = []
    for entry in data:
        new_dict = {}
        new_dict["timestamp"] = entry[1]
        new_dict["gid"] = entry[2]
        new_dict["pid"] = entry[3]
        new_dict["message"] = entry[4]
        games.append(new_dict)

    DB_CUR.execute("SELECT pid,points FROM players WHERE gid = ?", [gameid])
    data = DB_CUR.fetchall()

    players = []
    for entry in data:
        new_dict = {}
        new_dict["pid"] = entry[0]
        new_dict["points"] = entry[1]
        players.append(new_dict)

    return render_template("game.html", gid=gameid, games=games, players=players)


# @app.route("/players")
# def players():
#     DB_CUR.execute("SELECT * FROM players")
#     data = DB_CUR.fetchall()

#     dicts = []
#     for entry in data:
#         new_dict = {}
#         new_dict["timestamp"] = entry[1]
#         new_dict["gid"] = entry[2]
#         new_dict["pid"] = entry[3]
#         new_dict["message"] = entry[4]
#         dicts.append(new_dict)

#     return render_template("players.html", players=dicts)


# @app.route("/player/<playerid>")
# def player(playerid):
#     DB_CUR.execute("SELECT * FROM players WHERE gid = ?", [playerid])
#     data = DB_CUR.fetchall()

#     dicts = []
#     for entry in data:
#         new_dict = {}
#         new_dict["timestamp"] = entry[1]
#         new_dict["gid"] = entry[2]
#         new_dict["pid"] = entry[3]
#         new_dict["message"] = entry[4]
#         dicts.append(new_dict)

#     return render_template("player.html", gid=playerid, players=dicts)


@app.route("/is_running")
def is_running():
    if checkIfProcessRunning("sysop-srv"):
        return "running"
    else:
        return "not running"


if __name__ == "__main__":
    app.run()
