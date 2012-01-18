#!/usr/bin/env python
# Software License Agreement (BSD License)
#
# Copyright (c) 2008, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


import roslib; roslib.load_manifest('pr2_calibration_estimation')

import sys
import unittest
import rospy
import numpy
import yaml

from pr2_calibration_estimation.sensors.chain_sensor import ChainBundler, ChainSensor
#from pr2_calibration_estimation.blocks.camera_chain import CameraChainCalcBlock
#from pr2_calibration_estimation.blocks.camera_chain import CameraChainRobotParamsBlock



from calibration_msgs.msg import *
from sensor_msgs.msg import JointState, CameraInfo

from pr2_calibration_estimation.single_transform import SingleTransform
from pr2_calibration_estimation.dh_chain import DhChain
from pr2_calibration_estimation.camera import RectifiedCamera
from pr2_calibration_estimation.tilting_laser import TiltingLaser
from pr2_calibration_estimation.full_chain import FullChainCalcBlock
from pr2_calibration_estimation.checkerboard import Checkerboard

from numpy import *

def loadConfigList():

    config_yaml = '''
  - chain_id: chainA
    before_chain: [transformA]
    dh_link_num:  1
    after_chain:  [transformB]
  - chain_id: chainB
    before_chain: [transformC]
    after_chain:  [transformD]
    dh_link_num:  6
'''
    config_dict = yaml.load(config_yaml)

    return config_dict

class TestChainBundler(unittest.TestCase):
    def test_basic_match(self):
        config_list = loadConfigList()

        bundler = ChainBundler(config_list)

        M_robot = RobotMeasurement( target_id = "targetA",
                                    chain_id = "chainA",
                                    M_cam   = [],
                                    M_chain = [ ChainMeasurement(chain_id="chainA") ])

        blocks = bundler.build_blocks(M_robot)

        self.assertEqual( len(blocks), 1)
        block = blocks[0]
        self.assertEqual( block._M_chain.chain_id, "chainA")
        self.assertEqual( block._target_id, "targetA")

    def test_basic_no_match(self):
        config_list = loadConfigList()

        bundler = ChainBundler(config_list)

        M_robot = RobotMeasurement( target_id = "targetA",
                                    chain_id = "chainA",
                                    M_chain = [ ChainMeasurement(chain_id="chainB") ])

        blocks = bundler.build_blocks(M_robot)

        self.assertEqual( len(blocks), 0)

from pr2_calibration_estimation.robot_params import RobotParams

class TestChainSensor(unittest.TestCase):
    def load(self):
        config = yaml.load('''
                chain_id: chainA
                before_chain: [transformA]
                dh_link_num:  1
                after_chain:  [transformB]
            ''')

        robot_params = RobotParams()
        robot_params.configure( yaml.load('''
            dh_chains:
              chainA:
                dh:
                - [ 0, 0, 1, 0 ]
                gearing: [1]
                cov:
                  joint_angles: [1]
            tilting_lasers: {}
            rectified_cams: {}
            transforms:
                transformA: [0, 0, 0, 0, 0, 0]
                transformB: [0, 0, 0, 0, 0, 0]
            checkerboards:
              boardA:
                corners_x: 2
                corners_y: 2
                spacing_x: 1
                spacing_y: 1
            ''' ) )
        return config, robot_params

    def test_cov(self):
        config, robot_params = self.load()
        block = ChainSensor(config,
                            ChainMeasurement(chain_id="chainA",
                                             chain_state=JointState(position=[0]) ),
                            "boardA")
        block.update_config(robot_params)
        cov = block.compute_cov(None)

        self.assertAlmostEqual(cov[0,0], 0.0, 6)
        self.assertAlmostEqual(cov[1,0], 0.0, 6)
        self.assertAlmostEqual(cov[1,1], 1.0, 6)
        self.assertAlmostEqual(cov[4,4], 4.0, 6)

    def test_update1(self):
        config, robot_params = self.load()
        block = ChainSensor(config,
                            ChainMeasurement(chain_id="chainA",
                                             chain_state=JointState(position=[0]) ),
                            "boardA")
        block.update_config(robot_params)

        target = matrix([[1, 2, 1, 2],
                         [0, 0, 1, 1],
                         [0, 0, 0, 0],
                         [1, 1, 1, 1]])

        h = block.compute_expected(target)
        z = block.get_measurement()
        r = block.compute_residual(target)

        self.assertAlmostEqual(numpy.linalg.norm(target-h), 0.0, 6)

        print "z=\n",z
        print "target=\n",target

        self.assertAlmostEqual(numpy.linalg.norm(target-z), 0.0, 6)
        self.assertAlmostEqual(numpy.linalg.norm(r - numpy.zeros([12])), 0.0, 6)

    def test_update2(self):
        config, robot_params = self.load()
        block = ChainSensor(config,
                            ChainMeasurement(chain_id="chainA",
                                             chain_state=JointState(position=[numpy.pi / 2.0]) ),
                            "boardA")
        block.update_config(robot_params)

        target = matrix([[0, 0,-1,-1],
                         [1, 2, 1, 2],
                         [0, 0, 0, 0],
                         [1, 1, 1, 1]])

        h = block.compute_expected(target)
        z = block.get_measurement()
        r = block.compute_residual(target)

        self.assertAlmostEqual(numpy.linalg.norm(target-h), 0.0, 6)

        print "z=\n",z
        print "target=\n",target

        self.assertAlmostEqual(numpy.linalg.norm(target-z), 0.0, 6)
        self.assertAlmostEqual(numpy.linalg.norm(r - numpy.zeros([12])), 0.0, 6)

    def test_sparsity(self):
        config, robot_params = self.load()
        block = ChainSensor(config,
                            ChainMeasurement(chain_id="chainA",
                                             chain_state=JointState(position=[numpy.pi / 2.0]) ),
                            "boardA")
        block.update_config(robot_params)
        sparsity = block.build_sparsity_dict()
        self.assertEqual(sparsity['transforms']['transformA'], [1,1,1,1,1,1])
        self.assertEqual(sparsity['transforms']['transformB'], [1,1,1,1,1,1])
        self.assertEqual(sparsity['dh_chains']['chainA'], {'dh':[[1,1,1,1]], 'gearing':[1]})

if __name__ == '__main__':
    import rostest
    rostest.unitrun('pr2_calibration_estimation', 'test_ChainBundler', TestChainBundler)
    #rostest.unitrun('pr2_calibration_estimation', 'test_CameraChainRobotParamsBlock', TestCameraChainRobotParamsBlock, coverage_packages=['pr2_calibration_estimation.blocks.camera_chain'])
    rostest.unitrun('pr2_calibration_estimation', 'test_ChainSensor', TestChainSensor)
