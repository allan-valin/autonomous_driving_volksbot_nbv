# Tuning

The Nav2 config started life as the stock `nav2_bringup` template, which is
written for a small simulated robot on a clean map. Every deviation below was
made because the real robot misbehaved in a specific, repeatable way. Values
are what worked on a ~0.56 m square differential-drive base with a rear-mounted
sensor payload, indoors, in corridors and offices.

Read this as a list of symptoms, not as a list of numbers to copy.

---

## Geometry

| Parameter | Value | Why |
|---|---|---|
| `footprint` (both costmaps) | `[[0.28,0.28],[0.28,-0.28],[-0.28,-0.28],[-0.28,0.28]]` | The template's `robot_radius` circle does not describe this base. A square base approximated by a circle either clips corners on obstacles or refuses gaps it fits through. |
| `inflation_radius` | `0.42` | The template value inflates so far that a standard doorway is solid cost and the planner reports "no valid path". 0.42 keeps a usable safety margin and still leaves a drivable channel through doors. |
| `cost_scaling_factor` | `2.0` | Flatter cost falloff than the template. With a steep falloff the controller hugs walls in narrow corridors, because the gradient in the middle is nearly flat and anything else is a cliff. |
| `CostCritic.consider_footprint` | `true` | With the footprint ignored, MPPI evaluates the robot as a point and scores trajectories that scrape the real chassis through obstacles. Costs CPU; worth it. |

## Motion

| Parameter | Value | Why |
|---|---|---|
| `vx_max` | `0.2` | A mapping robot that outruns its own scan matcher produces smeared walls. Slow is a mapping-quality setting, not a safety setting. |
| `vx_min` | `-0.1` | Reverse is **allowed but expensive**. Fully forbidding reverse leaves the robot permanently stuck the first time a frontier turns out to be a dead end. |
| `wz_max` | `0.6` | Capped hard. Fast in-place rotation is where the scan-matcher and the odometry disagree most, and it is the main source of map rotation error. |
| `PreferForwardCritic.cost_weight` | `25.0` | Raised well above the template's value. Together with a non-zero `vx_min`, this makes reversing a last resort rather than a routine manoeuvre — the robot backs out of a dead end but does not creep backwards down a corridor. |
| `velocity_smoother` max/min | `[±0.20, 0.0, ±0.6]` | Must agree with the controller limits. Mismatched smoother limits silently clamp commands the controller thought it was issuing, which looks like a controller bug and is not. |

## Perception

| Parameter | Value | Why |
|---|---|---|
| `scan_topic` / obstacle sources | `/scan_filtered` | Everything consumes the masked scan, not the raw one. Listed separately in four places in `nav2_params.yaml` — miss one and the payload behind the robot reappears as an obstacle in that one layer only, which is a genuinely confusing failure. |
| `obstacle_max_range` | `2.5` | Beyond this, single noisy returns at long range mark cells the robot then has to re-clear. |
| `raytrace_max_range` | `3.0` | Slightly longer than the marking range so cells can always be cleared by the same scan that could have marked them. |
| `scan_mask.yaml` bounds | `-0.7854 .. 0.7854` | The payload cone, in the laser frame. Applied by `laser_filters` before anything else sees the scan. |
| `collision_monitor scan.min_height` | `0.15` | Ignores returns below 0.15 m, which are mostly floor and ramp artefacts rather than obstacles. |
| `track_unknown_space` (global) | `true` | Required for frontier exploration to mean anything: without it, unknown space is indistinguishable from free space and there are no frontiers to find. |

## Frontier selection (`frontier_exploration.yaml`)

| Parameter | Value | Why |
|---|---|---|
| `occ_threshold` | `75` | A goal is refused if any active costmap reports cost above this at that point. Lower values made the planner accept goals in inflated regions it could never actually reach, then fail on approach. |
| `min_frontier_size_cells` | `15` | Filters out the stream of 1-3 cell "frontiers" produced by scan noise along walls. These are never worth a full navigation cycle. |
| `frontier_selection_min_distance` | `0.5` | Stops the robot picking a goal it is effectively already standing on. |
| `frontier_visit_tolerance` | `0.30` | How close counts as visited. Too tight and the robot re-targets the same frontier forever. |
| `goal_preemption_enabled` | `false` | Preemption while driving caused near-continuous replanning: the robot stops, re-picks a goal, turns, and repeats without covering ground. |
| `goal_preemption_min_interval_s` | `200` | Backstop for the same problem, in case preemption is re-enabled. |
| `goal_skip_on_blocked_goal` | `true` | An unreachable frontier is dropped instead of retried indefinitely. |
| `strategy` | `nearest` | Nearest-frontier. Sweeps a floor plan in a reasonably systematic order and, unlike information-gain scoring, does not send the robot across the whole building for a marginally better goal. |
| `map_qos_durability` | `transient_local` | Must match how `slam_toolbox` publishes `/map`. Mismatched QoS means the subscription silently never connects: no error, no map, no exploration. |

## SLAM (`slam_online_async.yaml`)

| Parameter | Value | Why |
|---|---|---|
| `base_frame` | `base_footprint` | Must be the frame the EKF publishes, not `base_link`. The same trap applies to `ekf.yaml`, where `base_link_frame` is also `base_footprint`. A mismatch here breaks the TF chain in a way that looks like a sensor problem. |
| `scan_topic` | `/scan_filtered` | Same masked scan as Nav2, so the map and the costmaps agree about what exists. |
| `minimum_travel_distance` / `_heading` | `0.0` | Process every scan. A slow robot in a feature-poor corridor otherwise skips scans it needed. |
| `map_update_interval` | `2.5` | Publishing `/map` faster mostly burns bandwidth, which matters when the map crosses a wireless link. |
| `use_sim_time` | `false` | Pinned in the file and forced again in the launch file. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md). |

## Odometry fusion (`ekf.yaml`)

`two_d_mode: true`, fusing wheel odometry (x velocity, yaw rate) with IMU yaw
rate and x acceleration. The magnetometer is disabled in `imu_filter.yaml`:
indoors, next to motors and steel, it degrades yaw rather than improving it.

If the map rotates when the robot turns while the walls otherwise look right,
try dropping the IMU input entirely and running the EKF on wheel odometry
alone. Wheel odometry is usually the less wrong of the two on a four-wheel
skid-capable base, and the IMU's yaw-rate bias is what the scan matcher then
has to fight.
