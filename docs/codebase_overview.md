# TurtleBot3 DRL Navigation — Codebase Overview

## What This Project Is

A ROS2 framework for training Deep Reinforcement Learning (DRL) agents to autonomously navigate a TurtleBot3 robot using LiDAR. Training runs in Gazebo simulation; models can be deployed directly to a real robot. Three algorithms are supported: **DQN**, **DDPG**, and **TD3**.

---

## Project Structure

```
turtlebot3_drlnav/
├── src/
│   ├── turtlebot3_drl/turtlebot3_drl/
│   │   ├── common/               # Shared utilities and config
│   │   │   ├── settings.py       # All hyperparameters (single source of truth)
│   │   │   ├── replaybuffer.py   # Experience replay buffer
│   │   │   ├── ounoise.py        # Ornstein-Uhlenbeck exploration noise
│   │   │   ├── logger.py         # CSV/file logging for training and testing
│   │   │   ├── storagemanager.py # Save/load model weights and buffers
│   │   │   ├── graph.py          # Real-time matplotlib training graphs
│   │   │   ├── visual.py         # Live neural network activation visualizer
│   │   │   └── utilities.py      # Miscellaneous helpers
│   │   ├── drl_environment/
│   │   │   ├── drl_environment.py     # Gazebo simulation environment node
│   │   │   ├── drl_environment_real.py # Real robot environment node
│   │   │   └── reward.py         # Reward function definitions
│   │   ├── drl_agent/
│   │   │   ├── drl_agent.py      # Main training/testing orchestrator
│   │   │   ├── off_policy_agent.py # Abstract base class for all algorithms
│   │   │   ├── dqn.py            # DQN implementation
│   │   │   ├── ddpg.py           # DDPG implementation
│   │   │   └── td3.py            # TD3 implementation
│   │   └── drl_gazebo/
│   │       └── drl_gazebo.py     # Goal spawning and management in Gazebo
│   ├── turtlebot3_msgs/          # Custom ROS2 message/service definitions
│   └── turtlebot3_simulations/   # Gazebo world files and models
├── util/
│   ├── clean_single_model.py
│   ├── purge_all_models.py
│   └── reward_graph.py
└── docs/
```

---

## System Architecture

### ROS2 Node Communication

```
DrlAgent
  │── calls service "step_comm"  ──→  DRLEnvironment
  │       request:  [action, previous_action]
  │       response: [state, reward, done, success, distance]
  │
  │── calls service "goal_comm"  ──→  DRLEnvironment
  │
  └── calls /pause_physics, /unpause_physics  ──→  Gazebo

DRLEnvironment
  │── subscribes: /scan (LiDAR), odom, goal_pose, obstacle/odom, /clock
  └── publishes:  cmd_vel

DRLGazebo
  │── subscribes: task_succeed, task_fail (from DRLEnvironment)
  │── publishes:  goal_pose
  └── calls:      spawn_entity, delete_entity, reset_simulation
```

### Training Loop

1. Wait for goal from the `gazebo_goals` node
2. Pause Gazebo, reset episode state
3. Unpause Gazebo, sleep 0.5 s
4. For each step:
   - If `total_steps < OBSERVE_STEPS` (25,000): take random action
   - Else: forward state through actor network
   - Add exploration noise during training
   - Call `step_comm` service → get `(next_state, reward, done)`
   - Store transition in replay buffer
   - If buffer has enough samples: sample batch and train networks
5. Log episode statistics, save model/graphs periodically

---

## State Space (44 dimensions)

| Index | Description | Range |
|-------|-------------|-------|
| 0–39  | 40 LiDAR distance samples (normalized) | [0, 1] |
| 40    | Distance to goal (normalized) | [0, 1] |
| 41    | Angle to goal (normalized) | [-1, 1] |
| 42    | Previous linear action | [-1, 1] |
| 43    | Previous angular action | [-1, 1] |

With frame stacking enabled (`ENABLE_STACKING=True`), this state is repeated over multiple timesteps, increasing the input dimension.

---

## Reward Function (Reward A)

```python
r_yaw       = -|goal_angle|                                       # heading alignment penalty
r_distance  = (2 * d0) / (d0 + d) - 1                            # progress reward [-1, 1]
r_obstacle  = -20  if min_obstacle_dist < 0.22 else 0             # proximity penalty
r_vlinear   = -((0.22 - action_linear) * 10) ** 2                # slow-speed penalty
r_vangular  = -(action_angular ** 2)                              # angular smoothness penalty

reward = r_yaw + r_distance + r_obstacle + r_vlinear + r_vangular - 1
reward += 2500   # SUCCESS: goal reached (distance < 0.20 m)
reward -= 2000   # COLLISION: obstacle or wall (distance < 0.13 m)
```

**Episode outcomes:**

| Code | Outcome |
|------|---------|
| 0 | UNKNOWN |
| 1 | SUCCESS |
| 2 | COLLISION_WALL |
| 3 | COLLISION_OBSTACLE |
| 4 | TIMEOUT |
| 5 | TUMBLE |

---

## Algorithms

### DQN (Deep Q-Network)
- **Action space**: Discrete, 5 actions
  ```
  [0.3, -1.0], [0.3, -0.5], [1.0, 0.0], [0.3, 0.5], [0.3, 1.0]
  # each entry: [linear_vel, angular_vel]
  ```
- **Exploration**: Epsilon-greedy with decay
- **Target update**: Hard copy every 1,000 steps
- **Loss**: MSE on TD error

