#! /usr/bin/env python
# -*- coding: utf-8 -*-
# py 2.X

from __future__ import print_function
import socket
import select
import sys
import Queue

# Create a TCP/IP socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setblocking(0)

# Bind the socket to the port
server_address = ('localhost', 10000)
print('starting up on %s port %s' % server_address)
server.bind(server_address)

# Listen for incoming connections
server.listen(5)

# Keep up with the queues of outgoing messages
message_queues = {}

# Do not block forever(milliseconds)
TIMEOUT = 1000

# Commonly used flag setes
READ_ONLY = select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR
READ_WRITE = READ_ONLY | select.POLLOUT

# Set up the poller
poller = select.poll()
poller.register(server, READ_ONLY)

# Map file description to socket objects
fd_to_sockets = {server.fileno(): server}

while True:
    # Wait for at least one of the sockets to be ready for processing
    print('\nWaiting for the next event')
    events = poller.poll(TIMEOUT)

    for fd, flag in events:
        # Retrieve the actual socket from its file descriptor
        s = fd_to_sockets[fd]

        # Handle inputs
        if flag & (select.POLLIN | select.POLLPRI):
            # A readable server is ready to accept a connection
            if s is server:
                connection, client_address = s.accept()
                print('new connection from', client_address)
                connection.setblocking(0)
                fd_to_sockets[connection.fileno()] = connection
                poller.register(connection, READ_ONLY)

                # Give the connection a queue for the data we want to send
                message_queues[connection] = Queue.Queue()
            else:
                data = s.recv(1024)

                # A readable client socket has data
                if data:
                    print('received "%s" from %s' % (data, s.getpeername()))
                    # Add output channel for response
                    message_queues[s].put(data)
                    poller.modify(s, READ_WRITE)
                else:
                    # Interpret empty result as closed connection
                    print('closing ', client_address, 'after reading no data')
                    # Stop listening for input on the connection
                    poller.unregister(s)
                    s.close()

                    # Remove the message queue
                    del message_queues[s]

        elif flag & select.POLLHUP:
            # Client hung up
            print('closing', client_address, ' after receiving HUP')
            # Stop listening for input on the connection
            poller.unregister(s)
            s.close()
        elif flag & select.POLLOUT:
            # Socket is ready to send data, if there is any to send
            try:
                next_msg = message_queues[s].get_nowait()
            except Queue.Empty:
                # No message waiting so stop checking for writability
                print('output queue for', s.getpeername(), 'is empty')
                poller.modify(s, READ_ONLY)
            else:
                print('sending "%s" to "%s"' % (next_msg, s.getpeername()))
                s.send(next_msg)

        elif flag & select.POLLERR:
            print('handling exceptional condition for', s.getpeername())
            poller.unregister(s)
            s.close()

            # Remove message queue
            del message_queues[s]
