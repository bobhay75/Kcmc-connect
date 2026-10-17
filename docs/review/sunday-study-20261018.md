# October 18 Sunday Bible study reconciliation

Status: owner review required. No runtime content changes, merge, deployment, slide projection or website publication.

## Evidence
- September 11 Front Pew News explicitly says Friends of Faith resumes September 13 at 10:20 AM downstairs, studying John 1-3.
- October 9 Front Pew News lists Faith & Friends Adult Bible Study Class at 10:15 AM on October 11.
- October 16 Front Pew News lists Faith & Friends Adult Bible Study Class at 10:15 AM on October 18.
- Owner instructions specify Friends of Faith Sunday Bible Study, Becoming Like Jesus by Matt Chandler, beginning October 18 at 10:20 AM, Pairs & Spares Classroom. Omit the word “New”.
- Main content.json at 808b1967170b0e9101309a5c1091d6eb793406c8 has the older faith-friends-20260927 record. No October 18 or Becoming Like Jesus entry was found.
- Merged PR #125 adds dated October 14 onward newsletter items but does not infer another Sunday occurrence. Its documentation requires reconciliation against current host data before publication.
- Targeted PR and repository searches for Becoming Like Jesus / Friends of Faith / Faith & Friends found no matching new-study change. Searches do not establish the absence of unpublished host-editor records.

## Existing presentation materials
- KCMC_Friends_of_Faith_Announcement.pptx is a September announcement: September 13, 10:20 AM, downstairs classroom, John 1–3. Do not project it for October 18.
- Sunrise Friends of Faith Bible Study.png, created October 7, already contains October 18, 10:20 AM and Pairs & Spares Classroom. Reuse this prior art as a reference rather than commission duplicate artwork. It is a raster image, not a verified editable October 18 PowerPoint.
- No October 18 study PPTX was located by targeted filename searches. Do not treat search absence as proof that no such deck exists.

## Unresolved conclusion
Evidence confirms two descriptions, not two separate classes. The September newsletter proves the 10:20 Friends of Faith name predates the new study. Similar names and adjacent start times suggest a possible naming/time mismatch, but that remains an inference.

Preserve the established class. Do not change its name, move its time, assign Pairs & Spares to it, or publish both candidate events until identity is confirmed.

## Review candidates
sunday-study-20261018.proposed.json contains two draft candidates OUTSIDE runtime content. They are alternatives pending confirmation, not a two-event import.
- Separate classes: preserve the newsletter class at 10:15 and use the owner-directed study at 10:20.
- Same class: confirm the canonical name and time, then stage exactly one October 18 event with the study title and confirmed classroom.
- Unconfirmed: keep proposed study unpublished.

Before future approved publication inspect current host content and editor records privately, check equivalent name/date/time entries as well as IDs, preserve unrelated edits, and apply only the approved event delta. No wholesale source-content replacement.

## Slide copy held for confirmation
Friends of Faith
Sunday Bible Study
Becoming Like Jesus
by Matt Chandler
Beginning October 18, 2026
Sundays at 10:20 AM
Pairs & Spares Classroom

This copy follows the owner's instruction and is not independently confirmed against the 10:15 newsletter listing. Final deck must use 16:9, editable Arial Narrow 60 pt announcement text, authentic KCMC branding and the established visual reference. Omit “New”. Do not use the September deck unchanged.

## Validation and limits
Candidate JSON parses and candidate IDs differ. Both remain draft. No end times or recurrence rule were invented. Runtime content, security settings and all existing events remain unchanged. Production/editor state has not been inspected in this task. The local file-building environment failed to launch, preventing PowerPoint generation and visual validation. No finished PPTX is claimed.
