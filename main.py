#!/usr/bin/env python

from time import time
from signal import SIGINT

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.util import pmonitor, dumpNodeConnections
from mininet.log import setLogLevel


class SingleSwitchTopo(Topo):
    def build(self, bw, delay, loss):
        switch = self.addSwitch('s1')
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        self.addLink(h1, switch, bw=bw, delay=delay, loss=loss, use_htb=True)
        self.addLink(h2, switch, bw=bw, delay=delay, loss=loss, use_htb=True)


def run_test():
    topo = SingleSwitchTopo(bw=100, delay='50ms', loss=0)
    net = Mininet(topo=topo, link=TCLink, autoStaticArp=True)
    net.start()
    h1, h2 = net.getNodeByName('h1', 'h2')
    dumpNodeConnections(net.hosts)

    popens = {}
    popens[h1] = h1.popen(['./quic-go-cc/server/server',
                           '-addr', ':4242',
                           '-cert', 'cert.pem',
                           '-key', 'priv.key'])
    popens[h2] = h2.popen(['./quic-go-cc/client/client',
                           '-addr', '{}:4242'.format(h1.IP()),
                           '-cert', 'cert.pem'])

    seconds = 3
    endTime = time() + seconds
    print("monitoring...")
    for h, line in pmonitor(popens, timeoutms=500):
        if h:
            print('%s: %s' % (h.name, line))
            if time() >= endTime:
                for p in popens.values():
                    p.send_signal(SIGINT)

    net.stop()


if __name__ == "__main__":
    setLogLevel('info')
    run_test()
