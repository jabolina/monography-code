import argparse
import subprocess
from subprocess import PIPE
from time import sleep

from mininet.cli import CLI
from mininet.log import info, setLogLevel
from mininet.net import Containernet
from mininet.topo import Topo
from p4_mininet import P4Switch, P4Host

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

_THRIFT_BASE_PORT = 22222

_NUM_OF_ACCEPTORS = 3
_NUM_OF_LEARNERS = 1


class Topology(Topo):
    def __init__(self, sw_path, acceptor, coordinator, learner, **kwargs):

        Topo.__init__(self, **kwargs)

        self.acceptors = []
        self.containers = []
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
        for a in range(2, _NUM_OF_ACCEPTORS + 2):
            self.acceptors.append(self.addSwitch('s%d' % a,
                                                 sw_path=sw_path,
                                                 json_path=acceptor,
                                                 thrift_port=_THRIFT_BASE_PORT + a,
                                                 pcap_dump=False,
                                                 log_console=True,
                                                 verbose=True,
                                                 device_id=a))

        # Learners
        base_swid = len(self.acceptors) + 2
        for l in range(base_swid, base_swid + _NUM_OF_LEARNERS):
            self.learners.append(self.addSwitch('s%d' % l,
                                                sw_path=sw_path,
                                                json_path=learner,
                                                thrift_port=_THRIFT_BASE_PORT + l,
                                                pcap_dump=True,
                                                log_console=True,
                                                verbose=True,
                                                device_id=l))

        # Creating the containers
        for c in [1, 2, 3, 4]:
            self.containers.append(self.addDocker('d%d' % c))

        d1, d2, d3, d4 = self.containers

        # Container 1 and 4 connected only to coordinator
        self.addLink(d1, s1)
        self.addLink(d4, s1)

        # Containers 2 and 3 connects to all learners
        for i, s in enumerate(self.learners):
            for j, c in enumerate([d2, d3]):
                self.addLink(c, s,
                             intfName1='eth{0}'.format(i + 1),
                             params1={
                                 'ip': '10.0.{0}.{1}/8'.format(i + 1, j + 2)
                             })

        # All acceptors connected into the coordinator and into all learners
        for a in self.acceptors:
            self.addLink(a, s1)
            for l in self.learners:
                self.addLink(a, l)


def topology(sw_path, acceptor, coordinator, learner):
    """
            Will create the 4 containers for the applications, then will create
            the acceptors and learners.

            When everything is created, the links between the nodes will be
            created.

            The default topology contains 4 hosts and 5 switches. In the
            switches 1 will be the coordinator, 3 will acceptors and 1 will be
            the learner.

        :param sw_path: The switch used (simple_switch)
        :param acceptor: The path to the acceptor.json definition
        :param coordinator: The path to the coordinator.json definition
        :param learner: The path to the learner.json definition
        :param kwargs: Options for the Mininet topology
        :returns Containernet instance, acceptors, containers, learners
        """
    net = Containernet(host=P4Host, switch=P4Switch, controller=None)

    acceptors = []
    containers = []
    learners = []

    info('**** Adding coordinator switch ****\n')
    s1 = net.addSwitch('s1',
                       sw_path=sw_path,
                       json_path=coordinator,
                       thrift_port=_THRIFT_BASE_PORT + 1,
                       pcap_dump=False,
                       log_console=True,
                       verbose=True,
                       device_id=1)

    info('**** Adding %d acceptors ****\n' % _NUM_OF_ACCEPTORS)
    for a in range(2, _NUM_OF_ACCEPTORS + 2):
        acceptors.append(net.addSwitch('s%d' % a,
                                       sw_path=sw_path,
                                       json_path=acceptor,
                                       thrift_port=_THRIFT_BASE_PORT + a,
                                       pcap_dump=False,
                                       log_console=True,
                                       verbose=True,
                                       device_id=a))

    info('**** Adding %d learners ****\n' % _NUM_OF_LEARNERS)
    base_swid = len(acceptors) + 2
    for l in range(base_swid, base_swid + _NUM_OF_LEARNERS):
        learners.append(net.addSwitch('s%d' % l,
                                      sw_path=sw_path,
                                      json_path=learner,
                                      thrift_port=_THRIFT_BASE_PORT + l,
                                      pcap_dump=True,
                                      log_console=True,
                                      verbose=True,
                                      device_id=l))

    info('**** Adding containers ****\n')
    for c in [1, 2, 3, 4]:
        containers.append(net.addDocker('d%d' % c, ip='10.0.0.%d' % c, dimage='ubuntu:trusty'))

    d1, d2, d3, d4 = containers

    info('**** Creating links ****\n')
    net.addLink(d1, s1)
    net.addLink(d4, s1)

    # Containers 2 and 3 connects to all learners
    for i, s in enumerate(learners):
        for j, c in enumerate([d2, d3]):
            net.addLink(c, s,
                        intfName1='eth{0}'.format(i + 1),
                        params1={
                            'ip': '10.0.{0}.{1}/8'.format(i + 1, j + 2)
                        })

    # All acceptors connected into the coordinator and into all learners
    for a in acceptors:
        net.addLink(a, s1)
        for l in learners:
            net.addLink(a, l)

    return net, containers, acceptors, learners


