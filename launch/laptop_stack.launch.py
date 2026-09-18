#!/usr/bin/env python3
#
# laptop_stack.launch.py  --  runs ON THE OPERATOR LAPTOP.
# Pair with robot_bringup.launch.py, which runs on the robot.
# On an unreliable network, run this file on the robot too (docs/NETWORKING.md).
#
# WHY THIS SHAPE:
#   SLAM lives HERE, next to the EKF, so both read the same clock. Splitting
#   them across two machines produced a start-order race that made the stack
#   "work sometimes" -- see docs/TROUBLESHOOTING.md. Keeping them together also
#   makes use_sim_time:=false impossible to forget, which is the other half of
#   that same failure.
#   The stack is STAGED with timers so that no node starts before the TF or
#   topic it depends on exists.
#
# TOPICS / TF THIS FILE BRINGS UP:
#   imu_filter_madgwick :  in  /imu/data_raw           out /imu/data
#   ekf_filter_node     :  in  /odom, /imu/data        out /odometry/filtered
#                                                      out TF odom -> base_footprint
#   scan_to_scan_filter :  in  /scan                   out /scan_filtered
#   slam_toolbox        :  in  /scan_filtered, TF      out /map, TF map -> odom
#   nav2 (navigation)   :  in  /odometry/filtered,/map out /cmd_vel
#
# CONSUMES FROM THE ROBOT (over the network, same ROS_DOMAIN_ID):
#   /scan   /odom   /imu/data_raw
#   TF base_footprint -> base_link     TF base_link -> laser
#
# The frontier explorer is NOT started here -- see the STAGE 3 note below.
# --------------------------------------------------------------------------

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            TimerAction)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    cfg      = os.path.join(get_package_share_directory('volksbot_nbv_bringup'), 'config')
    nav2_dir = get_package_share_directory('nav2_bringup')
    slam_dir = get_package_share_directory('slam_toolbox')

    # Defaults assume a 360 deg LiDAR with the payload cone masked out.
    # For a ~270 deg sensor that has no blind-spot problem, launch with:
    #   use_scan_mask:=false
    #   nav2_params:=<share>/config/nav2_params_no_mask.yaml
    #   slam_params:=<share>/config/slam_online_async_no_mask.yaml
    args = [
        DeclareLaunchArgument('use_scan_mask', default_value='true'),
        DeclareLaunchArgument('nav2_params',
                              default_value=os.path.join(cfg, 'nav2_params.yaml')),
        DeclareLaunchArgument('slam_params',
                              default_value=os.path.join(cfg, 'slam_online_async.yaml')),
    ]

    # ---- STAGE 0 (t=0): odometry sources + scan filter --------------------

    # madgwick: /imu/data_raw -> /imu/data (adds the orientation quaternion)
    madgwick = Node(
        package='imu_filter_madgwick', executable='imu_filter_madgwick_node',
        name='imu_filter_madgwick', output='screen',
        parameters=[os.path.join(cfg, 'imu_filter.yaml')])

    # ekf: fuse /odom + /imu/data -> /odometry/filtered + TF odom->base_footprint
    ekf = Node(
        package='robot_localization', executable='ekf_node',
        name='ekf_filter_node', output='screen',
        parameters=[os.path.join(cfg, 'ekf.yaml')])

    # Scan mask: /scan -> /scan_filtered, via the upstream laser_filters chain.
    # Blanks the angular cone where a payload sits on the robot. Unmasked, that
    # payload reads as a permanent obstacle glued to the footprint and Nav2
    # refuses to move at all.
    # The cone's bounds live in config/scan_mask.yaml and are expressed in the
    # LASER frame, so they depend on the base_link->laser mounting yaw -- see
    # the comments in that file before changing them.
    scan_mask = Node(
        package='laser_filters', executable='scan_to_scan_filter_chain',
        name='scan_to_scan_filter_chain', output='screen',
        condition=IfCondition(LaunchConfiguration('use_scan_mask')),
        parameters=[os.path.join(cfg, 'scan_mask.yaml')])

    # ---- STAGE 1 (t=5s): SLAM, once the EKF publishes odom->base_footprint --
    # use_sim_time:=false is forced on purpose -- a real robot has no /clock,
    # and a stray true here is the single most common cause of "SLAM hangs".
    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(slam_dir + '/launch/online_async_launch.py'),
        launch_arguments={'slam_params_file': LaunchConfiguration('slam_params'),
                          'use_sim_time': 'false'}.items())

    # ---- STAGE 2 (t=8s): Nav2, once /map and /odometry/filtered exist ------
    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(nav2_dir + '/launch/navigation_launch.py'),
        launch_arguments={'use_sim_time': 'false',
                          'params_file': LaunchConfiguration('nav2_params')}.items())

    # ---- STAGE 3: frontier exploration -------------------------------------
    # LEFT OUT ON PURPOSE. Bundled into this launch, the explorer does not come
    # up reliably: it latches onto a /map or costmap that is still empty and
    # then sits idle. Start it by hand once the stack above is settled:
    #
    #   ros2 launch frontier_exploration_ros2 frontier_explorer.launch.py \
    #     params_file:=<share>/volksbot_nbv_bringup/config/frontier_exploration.yaml
    #
    # See docs/BRINGUP.md step 8.

    return LaunchDescription(args + [
        madgwick, ekf, scan_mask,
        TimerAction(period=5.0, actions=[slam]),
        TimerAction(period=8.0, actions=[nav2]),
    ])
