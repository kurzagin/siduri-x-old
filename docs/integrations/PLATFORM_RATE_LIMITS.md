# Platform rate-limit policy

Provider response limits, polling intervals, quotas, and retry-after values are authoritative. YouTube uses the returned polling interval and bounded page-token polling. Twitch uses bounded reconnect backoff. Local ingress applies per-author rate and repeated-text suppression. Never retry an outbound action after an unknown send result without operator reconciliation.
