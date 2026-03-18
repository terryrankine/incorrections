import io
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

# Mock curses before importing gps3 (curses unavailable on Windows)
sys.modules['curses'] = MagicMock()

import gps3


class TestUptime(unittest.TestCase):

    def test_zero_seconds(self):
        self.assertEqual(gps3.uptime(0), '')

    def test_seconds_only(self):
        self.assertEqual(gps3.uptime(45), '45s')

    def test_one_second(self):
        self.assertEqual(gps3.uptime(1), '1s')

    def test_minutes_and_seconds(self):
        self.assertEqual(gps3.uptime(125), '2m, 5s')

    def test_hours(self):
        self.assertEqual(gps3.uptime(3661), '1h, 1m, 1s')

    def test_days(self):
        self.assertEqual(gps3.uptime(90061), '1d, 1h, 1m, 1s')

    def test_weeks(self):
        self.assertEqual(gps3.uptime(694861), '1w, 1d, 1h, 1m')

    def test_truncates_to_four_units(self):
        result = gps3.uptime(694861 + 1)
        self.assertEqual(result, '1w, 1d, 1h, 1m')

    def test_large_value(self):
        result = gps3.uptime(1209600)  # exactly 2 weeks
        self.assertEqual(result, '2w')


class TestParseIpList(unittest.TestCase):

    def _write_conf(self, content):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_plain_ips(self):
        path = self._write_conf('10.0.0.1\n10.0.0.2\n')
        result = gps3.parse_ip_list(path)
        self.assertEqual(result, ['10.0.0.1', '10.0.0.2'])
        os.unlink(path)

    def test_comments_skipped(self):
        path = self._write_conf('# comment\n10.0.0.1\n# another\n')
        result = gps3.parse_ip_list(path)
        self.assertEqual(result, ['10.0.0.1'])
        os.unlink(path)

    def test_empty_lines_skipped(self):
        path = self._write_conf('\n\n10.0.0.1\n\n')
        result = gps3.parse_ip_list(path)
        self.assertEqual(result, ['10.0.0.1'])
        os.unlink(path)

    def test_samplicator_format(self):
        path = self._write_conf('10.20.23.230:10.20.66.109/5019\n')
        result = gps3.parse_ip_list(path)
        self.assertEqual(result, ['10.20.66.109'])
        os.unlink(path)

    def test_invalid_lines_skipped(self):
        path = self._write_conf('not_an_ip\n10.0.0.1\ngarbagegarbage\n')
        result = gps3.parse_ip_list(path)
        self.assertEqual(result, ['10.0.0.1'])
        os.unlink(path)

    def test_mixed_formats(self):
        path = self._write_conf(
            '# header\n'
            '10.0.0.1\n'
            '192.168.1.1:10.0.0.2/5019\n'
            '\n'
            '10.0.0.3\n'
        )
        result = gps3.parse_ip_list(path)
        self.assertEqual(result, ['10.0.0.1', '10.0.0.2', '10.0.0.3'])
        os.unlink(path)

    def test_empty_file(self):
        path = self._write_conf('')
        result = gps3.parse_ip_list(path)
        self.assertEqual(result, [])
        os.unlink(path)

    def test_only_comments(self):
        path = self._write_conf('# comment\n# another\n')
        result = gps3.parse_ip_list(path)
        self.assertEqual(result, [])
        os.unlink(path)


class TestSend(unittest.TestCase):

    def test_successful_send(self):
        mock_socket = MagicMock()
        result = gps3.send('10.0.0.1', b'test data', mock_socket, 5019)
        self.assertEqual(result, ('10.0.0.1', True))
        mock_socket.sendto.assert_called_once_with(b'test data', ('10.0.0.1', 5019))

    def test_failed_send(self):
        mock_socket = MagicMock()
        mock_socket.sendto.side_effect = OSError('send failed')
        result = gps3.send('10.0.0.1', b'test data', mock_socket, 5019)
        self.assertEqual(result, ('10.0.0.1', False))


