#!/usr/bin/env python3
import argparse
import ipaddress
import socket
import sys
import time
from multiprocessing.pool import ThreadPool

import psutil

##################################################################
# If you are reading this than what are you doing with your life #
# Made with coffee by Ben0 over several night shifts             #
# Relays UDP data to a specified list of IP addresses            #
#                                                                #
# see sample.conf for the file lines format.                     #
##################################################################


def parse_ip_list(filepath):
    '''
    Parse ip_list file and return list of destination IPs.
    Supports plain IPs and samplicator format (source:dest/port).
    Ignores comments (#) and blank lines.
    '''
    dest_ips = []
    with open(filepath, 'r') as f:
        for line in f.readlines():
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith('#'):
                continue
            # Try plain IP first, fall back to samplicator format source:dest/port
            try:
                ipaddress.ip_address(stripped_line)
                dest_ips.append(stripped_line)
            except ValueError:
                try:
                    split_line = stripped_line.split(':')
                    dest_ip = split_line[1].split('/')[0]
                    ipaddress.ip_address(dest_ip)
                    dest_ips.append(dest_ip)
                except (ValueError, IndexError):
                    pass
    return dest_ips


def send(ip, data, s, dest_port):
    '''
    Send {data} to {ip} using {s} (socket)
    This is threaded
    '''
    try:
        s.settimeout(0.01)
        s.sendto(data, (ip, dest_port))
        return (ip, True)
    except OSError:
        return (ip, False)


def uptime(seconds):
    '''
    Calculates uptime in weeks, days, hours, minutes, seconds
    '''
    intervals = (
        ('w', 604800),  # 60 * 60 * 24 * 7
        ('d', 86400),   # 60 * 60 * 24
        ('h', 3600),    # 60 * 60
        ('m', 60),
        ('s', 1),
    )
    result = []
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            result.append("{}{}".format(int(value), name))
    return ', '.join(result[:4])


def get_buffer(port):
    '''
    Checks if our UDP port is active using psutil.
    Returns [proto, active_bool].
    '''
    try:
        for conn in psutil.net_connections(kind='udp'):
            if conn.laddr and conn.laddr.port == port:
                return ['udp', True]
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass
    return ['udp', False]


def calc_percent(ok, errors):
    total = ok + errors
    if total == 0:
        return 100.0
    return round((ok / total) * 100, 2)


class CursesDisplay:
    '''
    Curses display for the current statistics (interactive mode)
    '''

    def __init__(self):
        import curses as _curses
        self.curses = _curses
        self.stdscr = _curses.initscr()
        _curses.start_color()
        _curses.use_default_colors()
        _curses.curs_set(0)
        _curses.init_pair(1, _curses.COLOR_RED, -1)

    def screen(self, stats):
        c = self.curses
        self.stdscr.clear()
        self.stdscr.border(0)
        self.stdscr.addstr(0, 32, "Minesystems' UDP Relay")

        box1 = c.newwin(3, 28, 1, 29)
        box2 = c.newwin(5, 28, 4, 1)
        box3 = c.newwin(5, 28, 4, 29)
        box4 = c.newwin(5, 28, 4, 57)
        box5 = c.newwin(4, 28, 9, 1)
        box6 = c.newwin(4, 28, 9, 29)
        box7 = c.newwin(4, 28, 9, 57)
        box8 = c.newwin(3, 28, 1, 1)
        box9 = c.newwin(3, 28, 1, 57)

        for box in [box1, box2, box3, box4, box5, box6, box7, box8, box9]:
            box.box()

        box1.addstr(0, 11, "Uptime")
        box2.addstr(0, 6, "Corrections In")
        box3.addstr(0, 6, "Corrections Out")
        box4.addstr(0, 5, "Corrections Sent")
        box5.addstr(0, 12, "List")
        box6.addstr(0, 10, "Binding")
        box7.addstr(0, 11, "Buffer")
        box8.addstr(0, 10, "Warning")
        box9.addstr(0, 12, "Delay")

        box1.addstr(1, 1, stats['uptime'].center(26))

        box2.addstr(1, 1, '      OK: {}'.format(stats['receive_ok']))
        box2.addstr(2, 1, '    Fail: {}'.format(stats['receive_errors']))
        box2.addstr(3, 1, ' Percent: {}%'.format(stats['receive_perc']))

        box3.addstr(1, 1, '      OK: {}'.format(stats['transmit_ok']))
        box3.addstr(2, 1, '    Fail: {}'.format(stats['transmit_errors']))
        box3.addstr(3, 1, ' Percent: {}%'.format(stats['transmit_perc']))

        box4.addstr(1, 1, '      OK: {}'.format(stats['send_ok']))
        box4.addstr(2, 1, '    Fail: {}'.format(stats['send_errors']))
        box4.addstr(3, 1, ' Percent: {}%'.format(stats['send_perc']))

        box5.addstr(1, 1, '    File: {}'.format(stats['ip_list_file']))
        box5.addstr(2, 1, '     IPs: {}'.format(stats['ip_count']))

        box6.addstr(1, 1, '  Local:{}:{}'.format(stats['binding_ip'], stats['dest_port']))
        box6.addstr(2, 1, ' Remote:{}:{}'.format(stats['source_ip'], stats['listen_port']))

        buf = stats['buffer']
        status = 'ACTIVE' if buf[1] else 'INACTIVE'
        box7.addstr(1, 1, '  Port: {}'.format(stats['listen_port']))
        box7.addstr(2, 1, '  Status: {}'.format(status))

        box8.addstr(1, 1, 'DO NOT CLOSE'.center(26), c.color_pair(1))

        box9.addstr(1, 1, str(round(stats['delay'], 3)).center(26))

        self.stdscr.refresh()
        for box in [box1, box2, box3, box4, box5, box6, box7, box8, box9]:
            box.refresh()

    def cleanup(self):
        self.curses.endwin()


