# Deploying a Trained Model on the Raspberry Pi

This package (`tb3_drl_deploy`) is a lightweight standalone ROS2 node that runs
actor-network inference directly on the Pi — no Docker, no Gazebo, no training code.

**Pi dependencies:** ROS2 Humble (already installed on TurtleBot3), `torch`, `numpy`

---

## 1. Install PyTorch on the Pi (one-time)

```bash
pip3 install torch --index-url https://download.pytorch.org/whl/cpu
pip3 install numpy
```

> PyTorch CPU-only is ~250 MB. Do NOT install the CUDA variant — the Pi has no GPU.

---

## 2. Copy the package and model to the Pi

From your **laptop**, copy the deploy package and the model weights:

```bash
# Copy the ROS2 package
scp -r /path/to/turtlebot3_drlnav/src/tb3_drl_deploy ubuntu@<PI_IP>:~/tb3_deploy_ws/src/

# Copy the actor weights file (example: TD3 pretrained model, episode 7400)
scp /path/to/turtlebot3_drlnav/src/turtlebot3_drl/model/examples/td3_0_stage9/actor_stage9_episode7400.pt \
    ubuntu@<PI_IP>:~/models/
```

> You only need the `actor_*.pt` file — not the critic, not the replay buffer.

---

## 3. Build the package on the Pi

SSH into the Pi:
```bash
ssh ubuntu@<PI_IP>
```

Build:
```bash
cd ~/tb3_deploy_ws
colcon build --packages-select tb3_drl_deploy
source install/setup.bash
```

---

## 4. Run the node

Make sure the robot's LiDAR, odometry, and velocity topics are active, then run:

```bash
ros2 launch tb3_drl_deploy deploy.launch.py \
  model_path:=/home/turtlebot3_drlnav/src/turtlebot3_drl/model/examples/td3_0_stage9/actor_stage9_episode7400.pt \
  goal_x:=1.5 \
  goal_y:=0.0 \
  lidar_correction:=0.0
```

Or with `ros2 run` directly:
```bash
ros2 run tb3_drl_deploy deploy_agent \
  --ros-args \
  -p model_path:=/home/ubuntu/models/actor_stage9_episode7400.pt \
  -p goal_x:=1.5 \
  -p goal_y:=0.0
```

The robot starts moving immediately. It stops automatically when it reaches the goal
or detects a collision.

To send a new goal at any time (from another terminal):
```bash
ros2 topic pub --once /goal_pose geometry_msgs/msg/Pose \
  "{position: {x: 2.0, y: 1.0, z: 0.0}, orientation: {w: 1.0}}"
```

---

## 5. Parameters

| Parameter    | Default | Description |
|-------------|---------|-------------|
| `model_path` | *(required)* | Absolute path to the `actor_*.pt` weights file |
| `goal_x`     | `0.0`   | Initial goal x position in metres |
| `goal_y`     | `0.0`   | Initial goal y position in metres |
| `step_hz`    | `10.0`  | Inference rate in Hz |

---

## 6. Tuning for your robot

All sensor/speed constants are at the top of [deploy_node.py](../src/tb3_drl_deploy/tb3_drl_deploy/deploy_node.py):

```python
LIDAR_CORRECTION    = 0.40   # subtract from raw scan to avoid false collisions
LIDAR_DISTANCE_CAP  = 3.5    # metres
THRESHOLD_GOAL      = 0.35   # metres — how close counts as reaching the goal
THRESHOLD_COLLISION = 0.11   # metres — how close counts as a collision
SPEED_LINEAR_MAX    = 0.22   # m/s
SPEED_ANGULAR_MAX   = 2.0    # rad/s
```

If the robot stops too early (thinks it collided), **increase** `LIDAR_CORRECTION`.  
If it runs into obstacles, **decrease** it.

---

---

## 7. Testing in Gazebo before deploying

The deploy node uses the same topic names as Gazebo (`/scan`, `/odom`, `/cmd_vel`),
so you can test it in simulation first — **no changes to the node needed**.

Open two terminals inside the Docker container (both sourced):

**Terminal 1** — launch Gazebo stage 9 (the stage the example models were trained on):
```bash
ros2 launch turtlebot3_gazebo turtlebot3_drl_stage9.launch.py pause:=false
```

> **`pause:=false` is required** — the deploy node does not call the Gazebo unpause service (unlike the training setup). Without it, the simulation stays frozen and neither `/scan` nor `/odom` will publish.

**Terminal 2** — run the deploy node with `lidar_correction:=0.0` (no correction in simulation):
```bash
ros2 launch tb3_drl_deploy deploy.launch.py \
  model_path:=/home/turtlebot3_drlnav/src/turtlebot3_drl/model/examples/td3_0_stage9/actor_stage9_episode7400.pt \
  goal_x:=1.5 \
  goal_y:=0.0 \
  lidar_correction:=0.0
```

The robot should start navigating toward the goal. You can send new goals from a third terminal:
```bash
ros2 topic pub --once /goal_pose geometry_msgs/msg/Pose \
  "{position: {x: 2.0, y: 1.0, z: 0.0}, orientation: {w: 1.0}}"
```

> **Note:** No `gazebo_goals` or `environment` node is needed — the deploy node reads
> sensors and drives the robot directly, just like it will on the Pi.

---

## Notes

- The pretrained example models were trained with `N_SCAN_SAMPLES=40`. If you change that, the weights will not match.
- The node uses CPU inference — no CUDA needed.
- Make sure `ROS_DOMAIN_ID` is the same on the Pi and your laptop if you want to monitor from the laptop.
