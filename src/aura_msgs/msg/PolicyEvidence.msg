# Generic evidence any planner attaches to one candidate policy.
# This is the middleware contract: utility, rule-based, RL, or LLM planners
# all publish this shape, which is what makes AURA planner-agnostic.
string  policy_name
string  evidence_type              # utility / rule / rl / llm
float32 score                      # normalized utility
float32 confidence                 # 0.0 - 1.0
string  attributes_json            # {"safety": s, "time": t, "energy": e}
string  raw_evidence_json          # planner-specific extras
