import os
import re
import sys
import time
import mmap
import pytz
import socket
import select
import sqlite3
import secrets
import hashlib
import threading
import configparser
from datetime import datetime, timedelta

from handlers import *
from data_classes import *

START_TIME = time.time()
timezone = pytz.timezone("UTC")

# ========================= #
#  Funkcja tworzenia logów  #
# ========================= #
def system_log(prefix, message):
    color_codes = {
        "ERR": "\u001b[31;1m",
        "INIT": "\u001b[32;1m",
        "INFO": "\u001b[33;1m",
        "GAME": "\u001b[34;1m",
        "QUEUE": "\u001b[36;1m",
        "reset": "\u001b[0m",
    }
    timestamp = time.time() - START_TIME
    m, s = divmod(timestamp, 60)
    h, m = divmod(m, 60)
    cprefix = f"{color_codes[prefix]}{prefix}{color_codes['reset']}"
    print(f"[{h:.0f}:{m:02.0f}:{s:02.4f}][{cprefix}] {message}")


# ======================== #
#  Init stałych roboczych  #
# ======================== #
system_log("INIT", "Starting SERVER...")

CONF_FILE = "config.ini"
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
    "i": "3",
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
except configparser.ParsingError:
    system_log("ERR", "Failed to parse configuration file, check integrity")
    sys.exit(3)

# ============================= #
#  Wczytanie stałych z configa  #
# ============================= #
try:
    DICT_FILE = str(config["APP"]["DICT_FILE"])
    DB_FILE = str(config["APP"]["DB_FILE"])

    IP = str(config["CONNECTION"]["IP"])
    PORT = int(config["CONNECTION"]["PORT"])
    LOGIN_TIMEOUT = int(config["CONNECTION"]["LOGIN_TIMEOUT"])

    MAX_PLAYERS = int(config["GAME"]["MAX_PLAYERS"])
    MIN_PLAYERS = int(config["GAME"]["MIN_PLAYERS"])
    QUEUE_TIMEOUT = int(config["GAME"]["QUEUE_TIMEOUT"])
    WORD_TIMEOUT = int(config["GAME"]["WORD_TIMEOUT"])
    GUESS_MISS_TIMEOUT = int(config["GAME"]["GUESS_MISS_TIMEOUT"])
    GUESS_KICK_TIMEOUT = int(config["GAME"]["GUESS_KICK_TIMEOUT"])
    MAX_GUESS_COUNT = int(config["GAME"]["MAX_GUESS_COUNT"])

    QUEUE_THREAD_TIME = float(config["TIMING"]["QUEUE_THREAD_TIME"])
    LOGGER_THREAD_TIME = float(config["TIMING"]["LOGGER_THREAD_TIME"])
    SELECT_TIMEOUT = float(config["TIMING"]["SELECT_TIMEOUT"])

    FORCE_WORD = config["CHEATS"]["FORCE_WORD"] == "True"
    FORCED_WORD_NUMBER = int(config["CHEATS"]["FORCED_WORD_NUMBER"])

except KeyError:
    system_log("ERR", "Failed to load values from configuration file, check integrity")
    sys.exit(3)

system_log("INIT", "Finished loading configuration from file")

# =============== #
#  Init słownika  #
# =============== #
try:
    open(os.path.join(ROOT_DIR, DICT_FILE))
except FileNotFoundError:
    system_log("ERR", f"Failed to access WORD_SET, file '{DICT_FILE}' is missing")
    sys.exit(1)

system_log("INIT", f"Using WORD_SET from file '{DICT_FILE}'")


# ================== #
#  Init bazy danych  #
# ================== #
system_log("INIT", "Starting database connection...")
DB_CON = sqlite3.connect(os.path.join(ROOT_DIR, DB_FILE))
DB_CUR = DB_CON.cursor()
system_log("INIT", f"Connected to database file '{DB_FILE}'")


