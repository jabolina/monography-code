#!/usr/bin/python

import netifaces
from math import ceil

import json
from scapy.all import *
from scapy.layers.inet import IP, UDP
from scapy.layers.l2 import Ether
from twisted.internet import defer

logging.basicConfig(filename="learner.log", level=logging.DEBUG, format='%(message)s')
VALUE_SIZE = 64
PHASE_1A = 1
PHASE_1B = 2
PHASE_2A = 3
PHASE_2B = 4


class PaxosMessage(object):
    """
    PaxosMessage class defines the structure of a Paxos message
    """

    def __init__(self, nid, inst, crnd, vrnd, value):
        """
        Initialize a Paxos message with:
        nid : node-id
        inst: paxos instance
        crnd: proposer round
        vrnd: accepted round
        value: accepted value
        """
        self.nid = nid
        self.inst = inst
        self.crnd = crnd
        self.vrnd = vrnd
        self.val = value


class PaxosLearner(object):
    """
    PaxosLearner acts as Paxos learner that learns a decision from a majority
    of acceptors.
    """

    def __init__(self, num_acceptors):
        """
        Initialize a learner with a the number of acceptors to decide the
        quorum size.
        """
        self.logs = {}
        self.states = {}
        self.proposerState = {}
        self.majority = ceil((num_acceptors + 1) / 2)
        logging.info("Majority must be [{}]".format(self.majority))

    class ProposerState(object):
        """
        The state of learner of a particular instance.
        """

        def __init__(self, crnd):
            self.crnd = crnd
            self.nids = set()
            self.hval = None
            self.hvrnd = 0
            self.finished = False

    class LearnerState(object):
        """
        The state of learner of a particular instance.
        """

        def __init__(self, crnd):
            self.crnd = crnd
            self.nids = set()
            self.val = None
            self.finished = True
            self.saved = False

    def handle_p1b(self, msg):
        """handle 1a message and return decision if existing a majority.
        Otherwise return None"""
        res = None
        state = self.proposerState.get(msg.inst)
        if state is None:
            state = self.ProposerState(msg.crnd)

        if state.crnd == msg.crnd:
            if msg.nid not in state.nids:
                state.nids.add(msg.nid)
                if state.hvrnd <= msg.vrnd:
                    state.hval = msg.val

                state.saved = True
                res = PaxosMessage(10, msg.inst, state.crnd, state.hvrnd, state.hval)
                self.proposerState[msg.inst] = state

        return res

    def handle_p2b(self, msg):
        """
            Handle message of type 2B, saving the response and
            delivering the packet back to the application

        :param msg: An Paxos Message ready to be learned by the application
        :return: Tuple with instance number and the result
        """
        res = None
        logging.info("Message with instance number [{}]".format(msg.inst))

        state = self.states.get(msg.inst)
        if state is None:
            state = self.LearnerState(msg.crnd)

        logging.info("Message instance is finished? [{}]".format(state.finished))

        if not state.saved:
            if state.crnd < msg.crnd:
                logging.info("state rnd < msg rnd")
                state = self.LearnerState(msg.crnd)

            if state.crnd == msg.crnd:
                logging.info("Saving new message in the logs and states")

                if msg.nid not in state.nids:
                    state.nids.add(msg.nid)
                    if state.val is None:
                        state.val = msg.val

                    state.saved = True
                    self.logs[msg.inst] = state.val
                    res = (msg.inst, state.val)
                    self.states[msg.inst] = state
        else:
            res = (msg.inst, self.logs[msg.inst])

        return res


