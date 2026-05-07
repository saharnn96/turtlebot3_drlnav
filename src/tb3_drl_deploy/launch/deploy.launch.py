#!/usr/bin/env python3
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('model_path', description='Absolute path to actor .pt weights file'),
        DeclareLaunchArgument('goal_x', default_value='1.0', description='Goal x in metres'),
        DeclareLaunchArgument('goal_y', default_value='0.0', description='Goal y in metres'),
        DeclareLaunchArgument('step_hz', default_value='10.0', description='Inference rate in Hz'),
        DeclareLaunchArgument('lidar_correction', default_value='0.4',
                              description='Metres subtracted from raw scan (0.0 for Gazebo, 0.4 for real robot)'),

        Node(
            package='tb3_drl_deploy',
            executable='deploy_agent',
            name='drl_deploy_agent',
            output='screen',
            parameters=[{
                'model_path':       LaunchConfiguration('model_path'),
                'goal_x':           LaunchConfiguration('goal_x'),
                'goal_y':           LaunchConfiguration('goal_y'),
                'step_hz':          LaunchConfiguration('step_hz'),
                'lidar_correction': LaunchConfiguration('lidar_correction'),
            }],
        ),
    ])
