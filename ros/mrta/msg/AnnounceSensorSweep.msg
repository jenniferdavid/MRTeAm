std_msgs/Header header  # Message header
string mechanism        # Robots need to know this in order to know how
                        # to bid
SensorSweepTask[] tasks # Tasks to announce. A list lets us announce
                        # bundles of tasks.