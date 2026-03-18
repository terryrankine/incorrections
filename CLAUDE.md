# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**incorrections** — A threaded UDP relay for CMR+ GPS corrections data. Python drop-in replacement for [samplicator](https://github.com/sleinen/samplicator).

Listens on a UDP port for packets from a configured source IP, then fans out the data to a list of destination IPs using threads.

## Build & Install

```bash
pip install -e .          # editable install (pulls psutil)
pip install .             # regular install
incorrections             # run via entry point
```

## Running

```bash
# Interactive mode (curses TUI, Linux only)
python gps3.py --bind-ip 10.0.0.1 --source-ip 10.0.0.2

# Non-interactive mode (log keepalive stats every 5 min)
python gps3.py --no-interactive --interval 300

# All options
python gps3.py --source-ip IP --source-port PORT --bind-ip IP --dest-port PORT --conf FILE --no-interactive --interval SECS

# Send a test packet to localhost:5019
python fake-udp-packet.py
```

## Tests

```bash
python -m pytest test_gps3.py -v       # all tests
python -m pytest test_gps3.py -k uptime # single test class/pattern
```

## Dependencies

Managed in `pyproject.toml`. Runtime: `psutil>=5.9`. Dev: `pytest`.

## Architecture

Single-file application (`gps3.py`):

- **CLI** (`parse_args()`): argparse-based, all config via flags (source IP, bind IP, ports, conf file, interactive/log mode).
- **IP parsing** (`parse_ip_list()`): Reads conf file, returns list. Supports plain IPs and samplicator `source:dest/port` format.
- **UDP relay loop** (`main()`): Binds socket, receives packets, filters by source IP, fans out via `ThreadPool`.
- **Display modes**: `CursesDisplay` (interactive TUI) or `LogDisplay` (non-interactive, prints stats line every N seconds). Selected via `--no-interactive`.
- **Buffer stats** (`get_buffer()`): Uses `psutil.net_connections()` + `psutil.net_io_counters()` for cross-platform network stats.

## Config File Format (`sample.conf`)

One IP per line. Lines starting with `#` are comments. Samplicator format `source:dest/port` supported (dest IP extracted, port-per-IP not used — port is global).
