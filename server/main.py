import os
import sys
import time
import mmap
import socket
import select
import sqlite3
import hashlib
import threading
import configparser

from handlers import *
from data_classes import *

# ========================= #
#  Funkcja tworzenia logów  #
# ========================= #
def system_log(prefix, message):
    color_codes = {
        "ERR": "\u001b[31;1m",
        "INIT": "\u001b[32;1m",
        "INFO": "\u001b[33;1m",
        "GAME": "\u001b[34;1m",
        "reset": "\u001b[0m",
    }
    cprefix = f"{color_codes[prefix]}{prefix}{color_codes['reset']}"
    print(f"[{cprefix}] {message}")


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
    WORD_SET_IN_RAM = config["APP"]["WORD_SET_IN_RAM"] == "True"
    DICT_FILE = str(config["APP"]["DICT_FILE"])
    DB_FILE = str(config["APP"]["DB_FILE"])

    IP = str(config["CONNECTION"]["IP"])
    PORT = int(config["CONNECTION"]["PORT"])

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
except KeyError:
    system_log("ERR", "Failed to load values from configuration file, check integrity")
    sys.exit(3)

system_log("INIT", "Finished loading configuration from file")

# =============== #
#  Init słownika  #
# =============== #
if WORD_SET_IN_RAM:
    system_log("INIT", f"Loading WORD_SET from file '{DICT_FILE}'...")

    try:
        with open(os.path.join(ROOT_DIR, DICT_FILE)) as wfile:
            for line in wfile:
                WORD_SET.add(line.rstrip())
    except FileNotFoundError:
        system_log("ERR", f"Failed to load WORD_SET, file '{DICT_FILE}' is missing")
        sys.exit(1)

    # WORD_SET.add("długonoga")

    system_log("INIT", f"Finished loading WORD_SET with {len(WORD_SET)} words")
else:
    try:
        open(os.path.join(ROOT_DIR, DICT_FILE))
    except FileNotFoundError:
        system_log("ERR", f"Failed to access WORD_SET, file '{DICT_FILE}' is missing")
        sys.exit(1)

    system_log("INIT", f"Using WORD_SET from file insead of loading into RAM")


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

            if rs and not len(player.recv(1024)):
                to_purge.append(player)

        for player in to_purge:
            system_log(
                "INFO",
                f"Closed connection from: {game.players[player].uid}",
            )
            player.close()
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

    # if len(messages_to_log) > 0:
    #     print("MESSAGES TO LOG:")

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
            elif message.action == "add":
                cur.execute(
                    "INSERT INTO queue (gid, pid) VALUES (?, ?)",
                    (message.gid, message.pid),
                )
                con.commit()
            elif message.action == "rem":
                cur.execute(
                    "DELETE FROM queue WHERE pid = ?",
                    [message.pid],
                )
                con.commit()
            messages_to_purge.append(message)
            pass

        else:
            messages_to_purge.append(message)
            pass

    for message in messages_to_purge:
        messages_to_log.remove(message)

    # if len(messages_to_log) > 0:
    #     print("================")

    con.close()


