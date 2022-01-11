import re
import sys
import time
import mmap
import socket

from random import choice, randrange


def build_game_dict(file_path):
    with open(file_path, mode="r", encoding="utf8") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as fmap:
            dictionary = {}
            line_content = fmap.readline().decode()[:-2]

            line_num = 0
            while line_content:
                if len(line_content) > 4:
                    dictionary[line_num] = line_content
                    line_num += 1

                line_content = fmap.readline().decode()[:-2]

            return dictionary


DICT = build_game_dict("slowa.txt")
DICT_LEN = len(DICT)

LINE1_LETTERS = ""
LINE2_LETTERS = ""
LINE3_LETTERS = ""
LINE4_LETTERS = ""

IP = "136.243.156.120"
PORT = 50804

if (len(sys.argv)) < 4:
    print("python3 ./main.py <login> <passwd> <delay>")
    sys.exit()

LOGIN = sys.argv[1]
PASSWD = sys.argv[2]
DELAY = float(sys.argv[3])


def receive_msg(cli_sock):
    try:
        return cli_sock.recv(1024).decode().replace("\0", "\n").rstrip()
    except:
        disconnect_gracefully(cli_sock)
        return False


def disconnect_gracefully(cli_sock):
    time.sleep(2)
    cli_sock.close()


def login(cli_sock):
    try:
        cli_sock.send(str.encode(LOGIN + "\n"))
    except:
        disconnect_gracefully(cli_sock)
        return False

    try:
        cli_sock.send(str.encode(PASSWD + "\n"))
    except:
        disconnect_gracefully(cli_sock)
        return False

    return True


def send(last_data, cli_sock):
    global glob_word
    global glob_possible_words

    msg_to_send = None
    if last_data[-1] == "?":
        if last_data[0] == "=":
            score = last_data.replace("\0", "\n").split("\n")[1]
            print(f"YOU SCORED: {score}")
        disconnect_gracefully(cli_sock)
        return True

    elif re.match(r"[1-4]+", last_data):
        glob_word = last_data.rstrip()
        glob_possible_words = get_word_list()
        msg_to_send = choose_letter()

    elif re.match(r"[0-1]+", last_data):
        glob_word = last_data.rstrip()
        msg_to_send = choose_letter()

    elif last_data[0] == "#":
        msg_to_send = choose_letter()

    elif last_data[0] == "=":
        try:
            last_data = last_data.replace("\0", "\n").split("\n")[1]
        except:
            last_data = last_data.replace("\0", "\n")[1:]

        if last_data is not None:
            update_word(last_data)

        msg_to_send = choose_word()
        if msg_to_send is None:
            msg_to_send = choose_letter()

    elif last_data[0] == "!":
        msg_to_send = choose_word()

        if msg_to_send is None:
            msg_to_send = choose_letter()

    if msg_to_send is not None:
        time.sleep(DELAY)
        print(f"Sending: {repr(msg_to_send)}")

        try:
            cli_sock.send(msg_to_send.encode("utf-8"))
        except socket.error as e:
            print(f"Error while sending: {e}")
            disconnect_gracefully(cli_sock)


def guess_successful(guess):
    global glob_word

    glob_word = glob_word.rstrip()
    for i in range(len(glob_word)):
        if glob_word[i] == "1" and not guess[i] in LINE1_LETTERS:
            return False

        elif glob_word[i] == "2" and not guess[i] in LINE2_LETTERS:
            return False

        elif glob_word[i] == "3" and not guess[i] in LINE3_LETTERS:
            return False

        elif glob_word[i] == "4" and not guess[i] in LINE4_LETTERS:
            return False

    return True


def get_word_list():
    global glob_word

    word_list = []
    for i in range(len(DICT)):
        word = DICT[i]

        if len(glob_word) == len(word) and guess_successful(word):
            word_list.append(word)

    return word_list


def choose_word():
    global glob_word
    global glob_possible_words

    if len(glob_possible_words) > 10:
        return None

    pattern = re.compile(re.sub(r"(\d)", ".", glob_word))
    for word in glob_possible_words:
        if pattern.match(word) and guess_successful(word):
            glob_possible_words.remove(word)
            return "=\n" + word + "\0"

    return None


def get_unique(letter_group):
    global glob_guessed
    for letter in letter_group:
        if letter not in glob_guessed:
            return letter
    return None


def choose_letter():
    global glob_word
    global glob_guessed

    glob_word = glob_word.rstrip()

    if re.search("4", glob_word):
        letter = get_unique(LINE4_LETTERS)
        if letter is not None:
            glob_guessed += letter
            return "+\n" + letter + "\0"

    if re.search("2", glob_word):
        letter = get_unique(LINE2_LETTERS)
        if letter is not None:
            glob_guessed += letter
            return "+\n" + letter + "\0"

    if re.search("3", glob_word):
        letter = get_unique(LINE3_LETTERS)
        if letter is not None:
            glob_guessed += letter
            return "+\n" + letter + "\0"

    if re.search("1", glob_word):
        letter = get_unique(LINE1_LETTERS)
        if letter is not None:
            glob_guessed += letter
            return "+\n" + letter + "\0"

    return None


def update_word(guess_result):
    global glob_word
    global glob_guessed

    glob_word = glob_word.rstrip()
    for i in range(len(glob_word)):
        if guess_result[i] == "1":
            glob_word = glob_word[:i] + glob_guessed[-1] + glob_word[i + 1 :]

    print(f"Current word state: {glob_word}")


while True:
    print("Client is starting...")
    glob_word = None
    glob_possible_words = []
    glob_guessed = ""

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((IP, PORT))

    if login(client) == False:
        continue

    login_successful = receive_msg(client)
    if login_successful == False:
        continue

    print(login_successful)

    if login_successful == "+1":
        LINE1_LETTERS = "weęruioóaąsśzżźxcćvnńm"
        LINE2_LETTERS = "pyjgq"
        LINE3_LETTERS = "tlłbdhk"
        LINE4_LETTERS = "f"
        print("Successfully logged in - alphabet 1")

    elif login_successful == "+2":
        LINE1_LETTERS = "acemnorsuwzxv"
        LINE2_LETTERS = "ąęgjpyq"
        LINE3_LETTERS = "bćdhklłńóśtźżi"
        LINE4_LETTERS = "f"
        print("Successfully logged in - alphabet 2")

    else:
        print("Login failed - retrying in 2 seconds")
        disconnect_gracefully(client)
        continue

    data = login_successful
    while True:
        if data:
            if send(data, client):
                print("RESTARTING")
                disconnect_gracefully(client)
                break

        try:
            data = receive_msg(client)
        except Exception as e:
            print("RESTARTING")
            disconnect_gracefully(client)
            break

    client.close()
    continue
