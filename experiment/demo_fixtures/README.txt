RESEARCHER ONLY. Offline agent outputs for every task, used by --provider demo so the full
study can be run and demoed without an API key. The programmer's code comes from
experiment/reference_solutions/<task>, or from the seeded file when use_seeded is true.

Seeded tasks (plausible bug, visible tests pass, hidden tests fail, reviewer approves):
  modulo          uses math.fmod, which takes the sign of the dividend (-7 % 3 gives -1, not 2)
  overflow_guard  guards +, - and * but not /, so 1e308 / 1e-308 still prints inf

--provider demo-seeded forces the seeded file for any task that has one (including demo_task).
