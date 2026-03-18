// SPDX-License-Identifier: MIT
use crate::config::Args;
use crate::stats::{format_uptime, Stats};
use chrono::Local;
use std::net::{IpAddr, SocketAddr};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::net::UdpSocket;
use tokio::sync::Mutex;

/// Run the UDP relay loop.
pub async fn run_relay(
    socket: Arc<UdpSocket>,
    args: &Args,
    dest_ips: &[IpAddr],
    stats: Arc<Mutex<Stats>>,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut buf = vec![0u8; 32768];
    let source_ip = args.source_ip;

    let dest_addrs: Vec<SocketAddr> = dest_ips
        .iter()
        .map(|ip| SocketAddr::new(*ip, args.dest_port))
        .collect();

    let mut last_stats_print = Instant::now();
    let stats_interval = Duration::from_secs(args.interval);
    let no_interactive = args.no_interactive;

    loop {
        // Receive with timeout, or catch Ctrl+C
        let recv_result = tokio::select! {
            r = tokio::time::timeout(Duration::from_millis(1100), socket.recv_from(&mut buf)) => r,
            _ = tokio::signal::ctrl_c() => {
                let s = stats.lock().await;
                println!("\nShutting down...");
                print_stats(&s, dest_ips.len());
                return Ok(());
            }
        };

        let mut s = stats.lock().await;

        match recv_result {
            Ok(Ok((len, addr))) => {
                s.receive_ok += 1;

                if addr.ip() == source_ip {
                    s.last_receive = Some(Instant::now());
                    s.transmit_ok += 1;

                    let data = &buf[..len];

                    // Fan out to all destinations
                    for dest in &dest_addrs {
                        match socket.send_to(data, dest).await {
                            Ok(_) => s.send_ok += 1,
                            Err(_) => s.send_errors += 1,
                        }
                    }
                }
            }
            Ok(Err(_)) => {
                s.receive_errors += 1;
            }
            Err(_) => {
                // Timeout
                s.receive_errors += 1;
            }
        }

        // Print stats in non-interactive mode
        if no_interactive && last_stats_print.elapsed() >= stats_interval {
            last_stats_print = Instant::now();
            print_stats(&s, dest_ips.len());
        }
    }
}

fn print_stats(stats: &Stats, ip_count: usize) {
    let now = Local::now();
    println!(
        "[{}] uptime={} \
         rx_ok={} rx_fail={} rx%={} \
         tx_ok={} tx_fail={} tx%={} \
         send_ok={} send_fail={} send%={} \
         delay={:.3}s ips={}",
        now.format("%Y-%m-%d %H:%M:%S"),
        format_uptime(stats.uptime_seconds()),
        stats.receive_ok,
        stats.receive_errors,
        stats.receive_percent(),
        stats.transmit_ok,
        stats.transmit_errors,
        stats.transmit_percent(),
        stats.send_ok,
        stats.send_errors,
        stats.send_percent(),
        stats.delay_secs(),
        ip_count,
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_relay_forwards_matching_packet() {
        let receiver = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        let receiver_addr = receiver.local_addr().unwrap();

        let relay_socket = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        let relay_addr = relay_socket.local_addr().unwrap();
        let relay_socket = Arc::new(relay_socket);

        let sender = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        let sender_addr = sender.local_addr().unwrap();

        let dest_ips = vec![receiver_addr.ip()];
        let stats = Arc::new(Mutex::new(Stats::new()));

        let args = Args {
            source_ip: sender_addr.ip(),
            listen_port: relay_addr.port(),
            bind_ip: "127.0.0.1".parse().unwrap(),
            dest_port: receiver_addr.port(),
            conf: "sample.conf".to_string(),
            no_interactive: true,
            interval: 9999,
        };

        let relay_socket_clone = Arc::clone(&relay_socket);
        let stats_clone = Arc::clone(&stats);

        let relay_handle = tokio::spawn(async move {
            let _ = run_relay(relay_socket_clone, &args, &dest_ips, stats_clone).await;
        });

        sender
            .send_to(b"test corrections data", relay_addr)
            .await
            .unwrap();

        let mut recv_buf = vec![0u8; 1024];
        let result =
            tokio::time::timeout(Duration::from_secs(2), receiver.recv_from(&mut recv_buf)).await;

        assert!(result.is_ok(), "Should receive forwarded packet");
        let (len, _) = result.unwrap().unwrap();
        assert_eq!(&recv_buf[..len], b"test corrections data");

        let s = stats.lock().await;
        assert!(s.receive_ok >= 1);
        assert!(s.transmit_ok >= 1);
        assert!(s.send_ok >= 1);

        relay_handle.abort();
    }

    #[tokio::test]
    async fn test_relay_ignores_wrong_source() {
        let receiver = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        let receiver_addr = receiver.local_addr().unwrap();

        let relay_socket = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        let relay_addr = relay_socket.local_addr().unwrap();
        let relay_socket = Arc::new(relay_socket);

        let sender = UdpSocket::bind("127.0.0.1:0").await.unwrap();

        let dest_ips = vec![receiver_addr.ip()];
        let stats = Arc::new(Mutex::new(Stats::new()));

        let args = Args {
            source_ip: "10.99.99.99".parse().unwrap(),
            listen_port: relay_addr.port(),
            bind_ip: "127.0.0.1".parse().unwrap(),
            dest_port: receiver_addr.port(),
            conf: "sample.conf".to_string(),
            no_interactive: true,
            interval: 9999,
        };

        let relay_socket_clone = Arc::clone(&relay_socket);
        let stats_clone = Arc::clone(&stats);

        let relay_handle = tokio::spawn(async move {
            let _ = run_relay(relay_socket_clone, &args, &dest_ips, stats_clone).await;
        });

        sender
            .send_to(b"should be ignored", relay_addr)
            .await
            .unwrap();

        let mut recv_buf = vec![0u8; 1024];
        let result =
            tokio::time::timeout(Duration::from_millis(500), receiver.recv_from(&mut recv_buf))
                .await;
        assert!(
            result.is_err(),
            "Should NOT receive packet from wrong source"
        );

        tokio::time::sleep(Duration::from_millis(100)).await;
        let s = stats.lock().await;
        assert!(s.receive_ok >= 1);
        assert_eq!(s.transmit_ok, 0);
        assert_eq!(s.send_ok, 0);

        relay_handle.abort();
    }
}
