# incorrections
Threaded UDP relay for CMR+ GPS corrections

Designed to be a python drop in replacement for [samplicator](https://github.com/sleinen/samplicator)

* Listens on specified UDP port for data from a specified source IP
* Forwards data to each IP in the config file on the specified port
* Interactive mode (curses TUI) or non-interactive mode (periodic log output)

## Install

```bash
pip install .
```

Requires Python 3.6+ and [psutil](https://pypi.org/project/psutil/).

## Usage

### Interactive mode (curses TUI, Linux only)

```bash
incorrections --bind-ip 10.0.0.1 --source-ip 10.0.0.2
```

### Non-interactive mode (headless / systemd)

```bash
incorrections --no-interactive --interval 300 --bind-ip 10.0.0.1 --source-ip 10.0.0.2
```

Prints a keepalive stats line every `--interval` seconds (default 300).

### All options

```
--source-ip     Source IP to filter packets from (default: 192.168.20.69)
--listen-port   Local UDP port to listen on (default: 5019)
--bind-ip       Local IP to bind to (default: 192.168.20.81)
--dest-port     Destination port for forwarded packets (default: 5019)
--conf          IP list config file (default: sample.conf)
--no-interactive  Non-interactive mode: log stats to stdout
--interval      Stats print interval in seconds (default: 300)
```

### IP List File Format

Default file: `sample.conf`

Plain IPs (one per line):
```
10.20.66.109
10.20.66.110
```

Or samplicator format (`source:dest/port`):
```
10.20.23.230:10.20.66.109/5019
```

Lines beginning with `#` are comments. Port-per-IP is not used — port is set globally via `--dest-port`.

## Tests

```bash
pip install pytest
python -m pytest test_gps3.py -v
```
