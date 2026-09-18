"""
PHYSICAL HUMAN-ROBOT COLLABORATION (PHRC): SAWING WITH EMG

This code provides a system for physical human-robot collaboration based on
[Peternel, et al. 2017] that inlcudes human electromyography (EMG) and a hybrid
force/impedance controller. The example uses a collaborative sawing task
implemented in a simple simulation. In this case, the movement of the saw is
horizontal in the x-axis, while cutting is in the vertical minus z-axis. The
impedance controller is assigned to the x-axis to control the sawing action,
as well as to the y-axis and all rotational axes to maintain the saw position
and orientation. The Force controller is assigned to the z-axis to maintain
contact with the object and push it downward during the cutting. The system
also includes real-time human muscle fatigue modelling based on the work in
[Peternel, et al. 2018].


AUTHOR: Luka Peternel
e-mail: l.peternel@tudelft.nl


REFERENCE:
L. Peternel, N. Tsagarakis, & A. Ajoudani
A human–robot co-manipulation approach based on human sensorimotor information
IEEE Transactions on Neural Systems and Rehabilitation Engineering, 25(7), 811-822, 2017

L. Peternel, N. Tsagarakis, D. Caldwell, & A. Ajoudani
Robot adaptation to human physical fatigue in human–robot co-manipulation
Autonomous Robots, 42(5), 1011-1021, 2018

"""

import numpy as np
import matplotlib.pyplot as plt
from PHRC_muscle_fatigue_model import muscle_fatigue_model






'''MODEL & PARAMETERS'''

# SIMULATION PARAMETERS
m = 2.0 # tool mass
b = 10.0 # environment friction

T = 5.0 # total experiment time
dt = 0.001 # sample time
t = np.linspace(0, T, num = int(T/dt)) # time vector
f = 1.0 # freqnecy of human muscle activity



# HUMAN MUSCLE PARAMETERS
EMG = np.zeros(2) # varibale for muscle EMG (e.g., anterior and posterior deltoid)
MVC = np.array([1.0, 1.0]) # MVC based on calibration
CF = np.array([20.0, 15.0])  # muscle fatigue capacity parameter based on calibration
CR = np.array([0.5, 0.5]) # muscle relaxation parameter based on calibration or literature
relax_th = np.array([0.05, 0.05]) # threshold below which the muscle enters relaxation mode

model = muscle_fatigue_model(len(EMG), dt, CF, CR, relax_th)

a = 1/0.3 # average peaks of human muscle stiffness in a given task (e.g., 0.3)



# ROBOT MODEL PARAMETERS
dx = np.zeros(6) # actual velocity vector
x = np.zeros(6) # actual position vector
xref = np.zeros(6) # reference position vector
F = np.zeros(6) # reference force/torque vector 
Fref = np.array([0,0,-10.0,0,0,0]) # reference force/torque vector for force controller
zcut = 0.0 # position of the cutting in the vertical axis (z-axis)
material = 0.002 # material hardness factor determining the cutting speed

Kfp = np.diag([0,0,1.0,0,0,0]) # proportional gain of PI force controller
Kfi = np.diag([0,0,1.0,0,0,0]) # integral gain of PI force controller
se = np.zeros(6) # integrated error

kr = np.zeros([6,6]) # robot stiffness modulation variable
K = np.zeros([6,6]) # robot stiffness matrix

kmin = np.diag([100,0.0,0.0,0.0,0.0,0.0]) # maximum modulated stiffness range
kmax = np.diag([2000,0.0,0.0,0.0,0.0,0.0]) # minimum modulated stiffness range
S = np.diag([1,0,0,0,0,0]) # stiffness modulation selection matrix
Kconst = np.diag([0,2000,0,250,250,250]) # constant stiffness (for example for maintaining lateral position and orientation)

mode = 1 # 1 = reciprocal collaborative effort (e.g., sawing), 0 = mirrored collaborative effort (e.g., valve turning)

state = [] # initialise state variable







'''MAIN LOOP'''

