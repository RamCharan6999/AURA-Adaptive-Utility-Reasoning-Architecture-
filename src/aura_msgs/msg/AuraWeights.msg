# Operator preference weights over quality attributes. Must sum to 1.0.
# Command channel: publish here (CLI, console sliders, or another node)
# or use `ros2 param set /utility_planner w_safety 0.2` — both converge.
std_msgs/Header header
float32 w_safety
float32 w_time
float32 w_energy
