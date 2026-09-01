# First shadow rollout

## Outcome

New assessment sessions freeze a communication shadow evaluator while official evaluation remains unchanged and paid shadow execution remains disabled by default.

## Scope

- Assign both platform roles to the explicitly designated platform owner.
- Publish `communication_shadow` v1 using the universal runtime contract.
- Clone `competencies_4k` v1 to v2 and add communication shadow scope `K1.1`–`K1.3`.
- Publish `4k_standard_shadow_v1` against the existing scenario and make it default.
- Do not edit any published version in place and do not enable LLM flags.

## Acceptance criteria

- [x] The designated owner has active methodologist and publisher roles.
- [x] Agent, methodology and configuration are published with frozen checksums.
- [x] Official communication agent remains v1 legacy adapter.
- [x] New default configuration contains frozen communication and shadow definitions.
- [x] Existing session snapshots remain unchanged.

## Rollback

Set `4k_standard_v1.is_default=true` and all other configurations to false in one transaction. Published additive versions may remain immutable and unused.

## Operational result

- `communication_shadow` v1 with 1200 output tokens failed contract validation on the three-skill synthetic input.
- The published v1 was not edited. `communication_shadow` v2 increased only `max_output_tokens` to 4096; `competencies_4k` v3 and `4k_standard_shadow_v2` froze that version.
- One paid synthetic shadow v2 run completed successfully: three skills compared, two exact level matches, 66.67% agreement.
- Stored comparison payloads passed the sanitization check. Persistent universal/shadow flags remain false.
- The account combining methodologist and publisher is an explicitly accepted owner-role exception; platform permissions remain independently defined.
