#!/usr/bin/env python3
"""
Standalone DRL navigation node for TurtleBot3 Raspberry Pi.

Runs actor-network inference directly — no Gazebo, no training code,
no replay buffer, no ROS2 services. Just LiDAR + odometry → cmd_vel.

Dependencies (pip): torch  numpy
ROS2 packages:      rclpy  sensor_msgs  geometry_msgs  nav_msgs

Usage:
  ros2 run tb3_drl_deploy deploy_agent \
    --ros-args \
    -p model_path:=/path/to/actor_stage9_episode7400.pt \
    -p goal_x:=1.5 \
    -p goal_y:=0.0
"""

import copy
import math
import sys

import numpy as np
import torch
import torch.nn as nn

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, qos_profile_sensor_data
from geometry_msgs.msg import Pose, Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan

# ── Constants (must match the values used when the model was trained) ──────────
N_SCAN_SAMPLES      = 40
LIDAR_DISTANCE_CAP  = 3.5    # metres — raw scan values are capped here
LIDAR_CORRECTION    = 0.40   # metres — subtracted from raw readings (set to 0.0 in Gazebo)
SPEED_LINEAR_MAX    = 0.22   # m/s
SPEED_ANGULAR_MAX   = 2.0    # rad/s
THRESHOLD_GOAL      = 0.35   # metres
THRESHOLD_COLLISION = 0.11   # metres
ARENA_LENGTH        = 4.2    # metres
ARENA_WIDTH         = 4.2    # metres
MAX_GOAL_DISTANCE   = math.sqrt(ARENA_LENGTH ** 2 + ARENA_WIDTH ** 2)

TOPIC_SCAN = 'scan'
TOPIC_VELO = 'cmd_vel'
TOPIC_ODOM = 'odom'
TOPIC_GOAL = 'goal_pose'

STATE_SIZE  = N_SCAN_SAMPLES + 4   # 44: scan(40) + goal_dist + goal_angle + prev_lin + prev_ang
HIDDEN_SIZE = 512
ACTION_SIZE = 2


# ── Minimal Actor (identical architecture for both TD3 and DDPG) ───────────────
class Actor(nn.Module):
    def __init__(self):
        super().__init__()
        self.fa1 = nn.Linear(STATE_SIZE, HIDDEN_SIZE)
        self.fa2 = nn.Linear(HIDDEN_SIZE, HIDDEN_SIZE)
        self.fa3 = nn.Linear(HIDDEN_SIZE, ACTION_SIZE)

    def forward(self, x):
        x = torch.relu(self.fa1(x))
        x = torch.relu(self.fa2(x))
        return torch.tanh(self.fa3(x))


