# Running statistics over the session. Published by metrics_node at 1 Hz.
std_msgs/Header header
uint32  total_decisions
uint32  policy_switches
uint32  conflicts_detected
uint32  three_way_conflicts
uint32  uncertain_decisions
float32 avg_latency_ms
float32 avg_score_gap
string  policy_frequency_json      # {"SAFE_MODE": n, ...}
