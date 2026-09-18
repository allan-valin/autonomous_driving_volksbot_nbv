# Troubleshooting

The failures that cost the most time, and what they actually turned out to be.
Nearly all of them present as silence rather than as an error, which is why
they are worth writing down.

---

## SLAM publishes nothing, or "hangs"

**Almost never a TF problem, almost always a time problem.** Two causes, in
order of likelihood:

1. **`use_sim_time` is `true` somewhere.** Real hardware publishes no `/clock`,
   so the node waits forever. Check every node, not just SLAM:
   ```bash
   ros2 param get /slam_toolbox use_sim_time
   ```
   `laptop_stack.launch.py` forces `false` for SLAM and Nav2 for this reason,
   and `slam_online_async.yaml` pins it too.

2. **The robot's and the laptop's clocks disagree.** Incoming transforms look
   like they are from the future, every TF lookup fails, nothing logs anything
   useful. See [NETWORKING.md](NETWORKING.md#checklist-before-blaming-the-software).

Only after both are ruled out is it worth looking at TF.

## No laser in RViz, no `/map`, TF chain broken at `base_footprint`

`robot_state_publisher` was started with the `.xacro` file **path** as a
positional argument. It then tries to parse that path as plain URDF, without
running xacro, fails, and exits — taking `base_footprint -> base_link` with it,
and with that the laser transform and any hope of a map.

The fix, which `robot_bringup.launch.py` already implements: expand the xacro in
Python and pass the result as the `robot_description` **parameter**.

```python
robot_desc = xacro.process_file(urdf_xacro).toxml()
Node(package='robot_state_publisher', executable='robot_state_publisher',
     parameters=[{'robot_description': robot_desc}])   # not arguments=[urdf]
```

Diagnose with `ros2 run tf2_ros tf2_echo map base_footprint` — whichever link is
missing names the producer that died.

## Nav2 refuses to move, robot appears surrounded

A payload mounted on the robot reads as a permanent obstacle touching the
footprint, so every trajectory is in collision. Fixed by masking that angular
cone out of the scan (`laser_filters`, `config/scan_mask.yaml`) and pointing
Nav2 at `/scan_filtered`.

Two things to check when the mask seems not to work:

* **The bounds point the wrong way.** They are in the *laser* frame. With
  `base_link -> laser` at `yaw=pi`, laser 0 rad is the robot's rear, so a cone
  of `-0.7854 .. 0.7854` masks the rear. Get the sign convention backwards and
  you mask the **front** instead — which looks exactly like the mask doing
  nothing, while the robot cheerfully drives into walls ahead of it. Widening
  the cone does not fix it; it is a direction error, not a width error.
* **Wrong filter variant.** `LaserScanAngularBoundsFilterInPlace` NaNs out what
  is *inside* the bounds. `LaserScanAngularBoundsFilter` keeps only what is
  inside, which throws away everything you wanted to keep.
* **One Nav2 layer still reads `/scan`.** The topic appears in four separate
  places in `nav2_params.yaml` (SLAM's own topic, the voxel layer, the obstacle
  layer, the collision monitor). Miss one and the obstacle reappears in that
  layer only.

Confirm the mask output directly:

```bash
ros2 topic echo /scan_filtered --once | head -40   # expect nan across the masked cone
```

## The whole launch aborts with "No such file or directory"

The LiDAR driver's plain launch file is literally named
`sllidar_a2m12_launch .py` — with a space before `.py` — and is not installed
into `share/`. Referencing it kills the entire launch. Use
`view_sllidar_a2m12_launch.py` instead; on a headless robot its RViz dies
harmlessly with "could not connect to display" and `/scan` publishes fine.

## Frontier explorer starts but never sends a goal

* **Started too early.** Bundled into the launch file it subscribes to a map
  and costmaps that are still empty, and then sits idle. Start it by hand, last,
  once `/map` has content. This is why STAGE 3 in `laptop_stack.launch.py` is
  commented out rather than timed.
* **QoS mismatch on `/map`.** `slam_toolbox` publishes latched
  (`transient_local`); a subscriber asking for `volatile` never connects, with
  no error on either side. `frontier_exploration.yaml` sets
  `map_qos_durability: transient_local` for exactly this reason.
* **No unknown space to explore.** `track_unknown_space: true` must be set on
  the global costmap, otherwise unknown and free are the same thing and there
  are no frontiers.

Check the subscription actually connected:

```bash
ros2 topic info /map --verbose     # explorer must appear, with matching QoS
```

## Robot stops, re-picks a goal, turns, repeats — and covers no ground

Goal preemption. Every new frontier evaluation cancels the goal in flight.
`goal_preemption_enabled: false` plus a long `goal_preemption_min_interval_s`
stops it. Symptom is easy to misread as a planner failure.

## Robot spins in place, or the map rotates while the walls stay straight

Yaw disagreement between the IMU and wheel odometry. The scan matcher then
fights the EKF. Try running the EKF on wheel odometry alone — comment out the
`imu0` block in `ekf.yaml` — and see whether the map stabilises. On a
four-wheel base, wheel odometry is often the less wrong of the two.

Also check that the `base_link -> laser` yaw matches the sensor's real mounting.
A 180-degree error there produces a map that is internally consistent and
mirrored relative to the world.

## Map looks mirrored or rotated 180 degrees only when Nav2 is running

**Known open issue.** With the driver, LiDAR and Nav2 parameters each verified
in isolation, a 180-degree error can still appear in `map -> odom` once the full
stack is up. The suspicion is a frame-naming mismatch between producers rather
than a bad parameter — two nodes publishing the same logical transform under
frame names that differ. If you hit this, dump the tree first:

```bash
ros2 run tf2_tools view_frames
```

and check for duplicate or unexpected publishers of `map -> odom` and
`odom -> base_footprint`.

## `colcon build` fails, or builds into the wrong Python

A conda environment on `PATH`. Its Python is picked up instead of the system
one. `conda deactivate` before building, and keep it deactivated in terminals
that launch ROS nodes.

## Nothing is visible from the other machine

Domain ID, discovery, or firewall. See
[NETWORKING.md](NETWORKING.md#checklist-before-blaming-the-software).
