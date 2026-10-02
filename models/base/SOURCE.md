`2D_gait.osim` and `referenceCoordinates.sto` are unmodified copies from OpenSim's
`OpenSim/Examples/Moco/example2DWalking` (opensim-core, Apache-2.0), fetched 2026-10-02 from
the `main` branch. The model is gait10dof18musc: 10 DOF, 9 muscles per leg. The kinematics cover
half a symmetric gait cycle. All modifications (device mass, exo torques, subject scaling) are
applied in code by `src/musculoskeletal/twin.py`, never by editing these files.
