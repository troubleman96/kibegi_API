# `internal/apps/assignments`

## Responsibility

The assignments package owns lecturer assignment CRUD, student draft/submit workflows, submission detail, grading, and feedback under `/api/v1/assignments/`.

## State model

Students can create or update drafts and submit according to assignment availability. Submission transitions should prevent unauthorized edits after submission when the existing contract requires it. Lecturers or permitted class managers can grade and attach feedback; students cannot modify grades.

## Authorization and data

Every query scopes through class membership and assignment ownership. Preserve existing assignment, submission, and user identifiers. Grading writes should update the durable row before returning the response and should invalidate any cached class or assignment reads if caching is introduced.
