#!/usr/bin/python

# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from time import sleep

import argparse
import os
import subprocess
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.topo import Topo
from p4_mininet import P4Switch, P4Host
from subprocess import PIPE

_THIS_DIR = os.path.dirname(os.path.realpath(__file__))
_THRIFT_BASE_PORT = 22222

_NUM_OF_ACCEPTORS = 3
_NUM_OF_LEARNERS = 1

parser = argparse.ArgumentParser(description='Mininet demo')
parser.add_argument('--behavioral-exe', help='Path to behavioral executable',
                    type=str, action="store", required=True)
parser.add_argument('--acceptor', help='Path to acceptor JSON config file',
                    type=str, action="store", required=True)
parser.add_argument('--coordinator', help='Path to coordinator JSON config file',
                    type=str, action="store", required=True)
parser.add_argument('--learner', help='Path to learner JSON config file',
                    type=str, action="store", required=True)
parser.add_argument('--cli', help='Path to BM CLI',
                    type=str, action="store", required=True)
parser.add_argument('--start-server', help='Start Paxos httpServer and backends',
                    action="store_true", default=False)

args = parser.parse_args()


class CustomTopology(Topo):
    def __init__(self, sw_path, acceptor, coordinator, learner, **opts):
        """
            Will create the coordinator and learner switch separately,
            then will create all 3 acceptors.

            Will create the 4 hosts, then will create the links between
            the hosts and switches

        :param sw_path: Switch used, BMv2
        :param acceptor: The path to acceptor.json
        :param coordinator: The path to coordinator.json
        :param learner: The path to learner.json
        :param opts: Another options of the topology, not being used
        """
        Topo.__init__(self, **opts)
        self.acceptors = []
        self.machines = []
        self.learners = []

        # Coordinator
        s1 = self.addSwitch('s1',
                            sw_path=sw_path,
                            json_path=coordinator,
                            thrift_port=_THRIFT_BASE_PORT + 1,
                            pcap_dump=False,
                            log_console=True,
                            verbose=True,
                            device_id=1)

        # Acceptors
        for i in range(2, _NUM_OF_ACCEPTORS + 2):
            self.acceptors.append(self.addSwitch('s%d' % i,
                                                 sw_path=sw_path,
                                                 json_path=acceptor,
                                                 thrift_port=_THRIFT_BASE_PORT + i,
                                                 pcap_dump=False,
                                                 log_console=True,
                                                 verbose=True,
                                                 device_id=i))

        # Learners
        base_swid = len(self.acceptors) + 2
        for i in range(base_swid, base_swid + _NUM_OF_LEARNERS):
            self.learners.append(self.addSwitch('s%d' % i,
                                                sw_path=sw_path,
                                                json_path=learner,
                                                thrift_port=_THRIFT_BASE_PORT + i,
                                                pcap_dump=False,
                                                log_console=True,
                                                verbose=True,
                                                device_id=i))

        # Create hosts
        for h in [1, 2, 3, 4]:
            self.machines.append(self.addHost('h%d' % h))

        h1, h2, h3, h4 = self.machines

        # Hosts 1 and 4 connected only to switch 1 (coordinator)
        self.addLink(h1, s1)
        self.addLink(h4, s1)

        # Hosts 2 and 3 connected to all learners
        for i, s in enumerate(self.learners):
            for j, h in enumerate([h2, h3]):
                self.addLink(h, s,
                             intfName1='eth{0}'.format(i + 1),
                             params1={
                                 'ip': '10.0.{0}.{1}/8'.format(i + 1, j + 2)}
                             )

        # All acceptors connected into the coordinator and to all learners
        for _, s in enumerate(self.acceptors):
            self.addLink(s, s1)
            for __, l in enumerate(self.learners):
                self.addLink(s, l)


def execute_command(cmd, rule=''):
    p = subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate(rule)
    if out:
        print(out)
    if err:
        print(err)


def main():
    topology = CustomTopology(
        args.behavioral_exe, args.acceptor, args.coordinator, args.learner)

    net = Mininet(topo=topology,
                  host=P4Host,
                  switch=P4Switch,
                  controller=None)

    net.start()

    for n in range(1, len(topology.machines) + 1):
        h = net.get('h%d' % n)

        for off in ["rx", "tx", "sg"]:
            cmd = "/sbin/ethtool --offload eth0 %s off" % off
            print(cmd)
            h.cmd(cmd)

        print("disable ipv6")
        h.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        h.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        h.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")
        h.cmd("sysctl -w net.ipv4.tcp_congestion_control=reno")
        h.cmd("iptables -I OUTPUT -p icmp --icmp-type destination-unreachable -j DROP")

        print("add mutlicast route")
        h.cmd("route add -net 224.0.0.0 netmask 224.0.0.0 eth0")

    sleep(2)

    print("Acceptors commands!")
    for i in range(2, len(topology.acceptors) + 2):
        cmd = [args.cli, args.acceptor, str(_THRIFT_BASE_PORT + i)]

        with open("commands/acceptor_commands.txt", "r") as f:
            print(" ".join(cmd))

            try:
                output = subprocess.check_output(cmd, stdin=f)
                print(output)
            except subprocess.CalledProcessError as e:
                print("Error happened issuing acceptors commands: [{}]".format(e))

    print("Coordinator commands!")
    learner_ids = []
    cmd = [args.cli, args.coordinator, str(_THRIFT_BASE_PORT + 1)]
    with open("commands/coordinator_commands.txt", "r") as f:
        print(" ".join(cmd))
        try:
            learner_id = i - 1
            learner_ids.append(learner_id)
            execute_command(cmd=[args.cli, args.acceptor, str(_THRIFT_BASE_PORT + i)],
                            rule='register_write datapath_id 0 %d' % learner_id)
            output = subprocess.check_output(cmd, stdin=f)
            print(output)
        except subprocess.CalledProcessError as e:
            print("Error happened issuing coordinator commands: [{}]".format(e))
    
    majority = 1 << learner_ids[0]
    if len(learner_ids) >= 2:
        majority = majority | (1 << learner_ids[1])

    print("Leaner commands!")
    base_swid = len(topology.acceptors) + 2
    for i in range(base_swid, base_swid + len(topology.learners)):
        cmd = [args.cli, args.learner, str(_THRIFT_BASE_PORT + i)]
        with open("commands/learner_commands.txt", "r") as f:
            print(" ".join(cmd))
            try:
                execute_command(cmd, rule='register_write majority_value 0 %d' % majority)
                output = subprocess.check_output(cmd, stdin=f)
                print(output)
            except subprocess.CalledProcessError as e:
                print("Error happened issuing learner commands: [{}]".format(e))

    if args.start_server:
        h1 = net.get('h1')
        h1.cmd("python ../app/httpServer.py --cfg ../app/paxos.cfg &")
        h2 = net.get('h2')
        h2.cmd("python ../app/backend.py --cfg ../app/paxos.cfg &")
        h3 = net.get('h3')
        h3.cmd("python ../app/backend.py --cfg ../app/paxos.cfg &")

    print("Ready !")

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    main()
