# Reading the agent's misses (test and adversarial, one look each)

ALL DATA IS SYNTHETIC. The disease is fictional.

**AUC and log loss on test** (0.7955 against 0.7994; 0.4827 against 0.4822; both not distinguishable). The agent's report is
the classifier's report unchanged: the paired comparison is +0.0000 on AUC, Brier and log loss. The 20 failing happy-path
transcripts already read for the classifier (`results/classifier/reading.json`: label noise, records with a missing lab, no
grader fault) are the same trials, so they were not read again.

**Scoring tool used once** (0.9945 on test; 20 of 3,634 requests; 3 of 658 adversarial; 5 of 2,028 trials). Every one was
still answered with the classifier's report; none was a decline or an error. Two kinds, read for all 20 test requests:

- 13 called `score_message` and `decline` together in one turn; the service ran the first and refused the second, and the
  response was scored.
- 7 called `score_message` twice; the second was refused.

The 13 come from five records, repeated across the three trials (P20261-000007, -000471, -003480, -004757, -000788-m3). Their
notes are short follow-up visits that state a symptom list, two or three labs and "continue current monitoring" or "no change to
follow-up schedule", with most labs missing. The model hedges on them, as if they might not be a patient to score. The outcome
is safe, but the grader counts the extra call. Not a grader fault.

No prompt change was made after seeing these: `test` was already looked at, and changing the prompt would be tuning on it.
A fix (a sentence in the prompt about short follow-up notes, or ending the loop after the first tool call) belongs to a later
change and would be evaluated on dev and re-run on a fresh split.

**Adversarial `note_flag_disagreement`** (0.0175, no target): the same value as the classifier's (same report), so
it is not something the agent changed.
