// SPDX-License-Identifier: MIT
use std::time::Instant;

/// Tracks relay statistics.
#[derive(Debug)]
pub struct Stats {
    pub receive_ok: u64,
    pub receive_errors: u64,
    pub transmit_ok: u64,
    pub transmit_errors: u64,
    pub send_ok: u64,
    pub send_errors: u64,
    pub start_time: Instant,
    pub last_receive: Option<Instant>,
}

impl Stats {
    pub fn new() -> Self {
        Self {
            receive_ok: 0,
            receive_errors: 0,
            transmit_ok: 0,
            transmit_errors: 0,
            send_ok: 0,
            send_errors: 0,
            start_time: Instant::now(),
            last_receive: None,
        }
    }

    pub fn uptime_seconds(&self) -> u64 {
        self.start_time.elapsed().as_secs()
    }

    pub fn delay_secs(&self) -> f64 {
        self.last_receive
            .map(|t| t.elapsed().as_secs_f64())
            .unwrap_or(0.0)
    }

    pub fn receive_percent(&self) -> f64 {
        calc_percent(self.receive_ok, self.receive_errors)
    }

    pub fn transmit_percent(&self) -> f64 {
        calc_percent(self.transmit_ok, self.transmit_errors)
    }

    pub fn send_percent(&self) -> f64 {
        calc_percent(self.send_ok, self.send_errors)
    }
}

pub fn calc_percent(ok: u64, errors: u64) -> f64 {
    let total = ok + errors;
    if total == 0 {
        return 100.0;
    }
    ((ok as f64 / total as f64) * 10000.0).round() / 100.0
}

/// Format seconds into human-readable uptime string (e.g., "1w, 2d, 3h, 4m").
/// Shows at most 4 units.
pub fn format_uptime(mut seconds: u64) -> String {
    const INTERVALS: &[(&str, u64)] = &[
        ("w", 604800),
        ("d", 86400),
        ("h", 3600),
        ("m", 60),
        ("s", 1),
    ];

    let mut parts = Vec::new();
    for &(name, count) in INTERVALS {
        let value = seconds / count;
        if value > 0 {
            seconds -= value * count;
            parts.push(format!("{}{}", value, name));
        }
    }

    parts.truncate(4);
    parts.join(", ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_uptime_zero() {
        assert_eq!(format_uptime(0), "");
    }

    #[test]
    fn test_uptime_seconds() {
        assert_eq!(format_uptime(45), "45s");
    }

    #[test]
    fn test_uptime_one_second() {
        assert_eq!(format_uptime(1), "1s");
    }

    #[test]
    fn test_uptime_minutes_seconds() {
        assert_eq!(format_uptime(125), "2m, 5s");
    }

    #[test]
    fn test_uptime_hours() {
        assert_eq!(format_uptime(3661), "1h, 1m, 1s");
    }

    #[test]
    fn test_uptime_days() {
        assert_eq!(format_uptime(90061), "1d, 1h, 1m, 1s");
    }

    #[test]
    fn test_uptime_weeks() {
        assert_eq!(format_uptime(694861), "1w, 1d, 1h, 1m");
    }

    #[test]
    fn test_uptime_truncates_to_four() {
        assert_eq!(format_uptime(694862), "1w, 1d, 1h, 1m");
    }

    #[test]
    fn test_uptime_large_value() {
        assert_eq!(format_uptime(1209600), "2w");
    }

    #[test]
    fn test_calc_percent_all_ok() {
        assert_eq!(calc_percent(100, 0), 100.0);
    }

    #[test]
    fn test_calc_percent_all_errors() {
        assert_eq!(calc_percent(0, 100), 0.0);
    }

    #[test]
    fn test_calc_percent_mixed() {
        assert_eq!(calc_percent(75, 25), 75.0);
    }

    #[test]
    fn test_calc_percent_zero_both() {
        assert_eq!(calc_percent(0, 0), 100.0);
    }

    #[test]
    fn test_stats_new() {
        let stats = Stats::new();
        assert_eq!(stats.receive_ok, 0);
        assert_eq!(stats.receive_errors, 0);
        assert_eq!(stats.transmit_ok, 0);
        assert_eq!(stats.transmit_errors, 0);
        assert_eq!(stats.send_ok, 0);
        assert_eq!(stats.send_errors, 0);
        assert!(stats.last_receive.is_none());
    }

    #[test]
    fn test_stats_percentages_initial() {
        let stats = Stats::new();
        assert_eq!(stats.receive_percent(), 100.0);
        assert_eq!(stats.transmit_percent(), 100.0);
        assert_eq!(stats.send_percent(), 100.0);
    }

    #[test]
    fn test_stats_delay_no_receive() {
        let stats = Stats::new();
        assert_eq!(stats.delay_secs(), 0.0);
    }
}
