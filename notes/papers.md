# Papers

Plain-language summary in parentheses for every one. Tag says how it matters to us.

---

## The anchor

### Zhang, Jiang, Ajoudani, Tsagarakis (2026)
*Muscle Fatigue-Aware Controller for a Semi-Rigid Knee Exoskeleton.* IEEE T-ASE 23:44-58.
Open access. **THE PAPER WE EXTEND.**

(They built a powered knee brace that notices when your thigh muscles are getting tired and quietly
gives you more help as that happens. The clever part: normally you would need sticky electrode pads
on the skin to measure muscle effort, and those are fragile and uncomfortable for all-day use. They
avoid that by teaching the system, once, in a lab session, how muscle effort relates to how the leg
is moving and how hard it pushes on the ground. After that it only needs the sensors already built
into the brace. Tested on three people doing squats and stair steps.)

Full teardown: `docs/mfac_teardown.md`.

---

## The fatigue model lineage

Our whole fatigue model comes down this chain. Each paper inherits the previous one's equation.

### Ma, Chablat, Bennis, Zhang (2009)
*A new simple dynamic muscle fatigue model and its validation.* Int J Ind Ergonom 39(1):211-220.

(The original idea: treat tiredness as a single number between 0 and 1 that climbs while a muscle is
working and falls while it rests. How fast it climbs depends on how hard the muscle is working.
Simple enough to compute in real time, which is why everyone downstream uses it.)

### Ma, Chablat, Bennis, Zhang, Guillaume (2010)
*A new muscle fatigue and recovery model and its ergonomics application in human simulation.*
Virtual and Physical Prototyping 5(3):123-137. **NEEDED FOR E6 — not yet obtained.**

(The follow-up that looks properly at the recovery side: how fast a muscle bounces back once you
stop using it. This is where published recovery-rate values live. We need it because everyone since
has just borrowed one number, 0.5, without justifying it.)

### Peternel, Tsagarakis, Caldwell, Ajoudani (2018)
*Robot adaptation to human physical fatigue in human-robot co-manipulation.*
Autonomous Robots 42(5):1011-1021. **Not obtained. No longer on the critical path.**

