# Networking

The two-machine split — sensors and driver on the robot, everything that thinks
on the laptop — is a convenience, not a requirement. It exists so you can watch
RViz on a decent screen and restart the navigation stack without touching the
robot. It assumes a network that behaves.

**If the network is unreliable, run everything on the robot.** This is the
single most effective fix for the whole class of "it worked yesterday"
problems, and it is worth doing before debugging anything else.

---

## Why a bad link breaks the split specifically

Everything crossing the link is either a control loop or a large periodic
message, and both degrade badly:

* `/scan` at ~10 Hz feeds SLAM, both costmaps *and* the collision monitor. Drop
  scans and the costmaps clear obstacles late, the collision monitor loses its
  observation source and stops the robot, and SLAM matches against gaps.
* `/cmd_vel` is the output of a 20 Hz smoother. Latency here is steering
  latency; the robot overshoots and the controller corrects into an oscillation.
* `/map` and the costmaps are large messages. On a saturated link they crowd
  out the small, latency-critical ones.
* TF is continuous. A stalled TF buffer produces `Lookup would require
  extrapolation into the future` and Nav2 simply stops planning.

None of this fails cleanly. It shows up as the robot pausing, twitching,
replanning constantly, or driving into something that *was* in the costmap a
second ago.

## Running everything on the robot

Launch both files on the robot:

```bash
# terminal 1, on the robot
ros2 launch volksbot_nbv_bringup robot_bringup.launch.py

# terminal 2, on the robot
ros2 launch volksbot_nbv_bringup laptop_stack.launch.py

# terminal 3, on the robot
ros2 launch frontier_exploration_ros2 frontier_explorer.launch.py \
  params_file:=$(ros2 pkg prefix volksbot_nbv_bringup)/share/volksbot_nbv_bringup/config/frontier_exploration.yaml
```

Nothing in either launch file assumes a particular machine, so this needs no
changes. The clock problem disappears too, since every node reads one clock.

Then run **only RViz** on the laptop. It subscribes to `/map` (latched,
`transient_local`) and TF, and if it stutters or disconnects, the robot carries
on regardless. Turn off the costmap and voxel displays in RViz first — they are
by far the largest subscriptions and the least useful over a weak link.

If the link is bad enough that even RViz is unusable, record a bag on the robot
and replay it on the laptop afterwards.

---

## Checklist before blaming the software

**Same `ROS_DOMAIN_ID` on every machine and every terminal.**

```bash
export ROS_DOMAIN_ID=<n>   # same n everywhere, in every shell, before launching
```

A terminal that inherited a different value sees an empty `ros2 topic list` and
gives no hint why. If several robots share one network, each needs its own
domain — otherwise two robots discover each other and both receive `/cmd_vel`.

**Discovery must be able to cross the network.** Default DDS discovery uses
multicast; many managed and campus networks drop it. Verify in both directions:

```bash
# on the robot
ros2 topic list | grep scan
# on the laptop
ros2 topic list | grep scan     # if /scan is missing here, it is discovery, not ROS
```

A local firewall is the usual culprit. `ros2 multicast receive` / `ros2
multicast send` will tell you quickly whether multicast works at all. If it
does not, either fix the network or run everything on the robot.

**Clocks must be in sync.** This one is vicious, because the failure is silent.
ROS 2 messages are stamped on the sending machine and compared against the
receiving machine's clock; a few seconds of skew makes every incoming transform
look like it is from the future, TF lookups fail, and SLAM appears to hang
while logging nothing interesting.

```bash
# on both machines
date -u +%s%N
# or, properly:
timedatectl status     # expect "System clock synchronized: yes" on both
```

Install `chrony` or enable NTP on both machines, or point the laptop at the
robot as its time source. Running everything on the robot also solves this.

**`use_sim_time` must be `false` everywhere.** There is no `/clock` on real
hardware. A single node left on simulated time waits forever for a clock that
never arrives, and reports nothing.

```bash
ros2 param get /slam_toolbox use_sim_time      # expect false
ros2 param get /controller_server use_sim_time # expect false
```

**Wi-Fi roaming.** A robot that moves between access points will re-associate
mid-run, taking DDS discovery down with it for several seconds. If the building
has more than one AP on the same SSID, expect this and prefer running
everything on the robot.
