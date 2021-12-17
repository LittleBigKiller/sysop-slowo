import os
import sys
import time
import socket
import select
import sqlite3
import hashlib
import threading
import configparser

from handlers import *

# ========================= #
#  Funkcja tworzenia logów  #
# ========================= #
def system_log(prefix, message):
    color_codes = {
        "ERR": "\u001b[31;1m",
        "INIT": "\u001b[32;1m",
        "INFO": "\u001b[33;1m",
        "reset": "\u001b[0m",
    }
    cprefix = f"{color_codes[prefix]}{prefix}{color_codes['reset']}"
    print(f"[{cprefix}] {message}")


# ======================== #
#  Init stałych roboczych  #
# ======================== #
system_log("INIT", "Starting SERVER...")

DICT_FILE = "slowa.txt"
CONF_FILE = "config.ini"
DB_FILE = "wordgame.db"
ROOT_DIR = os.path.dirname(__file__)
WORD_SET = set()
LETTER_DICT = {
    "a": "1",
    "ą": "2",
    "b": "3",
    "c": "1",
    "ć": "3",
    "d": "3",
    "e": "1",
    "ę": "2",
    "f": "4",
    "g": "2",
    "h": "3",
    "i": "0",
    "j": "2",
    "k": "3",
    "l": "3",
    "ł": "3",
    "m": "1",
    "n": "1",
    "ń": "3",
    "o": "1",
    "ó": "3",
    "p": "2",
    "q": "2",
    "r": "1",
    "s": "1",
    "ś": "3",
    "t": "3",
    "u": "1",
    "v": "1",
    "w": "1",
    "x": "1",
    "y": "2",
    "z": "1",
    "ź": "3",
    "ż": "3",
}

system_log("INIT", f"Loading WORD_SET from file '{DICT_FILE}'...")

# try:
#     with open(os.path.join(ROOT_DIR, DICT_FILE)) as wfile:
#         for line in wfile:
#             WORD_SET.add(line.rstrip())
# except FileNotFoundError:
#     system_log("ERR", f"Failed to load WORD_SET, file '{DICT_FILE}' is missing")
#     sys.exit(1)

system_log("INIT", f"Finished loading WORD_SET with {len(WORD_SET)} words")


# ==================== #
#  Init configparsera  #
# ==================== #
config = configparser.ConfigParser()

system_log("INIT", f"Loading config data from file '{CONF_FILE}'...")

try:
    with open(os.path.join(ROOT_DIR, CONF_FILE)) as cfile:
        config.read_file(cfile)
except IOError:
    system_log("ERR", f"Failed to load configuration, file '{CONF_FILE}' is missing")
    sys.exit(2)

# ============================= #
#  Wczytanie stałych z configa  #
# ============================= #
try:
    IP = str(config["CONNECTION"]["IP"])
    PORT = int(config["CONNECTION"]["PORT"])

    MAX_PLAYERS = int(config["GAME"]["MAX_PLAYERS"])
    MIN_PLAYERS = int(config["GAME"]["MIN_PLAYERS"])
    QUEUE_TIMEOUT = int(config["GAME"]["QUEUE_TIMEOUT"])
    WORD_TIMEOUT = int(config["GAME"]["WORD_TIMEOUT"])
    GUESS_MISS_TIMEOUT = int(config["GAME"]["GUESS_MISS_TIMEOUT"])
    GUESS_KICK_TIMEOUT = int(config["GAME"]["GUESS_KICK_TIMEOUT"])

    QUEUE_THREAD_TIME = float(config["TIMING"]["QUEUE_THREAD_TIME"])
    GAME_THREAD_TIME = float(config["TIMING"]["GAME_THREAD_TIME"])
    GAME_THREAD_TIME = float(config["TIMING"]["GAME_THREAD_TIME"])
except KeyError:
    system_log("ERR", "Failed to load values from configuration file, check integrity")
    sys.exit(2)

system_log("INIT", "Finished loading configuration from file")

# ================== #
#  Init bazy danych  #
# ================== #
system_log("INIT", "Starting database connection...")
DB_CON = sqlite3.connect(os.path.join(ROOT_DIR, DB_FILE))
DB_CUR = DB_CON.cursor()
# DB_CUR.execute("insert into users values (?, ?)", ('test00', hashlib.sha1("qq".encode("utf-8")).hexdigest()))
# DB_CON.commit()

# DB_CUR.execute("SELECT * FROM users")
# print(DB_CUR.fetchall())

# DB_CON.close()
system_log("INIT", f"Connected to database file '{DB_FILE}'")


# ================== #
#  Init socketa TCP  #
# ================== #
system_log("INIT", "Initiating listen socket...")
SRV_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
SRV_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
SRV_SOCKET.bind((IP, PORT))
SRV_SOCKET.listen()
SRV_SOCKET.setblocking(False)
system_log("INIT", f"Listening for connections on {IP}:{PORT}")


# ========================== #
#  Init zmiennych roboczych  #
# ========================== #
sockets_list = [SRV_SOCKET]
clients = {}
game_queue = []
sockets_to_purge = []
game_thread_list = []


