#!/usr/bin/env python
PKG  = 'cob_calibration_executive'
NODE = 'joint_state_listener_arm'
import roslib; roslib.load_manifest(PKG)
import rospy

import sensor_msgs.msg
import numpy as np

'''
Print joint states for cob arm.

Listens to /joints_states topic for joint state messages from arm controller 
and prints them.
'''
def main():
    rospy.init_node(NODE)
    print "==> %s started " % NODE
    
    # get joint names for arm from parameter server
    joint_names = rospy.get_param("arm_controller/joint_names");
    print joint_names

    while not rospy.is_shutdown():
        if rospy.is_shutdown(): exit(0)
        
        # try getting /joint_states message
        try:
            msg = rospy.wait_for_message("/joint_states", sensor_msgs.msg.JointState)
        except rospy.exceptions.ROSInterruptException:
            exit(0)
        if joint_names[0] in msg.name:
            # message is from arm
            angles = []
            for name in joint_names:
                angles.append(msg.position[msg.name.index(name)])
            # nicely print joint angles with 5 digits
            np.set_printoptions(precision=5, suppress=True)
            print np.array(angles)

if __name__ == '__main__':
    main()
