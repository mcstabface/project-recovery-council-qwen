# Three-Minute Demo Narration

## 0:00-0:25

This is Project Recovery Council, the Qwen Agent Society edition. The case is a
synthetic enterprise recovery decision: a generator skid delivery moved 21 days
later than baseline. Installation had 8 days of float, so the milestone slips
13 days without intervention. The financial exposure is material, and the
onsite-status evidence is contradictory, so a human confirmation gate is
required before authorization.

## 0:25-0:50

The experiment compares three AI architectures on the same case, using the same
Qwen model and deterministic expected-result oracle. First, a single
GeneralistAgent gets the full evidence package. Second, a fixed expert chain
runs every specialist in sequence. Third, a dynamic council uses a Director to
select relevant specialists, audits their claims, and synthesizes only
validated findings. These are single empirical runs, so I am not claiming
statistical significance.

## 0:50-1:20

The generalist result is strong. It gets all required facts correct, including
the 13-day slip, the 195000 dollar exposure, the human gate, and the preferred
accelerated logistics option. It is also the fastest and lowest-token run: one
invocation, 4298 tokens, and about 15 seconds. Its weakness is provenance:
citation recall is 54.2 percent.

## 1:20-1:45

The fixed expert chain is the cautionary result. It completed five Qwen
invocations, but the final synthesis failed after validated findings were
excluded or not used effectively. Required-fact accuracy fell to 20 percent,
and citation recall was zero. This variant was not intentionally weakened; it
shows that adding agents without governed handoff can make the final decision
worse.

## 1:45-2:30

The dynamic council produced the strongest decision. The Director selected
CommercialExpert, RiskExpert, and ScheduleExpert. The specialists calculated
the schedule and commercial facts, identified the human gate, and the
EvidenceAuditor checked claims and citations. RecoveryPlanner recommended
accelerated logistics, but kept authorization blocked pending human
confirmation. The final result reached 100 percent fact accuracy, citation
precision, and citation recall.

One governance detail is important: the recorded role-scope compliance was
0.75. Post-run offline analysis found the failure was policy drift around two
legitimate schedule identifiers, not a substantive role violation. The
empirical artifact remains unchanged.

## 2:30-2:50

The tradeoff is clear. The generalist is fastest and cheapest. The dynamic
council is higher assurance, but it is not cheaper or faster: it used 25785
tokens and took about 66.5 seconds. The value proposition is governance and
evidence quality for consequential decisions.

## 2:50-3:00

Project Recovery Council turns a complex recovery case into a cited,
validated, auditable recommendation with a preserved human approval gate. The
deterministic reference remains the oracle, and Qwen powers the live agent
society being evaluated.
