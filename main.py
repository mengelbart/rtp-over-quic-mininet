#!/usr/bin/env python

import argparse
import json
import os

from mininet.log import setLogLevel

from testcases import Implementation, VariableAvailableCapacitySingleFlow


def main():
    with open('./implementations.json') as json_file:
        data = json.load(json_file)

    tests = [k for k in range(len(data))]

    parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    parser.add_argument('-t', '--tests', nargs='+', metavar='N', default=tests,
                        help='test cases to run, list of keys from the dict'
                             ' in the implementations file')
    parser.add_argument('--implementations', default='implementations.json',
                        help='JSON file containing a dictionary of names to'
                             ' test implemnetations')
    parser.add_argument('--loglevel', default='info',
                        choices=['info', 'debug'],
                        help='log level for mininet')
    parser.add_argument('--input', default='input.y4m', help='input video'
                        ' file')
    parser.add_argument('--output', default='output.y4m', help='output video'
                        ' file')
    parser.add_argument('--dir', default='data/', help='output directory'
                        ' for logfiles')
    parser.add_argument('--pprof-cpu', action=argparse.BooleanOptionalAction,
                        help='create CPU profiles')
    parser.add_argument('--pprof-goroutine',
                        action=argparse.BooleanOptionalAction,
                        help='create goroutine profiles')
    parser.add_argument('--pprof-heap', action=argparse.BooleanOptionalAction,
                        help='create heap profiles')
    parser.add_argument('--pprof-allocs',
                        action=argparse.BooleanOptionalAction,
                        help='create allocs profiles')
    parser.add_argument('--pprof-block', action=argparse.BooleanOptionalAction,
                        help='create block profiles')
    parser.add_argument('--pprof-mutex', action=argparse.BooleanOptionalAction,
                        help='create mutex profiles')
    args = parser.parse_args()

    print(args)
    setLogLevel(args.loglevel)

    chosen_tests = [int(k) for k in args.tests]

    src = args.input
    dst = args.output
    base_out_dir = args.dir

    count = 0
    for k, v in enumerate(data):
        if int(k) not in chosen_tests:
            continue

        out_dir = os.path.join(base_out_dir, str(k))
        implementation = Implementation(
            k,
            v['description'],
            v['sender'],
            v['receiver'],
            v['transport'],
            v['rtp-cc'],
            v['scream-pacer'],
            v['quic-cc'],
            v['rtcp-feedback'],
            out_dir,
            src,
            dst,
            args.pprof_cpu,
            args.pprof_goroutine,
            args.pprof_heap,
            args.pprof_allocs,
            args.pprof_block,
            args.pprof_mutex,
        )
        tc = VariableAvailableCapacitySingleFlow(implementation, out_dir)
        ok = tc.run()
        if not ok:
            print('failed to run test: {}: {}, stopping execution'
                  .format(count, k))
            break
        count += 1

    print()
    print('finished {} out of {} test runs'.format(count, len(data)))


if __name__ == "__main__":
    main()
