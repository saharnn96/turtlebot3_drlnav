# Migration: ROS2 Foxy / Ubuntu 20.04 → Humble / Ubuntu 22.04

## What Changed

### 1. Dockerfile

| Component | Before | After |
|-----------|--------|-------|
| Base image | `nvidia/cuda:11.3.1-base-ubuntu20.04` | `nvidia/cuda:12.1.1-base-ubuntu22.04` |
| Python | Manually installed 3.8 via deadsnakes PPA | Python 3.10 ships by default on Ubuntu 22.04 — no install needed |
| PyTorch | `torch==1.10.0+cu113` | `torch==2.1.2+cu121` |
| numpy | 1.24.3 | 1.26.4 |
| matplotlib | 3.7.1 | 3.8.4 |
| pandas | 2.0.2 | 2.2.2 |
| pyqtgraph | 0.12.4 | 0.13.7 |
| PyQt5 | 5.14.1 | 5.15.10 |
| ROS2 | `ros-foxy-ros-base` | `ros-humble-ros-base` |
| TurtleBot3 | `ros-foxy-turtlebot3-description` | `ros-humble-turtlebot3-description` |
| Gazebo bridge | `ros-foxy-gazebo-ros-pkgs` | `ros-humble-gazebo-ros-pkgs` |
| Gazebo install | `curl \| sh` (osrf script) | `apt install gazebo` (native Ubuntu 22 package) |
| bashrc source | `/opt/ros/foxy/setup.bash` | `/opt/ros/humble/setup.bash` |

### 2. `drl_gazebo/drl_gazebo.py`

The path used to locate the goal box model SDF had a hardcoded `python3.8` segment:

```python
# Before
'turtlebot3_drl/lib/python3.8/site-packages/turtlebot3_drl/drl_gazebo'

# After
'turtlebot3_drl/lib/python3.10/site-packages/turtlebot3_drl/drl_gazebo'
```

## What Did NOT Change

- All ROS2 Python source code (`rclpy`, service/subscriber/publisher APIs) — Humble is API-compatible with Foxy for the patterns used here.
- `package.xml` files — dependencies are expressed without distro prefixes.
- `CMakeLists.txt` files — use standard CMake/ament patterns, no distro-specific code.
- Custom message/service definitions (`turtlebot3_msgs`) — no changes needed.
- The obstacle plugin `.cc` source files — standard Gazebo Classic API, unaffected.

## Rebuild Required

The `obstacle_plugin/lib/` directory contains pre-built binaries and CMake cache files from the Foxy build. These will need to be rebuilt inside the new container:

```bash
# Inside the running container, from /home/turtlebot3_drlnav
colcon build --symlink-install
```

The CMake cache files referencing `/opt/ros/foxy/` will be regenerated automatically.

## Notes on Gazebo Classic vs. Ignition

- ROS2 Humble officially supports **Gazebo Classic 11** (via `ros-humble-gazebo-ros-pkgs`).
- The new simulator (Gazebo Ignition / Garden) is also supported but requires different world/model files and a separate bridge (`ros-humble-ros-gz-bridge`).
- This migration stays on **Gazebo Classic** — no world or model files need to change.

## Building the New Docker Image

```bash
docker build -t turtlebot3_drlnav:humble .

docker run -it --gpus all \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v $(pwd):/home/turtlebot3_drlnav \
  turtlebot3_drlnav:humble
```
