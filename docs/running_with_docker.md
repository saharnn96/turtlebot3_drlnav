# Running the Project with Docker

## 1. Build the Docker Image

From the repository root:
```
docker build -t turtlebot3_drlnav .
```

## 2. Allow GUI Access
```
xhost +local:docker
```

## 3. Run the Container

> **Important:** Run this command from **inside the repository directory** (e.g. `cd ~/turtlebot3_drlnav`). The `-v $(pwd)` flag mounts your current directory into the container — if you run it from your home directory, the wrong folder gets mounted and the build will fail.

```
docker run -it --gpus all --privileged --env NVIDIA_VISIBLE_DEVICES=all --env NVIDIA_DRIVER_CAPABILITIES=all --env DISPLAY=${DISPLAY} --env QT_X11_NO_MITSHM=1 --volume /tmp/.X11-unix:/tmp/.X11-unix -v $(pwd):/home/turtlebot3_drlnav --network host turtlebot3_drlnav
```

## 4. Build the Workspace (inside the container)
```
cd /home/turtlebot3_drlnav
colcon build
source install/setup.bash
```

> **If you see a CMakeCache error** like `The current CMakeCache.txt directory is different than the directory where CMakeCache.txt was created`, it means stale build artifacts exist from a previous failed build. Clean them and rebuild:
> ```
> rm -rf build/ install/ log/
> colcon build
> source install/setup.bash
> ```

## 5. Open Four Terminals

Use `docker exec` to open additional terminals. In each new terminal tab on your host machine run:
```
docker exec -it <container_name> bash
```

To find your container name:
```
docker ps
```

In each new terminal, source the workspace:
```
source /home/turtlebot3_drlnav/install/setup.bash
```

## 6. Run the Training

**Terminal 1** — Launch Gazebo simulation:
```
ros2 launch turtlebot3_gazebo turtlebot3_drl_stage4.launch.py
```

**Terminal 2** — Start goal manager:
```
ros2 run turtlebot3_drl gazebo_goals
```

**Terminal 3** — Start environment node:
```
ros2 run turtlebot3_drl environment
```

**Terminal 4** — Start training (choose one):
```
ros2 run turtlebot3_drl train_agent ddpg
ros2 run turtlebot3_drl train_agent td3
ros2 run turtlebot3_drl train_agent dqn
```

## Testing a Pre-trained Model

Use the same 4-terminal setup but replace Terminal 4 with the test command.

Launch stage 9 in Terminal 1 (the examples were trained on stage 9):
```
ros2 launch turtlebot3_gazebo turtlebot3_drl_stage9.launch.py
```

Then in Terminal 4, run one of the included example models:

For TD3:
```
ros2 run turtlebot3_drl test_agent td3 'examples/td3_0_stage9' 7400
```

For DDPG:
```
ros2 run turtlebot3_drl test_agent ddpg 'examples/ddpg_0_stage9' 8000
```

To test your own trained model (substitute your model name and episode):
```
ros2 run turtlebot3_drl test_agent ddpg 'your_model_name_stageN' <episode>
```

> **Note:** The model path must end with the stage number (e.g. `_stage9`). The system reads the last character of the path to determine which stage the model was trained on.

## Testing the Deploy Node in Gazebo

Use this to verify the lightweight Pi deploy node works correctly before putting it on the robot.
Only **2 terminals** are needed — no goal manager, no environment node.

**Terminal 1** — Launch Gazebo stage 9 (unpaused — required for the deploy node, which has no unpause call):
```
ros2 launch turtlebot3_gazebo turtlebot3_drl_stage9.launch.py pause:=false
```

**Terminal 2** — Run the deploy node:
```
ros2 launch tb3_drl_deploy deploy.launch.py \
  model_path:=/home/turtlebot3_drlnav/src/turtlebot3_drl/model/examples/td3_0_stage9/actor_stage9_episode7400.pt \
  goal_x:=1.5 \
  goal_y:=0.0 \
  lidar_correction:=0.0
```

> `lidar_correction:=0.0` is important here — Gazebo scans don't need the offset correction that the real robot does.

The robot will start moving toward the goal immediately. To send a new goal while it is running, open a third terminal and run:
```
ros2 topic pub --once /goal_pose geometry_msgs/msg/Pose \
  "{position: {x: 2.0, y: 1.0, z: 0.0}, orientation: {w: 1.0}}"
```

## Notes

- Always launch the Gazebo simulation (Terminal 1) first before running any other node.
- After any code change to the Python packages, rebuild before restarting:
  ```
  colcon build --packages-select turtlebot3_drl tb3_drl_deploy
  source install/setup.bash
  ```
- Trained models are saved automatically to `src/turtlebot3_drl/model/`.