(Where the simplified tiredness equation first appears, driven by muscle electrical signals. Also
the origin of the recovery-rate value 0.5 that all later papers reuse. We stopped needing it once
the authors' own source code turned up, which contains the same equation and the same number.)

### Peternel, Fang, Tsagarakis, Ajoudani (2019)
*A selective muscle fatigue management approach to ergonomic human-robot co-manipulation.*
RCIM 58:69-79. **SECOND MOST IMPORTANT PAPER FOR US.**

(A robot holds a workpiece while a person drills or polishes it. The robot tracks tiredness in each
individual arm muscle, and when one group gets tired it rotates the workpiece so a different, rested
group takes over. The tired ones recover while work continues. Tested on six people, and it worked —
the tired muscles visibly recovered while the fresh ones took the load.)

Why it matters so much:
- Contains the **per-muscle** version of the equation, which Zhang et al. later collapsed back to a
  single number. Our E3 just restores what this paper already had.
- Contains a working demonstration of **shifting load between muscle groups to last longer**, which
  is the core idea behind our E2. So the idea is proven, not speculative.
- Gives a ready-made goal to optimise: make the *weakest* muscle last as long as possible.

Full teardown: `docs/peternel2019_teardown.md`.

---

## Closest competitors — found in the PubMed sweep, 2026-09-19

### Lambeth, Hakam, Sharma (2025)
*Bio-Inspired Synergistic Model Predictive Control for Control Reallocation and Reduced
Computational Cost in a Hybrid Exoskeleton.* IEEE TNSRE 33:3755-3769.
https://doi.org/10.1109/TNSRE.2025.3608567 — **SCOOPED OUR E9. NARROWS E2.**

(A walking aid combining two ways of moving the leg: electrical pulses that make the person's own
muscles contract, and motors at hip, knee and ankle. Deciding how much of each to use, at every
joint, every instant, is slow to compute. So instead of controlling every actuator separately they
group them into a handful of natural combinations, cutting computing time by about a quarter. They
show that when one muscle tires, the system shifts effort onto the others.)

- The grouping-into-natural-combinations idea was going to be our E9. It is theirs. Drop the claim,
  use the method, cite them.
- The "shift effort when a muscle tires, across hip/knee/ankle" result is very close to our E2.
- **What still separates us:** their tiredness is caused by the electrical stimulation itself, which
  behaves quite differently from ordinary tiredness from walking. And they never deal with muscles
  that span two joints, which is our angle.

### Bao, Molazadeh, Dodson, Dicianno, Sharma (2020)
*Using Person-Specific Muscle Fatigue Characteristics to Optimally Allocate Control in a Hybrid
Exoskeleton.* IEEE TMRB 2(2):226-235. https://doi.org/10.1109/TMRB.2020.2977416

(Helping someone stand up from sitting, using both electrical muscle stimulation and a motorised leg
brace. The system measures how quickly that specific person's muscles tire and recover, and uses it
to decide moment by moment how much of the work the person's own muscles should do versus the motor.
Tested on two people without disability and one with a spinal cord injury.)

Fatigue-driven control allocation has existed since 2020 — again for the electrical-stimulation
case, not ordinary walking fatigue.

### Divekar, Thomas, Yerva, Frame, Gregg (2024)
*A versatile knee exoskeleton mitigates quadriceps fatigue in lifting, lowering, and carrying
tasks.* Science Robotics 9(94):eadr8282. https://doi.org/10.1126/scirobotics.adr8282
**Must cite and distinguish — high-profile and adjacent.**

(A powered knee brace for warehouse-type work: repeated lifting, lowering and carrying, plus walking
on flat ground, ramps and stairs. It recognises which task you are doing and changes how it helps,
automatically, without needing setup for each individual. Tested on ten people. It reduced
thigh-muscle effort across most tasks and, importantly, reduced the drop in performance and the
slumping posture that appear once people get tired.)

Adjacent rather than competing: it reacts to task type, not to a running estimate of how tired the
muscle currently is. But it is in a top venue covering the same application, so a reviewer will
expect us to have read it.

### Bryan, Franks, Song, Reyes, O'Donovan, Gregorczyk, Collins (2021)
*Optimized hip-knee-ankle exoskeleton assistance reduces the metabolic cost of walking with worn
loads.* J NeuroEng Rehabil 18:161. https://doi.org/10.1186/s12984-021-00955-8

(Assisting all three leg joints at once while someone walks carrying weight, and tuning the help by
trial and error on the actual person while they walk, measuring their breathing to see what works.
Cut the effort of walking by roughly 40-48 percent. Notably, *when* to push mattered more than *how
hard* — the timing settings came out nearly identical across people, the strength settings did not.)

The whole-leg assistance precedent, with no tiredness modelling at all. Good non-fatigue baseline
for E2, and the timing-versus-strength finding is worth knowing.

### Romero-Sanchez, Bermejo-Garcia, Barrios-Muriel, Alonso (2019)
*Design of the Cooperative Actuation in Hybrid Orthoses.* Front Neurorobot 13:58.
https://doi.org/10.3389/fnbot.2019.00058

(A leg brace covering hip, knee and ankle that combines motors with electrical muscle stimulation.
Works out how much stimulation each muscle should get so the movement comes out natural, and adjusts
for the fact that stimulated muscles weaken quickly.)

### Co, Begon, Bailly, Moissenet
*Optimal control driven functional electrical stimulation: A scoping review.* Search to Feb 2024.
**Mine its reference list — still outstanding.**

(A survey of 44 studies that use electrical pulses to make paralysed muscles move, where the pulse
pattern is worked out by a computer rather than set by hand. Half were computer simulations only,
which is reassuring for us. Its conclusion is that the field cannot agree on how to model muscle
tiredness and rarely reports how long the computations take.)

Its references are the best available map of "tiredness modelled inside an optimiser". Needed to
settle whether E1's novelty claim is "first ever" or "first in this application".

### Toffoli, Tounekti, Hakim, Cocquerez, Ben Mansour (2026)
*Muscle fatigue and postural balance reorganisation during exoskeleton-assisted load handling.*
Gait & Posture 130:110613.

(Nineteen people held a 10 kg weight out in front of them until they could not hold it any longer,
with and without a spring-loaded arm support. The support almost tripled how long they lasted — 896
seconds versus 307. But it also changed how they balanced: their sway became more repetitive and
less varied, suggesting the body switches to a simpler balancing strategy when it is being helped.)

Two uses. It justifies "how long until exhaustion" as the right thing to measure, and gives a sense
of the effect size worth chasing. And it is a warning — help has side effects on things you were not
measuring, which a reviewer will raise.

### Bergmann, Hansmann, von Platen, Leonhardt, Ngo (2025)
*Fatigue assessment and control with lower limb exoskeletons.* IEEE Trans Hum-Mach Syst 55(1):10-22.
**Zhang et al. name this as their closest alternative. Not yet read.**

(Uses a more detailed tiredness model — one that splits a muscle into working, tired and resting
portions — inside a leg exoskeleton, and tunes the help using both how tired the person says they
feel and their measured strength loss.)

### Sheng, Iyer, Sun, Kim, Sharma (2022)
*A hybrid knee exoskeleton using real-time ultrasound-based muscle fatigue assessment.*
IEEE/ASME Trans Mechatron 27(4):1854-1862.

(Uses ultrasound imaging to watch the muscle physically thicken as it tires, and adjusts the brace
accordingly. Accurate, but the equipment is bulky and the probe has to stay put, so it suits a lab
rather than a workplace.)

### Del-Ama, Gil-Agudo, Pons, Moreno (2014)
*Hybrid FES-robot cooperative control of ambulatory gait rehabilitation exoskeleton.*
J NeuroEng Rehabil 11:27.

(Walking rehabilitation combining electrical muscle stimulation with a powered brace, using a rough
running total of how much work a muscle has done as a stand-in for how tired it is.)

---

## Tools and background

### Andersson, Gillis, Horn, Rawlings, Diehl (2019)
*CasADi: a software framework for nonlinear optimization and optimal control.*
Math Program Comput 11(1):1-36. **We use this. So do Zhang et al.**

(The maths engine that solves "what is the best thing to do next" problems. Its useful trick is
working out exact sensitivities automatically — how much the answer shifts if you nudge any input —
which lets it find good solutions quickly instead of guessing. This is precisely why the
non-smooth switch in the fatigue equation is a problem: at the switch, that sensitivity does not
exist.)

### Dembia, Bianco, Falisse, Hicks, Delp (2020)
*OpenSim Moco: Musculoskeletal optimal control.* PLoS Comput Biol.

(Free software that works backwards from a recorded movement to figure out what each muscle must
have been doing, and forwards to predict movements nobody recorded. Also built on CasADi, which is
convenient — same engine throughout our pipeline.)

### Dembia, Silder, Uchida, Hicks, Delp (2017)
*Simulating ideal assistive devices to reduce the metabolic cost of walking with heavy loads.*
PLoS ONE.

(Before building any hardware, simulate a perfect imaginary helper at each joint and see how much
easier walking gets. Tells you which joint is worth assisting before anyone machines a part.)

### Xia, Frey-Law (2008)
*A theoretical approach for modeling peripheral muscle fatigue and recovery.* J Biomech.
**Deliberately NOT used — see decisions.md.**

(A more detailed tiredness model: instead of one number it splits the muscle into three parts —
currently working, worn out, and available to be recruited — and tracks the flow between them.)

We stayed with the simpler Ma/Peternel model so our numbers stay directly comparable to Zhang et al.

### Camargo et al. (2021)
*A comprehensive, open-source dataset of lower limb biomechanics in multiple conditions of stairs,
ramps, and level-ground ambulation and transitions.* J Biomech.

(Free recordings of 22 people walking on flat ground, ramps and stairs, with their movement, the
force under their feet, and their muscle electrical signals captured together. Saves us collecting
our own data. Not needed yet — nothing so far has used real subject data.)

### Zhang, Ajoudani, Tsagarakis (2021)
*Exo-Muscle: A semi-rigid assistive device for the knee.* IEEE RA-L 6(4):8514-8521.

(The hardware used in the anchor paper. A cable-driven knee support — a motor pulls a cable routed
along a guide, which helps straighten the knee. Source for the real force limits we used.)

### Rajagopal et al. (2016), Umberger (2010), Falisse et al. (2019), Anderson and Pandy (2001)

(In order: a detailed digital skeleton-and-muscle model of the whole body; a way of estimating how
much energy muscles burn; techniques for making these simulations run in minutes rather than hours;
and a finding that for walking, the quick estimation method gives nearly the same answer as the slow
thorough one. That last one matters — it undercuts an argument we were going to make for E4, so we
had to change how E4 is justified.)

---

## Not worth your time

### Nacarino et al. (2026)
*Mechatronic Design and Development of a Lower-Limb Exoskeleton System...* Bioengineering 13(6):644.

(A hardware description of an air-powered knee brace for helping elderly people walk.)

Only use: plausible numbers for how strong and heavy a brace is. Lower-tier venue, no method we
need. One intro citation at most.
