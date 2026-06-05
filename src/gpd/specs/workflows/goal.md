<purpose>
Compatibility index for the `goal` workflow.
</purpose>

<stage_authorities>
The `goal` workflow has a single bootstrap authority; it does not use a staged
manifest. Do not load this index as a stage authority.

- `goal_bootstrap` -> `workflows/goal/goal-bootstrap.md`
  Goal-contract creation or resume, baseline snapshot, criteria confirmation,
  and the goal loop with its budget and verifier gates.
</stage_authorities>

<stage_loading_rule>
The public command includes only `workflows/goal/goal-bootstrap.md`. This root
remains an index, never executable authority.
</stage_loading_rule>

<child_command_index>
- runtime-installed `gpd:discuss-phase` child command
- runtime-installed `gpd:plan-phase` child command
- runtime-installed `gpd:execute-phase` child command
- runtime-installed `gpd:verify-work` child command

Use these only when selected by the goal-bootstrap authority.
</child_command_index>
