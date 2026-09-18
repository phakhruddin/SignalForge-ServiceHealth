# SignalForge — Service Health

A Dev Cloud scenario in the **Observability and Monitoring** taxonomy. An
asynchronous API can accept jobs while its worker is stalled; a synthetic
customer journey, structured telemetry, and alarms must expose that hidden
failure. Participants deploy supplied API, worker, and canary images and build
their AWS-compatible monitoring control plane with Terraform or OpenTofu.

- [`instruction.md`](instruction.md) is the participant-facing task.
- [`environment/workspace/contracts/`](environment/workspace/contracts/) contains
  the public runtime, infrastructure, observability, and manifest contracts.
- [`solution/`](solution/) is the reference Terraform implementation.
- [`tests/`](tests/) contains the behavior-led 100-point verifier.
- [`reasoning.md`](reasoning.md) explains the design and scoring intent.

The local setup uses Docker Compose and a pinned Floci emulator image. From the
repository root, `rv check --skip-judges` validates task structure. The full
local oracle run requires Docker and the `rv` runner; it builds the workload
images in `runtime-setup`, then executes the reference solution and verifier.
No real AWS account is contacted.

Validation: the reference solution passed the local 20-block verifier at
**100/100**. `rv check --skip-judges` passed all 20 Realm checks and all 18
static checks. `rv oracle` completed with one trial, zero exceptions, and a
**1.000 reward (100/100 score)**.
