# autonomous_driving_volksbot_nbv

Configuration and bringup for making a **Volksbot-class differential-drive
robot drive itself around an unknown indoor space**, mapping as it goes and
picking its own goals, using only openly available ROS 2 packages glued
together: `slam_toolbox` for the map, `robot_localization` for odometry,
[Nav2](https://github.com/ros-navigation/navigation2) for motion, and
[`frontier_exploration_ros2`](https://github.com/mertgulerx/frontier_exploration_ros2)
for choosing where to go next.

There is no new node code here at all. The work was in the wiring and the
parameter tuning — getting a real robot with a real sensor payload to stop fighting its
own costmap, stop refusing to move, and stop replanning itself into a corner.
That tuning, and the reasoning behind it, is the point of this repository.

> This is a carve-out of one part of a larger university project. The larger
> project stopped the robot at computed next-best-view poses and triggered a 3D
> laser scan there. **Those parts are not included** — only bringing the robot
> up and driving it autonomously with the frontier explorer, which is the part
> covered here.

## Demos

| | |
|---|---|
| [![Demo run 1](https://img.youtube.com/vi/T_6b75PGNpw/hqdefault.jpg)](https://youtu.be/T_6b75PGNpw) | [![Demo run 2](https://img.youtube.com/vi/JWfDaIo4NeI/hqdefault.jpg)](https://youtu.be/JWfDaIo4NeI) |
| **Demo run 1** — [youtu.be/T_6b75PGNpw](https://youtu.be/T_6b75PGNpw) | **Demo run 2** — [youtu.be/JWfDaIo4NeI](https://youtu.be/JWfDaIo4NeI) |
| [![Demo run 3](https://img.youtube.com/vi/-dB20vLv-Fg/hqdefault.jpg)](https://youtu.be/-dB20vLv-Fg) | |
| **Demo run 3** — [youtu.be/-dB20vLv-Fg](https://youtu.be/-dB20vLv-Fg) | |

## How it fits together

```
ROBOT                                    LAPTOP
-----------------------------------      ------------------------------------
volksbot_driver ──> /odom ──────────────> ekf_filter_node
                    /joint_states              │  in: /odom, /imu/data
                    <── /cmd_vel               │  out: /odometry/filtered
                                               │       TF odom -> base_footprint
phidgets_spatial ─> /imu/data_raw ──────> imu_filter_madgwick
                                               │  out: /imu/data
sllidar_ros2 ─────> /scan ──────────────> laser_filters chain
                                               │  out: /scan_filtered
robot_state_publisher                          v
  TF base_footprint -> base_link ────────> slam_toolbox
static_transform_publisher                     │  out: /map, TF map -> odom
  TF base_link -> laser ───────────────>       v
                                          nav2 (planner, MPPI controller,
teleop_twist_joy ─> /cmd_vel                    costmaps, behaviors)
  (manual override)                            │  out: /cmd_vel ──> robot
                                               v
                                          frontier_exploration_ros2
                                            in:  /map, costmaps
                                            out: NavigateToPose goals
```

Two launch files mirror that split:

* `launch/robot_bringup.launch.py` — everything bolted to the robot: base
  driver, URDF/TF tree, joystick, IMU, LiDAR.
* `launch/laptop_stack.launch.py` — everything that thinks: IMU filter, EKF,
  scan mask, SLAM, Nav2.

**On an unreliable network, run both on the robot.** The split exists for
convenience, not correctness, and a laggy link degrades it badly — see
[docs/NETWORKING.md](docs/NETWORKING.md).

## Quick start

Full instructions in [docs/SETUP.md](docs/SETUP.md) and
[docs/BRINGUP.md](docs/BRINGUP.md). Short version, both machines on the same
network and the same `ROS_DOMAIN_ID`:

```bash
# on the robot
ros2 launch volksbot_nbv_bringup robot_bringup.launch.py

# on the laptop, once /scan and /odom are visible there
ros2 launch volksbot_nbv_bringup laptop_stack.launch.py

# on the laptop, once /map and the costmaps are populated (~10 s later)
ros2 launch frontier_exploration_ros2 frontier_explorer.launch.py \
  params_file:=$(ros2 pkg prefix volksbot_nbv_bringup)/share/volksbot_nbv_bringup/config/frontier_exploration.yaml
```

The frontier explorer is started **separately and last**, on purpose. Bundled
into the launch file it latches onto an empty map and sits idle.

## What is in here

```
config/
  ekf.yaml                        robot_localization: /odom + /imu/data fusion, 2D mode
  imu_filter.yaml                 madgwick filter, magnetometer off
  nav2_params.yaml                Nav2, tuned for this robot (uses /scan_filtered)
  nav2_params_no_mask.yaml        same, for a ~270 deg sensor (uses /scan)
  slam_online_async.yaml          slam_toolbox async mapping (uses /scan_filtered)
  slam_online_async_no_mask.yaml  same, for a ~270 deg sensor (uses /scan)
  frontier_exploration.yaml       frontier_exploration_ros2 goal-selection tuning
  scan_mask.yaml                  laser_filters: blanks the payload cone of /scan
launch/
  robot_bringup.launch.py         runs on the robot
  laptop_stack.launch.py          runs on the laptop (or on the robot)
docs/
  SETUP.md                        what to install, where, and how to build
  BRINGUP.md                      launch-based and fully manual startup
  NETWORKING.md                   ROS_DOMAIN_ID, DDS, and why to run on the robot
  TUNING.md                       every non-default parameter and the reason for it
  TROUBLESHOOTING.md              the failures that cost the most time
```

## What is *not* in here

* The next-best-view planner and the 3D scanning pipeline from the parent
  project. Not my work, not included.
* The base driver (`volksbot_driver`) and the LiDAR driver (`sllidar_ros2`).
  Both are platform packages that have to be supplied separately.
* `frontier_exploration_ros2` itself. It is an upstream project, used as-is and
  only configured here; clone it from upstream.
* Any node source code. This repository is configuration, launch files and
  documentation; every node it starts belongs to an upstream package.
* Maps, bag files, and anything else recorded in the building this ran in.

## Requirements

* ROS 2 Jazzy on Ubuntu 24.04 (what this was developed and run on).
* A differential-drive base publishing `/odom` and consuming `/cmd_vel`.
* A 2D LiDAR publishing `/scan`, and an IMU publishing `/imu/data_raw`.
* Nav2, `slam_toolbox`, `robot_localization`, `imu_filter_madgwick`,
  `laser_filters`.

## Credits and origin

Originally built as a subsystem of a university team project. Everything that
is genuinely other people's work — the base driver, Nav2, `slam_toolbox`,
`robot_localization`, `frontier_exploration_ros2` — belongs to its upstream
authors and is only configured here. The repository was started fresh, with no
history from the original team repository.

Licensed under the [MIT License](LICENSE).
