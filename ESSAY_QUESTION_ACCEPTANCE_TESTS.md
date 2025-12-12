# Acceptance Tests: Essay Question Management

## Feature 1: Edit Essay Question

### POSITIVE ACCEPTANCE TESTS

#### Test 1.1: Successfully Edit Essay Question Text
**Acceptance Criteria:**
- GIVEN: A lecturer is logged in and viewing an exam with existing essay questions
- WHEN: The lecturer clicks the Edit button for an essay question and modifies the question text
- THEN: The updated question text is saved to the system and displayed correctly when the page is reloaded

#### Test 1.2: Successfully Update Essay Question Marks
**Acceptance Criteria:**
- GIVEN: A lecturer is logged in and editing an essay question
- WHEN: The lecturer changes the maximum marks allocated to the question from 10 to 15
- THEN: The system accepts the new marks value and persists the change in the database

#### Test 1.3: Successfully Update Optional Guidelines
**Acceptance Criteria:**
- GIVEN: A lecturer is editing an essay question that currently has no guidelines
- WHEN: The lecturer adds marking guidelines (e.g., "Award marks for clarity, structure, and accuracy")
- THEN: The guidelines are saved and displayed in the question details when viewed again

#### Test 1.4: Successfully Update All Question Attributes Simultaneously
**Acceptance Criteria:**
- GIVEN: A lecturer is editing an essay question
- WHEN: The lecturer modifies the question text, increases the marks, and adds/updates guidelines in a single edit session
- THEN: All changes are validated and saved together, and the system reflects all updates when the question is viewed

#### Test 1.5: Successfully Save and Reload Edited Question
**Acceptance Criteria:**
- GIVEN: A lecturer has edited an essay question and saved the changes
- WHEN: The lecturer navigates away from the edit form and returns to the exam questions list
- THEN: The system displays the updated question with all modifications persisted correctly

#### Test 1.6: Successfully Edit Question and Verify Cascading Updates
**Acceptance Criteria:**
- GIVEN: An essay question exists in the exam and has been answered by students
- WHEN: A lecturer edits the question marks from 10 to 20
- THEN: The system updates the question, and the mark change is reflected in future grading operations without affecting already-submitted attempts

---

### NEGATIVE ACCEPTANCE TESTS

#### Test 1.7: Reject Attempt to Save Empty Question Text
**Acceptance Criteria:**
- GIVEN: A lecturer is editing an essay question
- WHEN: The lecturer clears all text from the question field and attempts to save
- THEN: The system displays a validation error message (e.g., "Question text cannot be empty") and prevents the save operation

#### Test 1.8: Reject Attempt to Save Empty Marks Field
**Acceptance Criteria:**
- GIVEN: A lecturer is editing an essay question with marks set to 10
- WHEN: The lecturer clears the marks field and attempts to save
- THEN: The system displays a validation error and prevents the save, maintaining the original marks value

#### Test 1.9: Reject Attempt to Save Invalid Marks (Zero)
**Acceptance Criteria:**
- GIVEN: A lecturer is editing an essay question
- WHEN: The lecturer attempts to set the marks to 0 (zero)
- THEN: The system displays a validation error message (e.g., "Marks must be greater than 0") and prevents the save

#### Test 1.10: Reject Attempt to Save Invalid Marks (Negative)
**Acceptance Criteria:**
- GIVEN: A lecturer is editing an essay question
- WHEN: The lecturer attempts to enter a negative mark value (e.g., -5)
- THEN: The system rejects the input and displays a validation error, preventing the operation

#### Test 1.11: Reject Attempt to Save Marks Exceeding Maximum Threshold
**Acceptance Criteria:**
- GIVEN: A lecturer is editing an essay question with a system-defined maximum marks limit (e.g., 100)
- WHEN: The lecturer attempts to set marks to 150
- THEN: The system displays a validation error and prevents the save operation

