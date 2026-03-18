// SPDX-License-Identifier: MIT
use clap::Parser;
use std::fs;
use std::io;
use std::net::IpAddr;

/// Threaded UDP relay for CMR+ GPS corrections
#[derive(Parser, Debug, Clone)]
#[command(name = "incorrections", version, about)]
pub struct Args {
    /// Source IP to filter packets from
    #[arg(long, default_value = "192.168.20.69")]
    pub source_ip: IpAddr,

    /// Local UDP port to listen on
    #[arg(long, default_value_t = 5019)]
    pub listen_port: u16,

    /// Local IP to bind to
    #[arg(long, default_value = "192.168.20.81")]
    pub bind_ip: IpAddr,

    /// Destination port for forwarded packets
    #[arg(long, default_value_t = 5019)]
    pub dest_port: u16,

    /// IP list config file
    #[arg(long, default_value = "sample.conf")]
    pub conf: String,

    /// Non-interactive mode: log stats to stdout
    #[arg(long)]
    pub no_interactive: bool,

    /// Stats print interval in seconds
    #[arg(long, default_value_t = 300)]
    pub interval: u64,
}

/// Parse an IP list config file.
///
/// Supports:
/// - Plain IPs (one per line)
/// - Samplicator format: `source:dest/port` (extracts dest IP)
/// - Comments starting with `#`
/// - Blank lines
pub fn parse_ip_list(filepath: &str) -> io::Result<Vec<IpAddr>> {
    let content = fs::read_to_string(filepath)?;
    Ok(parse_ip_list_content(&content))
}

/// Parse IP list from string content (for testability).
pub fn parse_ip_list_content(content: &str) -> Vec<IpAddr> {
    let mut dest_ips = Vec::new();

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }

        // Try plain IP first
        if let Ok(ip) = trimmed.parse::<IpAddr>() {
            dest_ips.push(ip);
            continue;
        }

        // Try samplicator format: source:dest/port
        if let Some(after_colon) = trimmed.split(':').nth(1) {
            let dest_part = after_colon.split('/').next().unwrap_or("");
            if let Ok(ip) = dest_part.parse::<IpAddr>() {
                dest_ips.push(ip);
            }
        }
    }

    dest_ips
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::Ipv4Addr;

    #[test]
    fn test_plain_ips() {
        let content = "10.0.0.1\n10.0.0.2\n";
        let result = parse_ip_list_content(content);
        assert_eq!(
            result,
            vec![
                IpAddr::V4(Ipv4Addr::new(10, 0, 0, 1)),
                IpAddr::V4(Ipv4Addr::new(10, 0, 0, 2)),
            ]
        );
    }

    #[test]
    fn test_comments_skipped() {
        let content = "# comment\n10.0.0.1\n# another\n";
        let result = parse_ip_list_content(content);
        assert_eq!(result, vec![IpAddr::V4(Ipv4Addr::new(10, 0, 0, 1))]);
    }

    #[test]
    fn test_empty_lines_skipped() {
        let content = "\n\n10.0.0.1\n\n";
        let result = parse_ip_list_content(content);
        assert_eq!(result, vec![IpAddr::V4(Ipv4Addr::new(10, 0, 0, 1))]);
    }

    #[test]
    fn test_samplicator_format() {
        let content = "10.20.23.230:10.20.66.109/5019\n";
        let result = parse_ip_list_content(content);
        assert_eq!(result, vec![IpAddr::V4(Ipv4Addr::new(10, 20, 66, 109))]);
    }

    #[test]
    fn test_invalid_lines_skipped() {
        let content = "not_an_ip\n10.0.0.1\ngarbagegarbage\n";
        let result = parse_ip_list_content(content);
        assert_eq!(result, vec![IpAddr::V4(Ipv4Addr::new(10, 0, 0, 1))]);
    }

    #[test]
    fn test_mixed_formats() {
        let content = "# header\n10.0.0.1\n192.168.1.1:10.0.0.2/5019\n\n10.0.0.3\n";
        let result = parse_ip_list_content(content);
        assert_eq!(
            result,
            vec![
                IpAddr::V4(Ipv4Addr::new(10, 0, 0, 1)),
                IpAddr::V4(Ipv4Addr::new(10, 0, 0, 2)),
                IpAddr::V4(Ipv4Addr::new(10, 0, 0, 3)),
            ]
        );
    }

    #[test]
    fn test_empty_content() {
        let result = parse_ip_list_content("");
        assert!(result.is_empty());
    }

    #[test]
    fn test_only_comments() {
        let content = "# comment\n# another\n";
        let result = parse_ip_list_content(content);
        assert!(result.is_empty());
    }
}
