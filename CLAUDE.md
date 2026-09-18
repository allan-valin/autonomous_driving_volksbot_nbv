# Notes for Claude working in this repo

## What this repo is

A **public, sanitized carve-out** of one subsystem from a private university
team project. The private original is a separate repository that is not
referenced here by path, host or name. This repo is a fresh `git init` with a
single initial commit — **no history was imported and none should be**, and no
remote of the original may ever be added to it.

Scope here is deliberately narrow: bring the robot up, and drive it
autonomously with an external frontier explorer. The next-best-view planner and
the 3D scanning pipeline from the parent project are out of scope and must not
be added.

## Sanitization rules — apply to every change

Nothing that identifies the people, the institution or the machines may enter
this repo. Specifically, do not reintroduce:

- Names or email addresses of teammates, supervisors or anyone else.
- The university, the institute, the git host used by the team, or any
  SSO/account instructions for them.
- Robot hostnames and codenames used by the team, `user@host` shell prompts,
  and specific `ROS_DOMAIN_ID` values tied to a particular robot.
- IP addresses, MAC addresses, and hostnames of lab machines.
- Absolute paths from the original machines, and directory names from the
  original team workspace. Use `~/ros2_ws` or
  `$(ros2 pkg prefix volksbot_nbv_bringup)/share/...` instead.
- The brand/model of the 3D scanner payload. Say "sensor payload" or
  "payload mounted on the back plate".
- German-language comments and docs carried over from the original.

Before any commit that touches files copied from the original, grep for the
above. The upstream project names that *are* fine to keep: `volksbot_driver`,
`sllidar_ros2`, `slam_toolbox`, `nav2`, `robot_localization`,
`imu_filter_madgwick`, `frontier_exploration_ros2` and its GitHub URL.

## No node source code in this repo

This repository deliberately contains **no node implementations** — only
configuration, launch files and docs. A custom scan-masking node authored by a
teammate was removed for this reason and replaced by the upstream
`laser_filters` chain plus `config/scan_mask.yaml`. The same rule applies to
anything else from the original project: the cmd_vel-intercepting bridge nodes,
the mapper, the point-cloud converter and the homemade frontier explorer all
stay out. If a behaviour genuinely cannot be configured, prefer an upstream
package over writing a node here, and ask before adding one.

## Attribution

Configs and launch files here were produced by a group. The README credits "a
university team project" without names, and upstream packages by name. Keep it
that way: no per-file `@author` tags, no teammate names in commit messages, and
do not attribute other people's work to the repo owner either.

## Layout and conventions

- ROS 2 Jazzy, `ament_cmake` package `volksbot_nbv_bringup`.
- `config/` installs to `share/`; the launch files resolve config paths from
  `share/`, never from the source tree. A new config must be picked up by the
  `install(DIRECTORY launch config ...)` rule in `CMakeLists.txt`.
- `*_no_mask.yaml` variants exist for sensors that need no scan mask
  (~270 degree LiDAR publishing straight to `/scan`). Any change to
  `nav2_params.yaml` or `slam_online_async.yaml` that is not about the scan
  topic must be mirrored into its `_no_mask` twin.
- `/scan_filtered` appears in **four** places in `nav2_params.yaml` (SLAM topic,
  voxel layer, obstacle layer, collision monitor). Change all four or none.
- Code comment style, per the repo owner's preference: extractable header
  comment per file, short inline comments explaining *why*, roughly two lines
  maximum per comment.

## What has never been verified here

This repo has never been built or run in this location — there is no ROS 2
workspace around it. `colcon build` was not executed against it. Do not claim
the package builds or that a launch file works; say what was and was not
checked. The Python files were syntax-checked with `ast.parse`, nothing more.

`config/scan_mask.yaml` and the `laser_filters` node it configures have not
been run against a real sensor from this repo. Its bounds are derived from the
documented `base_link -> laser` mounting, not measured.

## Docs

`docs/TUNING.md` and `docs/TROUBLESHOOTING.md` are the substance of this repo —
the parameter reasoning and the failure modes. When a new failure mode is
diagnosed on the real robot, it belongs in `TROUBLESHOOTING.md` as
symptom → cause → check, in the same shape as the existing entries.
