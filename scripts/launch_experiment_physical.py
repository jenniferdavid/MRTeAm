#!/usr/bin/env python

import argparse
import datetime
import mrta
import mrta.msg
import pprint
import rospy
import signal
import subprocess
import sys
import time

# Paths to ROS binaries
#ROS_HOME = '/opt/ros/hydro'
ROS_HOME = '/opt/ros/indigo'
#ROS_HOME = '/home/esch/opt/ros/hydro'
ROSLAUNCH = "{0}/bin/roslaunch".format(ROS_HOME)
#ROSBAG = "{0}/bin/rosbag".format(ROS_HOME)
ROSBAG = "{0}/lib/rosbag/record".format(ROS_HOME)
ROSCORE = "{0}/bin/roscore".format(ROS_HOME)

# How many seconds to wait before killing all processes
TIMEOUT_DEFAULT = 300
# PSI can take longer than other mechanisms, with the clustered start config
TIMEOUT_PSI = 420

# Keep track of processes to terminate when done
running_procs = []

# Robots we want to start up
robots = [{'name': 'robot_1',
           'port': '11312'},
          {'name': 'robot_2',
           'port': '11313'},
          {'name': 'robot_3',
           'port': '11314'}]

maps = {'brooklyn': 'brooklyn_lab.png',
        'smartlab': 'smartlab_ugv_arena_v2.png' }

world_files = {'brooklyn': {'clustered': 'brooklyn_arena_3_robots_clustered.world',
                            'distributed': 'brooklyn_arena_3_robots_distributed.world',
                            'distributed_A': ''},
               'smartlab': {'clustered': 'smartlab_ugv_arena_3_robots_clustered.world',
                            'distributed': 'smartlab_ugv_arena_3_robots_distributed.world',
                            'distributed_A': 'smartlab_ugv_arena_3_robots_distributed_A.world'}}


mechanisms = ['RR', 'OSI', 'SSI', 'PSI']

# Topics to record with rosbag
record_topics = ['/experiment', '/tasks/announce', '/tasks/bid',
                 '/tasks/award', '/tasks/status', '/tasks/new', '/debug']

exp_running = False

pp = pprint.PrettyPrinter(indent=2)


def kill_procs():
    for proc in reversed(running_procs):
        try:
            #proc.terminate()
            proc.send_signal(signal.SIGINT)
            proc.wait()
        except:
            print("Error: {0}".format(sys.exc_info()[0]))
        time.sleep(2)


def sig_handler(sig, frame):
    # Terminate all child processes when we get a SIGINT
    if sig == signal.SIGINT:
        kill_procs()
        print("Shutting down...")
        sys.exit(0)

signal.signal(signal.SIGINT, sig_handler)          


def on_exp_event(exp_event_msg):
    print("######## on_exp_event() ########")
    print(pp.pformat(exp_event_msg))
    # if exp_event_msg.event == mrta.msg.ExperimentEvent.END_ALLOCATION:
    if exp_event_msg.event == mrta.msg.ExperimentEvent.END_EXPERIMENT:
        print("######## END_EXPERIMENT ########")
        global exp_running
        exp_running = False


def launch_experiment(mechanism, map_file, world_file, scenario_id, args):
    global exp_running
    exp_running = True

    start_time = datetime.datetime.now()

    # Start roscore
    print('######## Launching roscore ########')
    roscore_proc = subprocess.Popen(ROSCORE)
    time.sleep(5)

    print('######## Starting experiment_launcher node ########')
    rospy.init_node('experiment_launcher', disable_signals=True)
    rospy.Subscriber('/experiment',
                     mrta.msg.ExperimentEvent,
                     on_exp_event)

    time.sleep(3)

    # Start rosbag
    # Record the positions (amcl_pose) of all robots
    for robot in robots:
        record_topics.append("/{0}/amcl_pose".format(robot['name']))

    print('######## Launching rosbag record ########')
    rosbag_args = [ROSBAG, 'record']
    rosbag_args.extend([ '-j',  # compress
                         '-o',  # prepend world, mech and task to filename
                         "{0}__{1}__{2}__{3}_".format(args.map,
                                                      args.start_config,
                                                      mechanism,
                                                      scenario_id)])
    rosbag_args.extend(record_topics)
                                                
    rosbag_proc = subprocess.Popen(rosbag_args)
#    rosbag_proc = subprocess.Popen(' '.join(rosbag_args), shell=True)
    time.sleep(5)

    # Launch the auctioneer
    print('######## Launching auctioneer ########')
    auc_pkg = 'mrta_auctioneer'
    auc_launchfile = 'mrta_auctioneer_physical_fkie.launch'
    auc_port = '11315'
    mechanism = mechanism
    scenario_id = scenario_id
    auc_proc = subprocess.Popen([ROSLAUNCH,
                                 auc_pkg,
                                 auc_launchfile,
                                 '-p', auc_port,
                                 "mechanism:={0}".format(mechanism),
                                 "scenario_id:={0}".format(scenario_id)])

    running_procs.append(auc_proc)

    timeout_secs = 0
    if mechanism == 'PSI' and args.start_config == 'clustered':
        timeout_secs = TIMEOUT_PSI
    else:
        timeout_secs = TIMEOUT_DEFAULT

    # Now wait until we receive a SIGINT (Ctrl-C)
    while exp_running:
        time.sleep(1)

        # Time out if the experiment is taking too long
        now = datetime.datetime.now()
        time_delta = now - start_time
        if time_delta.seconds > timeout_secs:
            exp_running = False

    # Processes are terminated in reverse order of their insertion
    # into running_procs. We add the rosbag and roscore processes to
    # the list last so that they gets terminated first.
    running_procs.append(rosbag_proc)
    running_procs.append(roscore_proc)

    # The experiment is over.
    time.sleep(10)
    print("######## KILLING PROCESSES ########")
    rospy.signal_shutdown('Experiment finished.')
    kill_procs()
    del running_procs[:]
    time.sleep(10)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Launch a multirobot task-allocation experiment.')

    parser.add_argument('mechanism',
                        choices=['OSI', 'PSI', 'SSI', 'RR'],
                        help='Mechanism to allocate tasks.')
    parser.add_argument('map',
                        choices=['brooklyn', 'smartlab'],
                        help='Map through which the robots move.')
    parser.add_argument('start_config',
                        choices=['clustered', 'distributed', 'distributed_A'],
                        help='Starting locations of the robots.')
    parser.add_argument('scenario_id',
                        help='Name of the scenario that defines task locations (and other properties).')

    args = parser.parse_args()

    mechanism = args.mechanism
    map_file = maps[args.map]
    world_file = world_files[args.map][args.start_config]
    scenario_id = args.scenario_id

    launch_experiment(mechanism, map_file, world_file, scenario_id, args)