# ================== #
#  Init socketa TCP  #
# ================== #
system_log("INIT", "Initiating listen socket...")
SRV_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
SRV_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
SRV_SOCKET.bind((IP, PORT))
SRV_SOCKET.listen()
system_log("INIT", f"Listening for connections on {IP}:{PORT}")


# ========================== #
#  Init zmiennych roboczych  #
# ========================== #
sockets_list = [SRV_SOCKET]
clients = {}
game_queue = []
sockets_to_purge = []
messages_to_log = []

messages_to_log.append(QueueLog("purge"))

# ================ #
#  Funkcje wątków  #
# ================ #
def f_queue():
    for socket in sockets_to_purge:
        for game in game_queue:
            if socket in game.players.keys():
                system_log("ERR", f"Purging {game.players[socket].uid}")
                messages_to_log.append(QueueLog("rem", client.uid))
                del game.players[socket]
                sockets_to_purge.remove(socket)

    for socket, client in clients.items():
        if not client.queued:
            if len(game_queue) == 0:
                new_game = Game(int(time.time()))
                game_queue.append(new_game)
                system_log("INFO", f"Created New Game with ID: {new_game.gid}")

            last_game = game_queue[-1]

            if len(last_game.players.keys()) == MAX_PLAYERS:
                new_game = Game(int(time.time()))
                game_queue.append(new_game)
                system_log("INFO", f"Created New Game with ID: {new_game.gid}")
                last_game = new_game

            last_game.players[socket] = client
            system_log(
                "INFO",
                f"Added player (id: {client.uid}) to queued game (id: {last_game.gid})",
            )
            messages_to_log.append(QueueLog("add", client.uid, last_game.gid))
            client.queued = True

    for game in game_queue:
        time_passed = int(time.time() - game.gid)

        to_purge = []
        for player in game.players.keys():
            rs, _, _ = select.select([player], [], [], 0.01)

            try:
                if rs and not len(player.recv(1024)):
                    to_purge.append(player)
            except:
                to_purge.append(player)

        for player in to_purge:
            system_log(
                "INFO",
                f"Closed connection from: {game.players[player].uid}",
            )
            player.close()
            messages_to_log.append(QueueLog("rem", game.players[player].uid))
            sockets_to_purge.append(player)
            del game.players[player]
            del clients[player]

        if len(game.players.keys()) == MAX_PLAYERS:
            for player in game.players.keys():
                messages_to_log.append(QueueLog("rem", game.players[player].uid))
            start_game(game)

        elif time_passed >= QUEUE_TIMEOUT and len(game.players.keys()) >= MIN_PLAYERS:
            for player in game.players.keys():
                messages_to_log.append(QueueLog("rem", game.players[player].uid))
            start_game(game)


def f_logger():
    con = sqlite3.connect(os.path.join(ROOT_DIR, DB_FILE))
    cur = con.cursor()

    messages_to_purge = []

    for message in messages_to_log:
        if isinstance(message, GameLog):
            cur.execute(
                "INSERT INTO games(timestamp, gid, pid, message) VALUES (?, ?, ?, ?)",
                (
                    message.timestamp,
                    message.gid,
                    message.pid,
                    message.message,
                ),
            )
            con.commit()
            messages_to_purge.append(message)
            pass

        elif isinstance(message, PlayerLog):
            cur.execute(
                "INSERT INTO players(timestamp, gid, pid, points, attempts, result) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    message.timestamp,
                    message.gid,
                    message.pid,
                    message.points,
                    message.attempts,
                    message.result,
                ),
            )
            con.commit()
            messages_to_purge.append(message)
            pass

        elif isinstance(message, QueueLog):
            if message.action == "purge":
                cur.execute("DELETE FROM queue")
                con.commit()
                system_log(
                    "QUEUE",
                    f"Purged the queue",
                )
            elif message.action == "add":
                cur.execute(
                    "INSERT INTO queue (gid, pid) VALUES (?, ?)",
                    (message.gid, message.pid),
                )
                con.commit()
                system_log(
                    "QUEUE",
                    f"Added Player {message.pid} to the queue",
                )
            elif message.action == "rem":
                cur.execute(
                    "DELETE FROM queue WHERE pid = ?",
                    [message.pid],
                )
                con.commit()
                system_log(
                    "QUEUE",
                    f"Removed Player {message.pid} from the queue",
                )
            messages_to_purge.append(message)
            pass

        else:
            messages_to_purge.append(message)
            pass

    for message in messages_to_purge:
        messages_to_log.remove(message)

    con.close()


