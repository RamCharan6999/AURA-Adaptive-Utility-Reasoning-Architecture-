# Everything AURA can say about one decision, computed at runtime.
std_msgs/Header header

# Trigger — what happened
string  trigger_event
float32 trigger_value
string  trigger_unit
string  trigger_description

# Conflict — what tension was detected
bool    conflict_detected
string  conflict_qas
string  conflict_description
bool    three_way_conflict

# Decision — what was chosen
string  selected_policy
float32 selected_score
float32 confidence

# Tradeoff — why it won, at what price (exact: benefit - cost == score_gap)
string  dominant_qa
float32 dominant_weight
string  dominant_reason
float32 benefit_value
string  benefit_description
float32 cost_value
string  cost_description
string  gap_decomposition_json     # {"safety": c1, "time": c2, "energy": c3}

# Rejected alternative
string  rejected_policy
float32 rejected_score
float32 score_gap
string  rejection_reason
bool    uncertain_decision         # score_gap < 0.1

# Transition
bool    policy_changed
string  previous_policy
string  changed_context_variable
float32 changed_context_delta
string  change_reason
bool    context_unchanged          # operator-driven switch, world unchanged

# Human readable
string  explanation_text
