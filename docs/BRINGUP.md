# Bringup

Two ways to start the stack: the launch files, or node by node. The manual path
is slower but it is how you find out *which* piece is broken, so it is written
out in full below.

Before anything: both machines on the same network, same `ROS_DOMAIN_ID`, and
clocks in sync. See [NETWORKING.md](NETWORKING.md) — skipping that section is
the most reliable way to waste an afternoon.

---

## The short path

**1. On the robot:**

```bash
ros2 launch volksbot_nbv_bringup robot_bringup.launch.py
```

Brings up: base driver (`/odom`, `/joint_states`, consumes `/cmd_vel`), the
URDF TF tree, joystick teleop, the IMU (`/imu/data_raw`), the LiDAR (`/scan`),
and the static `base_link -> laser` transform.

**2. On the laptop**, once `ros2 topic list` there shows `/scan` and `/odom`:

```bash
ros2 launch volksbot_nbv_bringup laptop_stack.launch.py
```

Brings up, staged: IMU filter, EKF and the scan filter chain at t=0,
`slam_toolbox` at t=5 s, Nav2 at t=8 s. The delays are not decoration — each stage needs the
TF or topic the previous one publishes.

For a ~270 degree sensor that has no payload in its blind spot:

```bash
ros2 launch volksbot_nbv_bringup laptop_stack.launch.py \
  use_scan_mask:=false \
  nav2_params:=$(ros2 pkg prefix volksbot_nbv_bringup)/share/volksbot_nbv_bringup/config/nav2_params_no_mask.yaml \
  slam_params:=$(ros2 pkg prefix volksbot_nbv_bringup)/share/volksbot_nbv_bringup/config/slam_online_async_no_mask.yaml
```

**3. Check the map before going further.** Open RViz, fixed frame `map`, and
confirm the map grows as you drive the robot with the joystick. If the map is
empty or the walls smear when the robot turns, stop here — an autonomous run on
a broken map only produces a broken map faster. See
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

**4. On the laptop**, once `/map` and the costmaps are populated:

```bash
ros2 launch frontier_exploration_ros2 frontier_explorer.launch.py \
  params_file:=$(ros2 pkg prefix volksbot_nbv_bringup)/share/volksbot_nbv_bringup/config/frontier_exploration.yaml
```

The explorer is started last and on its own because bundling it into the launch
file makes it subscribe to an empty map and then sit idle forever. Keep the
joystick within reach: teleop publishes to `/cmd_vel` alongside Nav2 and is the
practical stop button.

---

## The manual path

Same stack, one node per terminal. Useful when something does not come up and
you need to see exactly which link in the chain is missing.

Paths below assume the installed share directory:

```bash
CFG=$(ros2 pkg prefix volksbot_nbv_bringup)/share/volksbot_nbv_bringup/config
```

### On the robot

**Base driver** — provides `/cmd_vel`, `/imu/data_raw`, `/imu/mag`,
`/joint_states`, `/joy`, `/odom`, `/robot_description`, `/tf`, `/tf_static`:

```bash
ros2 launch volksbot_driver volksbot_imu.py
```

**LiDAR** — provides `/scan`:

```bash
ros2 launch sllidar_ros2 view_sllidar_a2m12_launch.py
```

The non-`view_` launch file in that package has a space in its filename and is
not installed into `share/`, so referencing it aborts the launch. On a headless
robot the RViz instance started by `view_` dies harmlessly and `/scan` still
publishes.

**`base_link -> laser` transform.** Belongs in the URDF; it lives here because
this was faster to iterate on. For a rear-mounted 360 degree sensor:

```bash
ros2 run tf2_ros static_transform_publisher \
  --x 0.225 --y 0 --z 0 --yaw 3.14159 --pitch 0 --roll 0 \
  --frame-id base_link --child-frame-id laser
```

For a front-facing ~270 degree sensor, use `--yaw 0.0`. The yaw here decides
which direction the masked cone has to point — see the scan filter below.

### On the laptop

**Scan mask** — `/scan` in, `/scan_filtered` out, using the upstream
`laser_filters` chain. Skip it entirely if your sensor has no payload in its
field of view:

```bash
ros2 run laser_filters scan_to_scan_filter_chain --ros-args --params-file $CFG/scan_mask.yaml
```

The bounds in `scan_mask.yaml` are in the *laser* frame, so they follow the TF
above: with `yaw=pi`, laser 0 rad points at the robot's rear, so a rear cone is
`-0.7854 .. 0.7854`. Mounted the other way round the same physical cone sits at
`±pi` and needs two filter entries, one on each side of the wrap. Verify in
RViz rather than trusting the arithmetic.

**IMU filter** — `/imu/data_raw` in, `/imu/data` out (adds the orientation
quaternion). The magnetometer is off in the config; indoors, near motors, it is
worse than useless:

```bash
ros2 run imu_filter_madgwick imu_filter_madgwick_node --ros-args --params-file $CFG/imu_filter.yaml
```

**EKF** — `/odom` + `/imu/data` in, `/odometry/filtered` and TF
`odom -> base_footprint` out:

```bash
ros2 run robot_localization ekf_node --ros-args --params-file $CFG/ekf.yaml
```

**SLAM** — `/scan_filtered` + TF in, `/map` and TF `map -> odom` out:

```bash
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:=$CFG/slam_online_async.yaml \
  use_sim_time:=false
```

`use_sim_time:=false` is not optional on real hardware. A stray `true` leaves
every node waiting on a `/clock` that nobody publishes, and the symptom is not
an error — it is SLAM silently doing nothing.

**Nav2**:

```bash
ros2 launch nav2_bringup navigation_launch.py \
  params_file:=$CFG/nav2_params.yaml \
  use_sim_time:=false
```

**Frontier explorer** — last, as above.

---

## Sanity checks

```bash
ros2 topic hz /scan                  # sensor alive and arriving over the network
ros2 topic hz /odometry/filtered     # EKF running
ros2 run tf2_ros tf2_echo map base_footprint   # full TF chain resolves
ros2 topic echo /map --once          # SLAM publishing
```

A gap in `tf2_echo map base_footprint` tells you which of the three producers —
`robot_state_publisher`, the EKF, or SLAM — is missing, faster than any log.