#### Test 1.12: Prevent Edit Access Without Sufficient Permissions (Student)
**Acceptance Criteria:**
- GIVEN: A student is logged in and viewing an exam with essay questions
- WHEN: The student attempts to access the edit button for an essay question (via URL or button click)
- THEN: The system denies access, displays a permissions error, and redirects the student away from the edit interface

#### Test 1.13: Prevent Edit Access Without Sufficient Permissions (Unauthorized Lecturer)
**Acceptance Criteria:**
- GIVEN: Lecturer A is logged in, but they are not the instructor for the course containing the essay question
- WHEN: Lecturer A attempts to edit the essay question (directly via URL)
- THEN: The system denies access with a "Unauthorized" or "Access Denied" message and prevents the edit

#### Test 1.14: Attempt to Edit a Non-Existent Essay Question
**Acceptance Criteria:**
- GIVEN: A lecturer navigates to the edit form for an essay question using a question ID that does not exist in the system
- WHEN: The page loads or the lecturer attempts to save
- THEN: The system displays an error message (e.g., "Question not found") and prevents any modifications

#### Test 1.15: Prevent Simultaneous Edits (Concurrency)
**Acceptance Criteria:**
- GIVEN: Two lecturers have the same essay question open for editing in separate sessions
- WHEN: Both lecturers make different changes and attempt to save
- THEN: The system either locks the question during editing or displays a conflict message to the second user, preventing data inconsistency

#### Test 1.16: Prevent Edit of Question in Published/Locked Exam
**Acceptance Criteria:**
- GIVEN: An essay exam has been published or locked by the system
- WHEN: A lecturer attempts to edit an essay question in that exam
- THEN: The system prevents the edit with a message such as "Cannot modify questions in a published or locked exam"

#### Test 1.17: Reject Excessively Long Question Text
**Acceptance Criteria:**
- GIVEN: A lecturer is editing an essay question
- WHEN: The lecturer attempts to paste or enter question text exceeding the system character limit (e.g., 5000 characters)
- THEN: The system displays a validation error and prevents the save, or truncates the input with a warning

---

## Feature 2: Delete Essay Question

### POSITIVE ACCEPTANCE TESTS

#### Test 2.1: Successfully Delete Essay Question After Confirmation
**Acceptance Criteria:**
- GIVEN: A lecturer is logged in and viewing an exam with essay questions
- WHEN: The lecturer clicks the Delete button, a confirmation dialog appears, and the lecturer confirms the deletion
- THEN: The system removes the question from the database and displays a success message

#### Test 2.2: Successfully Remove Deleted Question from Exam View
**Acceptance Criteria:**
- GIVEN: A question has been successfully deleted
- WHEN: The lecturer views the exam questions list
- THEN: The deleted question no longer appears in the list, and the exam shows the updated question count

#### Test 2.3: Successfully Persist Deletion in the Database
**Acceptance Criteria:**
- GIVEN: An essay question has been deleted
- WHEN: The lecturer logs out and logs back in, then navigates to the same exam
- THEN: The system confirms that the question is permanently removed from the database and does not appear in the exam

#### Test 2.4: Successfully Delete Question and Cascade Delete Associated Answers
**Acceptance Criteria:**
- GIVEN: An essay question exists with student-submitted answers
- WHEN: A lecturer deletes the question after confirming the action
- THEN: The system removes the question and all associated student answer records from the database to maintain referential integrity

