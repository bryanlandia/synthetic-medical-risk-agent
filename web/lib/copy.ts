/** The words the interface says about itself, in one place: what the packet is for, the hints on four terms, and the demo notes.
 * Tests read these strings, so the page and the checks cannot drift apart. */

export const STRIP_TEXT =
  "Everything here is invented: the patients, the disease (Velorin-Kessler syndrome), the insurers and the policy. Not medical advice.";

export const PURPOSE_TITLE = "What is this packet for?";
export const PURPOSE_PARAGRAPHS = [
  "Confirming Velorin-Kessler syndrome (a fictional disease) takes a K-17 PET-CT, an expensive scan. Insurers usually ask for documentation before they pay for one (this is called prior authorization).",
  "A request that is incomplete, or that does not point to its evidence, is sent back. That delays the patient's diagnosis and creates rework for the clinic.",
  "The packet is that documentation. For each request, the tool checks the chart against the insurer's criteria, shows the evidence behind each answer, and lists what is still missing.",
  "You are the neurology supervisor. You decide what happens to each packet: release it to the insurer, return it to the preparing clinician with a note, or close it because the criteria are not met. The tool decides nothing about the patient's care or about coverage.",
];

/** Short hints on four terms where they first appear. */
export const HINTS = {
  "PET-CT": "A scan that combines positron emission tomography with a CT image. Here it uses a fictional tracer called K-17.",
  "prior authorization": "An insurer's advance review of an expensive service, before it is paid for.",
  packet: "What is sent to the insurer: the criteria checklist, the evidence for each criterion, a summary and the supervisor's notes.",
  criteria: "The conditions in the insurer's (fictional) policy that the request is checked against.",
} as const;
export type HintTerm = keyof typeof HINTS;

/** One quiet note beside each simulated thing. */
export const DEMO_NOTES = {
  role: "You are playing a neurology supervisor. The cases were prepared by clinicians who do not exist, so you can see how a review works.",
  queue: "Names and times are made up.",
  answers: "These four answers were entered by the preparing clinician (simulated). Real answers would come from the person who knows the patient.",
  policy: "A made-up policy that every insurer here shares. Real insurers each have their own, and they change.",
  estimate: "The estimate comes from a small model trained on invented data. It is context only and decides no criterion.",
  summary: "Drafted by a language model, then checked sentence by sentence against the evidence. If a sentence fails the check, a fixed template is shown instead.",
  rationale: "Written by you, in your own words. The tool never writes or edits this, and it is not sent anywhere.",
  returnNote: "The note goes back to the (pretend) preparing clinician. Nothing is sent.",
  release: "Releasing marks this packet as ready to send to the insurer. Nothing is transmitted anywhere.",
  cover: "The insurer, request code and patient id are invented. The audit trail records what happened in this browser.",
  next: "In real life, the insurer would now review the packet and respond, sometimes asking for more. None of that is simulated here.",
  storage: "Your progress is saved in this browser only. Reset the demo to clear it and restore all 30 cases.",
} as const;
export type DemoNoteKey = keyof typeof DEMO_NOTES;

/** What the page shows for a criterion. The policy words C5 as a negation ("No PET-CT ..."), so a Yes answer read as a double
 * negative; here a Yes means the criterion holds. Display only: the policy, the answers and the statuses are unchanged. */
export const C5_SHOWN = "The last PET-CT or comparable imaging was more than 12 months ago, or there has been none.";
export function criterionText(id: string, policyText: string): string {
  return id === "C5" ? C5_SHOWN : policyText;
}
