# Dev and test reading (packet, policy v2, prompt hash pk20ae709d578f)

ALL DATA IS SYNTHETIC. The disease is fictional.

**Dev (500).** No target was missed, so there were no failing graders to read. The summary prompt is unchanged from v1 and was frozen without iteration.
C1 is now met for 33 dev patients (v1: 2), unknown for 19 and unmet for 448, so the met path is exercised (the coverage rule asks for at least 20).

**Test (931, one look, after the freeze).** Two targets were missed, the same two as under v1: C2 accuracy 0.9946 and gap recall 0.9983. All five C2 errors
were read and are the same five records as under v1 (P20261-000533-m1, -000725-m1, -001966, -003054, -003539): each is a symptom the existing note reader
read differently from the note's plan, and the packet followed that reading correctly. The three missed gaps are those same records. C1 had no error on 931
patients (met for 54, unknown for 36, unmet for 841), and C3 to C6 had none. The fix, if wanted, belongs to the note reader, which this change does not touch.

**Template fallbacks rose.** The summary fell back to the fixed template for 6 of 500 dev packets (1.2%) and 18 of 931 test packets (1.9%), against 0.2% and 0.4% under v1.
The verifier's reason classes: dev 5 `status_text` and 1 `lab`; test 13 `status_text` and 5 `lab`. The service does not keep a rejected draft's text, so the exact wording that
tripped each check was not read. The likeliest cause is the new C1 evidence text (thresholds, "not above", longer sentences) giving the model more ways to word a
sentence that contains a different status word from the table. A fallback is a safe outcome (the template is shown and no fabricated sentence was), but it is a
quality cost; reading raw drafts would need the service to retain them for evals, which this change does not add.