def f_login(client_socket, client_address):
    system_log(
        "INFO",
        f"Connection attempt from {client_address[0]}:{client_address[1]}...",
    )

    try:
        login_data = rcv_login(client_socket)

        if not login_data:
            system_log(
                "INFO",
                f"Connection from {client_address[0]}:{client_address[1]} failed! \u001b[31mReason: LOGIN_ERROR\u001b[0m",
            )
            client_socket.send("-\n".encode("utf-8"))
            client_socket.close()
            return None

        id_num = login_data[0]

        passwd = login_data[1]

        if is_duped(id_num):
            system_log(
                "INFO",
                f"Connection from {client_address[0]}:{client_address[1]} failed! \u001b[31mReason: DUPLICATE_LOGIN\u001b[0m",
            )
            client_socket.send("-\n".encode("utf-8"))
            client_socket.close()
            return None

        if not auth_user(id_num, passwd):
            system_log(
                "INFO",
                f"Connection from {client_address[0]}:{client_address[1]} failed! \u001b[31mReason: BAD_AUTH\u001b[0m",
            )
            client_socket.send("-\n".encode("utf-8"))
            client_socket.close()
            return None

        user = Player(id_num, client_address)
    except Exception:
        system_log(
            "INFO",
            f"Connection from {client_address[0]}:{client_address[1]} failed! \u001b[31mReason: UNHANDLED_EXCEPTION\u001b[0m",
        )
        return None

    system_log(
        "INFO",
        f"Connection from {client_address[0]}:{client_address[1]} successful! Client id: {user.uid}",
    )

    client_socket.send("+2\n".encode("utf-8"))

    clients[client_socket] = user


def f_game(gd):
    gd.ended = False
    gd.word = None
    for player in gd.players.values():
        player.ingame = True

    messages_to_log.append(
        GameLog(
            time.time(),
            gd.gid,
            f"Game (id: {gd.gid}) started with {len(gd.players.values())} players",
        )
    )

    word = get_random_word()
    system_log("GAME", f"Word chosen as {word}")
    messages_to_log.append(GameLog(time.time(), gd.gid, f"Word chosen as: {word}"))
    gd.word = word
    num_str = let_to_num(word)
    system_log("GAME", f"Broadcasting number-string {num_str} to players")
    messages_to_log.append(
        GameLog(time.time(), gd.gid, f"Numerical Hint is: {num_str}")
    )
    for socket in gd.players.keys():
        socket.send((let_to_num(word) + "\n").encode("utf-8"))

    psocket = []
    for socket, player in gd.players.items():
        t_player = PlayerInGameHandler(f_player, gd, socket)
        psocket.append(socket)
        t_player.start()

    while not gd.ended:
        just_end = True
        for socket in psocket:
            if socket.fileno() != -1:
                just_end = False

        if just_end:
            break

    if gd.ended:
        system_log(
            "GAME",
            f"Game ended (id: {gd.gid}) with a correct guess",
        )
        messages_to_log.append(
            GameLog(time.time(), gd.gid, "Game ended with a correct guess")
        )
    else:
        system_log(
            "GAME",
            f"Game ended (id: {gd.gid}) with no correct guess",
        )
        messages_to_log.append(
            GameLog(time.time(), gd.gid, "Game ended with no correct guess")
        )


