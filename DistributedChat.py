#!/usr/bin/env python

import socket
import time
import argparse
import json
import random
import os
import shutil

from cmd import Cmd
from threading import Thread
from select import select
from queue import Queue


"""
Collections of colors for printing, taken from Blender's
build files
"""
BLUE = '\033[94m'
GREEN = '\033[92m'
RED = '\033[31m'
YELLOW = '\033[33m'
PURPLE = '\033[35m'
CYAN = '\033[36m'
ALTBLUE = '\033[34m'

COLOR_LIST = [BLUE, GREEN, RED, YELLOW, PURPLE, CYAN, ALTBLUE]

# Other formatting options
BOLD = '\033[1m'
UNDERLINE = '\033[4m'
ENDC = '\033[0m'  # clear formatting


class ChatServer(Thread):
    def __init__(self, port):
        """
        """
        Thread.__init__(self)
        self.running = True
        self.port = port
        self.clients = {}  # Dict of connections, IP's act as keys
        self.messages = []
        self.buffer_height = shutil.get_terminal_size()[1]
        self.buffer_width = shutil.get_terminal_size()[0]

        # Outgoing message queues (socket:Queue)
        self.message_queues = {}

    def run(self):
        """
        """
        host = '0.0.0.0'  # Listen on all IP's
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, self.port))
        server.listen(5)

        inputs = [server]
        outputs = []

        while self.running:
            # Wait for at least one of the sockets to be ready for processing
            readable, writable, exceptional = select(inputs, outputs, inputs)

            # Handle "exceptional conditions"
            for s in exceptional:
                print('Something went wrong with {}'.format(s.getpeername()))
                # Stop listening for input on the connection
                inputs.remove(s)
                if s in outputs:
                    outputs.remove(s)
                s.close()

                # Remove message queue
                del self.message_queues[s]

            # Handle outputs
            for out_socket in writable:
                # Handle output here
                if not self.message_queues[out_socket].empty():
                    out_socket.send(self.message_queues[out_socket].get())

            for in_socket in readable:
                if in_socket is server:
                    # A "readable" server socket is ready to accept a connection
                    connection, client_address = in_socket.accept()

                    if client_address[0] != '127.0.0.1':
                        print('New connection from {}'.format(client_address))

                    connection.setblocking(0)
                    inputs.append(connection)
                    outputs.append(connection)

                    # Give the connection a queue for data we want to send
                    self.message_queues[connection] = Queue()

                else:
                    data = in_socket.recv(1024)
                    if data and data.lower() != 'exit':
                        # A readable client socket has data
                        data = json.loads(data.decode())
                        message = '({}) : {}'.format(data['user'], data['message'])
                        self.messages.append(message)
                        clear_terminal()

                        print('\n' * (self.buffer_height - len(self.messages)-2))

                        for message in self.messages:
                            print(message)

                        print(BLUE + '='*self.buffer_width + ENDC)

                    else:
                        # Interpret empty result as closed connection
                        print('closing {} after reading no data'.format(in_socket.getpeername()))
                        # Stop listening for input on the connection
                        if in_socket in outputs:
                            outputs.remove(in_socket)
                        inputs.remove(in_socket)
                        in_socket.close()

                        # Remove message queue
                        del self.message_queues[in_socket]

    def kill(self):
        self.running = False


class ChatClient(Cmd):
    def __init__(self, user_info=None, user='Anon', escape='\\', port=2017):
        """
        """
        Cmd.__init__(self)
        self.user = user
        self.prompt = '({}) >> '.format(user)
        self.escape = escape
        self.connected = False

        # start the local server
        self.server = ChatServer(port)
        self.server.daemon = True
        self.server.start()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(('localhost', port))

        self.buffer_height = shutil.get_terminal_size()[1]

        clear_terminal()
        print('\n'*self.buffer_height)

    def do_connect(self, string):
        """
        """
        values = string.split(":", 1)
        self.connect(values[0], int(values[1]), self.server)

    def connect(self, host, port, server):
        """
        """
        connect_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connect_sock.connect((host, port))

    def do_c(self, string):
        self.do_connect(string)

    def do_update(self, string):
        bs = '\b'*1000
        print(bs)
        print(string)

    def onecmd(self, string):
        """
        Runs whenever a new text is entered and not covered by do_<something>

        """
        if not string:
            return

        if string[0] == self.escape:
            super(ChatClient, self).onecmd(string[1:])
            return
        elif string[0] == '?':
            super(ChatClient, self).onecmd(string)
            return
        elif string == 'EOF':
            self.do_exit('EOF')

        data = json.dumps({'user': self.user, 'message' : string})
        mess = data.encode()
        for outs in self.server.message_queues:
            outs.put(mess)
        self.sock.send(mess)
        time.sleep(.1)

    def do_exit(self, string):
        if not string:
            pass  # shut pep8 warnings

        print('Exiting the room...', ENDC)
        clear_terminal()
        exit()

    def do_help(self, string):
        print(GREEN, BOLD)

        help_messages = {
            self.escape+'help': 'Print command details (duh)',
            self.escape+'exit': 'Disconnect and exit the chat client',
            self.escape+'connect -OR- '+self.escape+'c':
                        'Connect to new user in "host:port" format (e.g. \c kelvin.net:2017)'
        }

        if not string:
            print('=================================================================================')
            print()
            print('\n'.join(['{} : {}'.format(cmd, help_messages[cmd]) for cmd in help_messages.keys()]))
            print('=================================================================================')
        else:
            print(help_messages.get(string, 'No such command: {}'.format(string)))

        print(ENDC)


def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')


def get_random_name():
    """
    """
    names = [
        "PokemonLover96",
        "STARWARS_IS_OVERRATED",
        "LVL78_Alolan_Exeggutor",
        "LVL69_BDK",
        "Egofaptor",
        "ColdSteel_The_Hedgehog",
        "Make_ChatRooms_Great_Again",
        "DAN_CANT_CODE",
        "TurtleLover69"
    ]

    return random.choice(names)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-host', action='store', default=None,
                        help='Provide the address of the user client. Will start an offline client if not provided.')
    parser.add_argument('-port', action='store', default=2017,
                        help='Provide the port to listen on (default: 2017)')
    parser.add_argument('-user', action='store', default=get_random_name(),
                        help='User handle, what others will see you as. Username is provided if one isn\'t provided')

    args = parser.parse_args().__dict__

    client = ChatClient(user=args['user'])
    client.cmdloop()
