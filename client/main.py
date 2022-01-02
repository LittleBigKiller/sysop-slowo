import os
import sys
import time
import socket
import select
import configparser

ROOT_DIR = os.path.dirname(__file__)

SLEEP_TIME = 0.05


def print_recv(message):
    print("===========RECV===========")
    print(message.rstrip())
    print(repr(message))
    print("==========================")


def print_auto(message):
    print("===========AUTO===========")
    print(message.rstrip())
    print(repr(message))
    print("==========================")


def print_dead():
    print("===========DEAD===========")
    print("Connection closed by the server?")
    print("==========================")


config = configparser.ConfigParser()
config.read(os.path.join(ROOT_DIR, "config.ini"))

IP = config["CONNECTION"]["IP"]
PORT = int(config["CONNECTION"]["PORT"])

if len(sys.argv) < 3:
    print("Usage: './main.py <username> <password>'")
    sys.exit()

my_username = sys.argv[1]
my_password = sys.argv[2]

cli_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli_socket.connect((IP, PORT))

username = (my_username + "\n").encode("utf-8")
password = (my_password + "\n").encode("utf-8")

cli_socket.send(username)
print_auto(username.decode())
time.sleep(SLEEP_TIME)
cli_socket.send(password)
print_auto(password.decode())

rcv = cli_socket.recv(1024).decode("utf-8")

if not len(rcv):
    print_dead()
    sys.exit()

print_recv(rcv)

sockets_list = [sys.stdin, cli_socket]

if len(sys.argv) == 4:
    SLEEP_TIME *= int(sys.argv[3])

while True:
    read_sockets, write_socket, error_socket = select.select(sockets_list, [], [])

    for sock in read_sockets:
        if sock == cli_socket:
            rcv = sock.recv(1024).decode("utf-8")

            if not len(rcv):
                print_dead()
                sys.exit()

            print_recv(rcv)

            if rcv.rstrip() == "@":
                word = "długonoga\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))

            elif rcv.rstrip() == "331211121":
                # time.sleep(SLEEP_TIME)
                word = "+\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))
                # time.sleep(SLEEP_TIME)
                word = "d\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))

            elif rcv.rstrip() == "100000000":
                time.sleep(2.5)
                word = "+\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))
                # time.sleep(SLEEP_TIME)
                word = "g\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))

            elif rcv.rstrip() == "000100010" or rcv.rstrip() == "#":
                # time.sleep(SLEEP_TIME)
                word = "+\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))
                # time.sleep(SLEEP_TIME)
                word = "o\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))

            elif rcv.rstrip() == "000010100":
                # time.sleep(SLEEP_TIME)
                word = "+\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))
                # time.sleep(SLEEP_TIME)
                word = "n\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))

            elif rcv.rstrip() == "000001000":
                # time.sleep(SLEEP_TIME)
                word = "+\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))
                # time.sleep(SLEEP_TIME)
                word = "u\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))

            elif rcv.rstrip() == "001000000":
                # time.sleep(SLEEP_TIME)
                word = "+\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))
                # time.sleep(SLEEP_TIME)
                word = "ł\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))

            elif rcv.rstrip() == "010000000":
                # time.sleep(SLEEP_TIME)
                word = "+\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))
                # time.sleep(SLEEP_TIME)
                word = "x\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))

            elif rcv.rstrip() == "!":
                # time.sleep(SLEEP_TIME)
                word = "=\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))
                # time.sleep(SLEEP_TIME)
                word = "długonoga\n"
                print_auto(word)
                cli_socket.send(word.encode("utf-8"))

        else:
            mess = sys.stdin.readline().rstrip() + "\n"

            cli_socket.send(mess.encode("utf-8"))

            print(repr(mess))
            print("==========================")