def execute_command(cmd, rule=''):
    p = subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate(rule)
    if out:
        print(out)
    if err:
        print(err)

def main():
    net, containers, acceptors, learners = \
        topology(args.behavioral_exe, args.acceptor, args.coordinator, args.learner)

    net.start()

    for n in range(1, len(containers) + 1):
        h = net.get('d%d' % n)

        for off in ["rx", "tx", "sg"]:
            cmd = "/sbin/ethtool --offload eth0 %s off" % off
            info(cmd + '\n')
            h.cmd(cmd)

        info("**** Disabling IPv6 for container %d ****\n" % n)
        h.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        h.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        h.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")
        h.cmd("sysctl -w net.ipv4.tcp_congestion_control=reno")
        h.cmd("iptables -I OUTPUT -p icmp --icmp-type destination-unreachable -j DROP")

        info("**** Add mutlicast route for container %d ****\n" % n)
        h.cmd("route add -net 224.0.0.0 netmask 224.0.0.0 eth0")

    sleep(2)

    info("**** Acceptors commands! ****\n")
    for i in range(2, len(acceptors) + 2):
        cmd = [args.cli, args.acceptor, str(_THRIFT_BASE_PORT + i)]

        with open("acceptor_commands.txt", "r") as f:
            info(" ".join(cmd) + '\n')

            try:
                output = subprocess.check_output(cmd, stdin=f)
                print(output)
            except subprocess.CalledProcessError as e:
                print("Error happened issuing acceptors commands: [{}]".format(e))

    info("**** Coordinator commands! ****\n")
    cmd = [args.cli, args.coordinator, str(_THRIFT_BASE_PORT + 1)]
    with open("coordinator_commands.txt", "r") as f:
        print(" ".join(cmd))
        try:
            output = subprocess.check_output(cmd, stdin=f)
            print(output)
        except subprocess.CalledProcessError as e:
            print("Error happened issuing coordinator commands: [{}]".format(e))

    learner_ids = []
    for i in range(2, len(acceptors) + 2):
        learner_id = i - 1
        learner_ids.append(learner_id)
        execute_command(cmd=[args.cli, args.acceptor, str(_THRIFT_BASE_PORT + i)],
                        rule='register_write datapath_id 0 %d' % learner_id)

    majority = 1 << learner_ids[0]
    if len(learner_ids) >= 2:
        id1 = learner_ids[1]
        majority = majority | (1 << id1)

    info("**** Leaner commands! ****\n")
    base_swid = len(acceptors) + 2
    for i in range(base_swid, base_swid + len(learners)):
        cmd = [args.cli, args.learner, str(_THRIFT_BASE_PORT + i)]
        with open("learner_commands.txt", "r") as f:
            print(" ".join(cmd))
            try:
                execute_command(cmd, rule='register_write majority_value 0 %d' % majority)
                output = subprocess.check_output(cmd, stdin=f)
                print(output)
            except subprocess.CalledProcessError as e:
                print("Error happened issuing learner commands: [{}]".format(e))

    if args.start_server:
        h1 = net.get('d1')
        h1.cmd("python ../app/httpServer.py --cfg ../app/paxos.cfg &")
        h2 = net.get('d2')
        h2.cmd("python ../app/backend.py --cfg ../app/paxos.cfg &")
        h3 = net.get('d3')
        h3.cmd("python ../app/backend.py --cfg ../app/paxos.cfg &")

    info("Ready!\n")

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    main()