def f_player(gd, sock):
    try_ctr = 0

    while try_ctr < MAX_GUESS_COUNT:
        if gd.ended:
            break

        try_ctr += 1

        try:
            res = rcv_guess(sock)

            if res == "kick":
                system_log(
                    "GAME",
                    f"No reply from {gd.players[sock].uid} in allotted time... Kicking...",
                )
                messages_to_log.append(
                    GameLog(
                        time.time(),
                        gd.gid,
                        f"Player {gd.players[sock].uid} timed out - kicked",
                        gd.players[sock].uid,
                    )
                )
                system_log(
                    "GAME",
                    f"Player {gd.players[sock].uid} achieved a total of {gd.players[sock].points} points!",
                )
                messages_to_log.append(
                    PlayerLog(
                        time.time(),
                        gd.gid,
                        gd.players[sock].uid,
                        gd.players[sock].points,
                        try_ctr,
                        "Timed out",
                    )
                )
                try:
                    sock.send("?\n".encode("utf-8"))
                finally:
                    sock.close()
                    sockets_to_purge.append(sock)
                    del gd.players[sock]
                    del clients[sock]
                    return None

            elif res == "miss":
                system_log(
                    "GAME",
                    f"Reply from {gd.players[sock].uid} took too long... Ignoring...",
                )
                messages_to_log.append(
                    GameLog(
                        time.time(),
                        gd.gid,
                        f"Player {gd.players[sock].uid} guessed too late - ignored",
                        gd.players[sock].uid,
                    )
                )
                try:
                    sock.send("#\n".encode("utf-8"))
                finally:
                    continue

            elif isinstance(res, list):
                cmd = res[0]
                guess = res[1]
                if cmd == "=":
                    if guess == gd.word:
                        gd.ended = True
                        gd.players[sock].points += 5
                        system_log(
                            "GAME",
                            f"Player {gd.players[sock].uid} guessed the word ({guess})!",
                        )
                        messages_to_log.append(
                            GameLog(
                                time.time(),
                                gd.gid,
                                f"Player {gd.players[sock].uid} guessed the word ({guess}) [+5 points]",
                                gd.players[sock].uid,
                            )
                        )
                        system_log(
                            "GAME",
                            f"Player {gd.players[sock].uid} achieved a total of {gd.players[sock].points} points!",
                        )
                        messages_to_log.append(
                            PlayerLog(
                                time.time(),
                                gd.gid,
                                gd.players[sock].uid,
                                gd.players[sock].points,
                                try_ctr,
                                "Guessed the word",
                            )
                        )
                        try:
                            reply_string = f"=\n{gd.players[sock].points}\n?\n"
                            sock.send(reply_string.encode("utf-8"))
                        finally:
                            sock.close()
                            sockets_to_purge.append(sock)
                            del gd.players[sock]
                            del clients[sock]
                            return None

                    else:
                        sock.send("!\n".encode("utf-8"))
                        continue

                elif cmd == "+":
                    if len(guess) == 1:
                        if not guess in gd.players[sock].guesses:
                            hit_count = gd.word.count(guess)
                            gd.players[sock].guesses.append(guess)

                            if hit_count == 0:
                                system_log(
                                    "GAME",
                                    f"Player {gd.players[sock].uid} did not guess a letter ({guess})!",
                                )
                                try:
                                    sock.send("!\n".encode("utf-8"))
                                finally:
                                    continue

                            else:
                                gd.players[sock].points += hit_count
                                system_log(
                                    "GAME",
                                    f"Player {gd.players[sock].uid} guessed a letter ({guess})!",
                                )
                                messages_to_log.append(
                                    GameLog(
                                        time.time(),
                                        gd.gid,
                                        f"Player {gd.players[sock].uid} guessed a letter ({guess}) [+{hit_count} points]",
                                        gd.players[sock].uid,
                                    )
                                )
                                try:
                                    reply_string = f"=\n{pos_in_word(gd.word, guess)}\n"
                                    sock.send(reply_string.encode("utf-8"))
                                finally:
                                    continue
                        else:
                            system_log(
                                "GAME",
                                f"Player {gd.players[sock].uid} guessed the same letter ({guess}) again! Nope, won't work!",
                            )
                            messages_to_log.append(
                                GameLog(
                                    time.time(),
                                    gd.gid,
                                    f"Player {gd.players[sock].uid} guessed the same letter ({guess}) again! Nope, won't work!",
                                    gd.players[sock].uid,
                                )
                            )
                            try:
                                sock.send("!\n".encode("utf-8"))
                            finally:
                                continue

            system_log(
                "GAME",
                f"Player {gd.players[sock].uid} submitted a malformed guess! Kicking...",
            )
            messages_to_log.append(
                GameLog(
                    time.time(),
                    gd.gid,
                    f"Player {gd.players[sock].uid} submitted a malformed guess - kicked",
                    gd.players[sock].uid,
                )
            )
            system_log(
                "GAME",
                f"Player {gd.players[sock].uid} achieved a total of {gd.players[sock].points} points!",
            )
            messages_to_log.append(
                PlayerLog(
                    time.time(),
                    gd.gid,
                    gd.players[sock].uid,
                    gd.players[sock].points,
                    try_ctr,
                    "Malformed guess",
                )
            )
            try:
                sock.send("?\n".encode("utf-8"))
            finally:
                sock.close()
                sockets_to_purge.append(sock)
                del gd.players[sock]
                del clients[sock]
                return None

        except:
            system_log(
                "GAME",
                f"Player {gd.players[sock].uid} caused a connection exception! Kicking...",
            )
            messages_to_log.append(
                GameLog(
                    time.time(),
                    gd.gid,
                    f"Player {gd.players[sock].uid} caused a connection exception - kicked",
                    gd.players[sock].uid,
                )
            )
            system_log(
                "GAME",
                f"Player {gd.players[sock].uid} achieved a total of {gd.players[sock].points} points!",
            )
            messages_to_log.append(
                PlayerLog(
                    time.time(),
                    gd.gid,
                    gd.players[sock].uid,
                    gd.players[sock].points,
                    try_ctr,
                    "Connection Exception",
                )
            )
            try:
                sock.send("?\n".encode("utf-8"))
            finally:
                sock.close()
                sockets_to_purge.append(sock)
                del gd.players[sock]
                del clients[sock]
                return None

    if try_ctr == MAX_GUESS_COUNT:
        system_log(
            "GAME",
            f"Player {gd.players[sock].uid} ran out of guesses! Kicking...",
        )
        messages_to_log.append(
            PlayerLog(
                time.time(),
                gd.gid,
                gd.players[sock].uid,
                gd.players[sock].points,
                try_ctr,
                "Ran out of guesses",
            )
        )
        try:
            sock.send("?\n".encode("utf-8"))
        except:
            pass

    else:
        system_log(
            "GAME",
            f"Player {gd.players[sock].uid} ran out of time, someone else guessed! Kicking...",
        )
        messages_to_log.append(
            PlayerLog(
                time.time(),
                gd.gid,
                gd.players[sock].uid,
                gd.players[sock].points,
                try_ctr,
                "Someone else guessed",
            )
        )
        try:
            reply_string = f"=\n{gd.players[sock].points}\n?\n"
            sock.send(reply_string.encode("utf-8"))
        except:
            pass

    system_log(
        "GAME",
        f"Player {gd.players[sock].uid} achieved a total of {gd.players[sock].points} points!",
    )
    sock.close()
    sockets_to_purge.append(sock)
    del gd.players[sock]
    del clients[sock]