### DDPG (Deep Deterministic Policy Gradient)
- **Action space**: Continuous 2D — linear and angular velocity
- **Networks**: Actor + Critic, each with a target copy
- **Exploration**: Ornstein-Uhlenbeck noise
- **Target update**: Soft update every step (`τ = 0.003`)
- **Loss**:
  - Critic: Smooth L1 on TD error
  - Actor: Negative mean Q-value (maximize Q)

### TD3 (Twin Delayed DDPG)
- All features of DDPG plus:
  - **Dual critics** (Q1, Q2): target uses `min(Q1, Q2)` to reduce overestimation
  - **Delayed policy update**: Actor updated every 2 critic updates
  - **Target policy smoothing**: Clipped noise added to target actions
    ```python
    noise = clamp(randn * 0.2, -0.5, 0.5)
    a' = clamp(actor_target(s') + noise, -1, 1)
    ```

---

## Neural Network Architectures

### Actor (DDPG / TD3)
```
Input (44) → Dense(512) + ReLU → Dense(512) + ReLU → Dense(2) + Tanh
```
Output: continuous action in [-1, 1] for [linear_vel, angular_vel]

### Critic (DDPG / TD3)
```
State(44) → Dense(256) + ReLU ─┐
                                 ├→ Dense(512) + ReLU → Dense(512) + ReLU → Dense(1)
Action(2) → Dense(256) + ReLU ─┘
```
Output: scalar Q-value

**TD3** duplicates the critic (Q1, Q2).

### DQN Network
```
Input (44) → Dense(512) + ReLU → Dense(512) + ReLU → Dense(5)
```
Output: Q-values for each of the 5 discrete actions

**Weight init**: Xavier uniform; biases initialized to 0.01.

---

## Key Configuration (`common/settings.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `EPISODE_TIMEOUT_SECONDS` | 50 | Max time per episode |
| `SPEED_LINEAR_MAX` | 0.22 m/s | Max forward speed |
| `SPEED_ANGULAR_MAX` | 2.0 rad/s | Max rotation speed |
| `LIDAR_DISTANCE_CAP` | 3.5 m | LiDAR range cap |
| `THRESHOLD_COLLISION` | 0.13 m | Collision distance |
| `THRESHOLD_GOAL` | 0.20 m | Goal success distance |
| `BATCH_SIZE` | 128 | Training batch size |
| `BUFFER_SIZE` | 1,000,000 | Replay buffer capacity |
| `LEARNING_RATE` | 0.003 | AdamW learning rate |
| `TAU` | 0.003 | Soft update coefficient |
| `DISCOUNT_FACTOR` | 0.99 | Gamma (future discount) |
| `OBSERVE_STEPS` | 25,000 | Pure-random steps before training |
| `HIDDEN_SIZE` | 512 | Neurons per hidden layer |
| `MODEL_STORE_INTERVAL` | — | Save model every N episodes |
| `ENABLE_STACKING` | False | Frame stacking (multi-timestep state) |
| `ENABLE_BACKWARD` | — | Allow robot backward movement |
| `ENABLE_DYNAMIC_GOALS` | — | Adaptive goal difficulty |

---

## Model Storage

Saved to: `src/turtlebot3_drl/model/[hostname]/[algo]_[id]_stage[N]/`

Saved files:
- `*.pt` — PyTorch network weights
- Pickled agent object (architecture)
- Pickled replay buffer
- Pickled graph data (episode history)

Old checkpoints are automatically pruned; intervals of ~1,000 episodes are kept.

---

## Running the System

### Simulation Training
```bash
# Terminal 1 — launch Gazebo world
ros2 launch turtlebot3_gazebo turtlebot3_drl_stage4.launch.py

# Terminal 2 — goal manager
ros2 run turtlebot3_drl gazebo_goals

# Terminal 3 — environment node
ros2 run turtlebot3_drl environment

# Terminal 4 — start training
ros2 run turtlebot3_drl train_agent ddpg   # or td3 / dqn
```

### Testing a Saved Model
```bash
ros2 run turtlebot3_drl test_agent ddpg "ddpg_0" 500
```

### Real Robot Deployment
```bash
ros2 run turtlebot3_drl real_environment
ros2 run turtlebot3_drl real_agent ddpg ddpg_0 1000
```

### Utilities
```bash
python3 util/reward_graph.py          # Plot training curves
python3 util/clean_single_model.py    # Clean up a single model directory
python3 util/purge_all_models.py      # Remove all saved models
```

---

## Training Stages

10 Gazebo worlds with increasing complexity. Higher stages add more static obstacles, dynamic (moving) obstacles (up to 6), and tighter corridors. Models trained on lower stages are typically used as a starting point for higher stages.

---

## Notable Design Choices

- **Observation normalization**: All LiDAR values and goal distances normalized to [0, 1]; angles normalized to [-1, 1]. Raw velocities are also normalized before being fed to the network.
- **Gradient clipping**: Gradient norm clipped to ≤ 2.0 for training stability.
- **OU noise decay**: Exploration noise sigma decays over time (`max_sigma → min_sigma`).
- **Dynamic goals**: When `ENABLE_DYNAMIC_GOALS=True`, goal placement radius shrinks/grows based on recent success rate, providing curriculum-like training.
- **Gazebo pause/unpause**: Simulation is paused between steps to decouple physics speed from training throughput.