class LogDisplay:
    '''
    Non-interactive display: prints a keepalive stats line every interval.
    '''

    def __init__(self, interval=300):
        self.interval = interval
        self.last_print = time.time()
        # Print header
        print("incorrections UDP relay started (non-interactive mode, {}s interval)".format(interval))

    def screen(self, stats):
        now = time.time()
        if now - self.last_print >= self.interval:
            self.last_print = now
            print(
                "[{}] uptime={} "
                "rx_ok={} rx_fail={} rx%={} "
                "tx_ok={} tx_fail={} tx%={} "
                "send_ok={} send_fail={} send%={} "
                "delay={:.3f}s ips={}".format(
                    time.strftime('%Y-%m-%d %H:%M:%S'),
                    stats['uptime'],
                    stats['receive_ok'], stats['receive_errors'], stats['receive_perc'],
                    stats['transmit_ok'], stats['transmit_errors'], stats['transmit_perc'],
                    stats['send_ok'], stats['send_errors'], stats['send_perc'],
                    stats['delay'], stats['ip_count']
                ),
                flush=True
            )

    def cleanup(self):
        pass


def parse_args():
    parser = argparse.ArgumentParser(description='Threaded UDP relay for CMR+ GPS corrections')
    parser.add_argument('--source-ip', default='192.168.20.69', help='Source IP to filter packets from')
    parser.add_argument('--listen-port', type=int, default=5019, help='Local UDP port to listen on')
    parser.add_argument('--bind-ip', default='192.168.20.81', help='Local IP to bind to')
    parser.add_argument('--dest-port', type=int, default=5019, help='Destination port for forwarded packets')
    parser.add_argument('--conf', default='sample.conf', help='IP list config file')
    parser.add_argument('--no-interactive', action='store_true', help='Non-interactive mode: log stats to stdout')
    parser.add_argument('--interval', type=int, default=300, help='Stats print interval in seconds (default: 300)')
    return parser.parse_args()


def main():
    args = parse_args()

    dest_ip_list = parse_ip_list(args.conf)
    if not dest_ip_list:
        print("Error: no valid IPs found in {}".format(args.conf), file=sys.stderr)
        sys.exit(1)

    # Stats
    receive_ok = 0
    receive_errors = 0
    transmit_ok = 0
    transmit_errors = 0
    send_ok = 0
    send_errors = 0
    timestamp = time.time()
    prev_delay = 0

    # Thread pool
    pool = ThreadPool(processes=max(len(dest_ip_list), 1))

    # Socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8388608)
    s.bind((args.bind_ip, args.listen_port))

    # Display
    if args.no_interactive:
        _display = LogDisplay(interval=args.interval)
    else:
        _display = CursesDisplay()

    try:
        while True:
            # Receive UDP on socket
            try:
                s.settimeout(1.1)
                data, addr = s.recvfrom(32768)
                receive_ok += 1
            except socket.timeout:
                receive_errors += 1
                addr = None

            try:
                if addr and addr[0] == args.source_ip:
                    prev_delay = time.time()
                    transmit_ok += 1
                    results = [pool.apply_async(send, args=(ip, data, s, args.dest_port)) for ip in dest_ip_list]
                    output = [r.get() for r in results]
                    for i in output:
                        if i[1]:
                            send_ok += 1
                        else:
                            send_errors += 1
            except (OSError, TypeError):
                transmit_errors += 1

            uptime_seconds = time.time() - timestamp
            stats = {
                'uptime': uptime(uptime_seconds),
                'receive_ok': receive_ok,
                'receive_errors': receive_errors,
                'receive_perc': calc_percent(receive_ok, receive_errors),
                'transmit_ok': transmit_ok,
                'transmit_errors': transmit_errors,
                'transmit_perc': calc_percent(transmit_ok, transmit_errors),
                'send_ok': send_ok,
                'send_errors': send_errors,
                'send_perc': calc_percent(send_ok, send_errors),
                'buffer': get_buffer(args.listen_port),
                'delay': time.time() - prev_delay if prev_delay else 0,
                'ip_list_file': args.conf,
                'ip_count': len(dest_ip_list),
                'binding_ip': args.bind_ip,
                'dest_port': args.dest_port,
                'source_ip': args.source_ip,
                'listen_port': args.listen_port,
            }

            _display.screen(stats)
    except KeyboardInterrupt:
        pass
    finally:
        _display.cleanup()
        pool.terminate()
        s.close()


if __name__ == '__main__':
    main()