# =============================== #
#  Funkcja rozpoczęcia sesji gry  #
# =============================== #
def start_game(game_info):
    system_log("GAME", f"Starting GAME (id: {game_info.gid})")
    t_game = GameHandler(f_game, game_info)
    t_game.start()

    game_queue.remove(game_info)


# ==================================== #
#  Funkcje pomocnicze do liter i słów  #
# ==================================== #
def let_to_num(word):
    letter_string = ""
    for letter in word.rstrip():
        letter_string += LETTER_DICT[letter]

    return letter_string


def pos_in_word(word, letter):
    pos_string = ""
    for let in word.rstrip():
        if let == letter:
            pos_string += "1"
        else:
            pos_string += "0"

    return pos_string


def check_in_wordset(word):
    with open(os.path.join(ROOT_DIR, DICT_FILE)) as wfile, mmap.mmap(
        wfile.fileno(), 0, access=mmap.ACCESS_READ
    ) as s:
        return s.find(word.encode("utf-8")) != -1


def get_random_word():
    with open(os.path.join(ROOT_DIR, DICT_FILE)) as wfile, mmap.mmap(
        wfile.fileno(), 0, access=mmap.ACCESS_READ
    ) as s:
        lines = 0
        while s.readline():
            lines += 1

        rline = secrets.randbelow(lines)

        if FORCE_WORD:
            rline = FORCED_WORD_NUMBER

        s.seek(0)
        lines = 0
        while lines < rline:
            s.readline()
            lines += 1

        return s.readline().decode().rstrip()