class TestGetBuffer(unittest.TestCase):

    @patch('gps3.psutil')
    def test_port_found(self, mock_psutil):
        mock_conn = MagicMock()
        mock_conn.laddr.port = 5019
        mock_psutil.net_connections.return_value = [mock_conn]
        result = gps3.get_buffer(5019)
        self.assertEqual(result, ['udp', True])

    @patch('gps3.psutil')
    def test_port_not_found(self, mock_psutil):
        mock_conn = MagicMock()
        mock_conn.laddr.port = 8080
        mock_psutil.net_connections.return_value = [mock_conn]
        result = gps3.get_buffer(5019)
        self.assertEqual(result, ['udp', False])

    @patch('gps3.psutil')
    def test_no_connections(self, mock_psutil):
        mock_psutil.net_connections.return_value = []
        result = gps3.get_buffer(5019)
        self.assertEqual(result, ['udp', False])

    @patch('gps3.psutil')
    def test_access_denied(self, mock_psutil):
        mock_psutil.AccessDenied = psutil_access_denied
        mock_psutil.NoSuchProcess = psutil_no_such_process
        mock_psutil.net_connections.side_effect = psutil_access_denied(1234)
        result = gps3.get_buffer(5019)
        self.assertEqual(result, ['udp', False])


class TestCalcPercent(unittest.TestCase):

    def test_all_ok(self):
        self.assertEqual(gps3.calc_percent(100, 0), 100.0)

    def test_all_errors(self):
        self.assertEqual(gps3.calc_percent(0, 100), 0.0)

    def test_mixed(self):
        self.assertEqual(gps3.calc_percent(75, 25), 75.0)

    def test_zero_both(self):
        self.assertEqual(gps3.calc_percent(0, 0), 100.0)


class TestLogDisplay(unittest.TestCase):

    def test_prints_on_interval(self):
        display = gps3.LogDisplay(interval=0)
        stats = {
            'uptime': '1m',
            'receive_ok': 10, 'receive_errors': 1, 'receive_perc': 90.91,
            'transmit_ok': 9, 'transmit_errors': 0, 'transmit_perc': 100.0,
            'send_ok': 18, 'send_errors': 0, 'send_perc': 100.0,
            'buffer': ['udp', True],
            'delay': 0.5,
            'ip_list_file': 'sample.conf', 'ip_count': 2,
            'binding_ip': '10.0.0.1', 'dest_port': 5019,
            'source_ip': '10.0.0.2', 'listen_port': 5019,
        }
        # Should not raise
        display.screen(stats)

    def test_skips_before_interval(self):
        display = gps3.LogDisplay(interval=9999)
        display.last_print = time.time()
        stats = {
            'uptime': '1m',
            'receive_ok': 0, 'receive_errors': 0, 'receive_perc': 100.0,
            'transmit_ok': 0, 'transmit_errors': 0, 'transmit_perc': 100.0,
            'send_ok': 0, 'send_errors': 0, 'send_perc': 100.0,
            'buffer': ['udp', False],
            'delay': 0,
            'ip_list_file': 'sample.conf', 'ip_count': 0,
            'binding_ip': '10.0.0.1', 'dest_port': 5019,
            'source_ip': '10.0.0.2', 'listen_port': 5019,
        }
        captured = io.StringIO()
        sys.stdout = captured
        display.screen(stats)
        sys.stdout = sys.__stdout__
        self.assertEqual(captured.getvalue(), '')

    def test_output_format(self):
        display = gps3.LogDisplay(interval=0)
        stats = {
            'uptime': '5m',
            'receive_ok': 100, 'receive_errors': 5, 'receive_perc': 95.24,
            'transmit_ok': 95, 'transmit_errors': 0, 'transmit_perc': 100.0,
            'send_ok': 190, 'send_errors': 0, 'send_perc': 100.0,
            'buffer': ['udp', True],
            'delay': 1.234,
            'ip_list_file': 'sample.conf', 'ip_count': 2,
            'binding_ip': '10.0.0.1', 'dest_port': 5019,
            'source_ip': '10.0.0.2', 'listen_port': 5019,
        }
        captured = io.StringIO()
        sys.stdout = captured
        display.screen(stats)
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIn('uptime=5m', output)
        self.assertIn('rx_ok=100', output)
        self.assertIn('delay=1.234s', output)
        self.assertIn('ips=2', output)


# Helpers for mocking psutil exceptions
class psutil_access_denied(Exception):
    def __init__(self, pid=None):
        self.pid = pid

class psutil_no_such_process(Exception):
    def __init__(self, pid=None):
        self.pid = pid


if __name__ == '__main__':
    unittest.main()
