cmake_minimum_required(VERSION 3.8)
project(aura_msgs)

find_package(ament_cmake REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/RobotContext.msg"
  "msg/AuraWeights.msg"
  "msg/PolicyEvidence.msg"
  "msg/AuraDecision.msg"
  "msg/AuraExplanation.msg"
  "msg/AuraDiagnostics.msg"
  "msg/AuraMetrics.msg"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
