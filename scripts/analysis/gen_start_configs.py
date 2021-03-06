#!/usr/bin/env python

import argparse
from collections import defaultdict
import csv
import glob
from itertools import chain, combinations
import math
import numpy as np
import os
from os import listdir
from os.path import isdir, isfile, join
import pandas as pd
import pprint
import re
from scipy.spatial import distance
import signal
import subprocess
import sys
import time
import yaml

import igraph

import rospkg
import rospy
import rosbag

import mrta
import mrta.msg
import mrta.mrta_planner_proxy

sys.path.append("/home/eric/GIT/mrta/scripts")
import random_poses

maps = {'brooklyn': 'brooklyn_lab.png',
        'smartlab': 'smartlab_ugv_arena_v2.png'}

ROBOT_NAMES = ['robot_1', 'robot_2', 'robot_3']

pp = pprint.PrettyPrinter(indent=4)

# Paths to ROS binaries
ROS_HOME = '/opt/ros/indigo'
ROSLAUNCH = "{0}/bin/roslaunch".format(ROS_HOME)

LAUNCH_PKG = 'mrta'
LAUNCHFILE = 'stage_dummy_robot.launch'
DUMMY_ROBOT_NAME = 'robot_0'
MAP_FILE = 'smartlab_ugv_arena_v2.png'
WORLD_FILE = 'smartlab_ugv_arena_dummy_robot.world'
# NOGUI_FLAG = ''
NOGUI_FLAG = '-g'

planner_proxy = None
main_proc = None


def start_ros():
    global main_proc, planner_proxy

    try:

        main_proc = subprocess.Popen([ROSLAUNCH,
                                      LAUNCH_PKG,
                                      LAUNCHFILE,
                                      "map_file:={0}".format(MAP_FILE),
                                      "world_file:={0}".format(WORLD_FILE),
                                      "dummy_robot_name:={0}".format(DUMMY_ROBOT_NAME),
                                      "nogui_flag:={0}".format(NOGUI_FLAG)])

        time.sleep(5)

        planner_proxy = mrta.mrta_planner_proxy.PlannerProxy(DUMMY_ROBOT_NAME)

        node_name = 'gen_median'
        rospy.loginfo("Starting node '{0}'...".format(node_name))
        rospy.init_node(node_name)

    except:
        print("Couldn't start ROS: {0}".format(sys.exc_info()[0]))
        stop_ros()
        sys.exit(1)


def stop_ros():
    global main_proc
    try:
        # proc.terminate()
        main_proc.send_signal(signal.SIGINT)
        main_proc.wait()
    except rospy.exceptions.ROSException as e:
        print(e)
        print("Error: {0}".format(sys.exc_info()[0]))


def sig_handler(sig):
    """ Terminate all child processes when we get a SIGINT """
    if sig == signal.SIGINT:
        stop_ros()
        print("Shutting down...")
        sys.exit(0)

signal.signal(signal.SIGINT, sig_handler)

def find_nearest_index(array,value):
    return (np.abs(array-value)).argmin()

def get_average_teammate_distance(start_poses):

    robot_graph = igraph.Graph()
    robot_graph.add_vertices(ROBOT_NAMES)

    # Turn on weighting
    robot_graph.es['weight'] = 1.0

    # For every pair of robots
    for pair in combinations(ROBOT_NAMES, 2):
        first_robot_name = pair[0]
        second_robot_name = pair[1]

        source_point = mrta.Point(start_poses[first_robot_name]['x'], start_poses[first_robot_name]['y'])
        source_pose = planner_proxy._point_to_pose(source_point)

        target_point = mrta.Point(start_poses[second_robot_name]['x'], start_poses[second_robot_name]['y'])
        target_pose = planner_proxy._point_to_pose(target_point)

        teammate_distance = planner_proxy.get_path_cost(source_pose, target_pose)

        robot_graph[first_robot_name, second_robot_name] = teammate_distance

        # dist_matrix = robot_graph.get_adjacency(type=2, attribute='weight').data

        print("robot_graph: {0}, distances: {1}".format(robot_graph.summary(),
                                                        robot_graph.es['weight']))
        # print("Distance-weighted adjacency matrix: {0}".format(pp.pformat(dist_matrix)))

        # robot_graph_mst = robot_graph.spanning_tree(weights=robot_graph.es['weight'])
        # print("robot_graph_mst: {0}, distances: {1}".format(robot_graph_mst.summary(),
        #                                                     robot_graph_mst.es['weight']))
        # print task_graph_mst
        team_diameter = robot_graph.diameter(directed=False, weights='weight')
        print "team diameter: {0}".format(team_diameter)

        average_teammate_distance = np.mean(robot_graph.es['weight'])
        print "average teammate distance: {0}".format(average_teammate_distance)

        return average_teammate_distance


def get_average_team_centroid_distance(start_poses):

    # Find the euclidean center of the team, then measure the average team
    # member distance to that center.
    team_centroid_x = sum([start_poses[rn]['x'] for rn in ROBOT_NAMES]) * 1. / len(ROBOT_NAMES)
    team_centroid_y = sum([start_poses[rn]['y'] for rn in ROBOT_NAMES]) * 1. / len(ROBOT_NAMES)

    total_team_centroid_distance = 0.0
    for robot_name in ROBOT_NAMES:
        robot_x = start_poses[robot_name]['x']
        robot_y = start_poses[robot_name]['y']
        total_team_centroid_distance += distance.euclidean((robot_x, robot_y), (team_centroid_x, team_centroid_y))

    average_team_centroid_distance = total_team_centroid_distance * 1. / len(ROBOT_NAMES)

    print "average team centroid distance: {0}".format(average_team_centroid_distance)


def generate_range_sequence(start, end, length):
    step = end - start * 1. / length
    return np.arange(start, end, step)


def generate_start_configs(map_file, avg_team_dist_range, avg_centroid_dist_range):
    global planner_proxy
    rospack = rospkg.RosPack()

    # Generate 5 start configs for a range of average teammate distances
    avg_team_dist_range_seq = generate_range_sequence(avg_team_dist_range[0], avg_team_dist_range[1], 5)

    random_poses = get_random_poses("{0}/config/maps/{1}".format(rospack.get_path('mrta'), map_file), 3, 70, occupy=True)


    # Generate 5 start configs for a range of average team centroid distances
    avg_centroid_dist_range_seq = generate_range_sequence(avg_centroid_dist_range[0], avg_centroid_dist_range[1], 5)

    random_poses = get_random_poses("{0}/config/maps/{1}".format(rospack.get_path('mrta'), map_file), 3, 70, occupy=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Launch a multirobot task-allocation experiment.')
    parser.add_argument('map',
                        choices=['brooklyn', 'smartlab', 'strand'],
                        help='Map through which the robots move.')

    args = parser.parse_args()
    map_file = maps[args.map]

    avg_team_dist_range = [1.1673862533, 9.22324297867]
    avg_centroid_dist_range = [0.670534674393, 3.96388329223]

    start_ros()
    generate_start_configs(map_file, avg_team_dist_range, avg_centroid_dist_range)
    stop_ros()
