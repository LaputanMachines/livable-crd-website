#!/usr/bin/env python3
"""Amend one of Herb Collins's submitted answers, at his request.

Written for one event and kept as the record of it, like `fix_answer_typos.py`,
whose checks, backup and write this reuses.

Herb Collins (Victoria, submission o91z5zX) wrote to the coalition after
submitting, asking for two changes to his healthcare comment (HLT-GEN):

  "I recently submitted my questionnaire and realized I should have used
  another term for "Mental Trauma Centre". Instead please could we say
  "Complex Trauma Centre" ? Also I should have included "Veterans" to the list
  of first responders for human and animal responders as well so that no one
  gets left behind."

Only those two changes are made. HLT-GEN is ungraded, so no grade rests on the
text and no grading tab carries a copy of it.

Dry-run by default.

  python3 scripts/questionnaire/amend_collins_answer.py            # preview
  python3 scripts/questionnaire/amend_collins_answer.py --apply    # do it
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fix_answer_typos as fat  # noqa: E402

SUBMISSION_ID = "o91z5zX"
# As the raw tab spells it; the tracking sheet has him as "Herb Collins".
CANDIDATE = "Herbert Collins"

EDITS = {
    "HLT-GEN": [
        ("“Mental Trauma Centre.”", "“Complex Trauma Centre.”"),
        ("all human and pet first responders receive",
         "all human and pet first responders and Veterans receive"),
    ],
}


if __name__ == "__main__":
    fat.main(SUBMISSION_ID, CANDIDATE, EDITS, __doc__)
