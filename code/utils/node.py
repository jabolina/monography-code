from mininet.node import Docker
from p4_mininet import P4Switch


class P4xosSwitch(P4Switch):
    def __init__(self, name, **params):
        super(P4xosSwitch, self).__init__(name, **params)


class P4xosHost(Docker):
    def __init__(self, name, dimage, dcmd=None, **params):
        super(P4xosHost, self).__init__(name, dimage, dcmd, **params)

        for off in ["rx", "tx", "sg"]:
            cmd = "/sbin/ethtool --offload eth0 %s off" % off
            self.cmd(cmd)

        self.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")
