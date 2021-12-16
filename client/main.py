import os
import sys
import socket
import select
import configparser

ROOT_DIR = os.path.dirname(__file__)

config = configparser.ConfigParser()
config.read(os.path.join(ROOT_DIR, "config.ini"))

IP = config["CONNECTION"]["IP"]
PORT = int(config["CONNECTION"]["PORT"])

my_username = config["CREDENTIALS"]["ID_NUMBER"]  # input("Username: ")
my_password = config["CREDENTIALS"]["PASSWORD"]  # input("Username: ")

cli_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cli_socket.connect((IP, PORT))

# cli_socket.setblocking(False)

# username = (my_username + "\n").encode("utf-8")
# password = (my_password + "\n").encode("utf-8")

# cli_socket.send(username)

# cli_socket.send(password)

# auth_resp = cli_socket.recv(1024)

# print(auth_resp.decode('utf-8').rstrip())

words = [
    "rozpamiętywany",
    "rozpamiętywanym",
    "rozpamiętywań",
    "rozpamiętywasz",
    "rozpanosz",
    "rozpanoszą",
    "rozpanoszcie",
    "rozpanoszcież",
]

sockets_list = [sys.stdin, cli_socket]

while True:
    read_sockets, write_socket, error_socket = select.select(sockets_list, [], [])

    for sock in read_sockets:
        if sock == cli_socket:
            rcv = sock.recv(1024)

            if not len(rcv):
                print('===========RECV===========')
                print('Connection closed by the server?')
                print('==========================')

                sys.exit()

            print('===========RECV===========')
            print(rcv.decode("utf-8").rstrip())
            print(repr(rcv.decode("utf-8")))
            print('==========================')

        else:
            mess = sys.stdin.readline().rstrip() + '\n'

            cli_socket.send(mess.encode('utf-8'))
            
            print(repr(mess))
            print('==========================')
