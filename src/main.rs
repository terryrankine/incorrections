// SPDX-License-Identifier: MIT
use clap::Parser;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::net::UdpSocket;
use tokio::sync::Mutex;

mod config;
mod relay;
mod stats;

use config::Args;
use relay::run_relay;
use stats::Stats;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let dest_ips = config::parse_ip_list(&args.conf)?;
    if dest_ips.is_empty() {
        eprintln!("Error: no valid IPs found in {}", args.conf);
        std::process::exit(1);
    }

    let bind_addr = SocketAddr::new(args.bind_ip, args.listen_port);
    let socket = UdpSocket::bind(bind_addr).await?;
    let socket = Arc::new(socket);
    let stats = Arc::new(Mutex::new(Stats::new()));

    println!(
        "incorrections UDP relay - listening on {} (source filter: {})",
        bind_addr, args.source_ip
    );
    println!(
        "Forwarding to {} destination(s) on port {}",
        dest_ips.len(),
        args.dest_port
    );

    if args.no_interactive {
        println!("Non-interactive mode, stats every {}s", args.interval);
    }

    run_relay(socket, &args, &dest_ips, stats).await
}
