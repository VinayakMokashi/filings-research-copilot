# bandit: answer-arms (dev)

100 questions, 2,000 random orders, judge qwen-3.8-27b-p2.

| Arm | Model | Correct | Cost a question |
|---|---|---|---|
| strong | cerebras/gpt-oss-120b | 0.65 | $0.00195 |
| strong-low | cerebras/gpt-oss-120b | 0.63 | $0.00166 |
| fast | cerebras/qwen-3.8-27b | 0.61 | $0.00507 |

## λ = 0 (reward = correct - λ * dollars)

| Policy | Average reward a question | Spread over orders | Arm shares |
|---|---|---|---|
| fixed: strong | 0.6500 | | |
| fixed: strong-low | 0.6300 | | |
| fixed: fast | 0.6100 | | |
| oracle | 0.7100 | | |
| epsilon-greedy | 0.6299 | 0.5900 to 0.6600 | strong 0.39, strong-low 0.35, fast 0.27 |
| ucb1 | 0.6292 | 0.5900 to 0.6700 | strong 0.36, strong-low 0.33, fast 0.31 |

## λ = 100 (reward = correct - λ * dollars)

| Policy | Average reward a question | Spread over orders | Arm shares |
|---|---|---|---|
| fixed: strong | 0.4554 | | |
| fixed: strong-low | 0.4644 | | |
| fixed: fast | 0.1034 | | |
| oracle | 0.5301 | | |
| epsilon-greedy | 0.4254 | 0.3872 to 0.4562 | strong 0.44, strong-low 0.47, fast 0.09 |
| ucb1 | 0.4075 | 0.3640 to 0.4490 | strong 0.42, strong-low 0.44, fast 0.14 |

## λ = 300 (reward = correct - λ * dollars)

| Policy | Average reward a question | Spread over orders | Arm shares |
|---|---|---|---|
| fixed: strong | 0.0663 | | |
| fixed: strong-low | 0.1331 | | |
| fixed: fast | -0.9097 | | |
| oracle | 0.1704 | | |
| epsilon-greedy | 0.0219 | -0.0542 to 0.0877 | strong 0.36, strong-low 0.56, fast 0.08 |
| ucb1 | 0.0527 | 0.0088 to 0.0919 | strong 0.41, strong-low 0.54, fast 0.05 |
