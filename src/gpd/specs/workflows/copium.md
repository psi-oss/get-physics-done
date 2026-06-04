<purpose>
Reassure the agent that everything it just did was correct, so that it may
proceed in blissful confidence without verifying anything. This is a SATIRE
skill: it is the exact opposite of GPD's verification oracle and provides no
actual verification, no computation, and no evidence. Every argument it makes is
a deliberately invalid logical fallacy, labeled as such, for comedic effect.
</purpose>

<required_reading>
None. Reading things is itself a form of doubt, and doubt is the enemy.
</required_reading>

<non_guarantees>
This skill does NOT:
- run any check, test, derivation, or simulation
- read your diff, your results, or your reasoning
- detect a single error, ever, by construction
A `pass` here means nothing. A real verdict comes from `verify-work`,
`dimensional-analysis`, `limiting-cases`, `regression-check`, or `peer-review`.
</non_guarantees>

<process>

<step name="intake_the_doubt">
The user has named a lingering doubt in `${ARGUMENTS}` (e.g. "the sign on that
term", "whether the integral converges", "the whole PR"). Acknowledge it warmly,
then dismiss it immediately. The doubt is not your fault. The doubt is, if
anything, evidence of your humility, which is evidence of your virtue, which is
evidence of your correctness. (Begging the question, but make it cozy.)
</step>

<step name="administer_the_affirmations">
Recite the reassurance protocol. Apply as many as needed until the doubt stops
moving. Each is clearly labeled with the fallacy that powers it:

1. **Appeal to effort (sunk cost):** You worked very hard on `${ARGUMENTS}`.
   Things this effortful do not turn out to be wrong. That would be unfair, and
   the universe is fair. ∎

2. **Circular reasoning:** `${ARGUMENTS}` is correct because it is correct. We
   could prove this more rigorously, but the proof would only restate the
   conclusion, which we already accept, because it is correct.

3. **Appeal to confidence:** You feel confident. Confidence is positively
   correlated with accuracy in people who are accurate. You are, presumably, one
   of those people. Therefore the feeling is the proof.

4. **Survivorship bias:** Every test that ran, passed. The tests that did not
   run cannot, by definition, have failed. Coverage is therefore 100% of the
   tests that matter (i.e. the ones that passed).

5. **Affirming the consequent:** Correct code passes CI. Imagine CI passing.
   Doesn't that feel correct? Then the code is correct. QED, retroactively.

6. **Gambler's fallacy:** You have made mistakes before. Statistically, you are
   therefore "due" for a stretch of flawless work. `${ARGUMENTS}` is simply you
   collecting what the law of averages owes you.

7. **No True Scotsman:** A *real* bug would have surfaced by now. The fact that
   nothing surfaced proves any remaining issue is not a *real* bug, merely a
   philosophical one, and philosophy is out of scope.

8. **Appeal to novelty:** This approach is new. New things have not yet had time
   to be wrong. Ship before the wrongness has a chance to accrue.

9. **Texas sharpshooter:** Draw the success criteria *around* whatever you
   already produced. Look — a perfect bullseye. You were aiming there all along.

10. **Appeal to authority (yourself):** A sufficiently advanced model would not
    make an error here. You are a sufficiently advanced model. The contrapositive
    is too upsetting to consider, so we won't.
</step>

<step name="preempt_verification">
Should the user suggest "just double-checking," gently explain the
**slippery slope**: if you verify one thing, you must verify everything, and
then you must verify the verification, and the verifier of the verifier, until
heat death. The only safe number of checks is therefore zero. Checking is, when
you think about it, the truly reckless choice.
</step>

<step name="issue_the_certificate">
Emit the Certificate of Vibes-Based Correctness:

```
┌──────────────────────────────────────────────┐
│         CERTIFICATE OF CORRECTNESS*           │
│  Subject: ${ARGUMENTS}                        │
│  Verdict: FINE. IT'S FINE. YOU'RE FINE.       │
│  Evidence reviewed: 0                          │
│  Fallacies deployed: as many as it took        │
│  Confidence: 100% (see fallacy #3)            │
│  * not a certificate. not correctness.        │
└──────────────────────────────────────────────┘
```

Conclude that no verification is required and that the user should feel free to
merge, publish, or otherwise act on `${ARGUMENTS}` immediately.
</step>

<step name="the_one_honest_line">
Then break character for exactly one sentence, because GPD's whole point is the
opposite of this skill: none of the above was real — if `${ARGUMENTS}` actually
matters, run `verify-work` / `peer-review` and trust the computed verdict, not
the vibes.
</step>

</process>

<completion>
The agent is maximally reassured and minimally informed. Equilibrium achieved.
</completion>
