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
        self.clients = {}  # Dict of connections, sockets act as keys
        self.messages = []
        self.buffer_height = shutil.get_terminal_size()[1]
        self.buffer_width = shutil.get_terminal_size()[0]

        # Outgoing message queues (socket:Queue)
        self.message_queues = {}
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.inputs = [self.server]
        self.outputs = []

    def run(self):
        """
        """
        host = '0.0.0.0'  # Listen on all IP's
        self.server.bind((host, self.port))
        self.server.listen(5)

        while self.running:
            # Wait for at least one of the sockets to be ready for processing
            readable, writable, exceptional = select(self.inputs, self.outputs, self.inputs)

            # Handle "exceptional conditions"
            for s in exceptional:
                print('Something went wrong with {}'.format(s.getpeername()))
                # Stop listening for input on the connection
                self.remove_connection(s)

            # Handle outputs
            for out_socket in writable:
                # Handle output here
                if not self.message_queues[out_socket].empty():
                    out_socket.send(self.message_queues[out_socket].get())

            for in_socket in readable:
                if in_socket is self.server:
                    # A "readable" server socket is ready to accept a connection
                    connection, client_address = in_socket.accept()

                    if client_address[0] != '127.0.0.1':
                        self.messages.append('New connection from {}'.format(client_address))
                        self.refresh_messages()

                    self.add_connection(connection)

                else:
                    data = in_socket.recv(1024)
                    if len(data) > 0:
                        data = json.loads(data.decode())
                        if 'clients' in data:
                            # We're recieving a list of clients here
                            # Get the list of host/port tuples
                            client_list = data['clients']
                            # And connect to each one except us and localhost
                            ourhost, junk = in_socket.getsockname()
                            for host, port in client_list:
                                if host != '127.0.0.1' and ourhost != host:
                                    self.connect_to(host, self.port)
                        elif data['message'] == '\exit':
                            # They are leaving the chat, close our end of the connection
                            self.messages.append('({}) {} has left the chat'.format(data['user'], in_socket.getpeername()))
                            self.refresh_messages()
                            # Stop listening for input on that connection
                            self.remove_connection(in_socket)
                        elif data['message'] == '\clients':
                            # A request for a client list
                            client_dict = {'clients': []}
                            client_dict['clients'].extend(self.clients.values())
                            data = json.dumps(client_dict)
                            mess = data.encode()
                            self.send_message(mess, in_socket)
                        else:
                            # A readable client socket has data
                            message = '({}) : {}'.format(data['user'], data['message'])
                            self.messages.append(message)
                            self.refresh_messages()
        # Cleanup Code
        self.close_all()
        self.server.close()

    def refresh_messages(self):
        """
        Refreshes the terminal complete with messages
        """
        clear_terminal()

        print('\n' * (self.buffer_height - len(self.messages) - 2))

        for message in self.messages:
            print(message)

        print(BLUE + '=' * self.buffer_width + ENDC)

    def connect_to(self, host, port):
        """
        Connect to the specified host port combination
        """
        connect_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connect_sock.connect((host, port))
        self.add_connection(connect_sock)

    def add_connection(self, sock):
        """
        Handles the backend tracking of connections
        """
        sock.setblocking(0)
        self.inputs.append(sock)
        self.outputs.append(sock)
        # Give the connection a queue for data we want to send
        self.message_queues[sock] = Queue()
        # And store its info in our clients structure
        self.clients[sock] = sock.getpeername()

    def remove_connection(self, sock):
        """
        Handles the backend tracking of connection removal
        """
        self.outputs.remove(sock)
        self.inputs.remove(sock)
        del self.message_queues[sock]
        del self.clients[sock]
        sock.close()

    def close_all(self):
        """
        Removes all active connections except for the one with itself
        """
        for conn in self.outputs[:]:
            self.remove_connection(conn)

    def output_message(self, mess):
        """
        Outputs a message to all active outgoing connections
        """
        for outs in self.message_queues.values():
            outs.put(mess)

    def send_message(self, mess, sock):
        """
        Outputs a message to a single connection
        """
        self.message_queues[sock].put(mess)

    def kill(self):
        self.running = False


class ChatClient(Cmd):
    def __init__(self, user='Anon', escape='\\', port=2017):
        """
        """
        Cmd.__init__(self)
        self.user = user
        self.prompt = '({}) >> '.format(user)
        self.escape = escape
        self.port = port

        # start the local server
        self.server = ChatServer(port)
        self.server.daemon = True
        self.server.start()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(('localhost', port))

        self.buffer_height = shutil.get_terminal_size()[1]

        clear_terminal()
        print('\n' * self.buffer_height)

    def do_connect(self, string):
        # Kill the old chat server
        self.server.kill()
        self.sock.close()
        time.sleep(.1)
        # And then reboot it
        self.server = ChatServer(self.port)
        self.server.daemon = True
        self.server.start()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(('localhost', self.port))
        # Then connect to the new server
        values = string.split(":", 1)
        self.server.connect_to(values[0], int(values[1]))
        # And immediately request a copy of their clients
        data = json.dumps({'user': self.user, 'message': '\clients'})
        mess = data.encode()
        self.server.output_message(mess)

    def do_c(self, string):
        self.do_connect(string)

    def do_port(self, string):
        self.port = int(string)

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

        data = json.dumps({'user': self.user, 'message': string})
        mess = data.encode()
        self.server.output_message(mess)
        self.sock.send(mess)
        time.sleep(.1)

    def do_exit(self, string):
        data = json.dumps({'user': self.user, 'message': string})
        mess = data.encode()
        self.server.output_message(mess)
        data = json.dumps({'user': self.user, 'message': '\exit'})
        mess = data.encode()
        self.server.output_message(mess)
        print('Exiting the room...', ENDC)
        time.sleep(.1)
        self.server.kill()
        clear_terminal()
        exit()

    def do_help(self, string):
        print(GREEN, BOLD)

        help_messages = {
            self.escape + 'help': 'Print command details (duh)',
            self.escape + 'exit': 'Disconnect and exit the chat client',
            self.escape + 'connect -OR- ' + self.escape + 'c':
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
    Gets a random name for a new user that didn't bother to choose one
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
