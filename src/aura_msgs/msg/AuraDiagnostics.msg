# Live middleware health. Published by aura_core_node at 1 Hz.
std_msgs/Header header
string  scenario
float32 planner_hz
float32 explanation_hz
float32 latency_ms                 # decision stamp -> explanation publish
bool    planner_alive
bool    dashboard_connected
