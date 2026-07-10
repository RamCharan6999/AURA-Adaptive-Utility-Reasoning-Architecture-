# Snapshot of the robot's sensed world state.
# Published by whatever drives the world: the scenario manager in the demo,
# a real sensor-fusion node on hardware. AURA and the planner only read it.
std_msgs/Header header
float32 battery_level              # 0.0 - 1.0
float32 human_proximity            # metres to nearest human
float32 obstacle_density           # 0.0 - 1.0
float32 localization_confidence    # 0.0 - 1.0
string  mission_priority           # normal / urgent / emergency
float32 sensor_health              # 0.0 - 1.0 (reserved)
