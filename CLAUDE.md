# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**incorrections** — An async UDP relay for CMR+ GPS corrections data. Replacement for [samplicator](https://github.com/sleinen/samplicator).

Listens on a UDP port for packets from a configured source IP, then fans out the data to a list of destination IPs. Written in Rust with tokio async runtime. Legacy Python version (`gps3.py`) is retained.

## Build & Test (Rust)

```bash
cargo build                    # debug build
cargo build --release          # release build
cargo test                     # run all unit tests
cargo test config              # run tests in config module
cargo test stats               # run tests in stats module
cargo test relay               # run tests in relay module (integration)
```

## Running

```bash
# Non-interactive mode (log keepalive stats every 5 min)
cargo run -- --no-interactive --bind-ip 10.0.0.1 --source-ip 10.0.0.2

# All CLI options
incorrections --source-ip IP --listen-port PORT --bind-ip IP --dest-port PORT --conf FILE --no-interactive --interval SECS
```

## Legacy Python

```bash
pip install -e .               # install with psutil dep
python gps3.py --no-interactive --bind-ip 10.0.0.1 --source-ip 10.0.0.2
python -m pytest test_gps3.py -v
```

## Architecture (Rust)

```
src/
  main.rs    — Entry point: CLI parsing, socket setup, startup banner
  config.rs  — Args struct (clap derive), parse_ip_list() config parser
  stats.rs   — Stats struct, calc_percent(), format_uptime()
  relay.rs   — run_relay() async loop: receive, filter, fan-out, stats printing
```

- **Async I/O**: tokio runtime with `UdpSocket::recv_from` / `send_to`, timeout via `tokio::time::timeout`
- **Source filtering**: Only forwards packets from `--source-ip`, silently drops others
- **Stats output**: Non-interactive mode prints a keepalive line every `--interval` seconds
- **No curses TUI in Rust version** — non-interactive log mode only

## Dependencies (Rust)

Managed in `Cargo.toml`: `tokio` (async runtime + UDP), `clap` (CLI), `chrono` (timestamps).

## Config File Format (`sample.conf`)

One IP per line. Lines starting with `#` are comments. Samplicator format `source:dest/port` supported (dest IP extracted, port-per-IP not used — port is global).
