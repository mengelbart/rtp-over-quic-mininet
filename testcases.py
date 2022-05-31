import json
import os
import subprocess

from pathlib import Path
from subprocess import TimeoutExpired, PIPE
from time import time, localtime, strftime
from threading import Timer

from mininet.clean import cleanup
from mininet.net import Mininet
from mininet.util import pmonitor, dumpNodeConnections

from topology import DumbbellTopo


class Implementation:
    name: str
    description: str
    sender_binary: str
    receiver_binary: str
    transport: str
    rtp_cc: str
    scream_pacer: str
    quic_cc: str
    rtcp_feedback: str
    out_dir: str
    input: str
    output: str
    cpu_profile: bool
    goroutine_profile: bool
    heap_profile: bool
    allocs_profile: bool
    block_profile: bool
    mutex_profile: bool

    def __init__(self,
                 name: str,
                 description: str,
                 sender_binary: str,
                 receiver_binary: str,
                 transport: str,
                 rtp_cc: str,
                 scream_pacer: str,
                 quic_cc: str,
                 rtcp_feedback: str,
                 out_dir: str,
                 input: str,
                 output: str,
                 cpu_profile: bool = False,
                 goroutine_profile: bool = False,
                 heap_profile: bool = False,
                 allocs_profile: bool = False,
                 block_profile: bool = False,
                 mutex_profile: bool = False,
                 ):
        self.name = name
        self.description = description
        self.sender_binary = sender_binary
        self.receiver_binary = receiver_binary
        self.transport = transport
        self.rtp_cc = rtp_cc
        self.scream_pacer = scream_pacer
        self.quic_cc = quic_cc
        self.rtcp_feedback = rtcp_feedback
        self.out_dir = out_dir
        self.input = input
        self.output = output

        self.cpu_profile = cpu_profile
        self.goroutine_profile = goroutine_profile
        self.heap_profile = heap_profile
        self.allocs_profile = allocs_profile
        self.block_profile = block_profile
        self.mutex_profile = mutex_profile

    def send_cmd(self, addr, port) -> [str]:
        cmd = [
            self.sender_binary,
            'send',
            '--addr', '{}:{}'.format(addr, port),
            '--source', self.input,
            '--rtp-dump', '{}/sender_rtp.log'.format(self.out_dir),
            '--rtcp-dump', '{}/sender_rtcp.log'.format(self.out_dir),
            '--cc-dump', '{}/cc.log'.format(self.out_dir),
            '--qlog', '{}'.format(self.out_dir),
            '--transport', self.transport,
            '--rtp-cc', self.rtp_cc,
            '--scream-pacer', self.scream_pacer,
            '--quic-cc', self.quic_cc,
            ]
        if self.cpu_profile:
            cmd.append('--pprof-cpu')
            cmd.append('{}/sender_cpu.pprof'.format(self.out_dir))
        if self.goroutine_profile:
            cmd.append('--pprof-goroutine')
            cmd.append('{}/sender_goroutine.pprof'.format(self.out_dir))
        if self.heap_profile:
            cmd.append('--pprof-heap')
            cmd.append('{}/sender_heap.pprof'.format(self.out_dir))
        if self.allocs_profile:
            cmd.append('--pprof-allocs')
            cmd.append('{}/sender_allocs.pprof'.format(self.out_dir))
        if self.block_profile:
            cmd.append('--pprof-block')
            cmd.append('{}/sender_block.pprof'.format(self.out_dir))
        if self.mutex_profile:
            cmd.append('--pprof-mutex')
            cmd.append('{}/sender_mutex.pprof'.format(self.out_dir))
        return cmd

    def receive_cmd(self, addr, port) -> [str]:
        cmd = [
            self.receiver_binary,
            'receive',
            '--addr', '{}:{}'.format(addr, port),
            '--sink', self.output,
            '--rtp-dump', '{}/receiver_rtp.log'.format(self.out_dir),
            '--rtcp-dump', '{}/receiver_rtcp.log'.format(self.out_dir),
            '--qlog', '{}'.format(self.out_dir),
            '--transport', self.transport,
            '--rtcp-feedback', self.rtcp_feedback,
            ]
        if self.cpu_profile:
            cmd.append('--pprof-cpu')
            cmd.append('{}/receiver_cpu.pprof'.format(self.out_dir))
        if self.goroutine_profile:
            cmd.append('--pprof-goroutine')
            cmd.append('{}/receiver_goroutine.pprof'.format(self.out_dir))
        if self.heap_profile:
            cmd.append('--pprof-heap')
            cmd.append('{}/receiver_heap.pprof'.format(self.out_dir))
        if self.allocs_profile:
            cmd.append('--pprof-allocs')
            cmd.append('{}/receiver_allocs.pprof'.format(self.out_dir))
        if self.block_profile:
            cmd.append('--pprof-block')
            cmd.append('{}/receiver_block.pprof'.format(self.out_dir))
        if self.mutex_profile:
            cmd.append('--pprof-mutex')
            cmd.append('{}/receiver_mutex.pprof'.format(self.out_dir))
        return cmd


