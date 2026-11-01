# Dev reading (packet, prompt hash pk20ae709d578f)

ALL DATA IS SYNTHETIC. The disease is fictional.

No dev target was missed, so there were no failing graders to read. The one packet that fell back to the template (1 of 500) was read: the
model named a lab in a sentence that did not cite it, the verifier rejected the draft (`lab`) and the template summary was shown, as designed.
The first prompt version met every target, so it was frozen without iteration.

Limit of the dev evidence: C1 is unmet for 488 of 500 patients and met for 2, so its accuracy of 1.0 says little about the met case.

# Test reading (after the freeze, one look)

C2 accuracy 0.9946 (5 of 931 wrong) and gap recall 0.9983 missed their targets. All 5 C2 errors were read: each is a symptom the existing
note reader read differently from the note's plan (a tremor read as not mentioned, a hedged symptom read as present or absent, a symptom
read as not mentioned). The packet logic followed those readings correctly, and the 3 missed gaps are the same records (a criterion decided
wrongly from a misread symptom is not marked unknown). The packet adds no error of its own on C1 or C3 to C6. The fix, if wanted, belongs to the
note reader, which this change does not touch.