# ================ #
#  Funkcje wątków  #
# ================ #
def f_queue():
    for socket in sockets_to_purge:
        for game in game_queue:
            if socket in game['players'].keys():
                del game['players'][socket]
                sockets_to_purge.remove(socket)

    for socket, client in clients.items():
        if not client['queued']:
            if len(game_queue) == 0:
                new_game = {"time_queued": int(time.time()), "players": {}}
                game_queue.append(new_game)
                system_log(
                    "INFO", f"Created New Game with ID: {new_game['time_queued']}"
                )

            if len(game_queue[-1]["players"].keys()) == MAX_PLAYERS:
                new_game = {"time_queued": int(time.time()), "players": {}}
                game_queue.append(new_game)
                system_log(
                    "INFO", f"Created New Game with ID: {new_game['time_queued']}"
                )

            last_game = game_queue[-1]
            game_queue[-1]["players"][client_socket] = client
            system_log(
                "INFO",
                f"Added player (id: {client['uid']}) to queued game (id: {last_game['time_queued']})",
            )
            client['queued'] = True
    
    for game in game_queue:
        # print(f"game {game['time_queued']}:")
        # for player in game['players'].values():
        #     print(f"player: {player['uid']}")
        # print('')

        time_passed = int(time.time()) - game["time_queued"]

        if len(game["players"].keys()) == MAX_PLAYERS:
            start_game(game)

        elif (
            time_passed >= QUEUE_TIMEOUT and len(game["players"].keys()) >= MIN_PLAYERS
        ):
            start_game(game)


def f_login(client_socket, client_address):
    system_log(
        "INFO",
        f"Connection attempt from {client_address[0]}:{client_address[1]}...",
    )

    try:
        id_num = client_socket.recv(1024)

        if not len(id_num):
            return None

        id_num = id_num.decode("utf-8").rstrip()

        passwd = client_socket.recv(1024)

        if not len(passwd):
            return None

        passwd = passwd.decode("utf-8").rstrip()

        if is_duped(id_num):
            system_log(
                "INFO",
                f"Connection from {client_address[0]}:{client_address[1]} failed: \u001b[31mDUPLICATE LOGIN\u001b[0m",
            )

            client_socket.send("-\n".encode("utf-8"))
            client_socket.close()

            return None

        if not auth_user(id_num, passwd):
            system_log(
                "INFO",
                f"Connection from {client_address[0]}:{client_address[1]} failed: \u001b[31mBAD AUTH\u001b[0m",
            )

            client_socket.send("-\n".encode("utf-8"))
            client_socket.close()

            return None

        user = {
            "uid": id_num,
            "address": client_address,
            "queued": False,
            "ingame": False,
        }
    except:
        return None

    system_log(
        "INFO",
        f"Connection from {client_address[0]}:{client_address[1]} successful (uid: {user['uid']})",
    )

    client_socket.send("+\n".encode("utf-8"))

    sockets_list.append(client_socket)
    clients[client_socket] = user


def f_game():
    print(f"Am Pomu")


# =============================== #
#  Funkcja rozpoczęcia sesji gry  #
# =============================== #
def start_game(game_info):
    system_log("INIT", f"Starting GAME (id: {game_info['time_queued']})")
    stop_game = threading.Event()
    test_game = GameHandler(stop_game, f_game, game_info, GAME_THREAD_TIME)
    game_thread_list.append({"event": stop_game, "thread": test_game})

    test_game.start()

    game_queue.remove(game_info)


# ================================ #
#  Funkcja rozbicia na kody liter  #
# ================================ #
def let_to_num(word):
    letter_string = ""
    for letter in word.rstrip():
        letter_string += LETTER_DICT[letter]

    letter_string += "\n"

    return letter_string


# ==================== #
#  Funkcje dołączania  #
# ==================== #
def handle_login(client_socket, client_address):
    t_login = ThreadHandler(f_login, client_socket, client_address)
    t_login.start()


def is_duped(num):
    for user in clients.values():
        if num == user["uid"]:
            return True
    return False


def auth_user(num, pas):
    con = sqlite3.connect(os.path.join(ROOT_DIR, DB_FILE))
    cur = con.cursor()
    phash = hashlib.sha1(pas.encode("utf-8")).hexdigest()
    cur.execute("SELECT * from users WHERE id_number = ? AND hash = ?", (num, phash))

    if len(cur.fetchall()):
        con.close()
        return True

    con.close()
    return False


# ======================== #
#  Funkcja odbioru danych  #
# ======================== #
def rcv_msg(client_socket):
    try:
        msg = client_socket.recv(1024)

        if not len(msg):
            return False

        return msg.decode("utf-8")

    except:
        return False


# ========================== #
#  Definicje i start wątków  #
# ========================== #
system_log("INIT", "Starting QueueHandler thread...")
e_stop_queue = threading.Event()
t_queue = QueueHandler(e_stop_queue, f_queue, QUEUE_THREAD_TIME)
t_queue.start()
system_log("INIT", "Started QueueHandler")


# =========== #
#  Main Loop  #
# =========== #
system_log("INIT", "Successfully started SERVER\n")
while True:
    read_sockets, _, exception_sockets = select.select(
        sockets_list, [], sockets_list, 0.5
    )

    for notified_socket in read_sockets:
        if notified_socket == SRV_SOCKET:
            client_socket, client_address = SRV_SOCKET.accept()

            handle_login(client_socket, client_address)

        else:
            msg = rcv_msg(notified_socket)

            if msg is False:
                system_log(
                    "INFO",
                    f"Closed connection from: {clients[notified_socket]['uid']}",
                )
                sockets_to_purge.append(notified_socket)
                sockets_list.remove(notified_socket)
                del clients[notified_socket]
                continue

            user = clients[notified_socket]

            print(f'Received message from {user["uid"]}: {repr(msg)}')

            if msg.rstrip() in WORD_SET:
                print(f"{msg.rstrip()} in wordset")

            else:
                print(f"{msg.rstrip()} not in wordset")

            print(let_to_num(msg.rstrip()))
            print("")

    for notified_socket in exception_sockets:
        sockets_list.remove(notified_socket)
        del clients[notified_socket]