class Learner(object):
    """
    A learner instance provides the ordering of requests to the overlay application.
    If a decision has been made, the learner delivers that decision to the application.
    """

    def __init__(self, num_acceptors, learner_addr, learner_port):
        """
        Initialize a learner with the number of acceptors, maximum number of requests,
        and the running duration.
        """
        self.learner = PaxosLearner(num_acceptors)
        self.learner_addr = learner_addr
        self.learner_port = learner_port
        self.min_uncommited_index = 1
        self.max_instance = 1
        self.deliver = None

    @staticmethod
    def respond(result, req_id, dst, sport, dport):
        """
        This method sends the reply from application server to the origin of the request.
        """
        packer = struct.Struct('>' + 'B {0}s'.format(VALUE_SIZE))
        packed_data = packer.pack(*(req_id, str(result)))
        pkt_header = IP(dst=dst) / UDP(sport=sport, dport=dport)

        logging.info("Sending response [{}] with id [{}]".format(packed_data, req_id))

        sendp(pkt_header / packed_data, verbose=True)

    @staticmethod
    def make_paxos(typ, i, rnd, vrnd, val):
        request_id = 10
        acceptor_id = 10
        values = (typ, i, rnd, vrnd, acceptor_id, request_id, val)
        packer = struct.Struct('!' + 'B H B B Q B {0}s'.format(VALUE_SIZE - 1))
        packed_data = packer.pack(*values)
        return packed_data

    @staticmethod
    def send_msg(msg, dst, dport):
        """
        This method sends the reply from application server to the origin of the request.
        """
        for itf in netifaces.interfaces():
            ether = Ether(src='00:04:00:00:00:01', dst='01:00:5e:03:1d:47')
            pkt_header = ether / IP(dst=dst) / UDP(sport=12345, dport=dport)

            logging.info("Sending msg [{}] with headers [{}] to interface [{}]".format(msg, pkt_header, itf))

            sendp(pkt_header / msg, iface=itf, verbose=True)

    def add_deliver(self, deliver_cb):
        """
        This method allows the application server attach the request handler when such a
        request has been chosen for servicing.
        """
        self.deliver = deliver_cb

    def retry_instance(self, inst):
        msg1a = self.make_paxos(PHASE_1A, inst, 1, 0, '')
        Learner.send_msg(msg1a, self.learner_addr, self.learner_port)

    def delivery_msg(self, inst):
        d = defer.Deferred()

        try:
            if inst in self.learner.logs:
                cmd = self.learner.logs[inst]
                cmd_in_dict = json.loads(cmd)

                logging.info("Trying to deliver [{}]".format(cmd_in_dict))

                self.deliver(cmd_in_dict, d)

        except KeyError as ex:
            logging.error("Error while delivering message [{}]".format(ex))
            self.retry_instance(inst)

        except Exception as ex:
            logging.error("Unexpected error delivering message [{}]".format(ex))
            self.retry_instance(inst)

        return d

    def handle_pkt(self, pkt):
        """
        The arrived packet will already been the learner switch, so
        they will be delivered to the application again with the
        response

        :arg pkt: Sniffed packet
        """

        try:
            if pkt['IP'].proto != 0x11:
                return
            datagram = pkt['Raw'].load
            fmt = '>' + 'B H B B Q B {0}s'.format(VALUE_SIZE - 1)
            packer = struct.Struct(fmt)
            packed_size = struct.calcsize(fmt)
            unpacked_data = packer.unpack(datagram[:packed_size])
            typ, inst, rnd, vrnd, acceptor_id, req_id, value = unpacked_data
            value = value.rstrip('\t\r\n\0')
            msg = PaxosMessage(acceptor_id, inst, rnd, vrnd, value)

            logging.info("Handling message [{}]".format(unpacked_data))

            if typ == PHASE_2B:
                res = self.learner.handle_p2b(msg)
                logging.info("Message 2B with req [{}] response [{}]".format(req_id, res))

                if res is not None:
                    inst = int(res[0])
                    if self.max_instance < inst:
                        self.max_instance = inst
                    d = self.delivery_msg(inst)
                    d.addCallback(self.respond, req_id, pkt[IP].src,
                                  pkt[UDP].dport, pkt[UDP].sport)
                else:
                    logging.error("Message with response None, cant be handled [{}]".format(unpacked_data))
            elif typ == PHASE_1B:
                res = self.learner.handle_p1b(msg)
                logging.info("Message 1B response [{}] is type None [{}]".format(res, res is None))

                if res is not None:
                    msg2a = self.make_paxos(PHASE_2A, res.inst, res.crnd, res.vrnd, res.val)
                    self.send_msg(msg2a, self.learner_addr, self.learner_port)

            else:
                logging.error("Message type not found to be delivered: [{}]".format(unpacked_data))

        except IndexError as ex:
            logging.error("Error while handling packet [{}]".format(ex))
        except Exception as ex:
            logging.error("Unknown error while handling packet [{}]".format(ex))

    def start(self, count, timeout):
        """
        Start a learner by sniffing on all learner's interfaces.
        """
        logging.debug("| %10s | %4s |  %2s | %2s | %4s | %s |" %
                      ("type", "inst", "pr", "ar", "val", "payload"))
        try:
            if timeout > 0:
                sniff(count=count, timeout=timeout, filter="udp && dst port 34952",
                      prn=lambda x: self.handle_pkt(x), store=0)
            else:
                sniff(count=count, filter="udp && dst port 34952",
                      prn=lambda x: self.handle_pkt(x), store=0)
        except Exception as e:
            logging.error("Error sniffing [{}]".format(e))

        logging.info("Learner finished")

    def stop(self):
        """
        Stop sniffing on the learner's interfaces. Not implemented yet
        """
        pass
# tcpdump -i eth0 -qtNnn port 34952
