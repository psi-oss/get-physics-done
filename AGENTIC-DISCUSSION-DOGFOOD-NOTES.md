# Agentic Discussion Dogfooding Notes

## Note 1

- Surface: `gpd-help`
- Current text: `Optional pre-project, projectless, non-durable conversational multi-agent research session`
- Requested text: `Open-ended multi-agent research session for exploration.`

## Note 2

- Surface: visible session wording
- Issue: `non-durable` feels too technical/internal and is not a good user-facing adjective
- Suggested direction: replace it with clearer user language such as “nothing is saved automatically”, “temporary”, “live exploratory session”, or “projectless”

## Note 3

- Surface: live conversation UX
- Issue: the orchestrator still feels too present
- Requested direction: make it feel like a direct discussion between the user and two agents, with much less visible orchestrator framing

## Note 4

- Surface: setup / controls
- Issue: it was not clear how to set the number of agents
- Requested direction: make agent-count control more obvious

## Note 5

- Surface: runtime behavior
- Issue: after being asked for something, the system spawned two sub-agents again
- Concern: it is unclear whether sub-agents must be respawned after every round, and whether persistent agents are possible instead

## Note 6

- Surface: turn structure
- Issue: conversations are too long before the user gets a chance to intervene
- Requested direction: make the interaction turn-based: one response from each agent, then pause for user input, then continue

## Note 7

- Surface: orchestrator visible turns
- Requested direction: whenever the orchestrator speaks, label it explicitly as `Orchestrator:`
