#!/usr/bin/env python

import json
import os
from time import time, sleep
from subprocess import TimeoutExpired
from pathlib import Path
from threading import Timer

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.util import pmonitor, dumpNodeConnections


class Implementation:
    name: str
    description: str
    sender_binary: str
    receiver_binary: str
    rtp_cc: str
    quic_cc: str
    rtcp_feedback: str

    def __init__(self,
                 name: str,
                 description: str,
                 sender_binary: str,
                 receiver_binary: str,
                 rtp_cc: str,
                 quic_cc: str,
                 rtcp_feedback: str,
                 ):
        self.name = name
        self.description = description
        self.sender_binary = sender_binary
        self.receiver_binary = receiver_binary
        self.rtp_cc = rtp_cc
        self.quic_cc = quic_cc
        self.rtcp_feedback = rtcp_feedback


class SingleSwitchTopo(Topo):
    def build(self, bw, delay, loss):
        switch = self.addSwitch('s1')
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        self.addLink(h1, switch, bw=bw, delay=delay, loss=loss, use_tbf=True)
        self.addLink(h2, switch, bw=bw, delay=delay, loss=loss, use_tbf=True)


def run_test(implementation, src, dst, out_dir):
    try:
        topo = SingleSwitchTopo(bw=1, delay='1ms', loss=0)
        net = Mininet(topo=topo, link=TCLink, autoStaticArp=True)
        net.start()
        h1, h2 = net.getNodeByName('h1', 'h2')
        dumpNodeConnections(net.hosts)
    except Exception as e:
        print(e)
        return False

    receive_cmd = [
            implementation.receiver_binary,
            'receive',
            '--addr', '{}:4242'.format(h1.IP()),
            '--sink', dst,
            '--rtcp-feedback', implementation.rtcp_feedback,
            '--rtp-dump', '{}/receiver_rtp.log'.format(out_dir),
            '--rtcp-dump', '{}/receiver_rtcp.log'.format(out_dir),
            '--qlog', '{}'.format(out_dir),
            ]
    send_cmd = [
            implementation.sender_binary,
            'send',
            '--addr', '{}:4242'.format(h1.IP()),
            '--source', 'sintel.y4m',
            '--rtp-cc', implementation.rtp_cc,
            '--quic-cc', implementation.quic_cc,
            '--rtp-dump', '{}/sender_rtp.log'.format(out_dir),
            '--rtcp-dump', '{}/sender_rtcp.log'.format(out_dir),
            '--cc-dump', '{}/cc.log'.format(out_dir),
            '--qlog', '{}'.format(out_dir),
            ]

    print(' '.join(receive_cmd))
    print(' '.join(send_cmd))
    try:
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        start = time()
        seconds = 120
        endTime = start + seconds
        t1 = Timer(60.0, update_link(h1.defaultIntf(), h2.defaultIntf(), 0.5))
        t1.start()
        t2 = Timer(90.0, update_link(h1.defaultIntf(), h2.defaultIntf(), 1))
        t2.start()

        popens = {}
        popens[h1] = h1.popen(receive_cmd)
        popens[h2] = h2.popen(send_cmd)

        try:
            out, err = popens[h1].communicate(timeout=1)
            print(out)
            print(err)
        except TimeoutExpired:
            pass
        try:
            out, err = popens[h2].communicate(timeout=1)
            print(out)
            print(err)
        except TimeoutExpired:
            pass

        print('run until {}'.format(endTime))
        sleep(120)
        for h, line in pmonitor(popens, timeoutms=1000):
            t = time()
            if h:
                print('{}: {}: {}'.format(t, h.name, line))
            if t >= endTime:
                print('time over')
                break

        for p in popens.values():
            p.terminate()
            try:
                print('waiting for {}'.format(p))
                p.wait(3)
            except TimeoutExpired:
                p.kill()
                print('killed {}'.format(p))
        ok = True

    except (KeyboardInterrupt, Exception) as e:
        if isinstance(e, KeyboardInterrupt):
            print("got KeyboardInterrupt, stopping mnet")
        else:
            print(e)
        ok = False
    finally:
        print('stopping...')
        net.stop()
        return ok


def update_link(i1, i2, bw):
    def update():
        print('found interfaces: {}, {}'.format(i1, i2))
        i1.config(bw=bw)
        i2.config(bw=bw)

    return update


if __name__ == "__main__":
    setLogLevel('info')
    # run_test()
    with open('./implementations.json') as json_file:
        data = json.load(json_file)

    src = 'sintel.y4m'
    dst = 'output.y4m'
    base_out_dir = 'data'

    count = 0
    for k, v in data.items():
        # run_test(k, v)
        implementation = Implementation(
            k,
            v['description'],
            v['sender'],
            v['receiver'],
            v['rtp-cc'],
            v['quic-cc'],
            v['rtcp-feedback'],
        )
        out_dir = os.path.join(base_out_dir, k)
        ok = run_test(implementation, src, dst, out_dir)
        if not ok:
            break
        count += 1

    print()
    print('finished {} out of {} test runs'.format(count, len(data)))
