#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # --- Launch arguments ---
    algorithm_arg  = DeclareLaunchArgument('algorithm',  default_value='td3',
                                           description='DRL algorithm: td3, ddpg, or dqn')
    model_arg      = DeclareLaunchArgument('model',      default_value='examples/td3_0_stage9',
                                           description='Model path relative to model/ directory')
    episode_arg    = DeclareLaunchArgument('episode',    default_value='7400',
                                           description='Episode number to load')
    goal_x_arg     = DeclareLaunchArgument('goal_x',    default_value='1.0',
                                           description='Goal x position in meters')
    goal_y_arg     = DeclareLaunchArgument('goal_y',    default_value='0.0',
                                           description='Goal y position in meters')

    # Write stage 9 (matches example models) to the stage file read by the agent
    os.makedirs('/tmp', exist_ok=True)
    with open('/tmp/drlnav_current_stage.txt', 'w') as f:
        f.write('9\n')

    # --- Nodes ---
    real_environment_node = Node(
        package='turtlebot3_drl',
        executable='real_environment',
        name='drl_environment',
        output='screen'
    )

    real_agent_node = Node(
        package='turtlebot3_drl',
        executable='real_agent',
        name='drl_agent',
        arguments=[
            LaunchConfiguration('algorithm'),
            LaunchConfiguration('model'),
            LaunchConfiguration('episode'),
        ],
        output='screen'
    )

    # Publish the goal after 5 seconds to give nodes time to start up
    publish_goal = TimerAction(
        period=5.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    'ros2', 'topic', 'pub', '--once', '/goal_pose',
                    'geometry_msgs/msg/Pose',
                    ['"{position: {x: ', LaunchConfiguration('goal_x'),
                     ', y: ', LaunchConfiguration('goal_y'),
                     ', z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}"'],
                ],
                output='screen'
            )
        ]
    )

    return LaunchDescription([
        algorithm_arg,
        model_arg,
        episode_arg,
        goal_x_arg,
        goal_y_arg,
        real_environment_node,
        real_agent_node,
        publish_goal,
    ])
