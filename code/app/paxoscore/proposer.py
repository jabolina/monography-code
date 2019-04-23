#!/usr/bin/env python
"""Paxos Client"""
__author__ = "Tu Dang"

import logging
import struct
from twisted.internet import defer
from twisted.internet.protocol import DatagramProtocol

logging.basicConfig(filename="proposer.log", level=logging.DEBUG, format='%(message)s')

VALUE_SIZE = 64
PHASE_2A = 3


class Proposer(DatagramProtocol):
    """
    Proposer class implements a Paxos proposer which sends requests and wait 
    asynchronously for responses.
    """

    def __init__(self, config, proposer_id):
        """
        Initialize a Proposer with a configuration of learner address and port.
        The proposer is also configured with a port for receiving UDP packets.
        """
        self.dst = (config.get('learner', 'addr'),
                    config.getint('learner', 'port'))
        self.rnd = proposer_id
        self.req_id = 0
        self.defers = {}

    def submit(self, msg):
        """
        Submit a request with an associated request id. The request id is used
        to lookup the original request when receiving a response.
        """
        self.req_id = self.req_id + 1 if self.req_id + 1 < 255 else 1

        values = (PHASE_2A, 0, self.rnd, self.rnd, 0, self.req_id, msg)
        packer = struct.Struct('>' + 'B H B B Q B {0}s'.format(VALUE_SIZE - 1))
        packed_data = packer.pack(*values)

        logging.info("Sending request [{}] with id [{}]".format(packed_data, self.req_id))

        self.transport.write(packed_data, self.dst)
        self.defers[self.req_id] = defer.Deferred()

        return self.defers[self.req_id]

    def datagramReceived(self, datagram, address):
        """
        Receive response from Paxos Learners, match the response with the original 
        request and pass it to the application handler.
        """
        try:
            fmt = '>' + 'B {0}s'.format(VALUE_SIZE)
            packer = struct.Struct(fmt)
            packed_size = struct.calcsize(fmt)
            unpacked_data = packer.unpack(datagram[:packed_size])
            req_id, result = unpacked_data

            logging.info("Response received [{}] with id [{}]".format(result, req_id))

            if req_id in self.defers:
                self.defers[req_id].callback(result)
                self.defers.pop(req_id)
        except defer.AlreadyCalledError as ex:
            logging.error("Error while handling response: [{}]".format(ex.message))