# ── ROS2 node ──────────────────────────────────────────────────────────────────
class DeployAgent(Node):
    def __init__(self):
        super().__init__('drl_deploy_agent')

        self.declare_parameter('model_path', '')
        self.declare_parameter('goal_x', 0.0)
        self.declare_parameter('goal_y', 0.0)
        self.declare_parameter('step_hz', 10.0)
        self.declare_parameter('lidar_correction', LIDAR_CORRECTION)

        model_path    = self.get_parameter('model_path').value
        self.goal_x   = self.get_parameter('goal_x').value
        self.goal_y   = self.get_parameter('goal_y').value
        step_hz       = self.get_parameter('step_hz').value
        self.lidar_correction = self.get_parameter('lidar_correction').value

        if not model_path:
            self.get_logger().error('model_path parameter is required')
            raise SystemExit(1)

        self.actor = Actor()
        self.actor.load_state_dict(torch.load(model_path, map_location='cpu'))
        self.actor.eval()
        self.get_logger().info(f'Loaded model: {model_path}')

        self.scan_ranges       = [1.0] * N_SCAN_SAMPLES
        self.obstacle_distance = LIDAR_DISTANCE_CAP
        self.robot_x           = 0.0
        self.robot_y           = 0.0
        self.robot_heading     = 0.0
        self.goal_distance     = MAX_GOAL_DISTANCE
        self.goal_angle        = 0.0
        self.prev_linear       = 0.0
        self.prev_angular      = 0.0
        self.local_step        = 0
        self.running           = self.goal_x != 0.0 or self.goal_y != 0.0

        qos = QoSProfile(depth=10)
        self.cmd_pub  = self.create_publisher(Twist, TOPIC_VELO, qos)
        self.scan_sub = self.create_subscription(LaserScan, TOPIC_SCAN, self._scan_cb, qos_profile_sensor_data)
        self.odom_sub = self.create_subscription(Odometry, TOPIC_ODOM, self._odom_cb, qos)
        self.goal_sub = self.create_subscription(Pose, TOPIC_GOAL, self._goal_cb, qos)
        self.create_timer(1.0 / step_hz, self._step)

        if self.running:
            self.get_logger().info(f'Starting with goal: x={self.goal_x:.2f}  y={self.goal_y:.2f}')
        else:
            self.get_logger().info(f'Waiting for goal on /{TOPIC_GOAL} ...')

    # ── Callbacks ──────────────────────────────────────────────────────────────

    def _goal_cb(self, msg):
        self.goal_x     = msg.position.x
        self.goal_y     = msg.position.y
        self.local_step = 0
        self.running    = True
        self.prev_linear  = 0.0
        self.prev_angular = 0.0
        self.get_logger().info(f'New goal: x={self.goal_x:.2f}  y={self.goal_y:.2f}')

    def _odom_cb(self, msg):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y

        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.robot_heading = math.atan2(siny, cosy)

        dx = self.goal_x - self.robot_x
        dy = self.goal_y - self.robot_y
        self.goal_distance = math.sqrt(dx * dx + dy * dy)

        angle = math.atan2(dy, dx) - self.robot_heading
        while angle >  math.pi: angle -= 2 * math.pi
        while angle < -math.pi: angle += 2 * math.pi
        self.goal_angle = angle

    def _scan_cb(self, msg):
        n_raw = len(msg.ranges)
        indices = [int(i * n_raw / N_SCAN_SAMPLES) for i in range(N_SCAN_SAMPLES)]
        min_dist = LIDAR_DISTANCE_CAP
        for out_i, raw_i in enumerate(indices):
            raw = msg.ranges[raw_i]
            if math.isinf(raw) or math.isnan(raw):
                raw = LIDAR_DISTANCE_CAP
            corrected = float(np.clip((raw - self.lidar_correction) / LIDAR_DISTANCE_CAP, 0.0, 1.0))
            self.scan_ranges[out_i] = corrected
            dist = corrected * LIDAR_DISTANCE_CAP
            if dist < min_dist:
                min_dist = dist
        self.obstacle_distance = min_dist

    # ── Inference step ─────────────────────────────────────────────────────────

    def _step(self):
        if not self.running:
            return

        self.local_step += 1

        if self.local_step > 15:
            if self.goal_distance < THRESHOLD_GOAL:
                self.get_logger().info('Goal reached!')
                self._stop()
                return
            if self.obstacle_distance < THRESHOLD_COLLISION:
                self.get_logger().warn('Collision detected — stopping.')
                self._stop()
                return

        state = copy.copy(self.scan_ranges)
        state.append(float(np.clip(self.goal_distance / MAX_GOAL_DISTANCE, 0.0, 1.0)))
        state.append(self.goal_angle / math.pi)
        state.append(self.prev_linear)
        state.append(self.prev_angular)

        t = torch.tensor(state, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            action = self.actor(t).squeeze(0).tolist()

        lin = (action[0] + 1.0) / 2.0 * SPEED_LINEAR_MAX
        ang = action[1] * SPEED_ANGULAR_MAX

        twist = Twist()
        twist.linear.x  = lin
        twist.angular.z = ang
        self.cmd_pub.publish(twist)

        self.prev_linear  = action[0]
        self.prev_angular = action[1]

        if self.local_step % 10 == 0:
            self.get_logger().info(
                f'GD:{self.goal_distance:.2f}m  GA:{math.degrees(self.goal_angle):.1f}°  '
                f'MinD:{self.obstacle_distance:.2f}m  lin:{lin:.2f}  ang:{ang:.2f}')

    def _stop(self):
        self.cmd_pub.publish(Twist())
        self.running      = False
        self.local_step   = 0
        self.prev_linear  = 0.0
        self.prev_angular = 0.0


def main(args=None):
    rclpy.init(args=args)
    node = DeployAgent()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