def update_link(i1, i2, bw, is_first, log):
    def update():
        print('found interfaces: {}, {}'.format(i1, i2))
        t = int(time() * 1000)
        for i in [i1, i2]:
            qdisc_cmd = 'tc qdisc {} dev {} root handle 1: tbf rate {}Mbit burst 15000 latency {}'.format(
                        'add' if is_first else 'change',
                        i,
                        bw,
                        '300ms',
                    )
            netem_cmd = 'tc qdisc {} dev {} parent 1: handle 2: netem delay {} loss {}'.format(
                        'add' if is_first else 'change',
                        i,
                        '50ms',
                        0,
                    )
            print('run cmd: {}'.format(qdisc_cmd))
            print('run cmd: {}'.format(netem_cmd))
            subprocess.run(qdisc_cmd.split(' '))
            subprocess.run(netem_cmd.split(' '))
        with open(log, 'a') as f:
            f.write('{}, {}\n'.format(t, bw * 1_000_000))

    return update


class VariableAvailableCapacitySingleFlow():
    implementation: Implementation
    out_dir: str
    timers: []

    def __init__(
            self,
            implementation: Implementation,
            out_dir: str,
            ):
        self.implementation = implementation
        self.out_dir = out_dir
        self.timers = []

    @staticmethod
    def net() -> Mininet:
        topo = DumbbellTopo(n=1)
        net = Mininet(topo=topo, autoStaticArp=True)
        dumpNodeConnections(net.hosts)
        return net

    def start_traffic_control(self, s1, s2):
        reference = 1.0
        tc_config = [
                {'start_time': 0, 'ratio': 1.0},
                {'start_time': 40, 'ratio': 2.5},
                {'start_time': 60, 'ratio': 0.6},
                {'start_time': 80, 'ratio': 1.0},
                {'start_time': 100, 'ratio': 1.0},
                ]

        is_first = True
        for c in tc_config:
            t = Timer(
                    c['start_time'],
                    update_link(
                        s1.intf('ls1-eth2'),
                        s2.intf('rs1-eth2'),
                        c['ratio'] * reference,
                        is_first,
                        os.path.join(self.out_dir, 'capacity.log'),
                        ),
                    )
            is_first = False
            self.timers.append(t)
            t.start()

    def stop_traffic_control(self):
        for timer in self.timers:
            timer.cancel()

    def dump_config(self, start):
        config_file = os.path.join(self.out_dir, 'config.json')
        with open(config_file, 'w', encoding='utf-8') as file:
            config = {
                    'basetime': int(start * 1000),
                } | self.implementation.__dict__
            json.dump(config, file, ensure_ascii=False, indent=4)

    def run(self):
        net = self.net()
        net.start()
        h1, h2 = net.getNodeByName('l0', 'r0')
        s1, s2 = net.getNodeByName('ls1', 'rs1')
        dumpNodeConnections(net.hosts)

        try:
            Path(self.out_dir).mkdir(parents=True, exist_ok=True)

            start = time()
            seconds = 100
            endTime = start + seconds
            print('run until {}'.format(strftime('%X', localtime(endTime))))

            self.dump_config(start)
            self.start_traffic_control(s1, s2)

            send_cmd = self.implementation.receive_cmd(h1.IP(), "4242")
            receive_cmd = self.implementation.send_cmd(h1.IP(), "4242")

            print(' '.join(send_cmd))
            print(' '.join(receive_cmd))

            popens = {}
            popens[h1] = h1.popen(send_cmd, stderr=PIPE, stdout=PIPE)
            popens[h2] = h2.popen(receive_cmd, stderr=PIPE, stdout=PIPE)

            for h, line in pmonitor(popens, timeoutms=1000):
                t = time()
                if h:
                    print('{}: {}: {}'.format(int(t * 1000), h.name, line))
                if t >= endTime:
                    print('time over')
                    break

            ok = True

        except (KeyboardInterrupt, Exception) as e:
            if isinstance(e, KeyboardInterrupt):
                print("got KeyboardInterrupt, stopping mnet")
            else:
                print(e)
            ok = False
        finally:
            print('stopping...')
            for p in popens.values():
                p.terminate()
                try:
                    print('waiting for {}'.format(p))
                    p.wait(3)
                    print('wait done')
                except TimeoutExpired:
                    p.kill()
                    print('killed {}'.format(p))
            net.stop()
            self.stop_traffic_control()
            cleanup()
            return ok