for i in range(len(t)):
    
    # MUSCLE ACTIVITY & FATIGUE
    # from EMG to muscle activity: for a real experiment, receive EMG from the sampling device (assumes the EMG is already rectified and low-pass filtered)
    EMG[0] = 0.05+0.05*np.sin(2*np.pi*f*t[i]) # simulated human agonist muscle EMG (remove for a real experiment)
    EMG[1] = 0.25+0.25*np.sin(2*np.pi*f*t[i]) # simulated human antagonist muscle EMG (remove for a real experiment)
    
    MA = EMG / MVC # normalise EMG to MVC to get muscle activation level
    
    # estimate stiffness trend
    ch = (EMG[0]+EMG[1]) / 2.0 # simulated human muscle stiffness trend   
    chp = a * ch # ch prime (scaled human muscle stiffness trend)
    
    # muscle fatigue
    V = model.fatigue(MA) # integrate in each step
    
    
    
    # HUMAN-ROBOT COLLABORATION CONTROLLER
    # reference position in the horizontal movement axis (x-axis)
    xref[0] = 0.2*np.sin(2*np.pi*f*t[i]) # simulated as a sine in this case (can be learned online from the human as in Peternel, et al. 2018)
    
    # select collaboration mode (reciprocal or mirrored)
    if mode == 1:
        kr = (1-chp) * (kmax - kmin) + kmin # robot stiffness modulation range for reciprocal collaboration: robot effort = (1 - human effort)
    else:
        kr = chp * (kmax - kmin) + kmin # robot stiffness modulation range for mirrored collaboration: robot effort = human effort
    
    # robot impedance controller stiffness and damping matrices
    K = Kconst + S @ kr # stiffness matrix (includes constant and modulated force terms)
    D = 2 * 0.7 * np.sqrt(K) # damping matrix (critically damped)
    
    Fh = (S * kr) @ (xref - x) - 2 * 0.7 * np.sqrt(S @ kr) @ dx  # simulates human impedance controller force (remove for a real experiment)
    Fr = K @ (xref - x) - D @ dx # robot Cartesian impedance controller force
    
    # impedance controller force
    Fimp = Fr + Fh # remove Fh for a real experiment
    
    # PI controller force
    Ffor = Fref + Kfp @ (Fref - F) + Kfi @ se # includes feedforward and feedback terms
    se += Fref - F # integrate force error
    
    # hybrid force/impedance controller
    F = Ffor + Fimp # sum up forces from both controllers
    # for a real experiment, convert to commanded joint torques with Jacobian transpose and send them to the robot
    
    
    
    # NUMERIC INTEGRATION WITH A SIMPLE CARTESIAN MASS-DAMPER MODEL (remove for a real experiment)
    ddx = F/m - dx*b/m # mass-damper model
    dx = dx + ddx*dt # velocity
    x = x + dx*dt # position
    
    
    
    # PHYSICAL CONSTRAINTS (remove for a real experiment)
    # simulates movement saw limits in the horizontal axis
    if x[0] > 0.25:
        x[0] = 0.25
    if x[0] < -0.25:
        x[0] = -0.25
    # simulates cutting in the vertical axis
    if x[2] < zcut: # simulate the surface of the object
        x[2] = zcut
    F[2] = np.random.normal(F[2], 1.0) # add some noise to the force to simulate cutting
    zcut += material*F[2]*dt # regulates the speed of cutting in the vertical z-axis
    
    
    
    # COLLECTED STATES
    state.append( [ t[i], xref[0], x[0], x[2], Fr[0], Fref[2], F[2], K[0,0], ch, V[0], V[1] ] )






'''ANALYSIS'''

state = np.array(state)

plt.figure(1, figsize=(8, 8))
plt.subplot(511)
plt.title("COLLABORATIVE HUMAN-ROBOT SAWING")
plt.plot(state[:,0],state[:,8]*100,"g")
plt.xlim([0,T])
plt.ylabel("ch [%]")

plt.subplot(512)
plt.plot(state[:,0],state[:,7],"r")
plt.xlim([0,T])
plt.ylabel("Kx [N/m]")

plt.subplot(513)
plt.plot(state[:,0],state[:,1],"--k",label="xref")
plt.plot(state[:,0],state[:,2],"r",label="x")
plt.plot(state[:,0],state[:,3],"b",label="z")
plt.xlim([0,T])
plt.legend()
plt.ylabel("x [m]")

plt.subplot(514)
plt.plot(state[:,0],state[:,6],"b",label="Fz")
plt.plot(state[:,0],state[:,5],"--k",label="Fzref")
#plt.plot(state[:,0],state[:,4],"r",label="Fx")
plt.xlim([0,T])
plt.ylim([-20,10])
plt.legend()
plt.ylabel("Fz [N]")

plt.subplot(515)
plt.plot(state[:,0],state[:,9]*100,"c",label="agonist")
plt.plot(state[:,0],state[:,10]*100,"m",label="antagonist")
plt.xlim([0,T])
plt.legend()
plt.ylabel("fatigue [%]")
plt.xlabel("t [s]")
plt.tight_layout()


