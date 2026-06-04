<purpose>
Present the candidate persona patch for review and route durable mutation only
through the local research-persona CLI.
</purpose>

<process>
1. Show a concise summary of source modes, facts, axes, list changes, privacy
   labels, and inferred or low-confidence entries.
2. Show the local review sequence:

```text
gpd research-persona validate
gpd research-persona diff GPD/persona/candidate-patch.json
explicit user approval
gpd research-persona apply-patch GPD/persona/candidate-patch.json
```

3. Explicit user approval is required before mutation. Do not apply-patch until
   approval is given after the candidate patch and diff are reviewed.
4. Do not imply that source ingestion has changed durable persona memory;
   ingestion only produced a candidate patch.
5. If the user declines, stop without mutation and keep the candidate patch as
   a review artifact only.
6. If the user approves and asks you to apply it, run only the CLI
   `apply-patch` command and then validate the stored persona through the CLI.
7. After application, offer prompt-safe capsule and preview commands only; do
   not read raw persona storage or hand raw profile contents to application
   agents.
</process>

<forget_route>
For later removal, direct the user to:

```text
gpd research-persona forget <fact-id>
```
</forget_route>

<post_apply_guidance>
Use these only after the user-approved patch has been applied, or against an
already-existing persona profile:

```text
gpd research-persona export-capsule --role doppelganger
gpd research-persona export-capsule --role explainer
gpd research-persona export-capsule --role taste
gpd research-persona doppelganger --task "<current research decision>"
gpd research-persona explain-plan PLAN_JSON|- --task "<explanation target>"
gpd research-persona taste-check CANDIDATE_JSON|- --focus "<direction set>"
```

These commands use prompt-safe capsules or advisory previews. They do not
mutate persona storage and they do not authorize raw profile reads.
</post_apply_guidance>