# ==================== #
#  Funkcje dołączania  #
# ==================== #
def handle_login(client_socket, client_address):
    t_login = LoginHandler(f_login, client_socket, client_address)
    t_login.start()


def is_duped(num):
    for user in clients.values():
        if num == user.uid:
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
#  Funkcje odbioru danych  #
# ======================== #
def rcv_msg(client_socket):
    try:
        msg = client_socket.recv(1024)

        if not len(msg):
            return False

        return msg.decode("utf-8")

    except:
        return False


def rcv_login(cli_sock):
    not_done = True
    rcv_str = ""
    start_time = time.time()

    while not_done:
        rs, _, _ = select.select([cli_sock], [], [], SELECT_TIMEOUT)

        for sock in rs:
            try:
                msg = sock.recv(1024)

                if not len(msg):
                    return False

                msg = msg.decode("utf-8").replace("\0", "\n")

                rcv_str += msg

            except:
                return False

        match = re.search(r".+\n.+\n", rcv_str)

        if match != None:
            if not rcv_str == match.group():
                return False
            lt = match.group().rstrip().split("\n")
            not_done = False
            return lt

        if time.time() - start_time > LOGIN_TIMEOUT:
            return False

    return False


def rcv_guess(cli_sock):
    not_done = True
    rcv_str = ""
    start_time = time.time()

    while not_done:
        rs, _, _ = select.select([cli_sock], [], [], SELECT_TIMEOUT)

        for sock in rs:
            try:
                msg = sock.recv(1024)

                if not len(msg):
                    return "malf"

                msg = msg.decode("utf-8").replace("\0", "\n")

                rcv_str += msg

            except:
                return "malf"

        match = re.search(r"[+=]\n.+\n", rcv_str)

        if match != None:
            if not rcv_str == match.group():
                return "malf"
            lt = match.group().rstrip().split("\n")
            if time.time() - start_time > GUESS_MISS_TIMEOUT:
                return "miss"
            not_done = False
            return lt

        if time.time() - start_time > GUESS_KICK_TIMEOUT:
            return "kick"

    return "malf"


# ========================== #
#  Definicje i start wątków  #
# ========================== #
system_log("INIT", "Starting QueueHandler thread...")
e_stop_queue = threading.Event()
t_queue = QueueHandler(e_stop_queue, f_queue, QUEUE_THREAD_TIME)
t_queue.start()
system_log("INIT", "Started QueueHandler")

system_log("INIT", "Starting LoggerHandler thread...")
e_stop_logger = threading.Event()
t_logger = LoggerHandler(e_stop_logger, f_logger, LOGGER_THREAD_TIME)
t_logger.start()
system_log("INIT", "Started LoggerHandler")


# =========== #
#  Main Loop  #
# =========== #
system_log("INIT", "Successfully started SERVER\n")
while True:
    read_sockets, _, exception_sockets = select.select(
        sockets_list, [], sockets_list, SELECT_TIMEOUT
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
                    f"Closed connection from: {clients[notified_socket].uid}",
                )
                notified_socket.close()
                sockets_to_purge.append(notified_socket)
                sockets_list.remove(notified_socket)
                del clients[notified_socket]

            continue

    for notified_socket in exception_sockets:
        sockets_list.remove(notified_socket)
        del clients[notified_socket]
