"""
PHYSICAL HUMAN-ROBOT COLLABORATION (PHRC): MUSCLE FATIGUE MODEL

This code provides an online human muscle fatigue model that operated based on
muscle activity as measured in real-time by electromyography (EMG). The model
is based on [Peternel, et al. 2018]. Muscle activity can be replaced by other
real-time effort variables such as muscle force from a biomechanical model as
in [Peternel, et al. 2019].


AUTHOR: Luka Peternel
e-mail: l.peternel@tudelft.nl


REFERENCE:
L. Peternel, N. Tsagarakis, D. Caldwell, & A. Ajoudani
Robot adaptation to human physical fatigue in human–robot co-manipulation
Autonomous Robots, 42(5), 1011-1021, 2018

L. Peternel, C. Fang, N. Tsagarakis, & A. Ajoudani
A selective muscle fatigue management approach to ergonomic human-robot co-manipulation
Robotics and Computer-Integrated Manufacturing, 58, 69-79, 2019

"""

import numpy as np






'''MODEL'''

class muscle_fatigue_model:
    def __init__(self, N, dt, CF, CR, relax_th):

        # parameters and variables
        self.N = N # number of muscles in the model
        self.dt = dt # sample time
        self.CF = CF # muscle fatigue capacity parameter based on calibration
        self.CR = CR # muscle relaxation parameter based on calibration or literature
        self.relax_th = relax_th # threshold below which the muscle enters relaxation mode
        
        self.MA = np.zeros(N) # muscle activations
        self.dV = np.zeros(N) # muscle fatigue change
        self.V = np.zeros(N) # muscle fatigue index
    
    
    
    # calcuate fatigue at each sample time based on muscle activations
    def fatigue(self, MA):
        
        for i in range(2):
            # just to make sure muscle activation is always positive
            if (MA[i] < 0.0):
                MA[i] = 0.0
        
            	# fatigue index calculation through differential equations
            if(MA[i] > self.relax_th[i]): # fatigue mode
            		self.dV[i] = (1 - self.V[i]) * MA[i]/self.CF[i]
            		self.V[i] += self.dV[i] * self.dt
            else: # relaxation mode
            		self.dV[i] = self.V[i] * self.CR[i]/self.CF[i]
            		self.V[i] -= self.dV[i] * self.dt
            
            	# just to make sure the fatigue index stays within the bounds
            if (self.V[i] > 1.0):
            		self.V[i] = 1.0
            if (self.V[i] < 0.0):
            		self.V[i] = 0.0
        
        return self.V
        	# NOTE: It is crucial that this loop runs with the defined sample time, otherwise the integration of fatigue will not work properly!


