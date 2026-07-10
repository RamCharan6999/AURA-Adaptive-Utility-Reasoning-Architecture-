# One planner decision: the winner plus every rejected candidate.
std_msgs/Header header
aura_msgs/PolicyEvidence selected
aura_msgs/PolicyEvidence[] alternatives   # score-sorted, best first
bool   policy_changed
string previous_policy