def f_login(client_socket, client_address):
    system_log(
        "INFO",
        f"Connection attempt from {client_address[0]}:{client_address[1]}...",
    )

    try:
        id_num = client_socket.recv(1024)

        if not len(id_num):
            system_log(
                "INFO",
                f"Connection from {client_address[0]}:{client_address[1]} failed! \u001b[31mReason: CONNECTION_INTERRUPTED\u001b[0m",
            )
            return None

        id_num = id_num.decode("utf-8").rstrip()

        passwd = client_socket.recv(1024)

        if not len(passwd):
            system_log(
                "INFO",
                f"Connection from {client_address[0]}:{client_address[1]} failed! \u001b[31mReason: CONNECTION_INTERRUPTED\u001b[0m",
            )
            return None

        passwd = passwd.decode("utf-8").rstrip()

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
        # {
        #     "uid": id_num,
        #     "address": client_address,
        #     "queued": False,
        #     "ingame": False,
        #     "points": 0,
        #     "guesses": [],
        # }
    except:
        system_log(
            "INFO",
            f"Connection from {client_address[0]}:{client_address[1]} failed! \u001b[31mReason: UNHANDLED_EXCEPTION\u001b[0m",
        )
        return None

    system_log(
        "INFO",
        f"Connection from {client_address[0]}:{client_address[1]} successful (id: {user.uid})",
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

    while gd.word == None:
        if not len(gd.players.values()):
            break

        wordsmith = list(gd.players.keys())[0]
        system_log("GAME", f"Selecting {gd.players[wordsmith].uid} as wordsmith")
        messages_to_log.append(
            GameLog(
                time.time(),
                gd.gid,
                f"Player {gd.players[wordsmith].uid} chosen as wordsmith",
                gd.players[wordsmith].uid,
            )
        )

        wordsmith.send("@\n".encode("utf-8"))
        rs, _, _ = select.select([wordsmith], [], [], WORD_TIMEOUT)

        if not rs:
            system_log(
                "GAME", f"No reply from wordsmith in allotted time... Kicking..."
            )
            messages_to_log.append(
                GameLog(
                    time.time(),
                    gd.gid,
                    f"Wordsmith (player: {gd.players[wordsmith].uid}) timed out",
                    gd.players[wordsmith].uid,
                )
            )
            wordsmith.close()
            sockets_to_purge.append(wordsmith)
            del gd.players[wordsmith]
            del clients[wordsmith]
        else:
            word = wordsmith.recv(1024).decode("utf-8").rstrip()
            if not check_in_wordset(word):
                system_log(
                    "GAME", f"Reply from wordsmith is not a valid word... Kicking..."
                )
                messages_to_log.append(
                    GameLog(
                        time.time(),
                        gd.gid,
                        f"Wordsmith (player: {gd.players[wordsmith].uid}) sent an invalid word: {repr(word)}",
                        gd.players[wordsmith].uid,
                    )
                )
                wordsmith.close()
                sockets_to_purge.append(wordsmith)
                del gd.players[wordsmith]
                del clients[wordsmith]
            else:
                system_log("GAME", f"Word successfully chosen as {word}")
                messages_to_log.append(
                    GameLog(time.time(), gd.gid, f"Word chosen as: {word}")
                )
                gd.word = word
                num_str = let_to_num(word).rstrip()
                system_log("GAME", f"Broadcasting number-string {num_str} to players")
                messages_to_log.append(
                    GameLog(time.time(), gd.gid, f"Numerical Hint is: {num_str}")
                )
                for socket in gd.players.keys():
                    if not socket == wordsmith:
                        socket.send(let_to_num(word).encode("utf-8"))
                system_log("GAME", f"Kicking the wordsmith because... Kicking...")
                messages_to_log.append(
                    GameLog(
                        time.time(),
                        gd.gid,
                        f"Kicking wordsmith (player: {gd.players[wordsmith].uid})",
                        gd.players[wordsmith].uid,
                    )
                )
                wordsmith.close()
                sockets_to_purge.append(wordsmith)
                del gd.players[wordsmith]
                del clients[wordsmith]

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
        time_pre = time.time()
        rs, _, _ = select.select([sock], [], [], GUESS_KICK_TIMEOUT)

        if not rs:
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

            sock.close()
            sockets_to_purge.append(sock)
            del gd.players[sock]
            del clients[sock]
            return None

        else:
            if time.time() - time_pre > GUESS_MISS_TIMEOUT:
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
                sock.send("#\n".encode("utf-8"))
                return None

            else:
                # TODO tutaj nie sprawdzam czy rzeczywiście przyszło
                cmd = sock.recv(1024).decode("utf-8").rstrip()
                guess = None

                # print("repr cmd", repr(cmd))
                # print("split cmd", cmd.split("\n"))
                # print("len split cmd", len(cmd.split("\n")))

                if len(cmd.split("\n")) > 1:
                    if cmd.split("\n")[-1] == "":
                        rs, _, _ = select.select([sock], [], [], GUESS_KICK_TIMEOUT)

                        if not rs:
                            system_log(
                                "GAME",
                                f"Player {gd.players[sock].uid} submitted a malformed guess... Kicking...",
                            )
                            messages_to_log.append(
                                GameLog(
                                    time.time(),
                                    gd.gid,
                                    f"Player {gd.players[sock].uid} submitted a malformed guess - kicked",
                                    gd.players[sock].uid,
                                )
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
                            # print('malf cmd', cmd)
                            sock.close()
                            sockets_to_purge.append(sock)
                            del gd.players[sock]
                            del clients[sock]
                            return None

                        guess = sock.recv(1024).decode("utf-8").rstrip()
                        # print('guess', guess)

                    else:
                        guess = cmd.split("\n")[1]
                        cmd = cmd.split("\n")[0]
                else:
                    rs, _, _ = select.select([sock], [], [], GUESS_KICK_TIMEOUT)

                    if not rs:
                        system_log(
                            "GAME",
                            f"Player {gd.players[sock].uid} submitted a malformed guess... Kicking...",
                        )
                        messages_to_log.append(
                            GameLog(
                                time.time(),
                                gd.gid,
                                f"Player {gd.players[sock].uid} submitted a malformed guess - kicked",
                                gd.players[sock].uid,
                            )
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
                        # print('malf cmd', cmd)
                        sock.close()
                        sockets_to_purge.append(sock)
                        del gd.players[sock]
                        del clients[sock]
                        return None

                    guess = sock.recv(1024).decode("utf-8").rstrip()

                # print("repr cmd1", repr(cmd))
                # print("repr guess1", repr(guess))

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
                                f"Player {gd.players[sock].uid} guessed the word ({guess}) - +5 points",
                                gd.players[sock].uid,
                            )
                        )
                        sock.send("=\n".encode("utf-8"))
                        time.sleep(0.05)
                        sock.send(f"{gd.players[sock].points}\n".encode("utf-8"))
                        time.sleep(0.05)
                        sock.send("?\n".encode("utf-8"))
                        time.sleep(0.05)
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
                                sock.send("!\n".encode("utf-8"))
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
                                        f"Player {gd.players[sock].uid} guessed a letter ({guess}) - +{hit_count} points",
                                        gd.players[sock].uid,
                                    )
                                )
                                sock.send("=\n".encode("utf-8"))
                                time.sleep(0.05)
                                sock.send(
                                    f"{pos_in_word(gd.word, guess)}\n".encode("utf-8")
                                )
                                continue
                        else:
                            system_log(
                                "GAME",
                                f"Player {gd.players[sock].uid} guessed the same letter ({guess}) again! Nope, won't work!",
                            )
                            # print('same repr guess', repr(guess))
                            sock.send("!\n".encode("utf-8"))
                            continue

                    else:
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
                        # print('malf0 repr cmd', repr(cmd))
                        # print('malf0 repr guess', repr(guess))
                        sock.close()
                        sockets_to_purge.append(sock)
                        del gd.players[sock]
                        del clients[sock]
                        return None

                else:
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
                    # print('malf1 repr cmd', repr(cmd))
                    # print('malf1 repr guess', repr(guess))
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
        sock.send("=\n".encode("utf-8"))
        time.sleep(0.05)
        sock.send(f"{gd.players[sock].points}\n".encode("utf-8"))
        time.sleep(0.05)
        sock.send("?\n".encode("utf-8"))
        time.sleep(0.05)

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


# ============================= #
#  Funkcje pomocnicze do liter  #
# ============================= #
def let_to_num(word):
    letter_string = ""
    for letter in word.rstrip():
        letter_string += LETTER_DICT[letter]

    letter_string += "\n"

    return letter_string


def pos_in_word(word, letter):
    pos_string = ""
    for let in word.rstrip():
        if let == letter:
            pos_string += "1"
        else:
            pos_string += "0"

    pos_string += "\n"

    return pos_string


def check_in_wordset(word):
    if WORD_SET_IN_RAM:
        return word in WORD_SET
    else:
        with open(os.path.join(ROOT_DIR, DICT_FILE)) as wfile, mmap.mmap(
            wfile.fileno(), 0, access=mmap.ACCESS_READ
        ) as s:
            return s.find(word.encode("utf-8")) != -1


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
                sockets_to_purge.append(notified_socket)
                sockets_list.remove(notified_socket)
                del clients[notified_socket]
                continue

            user = clients[notified_socket]

            print(f'Received message from {user.uid}: {repr(msg)}')

    for notified_socket in exception_sockets:
        sockets_list.remove(notified_socket)
        del clients[notified_socket]