#### Test 2.5: Successfully Delete Question and Update Exam Score Calculation
**Acceptance Criteria:**
- GIVEN: An essay exam includes multiple questions, and students have submitted answers
- WHEN: A lecturer deletes one of the essay questions
- THEN: The system recalculates total exam marks (removing the deleted question's contribution) and updates student scores accordingly

#### Test 2.6: Confirmation Dialog Appears Before Deletion
**Acceptance Criteria:**
- GIVEN: A lecturer clicks the Delete button for an essay question
- WHEN: The confirmation dialog appears
- THEN: The dialog clearly states which question is being deleted and asks for explicit confirmation (not auto-confirmed)

---

### NEGATIVE ACCEPTANCE TESTS

#### Test 2.7: Prevent Deletion Without Explicit Confirmation
**Acceptance Criteria:**
- GIVEN: A lecturer clicks the Delete button for an essay question
- WHEN: A confirmation dialog appears but the lecturer clicks "Cancel" or closes the dialog
- THEN: The system does NOT delete the question, and it remains in the exam

#### Test 2.8: Prevent Deletion if User Closes Browser/Session Before Confirming
**Acceptance Criteria:**
- GIVEN: A confirmation dialog is displayed for a question deletion
- WHEN: The user closes the browser tab or session without confirming
- THEN: The question is NOT deleted, and the system retains the original data

#### Test 2.9: Prevent Delete Access Without Sufficient Permissions (Student)
**Acceptance Criteria:**
- GIVEN: A student is logged in
- WHEN: The student attempts to access the delete functionality for an essay question (via URL or button click)
- THEN: The system denies access, displays a permissions error, and prevents the deletion

#### Test 2.10: Prevent Delete Access Without Sufficient Permissions (Unauthorized Lecturer)
**Acceptance Criteria:**
- GIVEN: Lecturer A is logged in, but they do not have authority over the course containing the essay question
- WHEN: Lecturer A attempts to delete an essay question (directly via URL or API)
- THEN: The system denies the action with an "Unauthorized" message and prevents the deletion

#### Test 2.11: Attempt to Delete a Non-Existent Essay Question
**Acceptance Criteria:**
- GIVEN: A lecturer uses a DELETE request with a question ID that does not exist in the system
- WHEN: The system processes the deletion request
- THEN: The system displays an error message (e.g., "Question not found") and returns to the exam questions list without performing any deletion

#### Test 2.12: Prevent Deletion of Question with Student Submissions (If Business Logic Requires)
**Acceptance Criteria:**
- GIVEN: An essay question has already been answered by students
- WHEN: A lecturer attempts to delete the question
- THEN: The system either:
  - Displays a warning: "This question has student submissions. Deleting will remove all associated answers. Do you want to proceed?" 
  - OR prevents deletion with a message: "Cannot delete a question with existing student submissions"
  - (Dependent on organizational policy)

#### Test 2.13: Prevent Deletion of Question in Published/Locked Exam
**Acceptance Criteria:**
- GIVEN: An essay exam has been published or locked by the system
- WHEN: A lecturer attempts to delete an essay question in that exam
- THEN: The system prevents the deletion with a message such as "Cannot delete questions from a published or locked exam"

#### Test 2.14: Prevent Race Condition: Double Deletion Attempt
**Acceptance Criteria:**
- GIVEN: Two lecturers attempt to delete the same essay question at nearly the same time
- WHEN: Both send delete requests within milliseconds of each other
- THEN: The first deletion succeeds, and the second request receives an error message ("Question not found" or "Already deleted") without causing data inconsistency

#### Test 2.15: Prevent Deletion via Invalid Request Methods
**Acceptance Criteria:**
- GIVEN: A malicious user attempts to delete a question using an invalid HTTP method or corrupted request
- WHEN: The system receives the malformed request
- THEN: The system rejects the request with an appropriate error response (e.g., "Bad Request" or "Method Not Allowed") and does not delete the question

#### Test 2.16: Prevent Deletion When Database is in Read-Only Mode
**Acceptance Criteria:**
- GIVEN: The system database is in a read-only or maintenance mode
- WHEN: A lecturer attempts to delete an essay question
- THEN: The system displays an error message (e.g., "System is in maintenance mode. Try again later") and prevents the deletion

---

## Summary of Test Coverage

| Feature | Positive Tests | Negative Tests | Total |
|---------|-----------------|-----------------|-------|
| Edit Essay Question | 6 | 11 | 17 |
| Delete Essay Question | 6 | 10 | 16 |
| **Total** | **12** | **21** | **33** |

All tests follow the Given-When-Then format and focus on user-level acceptance criteria without implementation details. Tests cover both happy paths and edge cases, including permission validation, data persistence, error handling, and potential system failures.
