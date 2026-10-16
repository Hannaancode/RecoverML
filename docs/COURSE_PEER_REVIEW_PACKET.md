# Course peer-review packet â€” awaiting assignment

Prepared 16 October 2026. The author reported **no assigned reviewers and no received comments**. No review request has been sent. No genuine human/course review is claimed complete. This packet is preparation, not a completed review or manuscript revision.

## Establish the actual course obligation first

The transcribed Milestone3 rubric lists two peer-review deliverables at 35% each and an author changelog/rebuttal at 30%. That can involve both reviewing other students' assigned papers and receiving critiques of this project. Receiving two reviews is not automatically equivalent to writing the two reviews required by a course. Obtain the actual assignment instructions and instructor allocation before marking either obligation complete.

The [tracker](COURSE_PEER_REVIEW_TRACKER.json) records these as separate activities. Assignment identities, deadlines and original review documents are intentionally empty until real information is supplied. No names, scores, approvals or dates of completed review are invented.

## Material to give a reviewer

Use a fixed commit URL from the current published main/research history, recording the actual commit in the tracker when the instructor assigns the review. The technical evidence reviewed here was at `85a086b`; later review-document commits must be separately identified.

1. `paper/RecoverML_capability_loss.md` and its PDF: clearly labelled **unchanged 14 October draft**. It has not yet integrated all final studies.
2. Final result supplements: scientific `RESULTS.md`, retinal `RESULTS.md`, Letter `RESULTS.md`, native retinal DVC report, complete storage follow-up and paired native frontier RESULTS.md files, and `docs/RELEASE_STATUS_OCT16.md`. Include `docs/COMPARATOR_DECISION_OCT16.md` as an optional internal assessment, not a reviewer verdict.
3. `docs/CONTRIBUTION_POSITIONING_OCT16.md` and `docs/INTERNAL_REVIEW_OCT16.md`: optional author/internal assessments, explicitly separate from the reviewer's independent judgment. Ask the reviewer to read the manuscript first if they wish to avoid anchoring on this assessment.
4. `reproducibility.txt`, `docs/WORK_HANDOVER.md`, source/tests, and the frozen protocols. Verification entry points are `scripts/verify_release.py` and `scripts/audit_contribution_evidence.py`. State whether the reviewer ran anything or only inspected documents.
5. Actual course rubric and instructions supplied by the instructor, including any missing/cropped text. The repository transcription does not replace instructor clarification.

Do not present internal AI reports as human reviews or claim that supplying this packet completes Milestone3.

## Neutral review questions

- Summarize the problem and the claimed contribution in your own words. Which contribution, if any, is new and useful relative to the closest named work?
- Are the dependency, determinism, byte-identity, capability-loss, environment and intact-file assumptions clear and justified?
- Check a claimed optimum/certificate and the distinction between separately coded formulations and external validation. Identify a counterexample or missing assumption if possible.
- Are comparisons fair under each objective and budget? Are native systems, released components, reimplemented rules and manual frontiers correctly distinguished?
- Do the strong-heuristic ties and tractable graph structures change the scientific contribution? What evidence would establish meaningful general optimization choices?
- Check the canonical/compressed/native representation controls, zero-saving cases and recovery-time cost. Are any headline claims broader than the data?
- Does the evaluation use the right units? Separate workflow captures, seeds, versions, structural cases and executed recovery requests.
- List strengths, major issues, minor issues, and concrete changes that would alter your assessment. A negative or mixed assessment is useful and must be retained.

Suggested complementary expertise is one methods/algorithm reviewer and one systems/evaluation reviewer **if the instructor permits this allocation**. These are roles to request, not two assigned or completed reviews.

## Unsent request text

> Please review RecoverML under our course's assigned peer-review process. The packet links the dated draft, final experiment supplement and reproducibility material. Please identify the version you reviewed, separate strengths from major/minor concerns, and give specific evidence or suggested checks. We particularly welcome challenges to contribution novelty, the failure model, baseline fairness and the need for exact optimization. The author/internal assessment is optional context; please form your own view. Please state what you inspected or executed and any conflicts. We will preserve your actual comments and respond point by point.

This is a draft for the author to send after allocation and any course permission requirements are known. No recipient, contact permission or deadline has been assumed.

## Processing real reviews when they arrive

Keep each original review unchanged with reviewer attribution/receipt available to the course as required. Obtain consent before publishing personal identifiers or nonpublic correspondence to the public repository. Record actual evidence location and document hash in the tracker.

Create one response row per real comment: reviewer/comment reference, concern, decision, exact change or reasoned disagreement, supporting test/result, and verification status. Do not mark a response resolved until its cited change/check exists. Maintain received feedback and the student's own outbound peer reviews as separate deliverables. External expert novelty review can supplement the course process but cannot silently replace an instructor-assigned activity.
