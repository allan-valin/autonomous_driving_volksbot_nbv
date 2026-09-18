#!/usr/bin/env python3
#
# robot_bringup.launch.py  --  runs ON THE ROBOT.
# Pair with laptop_stack.launch.py, which runs on the operator laptop.
# For an unreliable network, run both on the robot instead (see docs/NETWORKING.md).
#
# This file owns everything that is bolted to the robot: the base driver, the
# URDF/TF tree, the joystick, the IMU and the LiDAR. It deliberately does NOT
# run SLAM -- SLAM sits next to the EKF on the laptop so the two share one
# clock (see docs/TROUBLESHOOTING.md, "SLAM comes up empty").
#
# Two mistakes are baked out of this file on purpose:
#   * robot_state_publisher gets `robot_description` as a PARAMETER holding
#     xacro-expanded XML. Passing the .xacro PATH as a positional argument
#     makes it parse the file as plain URDF, fail, and exit -- which silently
#     kills base_footprint->base_link, and with it the laser TF and /map.
#   * The LiDAR is started through the *view* launch file. The plain one
#     shipped by the driver has a space in its filename and is not installed
#     into share/, so referencing it aborts the whole launch.
#
# TOPICS / TF THIS FILE BRINGS UP:
#   robot_state_publisher : out /robot_description, TF base_footprint->base_link (+ wheels)
#   base driver           : out /odom, /joint_states  ; in /cmd_vel
#   teleop_twist_joy      : out /cmd_vel (joystick)   ; in /joy
#   phidgets_spatial      : out /imu/data_raw, /imu/mag              (USB)
#   sllidar a2m12         : out /scan                                (USB)
#   static_transform_pub  : out TF base_link->laser  (x=0.225, yaw=pi)
# --------------------------------------------------------------------------

import os
import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            OpaqueFunction)
from launch.launch_context import LaunchContext
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, ComposableNodeContainer
from launch_ros.descriptions import ComposableNode


# Joystick: include teleop_twist_joy's launch with the platform joystick config.
# Resolved in an OpaqueFunction so the config-file name (a launch arg) is a
# concrete string by the time we build the path.
def make_joystick(context: LaunchContext, joy_cfg_name):
    teleop_dir = get_package_share_directory('teleop_twist_joy')
    driver_dir = get_package_share_directory('volksbot_driver')
    cfg_name = context.perform_substitution(joy_cfg_name)
    joy_cfg = os.path.join(driver_dir, 'config/joystick', cfg_name)
    return [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(teleop_dir + '/launch/teleop-launch.py'),
        launch_arguments={'config_filepath': joy_cfg}.items())]


def generate_launch_description():
    driver_dir  = get_package_share_directory('volksbot_driver')
    sllidar_dir = get_package_share_directory('sllidar_ros2')

    # --- URDF: xacro-processed to XML, passed as a PARAMETER (the correct way) ---
    urdf_xacro = os.path.join(driver_dir, 'urdf', 'volksbot.urdf.xacro')
    robot_desc = xacro.process_file(urdf_xacro).toxml()

    imu_cfg = os.path.join(driver_dir, 'config/imu', 'phidgets_imu.yaml')

    # robot_state_publisher: publishes TF base_footprint->base_link and the rest
    # of the URDF tree. NO positional `arguments=[urdf]` -- that was the bug.
    rsp = Node(
        package='robot_state_publisher', executable='robot_state_publisher',
        name='robot_state_publisher', output='screen',
        parameters=[{'use_sim_time': False, 'robot_description': robot_desc}])

    # Base driver: /odom + /joint_states, consumes /cmd_vel.
    driver = Node(
        package='volksbot_driver', executable='volksbot', name='volksbot',
        output='screen',
        parameters=[{'num_wheels': 4, 'wheel_radius': 0.0985,
                    'robot_description': robot_desc}])

    # Phidgets IMU, inlined -> /imu/data_raw, /imu/mag
    phidgets_imu = ComposableNodeContainer(
        name='phidgets_container', namespace='',
        package='rclcpp_components', executable='component_container',
        composable_node_descriptions=[
            ComposableNode(
                package='phidgets_spatial', plugin='phidgets::SpatialRosI',
                name='phidgets_spatial', parameters=[imu_cfg])],
        output='both')

    return LaunchDescription([

        DeclareLaunchArgument('joystick_config', default_value='8bitdo.config.yaml'),

        rsp,
        driver,

        # Joystick teleop -- manual override while the stack is running.
        OpaqueFunction(function=make_joystick,
                       args=[LaunchConfiguration('joystick_config')]),

        # base_link -> laser (front mount, tail-to-centre x=0.225, yaw=pi).
        # The yaw=pi is what makes laser 0 deg point at the robot's REAR; the
        # rear scan mask on the laptop side depends on that convention.
        Node(package='tf2_ros', executable='static_transform_publisher',
             arguments=['0.225', '0', '0', '3.14159', '0', '0', 'base_link', 'laser']),

        phidgets_imu,

        # 360 deg LiDAR -> /scan.
        # The no-rviz driver launch shipped upstream is literally named
        # 'sllidar_a2m12_launch .py' -- with a space before .py -- and is not
        # installed into share/, so referencing it kills the launch with
        # "No such file or directory". The view_* variant has no space and IS
        # installed. On a headless robot its rviz dies harmlessly
        # ("could not connect to display") and /scan still publishes.
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(sllidar_dir + '/launch/view_sllidar_a2m12_launch.py')),
    ])
