#!/usr/bin/env python3
"""Turn the graded master into the two post-voting tabs the questionnaire is built from.

Grading is over. This script applies the committee's dispositions - the `Needs rewording`
and `Shouldn't be graded` ticks, the EXCLUDE votes and, mostly, the free-text comments -
and writes two tabs:

  Reworded Questions   Every question that changed, with its original text beside the new
                       one, who asked for the change, and why. The audit trail.
  Finalized Questions  The whole shipping set, one row per question a candidate will see,
                       flat enough to export as a single CSV and import into Tally.

Editorial decisions live in FINAL below, in question order. Submitter, municipality scope
and source tab are read from the master at run time rather than restated here, so no
submitter email ever lands in this repo.

Both tabs are rebuilt from scratch on every run. Neither is read by anything else, so a
rebuild is safe at any time - unlike tables.py and voting.py, this touches no votes.

Usage:
  QUESTIONNAIRE_SHEET_ID=... python3 scripts/questionnaire/finalize.py
  QUESTIONNAIRE_SHEET_ID=... python3 scripts/questionnaire/finalize.py --csv out.csv
"""

import argparse
import csv
import sys

import gspread

from aggregate import MASTER, open_sheet

REWORDED = "Reworded Questions"
FINALIZED = "Finalized Questions"
EXCLUDED = "Excluded Questions"

# Build tracking, ticked by hand as each question goes into the Tally form. Sheet-only:
# it is deliberately not in FINAL_HEADERS, so it stays out of the CSV that gets
# imported into Tally, where an empty tracking column would just be noise.
TRACK_HEADER = "Added To Tally Questionnaire"

ALL = "All municipalities"

# The 13 jurisdictions the questionnaire goes out to. The CRD's three electoral areas -
# Juan de Fuca, Salt Spring Island and Southern Gulf Islands - are deliberately out of
# scope: they elect an electoral area director rather than a council, so neither
# municipality-specific question applies and much of the shared set reads oddly.
#
# _data/municipalities.yml still publishes all 16 on the site. That is a separate decision
# from who gets a questionnaire, so it is left alone here.
MUNICIPALITIES = [
    "Victoria", "Saanich", "Oak Bay", "Central Saanich", "Esquimalt", "Sidney",
    "Langford", "View Royal", "North Saanich", "Colwood", "Sooke", "Highlands",
    "Metchosin",
]

# Homes for Living objected on 2026-08-13 to their questions having been reworded, so every
# HFL-* question now ships exactly as it was submitted, under its own submission code, in
# submission order, and none of them appears on `Reworded Questions`. Three things follow:
#
#   - The eight HSG-* rows that were rewrites or merges of HFL text are gone. The HFL row
#     each was built on ships in its place.
#   - The non-HFL questions those rows had absorbed (FR-13, FR-14, FR-15, FR-16, FR-36) are
#     absorbed into the HFL row that replaced them instead, so nothing is asked twice and
#     nothing vanishes from the ledger. The committee's argument for each merge is still in
#     MERGED_WHY; what changed is which question carries it.
#   - The two municipality-templated blocks are HFL's own rows again wherever HFL wrote one,
#     so only the infrastructure question is still templated, and only for the eight
#     municipalities HFL never submitted one for.
#
# The cost is deliberate and worth stating: the wording HFL-18's options had already drifted
# to, the copy-paste error in HFL-09, and the overlaps the committee had merged away all ship
# as submitted. Those are notes on the rows below, not edits to them.
AS_SUBMITTED = ("Ships as submitted, not reworded, at Homes for Living's request "
                "(2026-08-13).")

# The HFL tab has no question-type column, so a select-one / select-all-that-apply reading of
# the answer list is the one call this file still makes on an HFL row. Flagged where the list
# does not settle it, because getting it wrong changes what the question asks.
INFERRED_TYPE = ("Question type inferred from the submitted answer list; the HFL tab has no "
                 "type column. Confirm with Homes for Living before the form is built.")

TARGET_NOTE = ("Options are in the order submitted (fewer / more / about right), which is "
               "not the order of the underlying scale. Targets: https://www2.gov.bc.ca/gov/"
               "content/housing-tenancy/local-governments-and-housing/housing-targets/orders")

# The five municipalities HFL researched an infrastructure figure for and wrote a question
# around. Those ship verbatim as the mapped rows; the other eight get the templated question
# below, because FR-35 and FR-53 asked it region-wide.
HFL_INFRA = {
    "Victoria": "HFL-12",
    "Saanich": "HFL-14",
    "Oak Bay": "HFL-16",
    "Esquimalt": "HFL-19",
    "Colwood": "HFL-25",
}

# The three municipalities the province never issued a housing target order to. They get one
# municipality-specific question rather than two, rather than a hollow version of the target
# question. HFL submitted target questions for the other ten, which ship as HFL-11..HFL-24.
NO_TARGET = {"Sooke", "Highlands", "Metchosin"}

# Figures for the eight municipalities with no HFL infrastructure question, keyed to a clause
# that reads after "In <muni>, ...". None has been researched yet, so all eight ship the
# generic wording and print FIGURE NEEDED on every run - fill one in citing the document and
# year, in the shape of HFL's own five, and its row picks the figure up.
INFRA_FIGURES = {
    "Central Saanich": "",
    "Sidney": "",
    "Langford": "",
    "View Royal": "",
    "North Saanich": "",
    "Sooke": "",
    "Highlands": "",
    "Metchosin": "",
}

# Victori'Us resubmitted their whole set on 2026-08-09, after voting closed. The new
# questions replaced VU-01..VU-11 in the master one for one, so the origins below still
# point at the right subject matter, but no committee member has scored this text. The
# rewordings are the ones the committee argued for on the 2026-08-01 version, re-applied
# to the new wording, plus whatever the resubmission genuinely added. Stamped on every
# arts row so nobody reads a `why` as a verdict on words the committee never saw.
RESUB = ("Refreshed against the Victori'Us resubmission of 2026-08-09, which arrived "
         "after voting closed and was not scored. The rewording is the committee's, "
         "carried over from the 2026-08-01 version of the same question.")

# Two walking questions that arrived 2026-08-16, by the same route as CLI-12: straight to
# the committee, after voting closed and after the master was built. Like CLI-12 they carry
# their own text rather than an origin, and for the same reason - append.py cannot take
# them, because a new Form Responses 1 row renumbers every FR-* ID and its prefix check
# refuses the run. Unlike CLI-12 and the RUSH block they are graded. That is a decision
# made off the sheet, since no committee member has scored either question, which is the
# argument that kept the other four late arrivals ungraded.
LATE_WALKING = ("Submitted 2026-08-16 14:40 PDT, after voting closed and after the master "
                "was built, so it has no master row behind it and no committee score. "
                "Ships as submitted and graded; write a scoring guide before it goes out, "
                "because nothing on the sheet establishes what a strong answer looks like.")

INFRA_OPTIONS = (
    "a) Allow substantially more housing and commercial development to grow the tax base "
    "and help fund infrastructure renewal. "
    "b) Increase property taxes or introduce a dedicated infrastructure levy. "
    "c) Increase development cost charges, amenity contributions, or other fees imposed "
    "on new housing and development. "
    "d) Reduce or defer infrastructure projects, service levels, or replacement standards. "
    "e) Seek additional provincial or federal funding."
)

# Every question in the shipping set, in the order candidates will see it.
#
#   ref        stable ID for the final questionnaire
#   origins    the master IDs this row came from; the first is the row we inherit
#              submitter / source / municipality from. Empty only for a question that
#              never went through the master at all - see CLI-12, WLK-05, WLK-06 - which
#              then has to carry its own question, options, qtype and source
#   change     "Unchanged" | "Reworded" | "Merged" | "Reworded + merged" | "Recategorised"
#   asked_by   who called for the change, from the voter comments
#   why        the argument for it, condensed from those comments
#   graded     False for questions we publish but do not score
#   source     overrides the source tab read from the master; origin-less rows only
#   submitter  same, for the submitter column. Left blank rather than filled in with a
#              name or address, for the same reason nothing else here carries one
#   note       anything the person building the Tally form has to act on
FINAL = [
    # ---------------------------------------------------------------- General
    dict(
        ref="GEN-01", category="General", origins=["FR-50"],
        question="If you could change one policy or one piece of infrastructure in the "
                 "municipality you are running in, what would it be - and why that one?",
        options="", qtype="Short answer (500 characters)",
        change="Reworded + recategorised", asked_by="Michael, Claude",
        why="Filed under Housekeeping, but a single forced choice reveals priorities "
            "better than the 'do you support' items. Promote to General and publish it.",
    ),
    dict(
        ref="GEN-02", category="General", origins=["VU-01"], municipality=ALL,
        question="Your municipality has received $10 million in new annual funding and "
                 "must spend all of it. How would you allocate it across the following "
                 "areas? Your answers must total $10 million.",
        options="a) Housing b) Transit c) Walking, rolling and cycling infrastructure "
                "d) Roads and vehicle infrastructure e) Police f) Fire and emergency "
                "services g) Parks and recreation h) Arts and culture i) Climate action "
                "and the environment j) Services for unhoused residents",
        qtype="Allocation - responses must total $10M",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="Best-designed question in the VU block: a forced trade-off that works in any "
            "municipality. Trimmed from 14 line items to 10 - 14 is heavy for a form.",
        note="Dropped line items: Accessibility, Healthcare access & community wellbeing, "
             "Economic development & local business, Other. Police kept as its own line "
             "despite being the most loaded item - removing it removes the sharpest "
             "signal. Sam asked for links to each municipality's budget alongside it. "
             "The resubmission restated the same 14 line items, so the trim stands. "
             + RESUB,
    ),

    # ---------------------------------------------------------------- Walking
    dict(
        ref="WLK-01", category="Walking", origins=["FR-01"],
        question="Your municipality, the CRD and the Province have all adopted targets to "
                 "shift trips away from driving - the CRD Regional Transportation Plan "
                 "aims for 42% of regional trips by walking, rolling and transit by 2038. "
                 "Do you support meeting your municipality's adopted mode-shift targets, "
                 "and would you vote for the street-space and budget changes needed to "
                 "meet them?",
        options="a) Yes b) Yes, but not where it removes road space from drivers c) No "
                "d) Unsure",
        qtype="Single choice + optional comment",
        change="Reworded", asked_by="Caleb, Michael, Sam, Claude",
        why="As submitted it asked whether candidates would 'eliminate' mode-shift "
            "targets, which is almost certainly inverted, and six bullets of municipal "
            "and provincial figures preceded the actual question.",
        note="Confirm with the submitter that 'eliminate' was meant as 'achieve' before "
             "this ships.",
    ),
    dict(
        ref="WLK-02", category="Walking", origins=["FR-02", "FR-04"],
        question="Which pedestrian safety problem in your municipality concerns you most, "
                 "and what is the one change you would commit to in your first term to "
                 "make walking safer and more attractive than driving for short trips?",
        options="", qtype="Short answer (750 characters)",
        change="Reworded + merged", asked_by="Caleb, Michael, Claude",
        why="Three open 'what would you do' prompts in the bank (FR-02, FR-04, FR-11) and "
            "as written they collect platitudes that all score alike. FR-04 is the same "
            "shape but vaguer, so it folds in and the merged question demands one "
            "concrete commitment.",
    ),
    dict(
        ref="WLK-03", category="Walking", origins=["FR-18", "FR-19"],
        question="Sidewalk construction and maintenance is chronically underfunded across "
                 "the region. Would you vote to increase the share of your municipality's "
                 "transportation capital budget dedicated to pedestrian infrastructure?",
        options="a) Yes - a substantial increase (more than double the current share) "
                "b) Yes - a modest increase c) No - the current share is about right "
                "d) No - it should decrease",
        qtype="Single choice + optional comment",
        change="Reworded + merged", asked_by="Michael, Sam, Claude",
        why="FR-18 asked whether candidates would advocate for sidewalk funding - nobody "
            "says no, zero separation. FR-19 attempted the numeric version but tied the "
            "budget share to the proportion of residents without a driver's licence, a "
            "formula no candidate can compute. Merged into a budget commitment with the "
            "invented ratio dropped.",
    ),
    dict(
        ref="WLK-04", category="Walking", origins=["FR-38"], municipality=ALL,
        question="Do you support expanding pedestrian-priority and car-free streets in "
                 "your municipality's downtown, main street or village centre?",
        options="a) Yes - and I would pursue a permanent expansion in my first term "
                "b) Yes - but seasonal or pilot closures only c) No d) Unsure",
        qtype="Single choice",
        change="Reworded", asked_by="Sam, Claude",
        why="Scoped to Victoria as submitted. 'The downtown area' means something very "
            "different in Sidney or North Saanich, so it is reworded to reach the whole "
            "region.",
    ),
    dict(
        ref="WLK-05", category="Walking", origins=[], municipality=ALL,
        question="Parents frequently express concerns about safety risks their children "
                 "experience from motor traffic while walking to school and neighbourhood "
                 "playgrounds. Dangers of speeding traffic, lack of safe crosswalks, "
                 "absence of Stop signs, and in some municipalities lack of 30km/hr school "
                 "zone/playground signage persist. How will you work with parent groups, "
                 "school staff, and municipal staff to assure that children's safety is "
                 "prioritized over convenience and flow of motor traffic?",
        options="", qtype="Long answer (1000 characters)",
        source="Late submission", change="Unchanged",
        note=LATE_WALKING + " Overlaps WLK-02, which asks for one concrete first-term "
             "commitment on pedestrian safety region-wide; this one is narrower (children, "
             "school and playground routes) and asks about process rather than a "
             "commitment, so the two are worth asking together, but read them side by side "
             "before the form is built.",
    ),
    dict(
        ref="WLK-06", category="Walking", origins=[], municipality=ALL,
        question="The CRD is home to some of the oldest people in Canada. Many of these "
                 "older adults once drove but now rely on walking to get to their "
                 "destinations, and very frequently pedestrian conditions are hazardous. "
                 "Broken and tilting pavement on sidewalks, lips on curb cuts, absent or "
                 "poorly maintained crosswalks, and lack of engineered traffic calming all "
                 "increase the risk of falls that threaten the independence of older adults "
                 "and those living with disabilities. To date, few municipalities have "
                 "constructed pedestrian infrastructure to make safe and pleasant walking a "
                 "priority. What will you do, in a 4 year term, to identify, prioritize and "
                 "set time-lines to assure that pedestrian infrastructure is improved to "
                 "meet the needs of the older and disabled members of your community?",
        options="", qtype="Long answer (1000 characters)",
        source="Late submission", change="Unchanged",
        note=LATE_WALKING + " Asks for three things at once - identify, prioritise, set "
             "timelines - so a scoring guide should say whether a candidate who answers "
             "only the first two can still score full marks. Sits next to WLK-03, which "
             "asks the budget-share version of the same problem as a single choice.",
    ),

    # ------------------------------------------------------ Rolling & cycling
    dict(
        ref="ROL-01", category="Rolling & cycling", origins=["FR-10", "FR-07"],
        question="Bike and roll routes in this region frequently end abruptly at "
                 "municipal boundaries or fail to connect safely to the regional trail "
                 "network. Will you commit to funding and completing at least one "
                 "'missing link' in your municipality's Active Transportation Plan during "
                 "your four-year term? If yes, which one would you prioritise?",
        options="", qtype="Yes/no + short answer",
        change="Reworded + merged", asked_by="Caleb, Michael, Claude",
        why="FR-07 asked whether candidates support an all-ages-and-abilities network - "
            "almost everyone says yes in the abstract. FR-10 asked for 'fully funding and "
            "completing' missing links, a blank cheque with no timeline attached. Merged "
            "and anchored to one link inside one term, which can actually be held to.",
    ),
    dict(
        ref="ROL-02", category="Rolling & cycling", origins=["FR-08"],
        question="Will you commit to physical protection - not paint alone - as the "
                 "standard for all new and upgraded cycling infrastructure on busy streets "
                 "in your municipality?",
        options="a) Yes b) Yes, except where physically impossible c) No d) Unsure",
        qtype="Single choice",
        change="Reworded", asked_by="Michael, Sam",
        why="Dropped the concrete-curb / planter / bollard list and the 30 km/h threshold. "
            "Ask for the standard, not the materials - specifying the mechanism trips our "
            "own 'prescribes how rather than what' criterion.",
    ),
    dict(
        ref="ROL-03", category="Rolling & cycling", origins=["FR-09"],
        question="Will you oppose efforts to remove, narrow or downgrade existing "
                 "protected bike lanes and other all-ages-and-abilities cycling "
                 "infrastructure in your municipality during your term?",
        options="a) Yes b) No c) Case by case", qtype="Single choice",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="Dropped the Ontario 54%-collision-increase citation. The number is real, but "
            "importing an out-of-province statistic invites candidates to argue the "
            "statistic instead of taking a position.",
        note="Keep the CIMA+ / MTO source in our scoring notes rather than in the "
             "question text.",
    ),
    dict(
        ref="ROL-04", category="Rolling & cycling", origins=["FR-11"],
        change="Unchanged",
        note="Caleb: tests a candidate's knowledge of their own municipality; anyone "
             "unfamiliar with active transportation will struggle to answer.",
    ),
    dict(
        ref="ROL-05", category="Rolling & cycling", origins=["FR-05"], graded=False,
        question="If you have previously served in local government, what did you do to "
                 "advance walking, rolling, cycling or transit? If you have not, what in "
                 "your record outside of council shows the same commitment?",
        options="", qtype="Short answer (750 characters)",
        change="Reworded", asked_by="Michael, Sam, Claude, sheet note",
        why="As written only incumbents could answer, so it returned blanks across most of "
            "the field and handed sitting councillors a free paragraph. Reworded to reach "
            "challengers, and not scored.",
    ),

    # ---------------------------------------------------------------- Transit
    dict(
        ref="TRN-01", category="Transit", origins=["FR-03", "FR-21", "FR-20"],
        question="Fares are set by BC Transit and the Victoria Regional Transit Commission, "
                 "not by municipal councils. Which fare measures would you actively "
                 "advocate for at the VRTC? Select all that apply. Then tell us why.",
        options="a) Free transit for everyone under 19 b) Free or half-price transit for "
                "seniors 65+ c) Free or half-price transit for people receiving income or "
                "disability assistance d) A lower-cost regional monthly pass e) None of "
                "the above",
        qtype="Multi-select + short answer",
        change="Reworded + merged", asked_by="Michael, Claude",
        why="Three separate fare questions (under-19 free travel, 13-19 free passes, "
            "half-price off-peak senior passes) that councils cannot decide. Merged into "
            "one question framed as VRTC advocacy, which is the lever a councillor "
            "actually has. FR-20's fare schedule - a price point, an age, a licence test "
            "and two time windows in one yes/no - was dropped rather than corrected.",
        note="Under-12s already ride free region-wide. Sam noted FR-20's off-peak window "
             "should have ended at 14:30, not 16:00, if we ever restore that detail.",
    ),
    dict(
        ref="TRN-02", category="Transit", origins=["FR-37"],
        question="Do you support removing general on-street parking (excluding accessible "
                 "parking spaces) from frequent transit corridors and main arterial "
                 "streets in your municipality, and reallocating that space to bus lanes, "
                 "loading zones, and walking and cycling infrastructure?",
        options="a) Yes, across the corridor b) Yes, at peak hours only c) Only where a "
                "specific project requires it d) No",
        qtype="Single choice",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="Sharpest transit question in the bank, but 'all corridors, no exceptions' "
            "does not fit every municipality (Sam: Highlands) and picks an avoidable fight "
            "with BIAs and small merchants who are otherwise winnable. Tiered options let "
            "a conditional supporter answer honestly.",
        note="Expect BIA and accessibility pushback either way. Be ready for it.",
    ),
    dict(
        ref="TRN-03", category="Transit", origins=["FR-40"],
        question="Do you support rapid deployment of transit priority measures - bus "
                 "lanes, queue jumps, signal priority - on frequent transit corridors, "
                 "even where this requires removing on-street parking or a "
                 "general-purpose traffic lane?",
        options="a) Yes b) Yes, but not at the cost of a general-purpose lane c) No "
                "d) Unsure",
        qtype="Single choice",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="The submitted question carried unfinished drafting - Douglas Street, "
            "McKenzie Avenue and an open TODO for the western communities - which could "
            "not be scored across the region. Kept the stem, deleted the bullets, and "
            "added Sam's clause naming the actual trade-off.",
    ),
    dict(ref="TRN-04", category="Transit", origins=["FR-42"], change="Unchanged"),
    dict(
        ref="TRN-05", category="Transit", origins=["FR-45"], municipality=ALL,
        question="Do you support building new bus- and bike-only connections through "
                 "parks, golf courses or other public land where doing so would "
                 "substantially shorten transit and cycling trips?",
        options="a) Yes b) Yes, if no mature trees are lost c) No d) Unsure",
        qtype="Single choice",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="Hyper-local as submitted: one named corridor across Cedar Hill golf course in "
            "Saanich, needing site-specific knowledge, and pitting us against the parks "
            "constituency. Generalised per Sam's rewrite so every candidate can answer.",
        note="Keep the Derby Road crossing as a Saanich-only follow-up if we run "
             "municipality-specific transit questions.",
    ),

    # ---------------------------------------------------------------- Housing
    dict(
        ref="HSG-01", category="Housing", origins=["FR-12"],
        question="Bill 44 already requires most single-family lots to allow three to four "
                 "units. Should it be possible to build multifamily housing beyond that "
                 "minimum - up to the size of a large single-family house - with only a "
                 "building permit, and no rezoning or public hearing?",
        options="a) Yes b) No c) Unsure", qtype="Single choice",
        change="Reworded", asked_by="Caleb, Michael, Claude",
        why="Without naming SSMUH / Bill 44, a yes just endorses the status quo, and "
            "'multifamily of similar size to a single-family house' had no concrete unit "
            "ceiling. Adjacent to HFL-06, not a duplicate - process versus built form.",
    ),

    # ------------------------------- Homes for Living, exactly as submitted (HFL-01..25)
    #
    # Refs are the submission codes and the block is in submission order, so a reader can
    # lay this against the `HFL Questions` tab row for row. Every row here is `Unchanged`,
    # which is what keeps the whole block off `Reworded Questions`; question text, options
    # and municipality scope come from the master, which holds HFL's own words.
    dict(
        ref="HFL-01", category="Housing", origins=["HFL-01"], change="Unchanged",
        qtype="Multi-select",
        note=AS_SUBMITTED + " The committee had merged this into HFL-06 and cut its "
             "'luxury housing' option; both reversed, so all nine options ship. " +
             INFERRED_TYPE,
    ),
    dict(
        ref="HFL-02", category="Housing", origins=["HFL-02"], change="Unchanged",
        qtype="Multi-select",
        note=AS_SUBMITTED + " Nine options, uncapped: the committee's cap of three is "
             "reversed. " + INFERRED_TYPE,
    ),
    dict(
        ref="HFL-03", category="Housing", origins=["HFL-03", "FR-16"], change="Unchanged",
        qtype="Single choice",
        note=AS_SUBMITTED + " FR-16 asked the same thing with 'maximum' rather than "
             "'target' and is folded in here; HFL's wording stands.",
    ),
    dict(
        ref="HFL-04", category="Housing", origins=["HFL-04", "FR-15"], change="Unchanged",
        qtype="Multi-select",
        note=AS_SUBMITTED + " FR-15 asked for the same incentive list and is folded in "
             "here. Option (g) is 'Other (specify)', so the form needs a free-text "
             "follow-up. " + INFERRED_TYPE,
    ),
    dict(
        ref="HFL-05", category="Housing", origins=["HFL-05", "FR-13"], change="Unchanged",
        qtype="Single choice",
        note=AS_SUBMITTED + " FR-13 asked the same thing in weaker wording and is folded "
             "in here. Bill 44 already bars public hearings on OCP-consistent residential "
             "rezonings, so part of this is compliance with existing law, and several "
             "municipalities have already done it (Sam).",
    ),
    dict(
        ref="HFL-06", category="Housing", origins=["HFL-06"], change="Unchanged",
        qtype="Single choice",
        note=AS_SUBMITTED + " Option (a), 'Single-family and suites only', is below the "
             "three-to-four units Bill 44 already requires, so it is not a choice a "
             "council can make; the committee's 'beyond the provincial minimum' framing is "
             "reversed. Answers need reading as an ordinal ladder for scoring.",
    ),
    dict(
        ref="HFL-07", category="Housing", origins=["HFL-07"], change="Unchanged",
        qtype="Single choice",
        note=AS_SUBMITTED + " Highest-scoring question in the bank. The committee's two "
             "edits - saying the proposal is OCP-compliant, and 'public' for "
             "'neighbourhood' opposition - are both reversed.",
    ),
    dict(
        ref="HFL-08", category="Housing", origins=["HFL-08", "FR-14", "FR-36"],
        change="Unchanged", qtype="Single choice",
        note=AS_SUBMITTED + " The other two parking-minimum questions fold in here: "
             "FR-14's split by land use and FR-36's 2030 deadline are not in this wording, "
             "and neither is Michael's point that Bill 47 already bars residential "
             "minimums in transit-oriented areas.",
    ),
    dict(
        ref="HFL-09", category="Housing", origins=["HFL-09"], change="Unchanged",
        qtype="Multi-select",
        note=AS_SUBMITTED + " Its question text is copy-pasted from HFL-08 while its "
             "options are non-market housing delivery tools, so as submitted the question "
             "and the answers do not match. Confirm the intended question text with Homes "
             "for Living before the form is built. " + INFERRED_TYPE,
    ),
    dict(
        ref="HFL-10", category="Housing", origins=["HFL-10"], change="Unchanged",
        qtype="Long answer (1000-2000 characters, bullet points)",
        note=AS_SUBMITTED + " Homes for Living scores this one manually, per their tab.",
    ),
    dict(
        ref="HFL-11", category="Housing", origins=["HFL-11"], change="Unchanged",
        qtype="Single choice", note=AS_SUBMITTED + " " + TARGET_NOTE,
    ),
    dict(
        ref="HFL-12", category="Governance", origins=["HFL-12"], change="Unchanged",
        qtype="Multi-select (max 2)", note=AS_SUBMITTED,
    ),
    dict(
        ref="HFL-13", category="Housing", origins=["HFL-13"], change="Unchanged",
        qtype="Single choice", note=AS_SUBMITTED + " " + TARGET_NOTE,
    ),
    dict(
        ref="HFL-14", category="Governance", origins=["HFL-14"], change="Unchanged",
        qtype="Multi-select (max 2)", note=AS_SUBMITTED,
    ),
    dict(
        ref="HFL-15", category="Housing", origins=["HFL-15"], change="Unchanged",
        qtype="Single choice", note=AS_SUBMITTED + " " + TARGET_NOTE,
    ),
    dict(
        ref="HFL-16", category="Governance", origins=["HFL-16"], change="Unchanged",
        qtype="Multi-select (max 2)", note=AS_SUBMITTED,
    ),
    dict(
        ref="HFL-17", category="Housing", origins=["HFL-17"], change="Unchanged",
        qtype="Single choice", note=AS_SUBMITTED + " " + TARGET_NOTE,
    ),
    dict(
        ref="HFL-18", category="Housing", origins=["HFL-18"], change="Unchanged",
        qtype="Single choice",
        note=AS_SUBMITTED + " Its options are numbered 1/2/3 where every sibling row uses "
             "a/b/c; kept as submitted. " + TARGET_NOTE,
    ),
    dict(
        ref="HFL-19", category="Governance", origins=["HFL-19"], change="Unchanged",
        qtype="Multi-select (max 2)", note=AS_SUBMITTED,
    ),
    dict(
        ref="HFL-20", category="Housing", origins=["HFL-20"], change="Unchanged",
        qtype="Single choice", note=AS_SUBMITTED + " " + TARGET_NOTE,
    ),
    dict(
        ref="HFL-21", category="Housing", origins=["HFL-21"], change="Unchanged",
        qtype="Single choice", note=AS_SUBMITTED + " " + TARGET_NOTE,
    ),
    dict(
        ref="HFL-22", category="Housing", origins=["HFL-22"], change="Unchanged",
        qtype="Single choice", note=AS_SUBMITTED + " " + TARGET_NOTE,
    ),
    dict(
        ref="HFL-23", category="Housing", origins=["HFL-23"], change="Unchanged",
        qtype="Single choice", note=AS_SUBMITTED + " " + TARGET_NOTE,
    ),
    dict(
        ref="HFL-24", category="Housing", origins=["HFL-24"], change="Unchanged",
        qtype="Single choice", note=AS_SUBMITTED + " " + TARGET_NOTE,
    ),
    dict(
        ref="HFL-25", category="Governance", origins=["HFL-25"], change="Unchanged",
        qtype="Multi-select (max 2)", note=AS_SUBMITTED,
    ),

    dict(
        ref="HSG-10", category="Housing", origins=["FR-34"], graded=False,
        question="What is your current housing situation? If you are not currently "
                 "renting, when were you last a renter?",
        options="a) Renter b) Owner c) Living with family d) Other e) Prefer not to say",
        qtype="Single choice + short answer",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="Housing tenure is a demographic attribute with no defensible A-F grade, and "
            "asking for it is a real privacy ask. Published as context with a "
            "'prefer not to say' option, and not scored. Sam's 'when were you last a "
            "renter?' added.",
    ),

    # -------------------------------------------------------------- Governance
    dict(
        ref="GOV-01", category="Governance", origins=["FR-06"], municipality=ALL,
        question="Do you support expanding shared or regional delivery of municipal "
                 "services in the Capital Region? And separately: do you support studying "
                 "the amalgamation of one or more municipalities here - if so, which?",
        options="Part 1: a) Yes b) No c) Unsure. Part 2: a) Yes b) No c) Unsure, plus "
                "short answer.",
        qtype="Two single choices + short answer",
        change="Reworded", asked_by="Michael, Sam, Claude, sheet note",
        why="As submitted it named Saanich and Victoria, so only their candidates could "
            "answer. We also have no coalition position on amalgamation, which leaves no "
            "defensible way to score it and splits people we agree with on housing and "
            "transit. Reworded region-neutral, per the sheet's own suggested rewrite: "
            "regional services first, amalgamation second.",
        note="Score part 1 only. Publish part 2 unscored.",
    ),
    dict(
        ref="GOV-02", category="Governance", origins=["FR-56"], municipality=ALL,
        question="Do you support creating a regional service that designs, builds and "
                 "maintains local municipal infrastructure - sewer, stormwater and paving "
                 "- shared across Capital Region municipalities?",
        options="a) Yes b) Yes, if full cost recovery is guaranteed c) No d) Unsure",
        qtype="Single choice + optional comment",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="The longest preamble in the bank: four questions in one paragraph, branching "
            "by municipality, with a fifth floated at the end under 'perhaps also'. Cut to "
            "the single shared-services question all four branches were circling.",
    ),

    # --------------------------------------------------------------- Climate
    dict(
        ref="CLI-01", category="Climate", origins=["FR-22", "FR-23", "FR-31", "FR-24"],
        question="Would you support ending fossil fuel advertising and sponsorship on "
                 "property, media and events controlled by your municipality, to the "
                 "extent the law allows? And would you advocate for the same at the "
                 "Victoria Regional Transit Commission for BC Transit vehicles and "
                 "shelters?",
        options="a) Yes - both advertising and sponsorship b) Yes - advertising only "
                "c) Yes - sponsorship only d) No e) Unsure. Follow-up: would you raise it "
                "at the VRTC? a) Yes b) No c) Unsure",
        qtype="Single choice + follow-up",
        change="Reworded + merged", asked_by="Michael, Sam, Claude",
        why="Four fossil-fuel-adjacent questions were competing for the same climate slots. "
            "FR-22 (advertising) and FR-23 (sponsorship) are one gesture; FR-31 asked the "
            "same as FR-23 but never said whether it meant the candidate personally or the "
            "municipality. FR-24 concerns BC Transit advertising, which the VRTC decides "
            "and not council - kept as an advocacy follow-up rather than a council "
            "commitment.",
        note="FR-24's submitter noted a transit ad ban 'is illegal'. Charter s.2(b) makes "
             "it contestable rather than flatly illegal, which is why the follow-up asks "
             "about advocacy and carries 'to the extent the law allows'. Sam asked that "
             "the scope cover regional as well as municipal property.",
    ),
    dict(
        ref="CLI-02", category="Climate", origins=["FR-27"],
        question="The CRD declared a climate emergency in 2019. How should your "
                 "municipality treat climate action in its next four-year plan?",
        options="a) The overriding priority - other decisions should be tested against it "
                "b) One of the top three priorities, with dedicated budget c) One priority "
                "among many, addressed where affordable d) Not a municipal priority - it "
                "is a provincial and federal responsibility",
        qtype="Single choice",
        change="Reworded", asked_by="Michael, Sam, Claude, sheet note",
        why="Every candidate agrees the climate crisis is critical, so as a yes/no this "
            "graded the whole field an A. Converted to the gradation the sheet note asked "
            "for, so that 'critical' and 'one priority among many' land differently.",
    ),
    dict(
        ref="CLI-03", category="Climate", origins=["FR-28"],
        question="Would you support publishing a register of all lobbying meetings held by "
                 "councillors, including meetings with fossil fuel companies and their "
                 "representatives?",
        options="a) Yes b) No c) Unsure", qtype="Single choice",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="A pledge to never meet fossil fuel lobbyists is a purity test we do not hold "
            "as a position, and it makes us read as an advocacy group rather than a voter "
            "guide. 'I meet anyone but vote against them' is a defensible councillor "
            "position we would have been scoring as a fail. Reframed to lobbying "
            "transparency, which is a municipal lever.",
    ),
    dict(
        ref="CLI-04", category="Climate", origins=["FR-29"],
        question="Climate-related damage and adaptation costs increasingly fall on "
                 "municipal budgets. Would you vote to have your municipality join other "
                 "BC local governments in legal action to recover a share of those costs "
                 "from major fossil fuel producers?",
        options="a) Yes b) Yes, if the cost to the municipality is capped c) No d) Unsure",
        qtype="Single choice",
        change="Reworded", asked_by="Michael, Claude",
        why="Cut on posture, not on disagreement: as submitted it asked candidates to sign "
            "a named external campaign at a set per-resident dollar figure, which is a "
            "loyalty test rather than a policy question. Reframed to the underlying "
            "question of climate cost recovery.",
        note="Live locally - View Royal has already joined.",
    ),
    dict(
        ref="CLI-05", category="Climate", origins=["FR-33"], change="Unchanged",
        note="Michael: best of the small-bore climate questions. A zoning amendment is the "
             "only lever council has here, so it is the policy rather than a prescription "
             "of one.",
    ),
    dict(
        ref="CLI-06", category="Climate", origins=["FR-26", "FR-25"],
        question="Extreme heat, wildfire smoke and wildfire risk all affect people living "
                 "in existing homes. What would you have your municipality do to protect "
                 "them? Select all you support.",
        options="a) Subsidised home assessments for heat, air quality and wildfire risk "
                "b) Grants or financing for cooling, filtration and building retrofits "
                "c) Bylaw requirements on vegetation management and exterior cladding in "
                "wildfire-exposed areas d) Designated cooling and clean-air centres with "
                "guaranteed opening hours e) A public information campaign only f) None "
                "of the above",
        qtype="Multi-select",
        change="Reworded + merged", asked_by="Michael, Sam, Claude",
        why="FR-25 (a Victoria-scoped wildfire awareness campaign) and FR-26 (a subsidised "
            "indoor air-quality audit) both named a specific programme instead of asking "
            "what the municipality should do, and nobody opposes an awareness campaign. "
            "Merged into our only climate adaptation question, with the teeth Sam asked "
            "for: vegetation and cladding bylaws, and retrofit funding.",
    ),
    dict(
        ref="CLI-07", category="Climate", origins=["FR-30"], municipality=ALL,
        change="Unchanged",
        note="Michael: small-bore but genuinely municipal, and it does separate. Expect "
             "landscaping-contractor pushback. Claude: first cut if the questionnaire has "
             "to shrink.",
    ),
    dict(
        ref="CLI-08", category="Climate", origins=["FR-32"],
        question="Large data centres can add substantial electricity and water demand. "
                 "Under what conditions, if any, would you support a new data centre in "
                 "your municipality?",
        options="a) Only with waste-heat recovery and no net increase in potable water use "
                "b) Only under conditions set case by case c) Support without special "
                "conditions d) Oppose all new data centres",
        qtype="Single choice",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="'Prevent the construction of all AI data centers' is absolutist, is a "
            "mechanism rather than a goal, and is not a position this coalition has taken "
            "- it also left unclear whether the concern is electricity, water or land use, "
            "and whether it covers all data centres or only AI. Reworded around the "
            "conditions, which is what a council can actually set.",
    ),
    dict(ref="CLI-09", category="Climate", origins=["RUSH-01"], change="Unchanged",
         graded=False, note="Submitted after voting closed - ungraded by the committee."),
    dict(ref="CLI-10", category="Climate", origins=["RUSH-02"], change="Unchanged",
         graded=False, note="Submitted after voting closed - ungraded by the committee."),
    dict(ref="CLI-11", category="Climate", origins=["RUSH-03"], change="Unchanged",
         graded=False, note="Submitted after voting closed - ungraded by the committee."),
    dict(
        ref="CLI-12", category="Climate", origins=[], municipality=ALL, graded=False,
        question="The UBCM passed several resolutions saying municipalities should be able "
                 "to have climate action lens and climate considerations in development and "
                 "housing mandates. Do you support blue green infrastructure upgrades as a "
                 "requirement of developments for climate readiness?",
        options="a) Yes b) No", qtype="Yes/no",
        source="Late submission", change="Unchanged",
        note="Arrived 2026-08-13, after voting closed and after the master was built, so "
             "this is the only shipping question with no master row behind it. Ungraded by "
             "the committee, on the same footing as CLI-09 to CLI-11. Ships as received, "
             "including 'should be able to have climate action lens' - read 'to apply a "
             "climate action lens' if that is meant as a typo. 'Blue green infrastructure' "
             "is specialist vocabulary that candidates may read as anything from a rain "
             "garden to a daylighted creek, so gloss it with examples if the committee "
             "wants comparable answers.",
    ),

    # ------------------------------------------------------------------ Arts
    dict(
        ref="ART-01", category="Arts", origins=["VU-02"], municipality=ALL,
        question="Do you consider arts and culture to be a core part of your "
                 "municipality's economic development strategy? If yes, what role should "
                 "the municipality play?",
        options="a) Yes b) No c) Unsure, plus follow-up (500 characters)",
        qtype="Single choice + short answer",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="The preamble answered the question - nobody says arts are bad for the economy "
            "- and it named Victoria, so it could not go to other municipalities. Preamble "
            "stripped, scope broadened. The resubmission restored both, so both come back "
            "out.",
        note="Score the follow-up, not the yes/no. " + RESUB,
    ),
    dict(
        ref="ART-02", category="Arts", origins=["VU-03", "VU-11"], municipality=ALL,
        question="If elected, what specific action will you commit to in your first year "
                 "to strengthen your municipality's arts and cultural sector, and what "
                 "measurable outcome should residents expect by the end of your four-year "
                 "term?",
        options="Name measurable outcomes where you can. Policy changes, funding "
                "commitments, infrastructure projects, regulatory reforms and "
                "partnerships all count.",
        qtype="Open response (2000 characters), scored 0-3",
        change="Reworded + merged", asked_by="Michael, Sam, Claude",
        why="VU-11 is VU-03 at a different horizon. Merged into one question covering both "
            "and reworded away from 'Victoria's arts sector' so it reaches the region.",
        note="Rubric: 0 = no commitment or vague support, 1 = identifies a general "
             "priority, 2 = identifies a specific policy action, 3 = specific action with "
             "a measurable outcome or timeline. The resubmission spelled out the kinds of "
             "outcome it wanted named, which is worth having and is now the prompt under "
             "the question; its 2000 character limit replaces the 1500 this carried, since "
             "one box answers what were two questions. " + RESUB,
    ),
    dict(
        ref="ART-03", category="Arts", origins=["VU-04"], municipality=ALL,
        question="Cultural strategies are often adopted and then not implemented. Would "
                 "you support a cultural space implementation framework with defined "
                 "tools, timelines and public reporting? Select up to three components you "
                 "would prioritise.",
        options="a) A regularly updated inventory of cultural spaces and vulnerable venues "
                "b) Identifying priority cultural spaces requiring protection or "
                "intervention c) Establishing municipal tools to support long-term "
                "affordability and stability d) Partnerships with non-profits to secure "
                "permanent cultural assets e) Reviewing zoning, permitting and regulatory "
                "barriers affecting cultural uses f) Measurable implementation targets and "
                "timelines g) Reporting publicly on progress h) Developing or updating a "
                "cultural space strategy or action plan first "
                "i) I do not support such a framework",
        qtype="Multi-select (max 3)",
        change="Reworded", asked_by="Michael, Claude",
        why="'Would you support timelines and accountability' is a free yes, and it was "
            "Victoria-scoped. Six components that all sound reasonable meant most "
            "candidates would tick most boxes, so it is capped at three and an opposing "
            "option was added.",
        note="Two components added from the resubmission: measurable targets (f), and "
             "writing another strategy first (h). Option (h) is the weak answer to a "
             "question about why strategies do not get implemented, which is exactly why "
             "it is worth offering - spending one of three picks on it says something. The "
             "cap of three does the work of holding a nine-option list down. " + RESUB,
    ),
    dict(
        ref="ART-04", category="Arts", origins=["VU-05"], municipality=ALL,
        question="Arts organisations and event producers identify permitting, zoning and "
                 "regulatory requirements as barriers to cultural activity. What would you "
                 "commit to? Select all that apply.",
        options="a) Clear, published service standards for permit decisions b) Published "
                "decision-making criteria, so requirements are not interpreted "
                "inconsistently c) A dedicated review of cultural and event permitting "
                "processes and policies d) Simplified requirements for small-scale events "
                "e) Better coordination between municipal departments f) A single point of "
                "coordination for cultural and event permits g) Reviewing zoning barriers "
                "for cultural uses h) Reviewing requirements that impose disproportionate "
                "costs on non-profits i) None - current processes are working",
        qtype="Multi-select",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="Unopposable by construction: no candidate defends unnecessary barriers, and "
            "neither the question nor any of the seven options had an opposing answer. "
            "Reordered to lead with measurable service standards, widened to 'processes "
            "and policies' per Sam, and given an opt-out option.",
        note="Option (b) is new from the resubmission, which named inconsistent "
             "interpretation as a barrier in its own right rather than a symptom of the "
             "others. " + RESUB,
    ),
    dict(
        ref="ART-05", category="Arts", origins=["VU-06", "VU-07", "VU-10"],
        municipality=ALL,
        question="Preserving cultural venues costs money. Which funding and ownership "
                 "approaches would you support? Select up to five.",
        options="a) Reallocating existing municipal resources b) Increasing property taxes "
                "or a dedicated cultural infrastructure levy c) Development contributions "
                "or amenity fees (e.g. ~1% of capital project budgets to public art) d) A "
                "regional cultural infrastructure fund shared across CRD municipalities "
                "e) Municipal money used to leverage matching, foundation or community "
                "capital f) Requiring or incentivising cultural space as part of major "
                "developments g) Density or other development incentives in exchange for "
                "dedicated cultural space h) Reduced or waived municipal fees, or property "
                "tax relief, for eligible cultural spaces i) A cultural land trust or "
                "non-profit ownership model j) Municipal loan guarantees or financing "
                "partnerships k) Long-term municipal leases for cultural use l) I do not "
                "support additional municipal investment",
        qtype="Multi-select (max 5)",
        change="Reworded + merged", asked_by="Michael, Claude",
        why="VU-06 is the one arts question that makes candidates choose. VU-07 ('would "
            "you support exploring...') costs nothing to say yes to, and VU-10 was a free "
            "yes already covered by one of VU-06's options. Both fold in as options here.",
        note="VU-07's full tool menu - patient capital, community bonds, loan guarantees, "
             "collateral funds - is municipal-finance specialist vocabulary; most "
             "candidates would have picked 'Unsure'. Condensed to two plain-language "
             "options. The resubmission turned VU-10 from a bare yes/no into a real menu, "
             "so its development-linked tools now appear as (f) to (h), and VU-06 added "
             "(d) and (e). That took the merged list from eight options to twelve, and an "
             "uncapped select-all that long invites ticking everything, so it is capped at "
             "five - the same move the committee made on ART-03. Drop the cap if the "
             "committee would rather see the full spread. " + RESUB,
    ),
    dict(
        ref="ART-06", category="Arts", origins=["VU-08"], municipality=ALL,
        question="Municipal budgets require difficult choices. Would you support "
                 "maintaining arts and culture investment alongside other core municipal "
                 "services?",
        options="a) Yes - arts and culture should maintain or grow alongside other core "
                "services b) No - arts and culture funding should remain secondary to "
                "other municipal priorities c) Only if new revenue sources are identified "
                "d) Unsure",
        qtype="Single choice",
        change="Reworded", asked_by="Michael, Claude",
        why="Deleted the '(i.e. Police funding)' aside. Those four words turn an "
            "arts-budget question into a police-budget question - candidates answer the "
            "parenthetical - and cost us the non-partisan posture.",
        note="The resubmission dropped that aside and arrived at the same four options "
             "independently, so this one needed nothing. " + RESUB,
    ),
    dict(
        ref="ART-07", category="Arts", origins=["VU-09"], municipality=ALL,
        question="When a major development project affects an existing cultural space, "
                 "what should your municipality prioritise? Select one.",
        options="a) Preserve the existing cultural space where feasible b) Require "
                "replacement cultural space or an equivalent community benefit as part of "
                "the redevelopment c) Weigh housing supply and cultural space together, "
                "with neither automatically taking precedence d) Evaluate case by case "
                "against overall community benefit",
        qtype="Single choice",
        change="Reworded", asked_by="Michael, Claude",
        why="Framing development as 'pressure on culture' sets Victori'Us against Homes "
            "for Living, and the original option (c) put housing supply and cultural space "
            "in direct opposition - our arts partners against our housing partners. "
            "Reworded neutral, trade-off intact, and select-one resolved per the sheet "
            "note.",
        note="The resubmission restated both the 'pressure' framing and the original "
             "option (c) verbatim, so the committee's version stands. This is the one arts "
             "row where we are knowingly not shipping what was asked for; if that is the "
             "wrong call it is a one-line diff here. " + RESUB,
    ),
    dict(
        ref="ART-08", category="Arts", origins=["VU-12"], municipality=ALL, graded=False,
        question="Should your municipality show a preference for particular types of arts "
                 "and cultural activity when deciding where to invest, or treat them "
                 "alike? If it should choose, how should those priorities be set?",
        options="Criteria you might weigh: community demand, gaps in cultural "
                "infrastructure, economic impact, equity and access, preservation of "
                "cultural heritage, or others of your own.",
        qtype="Open response (1000 characters)",
        change="Reworded", asked_by="(arrived after voting closed, no committee comment)",
        why="New in the resubmission and the only genuinely new arts question in it. "
            "Reworded off 'Victoria and municipalities across the CRD have historically "
            "supported ... particular types of performing arts', which both scoped it to "
            "one municipality and answered it: naming the incumbent preference tells a "
            "candidate which way to lean. The choice is put both ways instead.",
        note="Published unscored at the submitter's request - they asked that answers "
             "appear beside the scorecard without affecting a grade, which is also the "
             "only defensible call on a question no committee member has seen. " + RESUB,
    ),

    # ------------------------------------------------------- Healthcare access
    dict(
        ref="HLT-01", category="Healthcare access", origins=["FR-57"], graded=False,
        question="What role should your municipality play in establishing new primary care "
                 "clinics? Select one, then elaborate if you wish.",
        options="a) Municipality as operator - physicians, nurse practitioners and support "
                "staff are municipal employees (the Colwood model) b) Municipality "
                "supports indirectly through permissive tax exemptions, zoning and "
                "below-market rent, with a non-profit such as South Island Primary Care "
                "Society or Shoreline Medical Society operating the clinic (the Langford / "
                "Sidney / Central Saanich model) c) No municipal role - medical care is "
                "solely a provincial responsibility. Optional elaboration (500 characters).",
        qtype="Single choice + short answer",
        change="Reworded", asked_by="Michael, Sam, Claude, sheet note",
        why="Good question, buried under its own footnote. The MSP funding note moves out "
            "of the question body, and the sheet note's optional elaboration box is added.",
        note="Footnote to display: in all three cases the BC Medical Services Plan pays "
             "the clinic operator per patient or per visit, so there is no direct "
             "per-patient cost to the municipality. This is the only Healthcare access "
             "question in the bank - it cannot carry a published category on its own. "
             "Either commission a second or do not publish the column. Marked ungraded "
             "on every voter tab.",
    ),

    # --------------------------------------------------------- Reconciliation
    dict(
        ref="REC-01", category="Reconciliation", origins=["FR-55"], graded=False,
        municipality=ALL, change="Unchanged",
        note="Only Reconciliation question in the bank, and everyone says yes - an all-A "
             "column is decoration. Sam: we need a partner such as the Native Friendship "
             "Centre on board before we grade on Reconciliation. Publish unscored, or hold "
             "the category until two or three more questions are commissioned with the "
             "relevant Nations.",
    ),

    # ------------------------------------------------ Housekeeping (internal)
    dict(
        ref="HK-01", category="Housekeeping", origins=["FR-47", "FR-49"], graded=False,
        question="How competitive is your campaign? Tell us about volunteers, individual "
                 "donors, when you announced, previous runs, and incumbency. Roughly how "
                 "much has your campaign raised so far, and how much do you expect to "
                 "raise in total? Ranges are fine. We use this only to decide which "
                 "candidates appear in our social and print materials. It is not scored "
                 "and not published.",
        options="", qtype="Short answer + range",
        change="Reworded + merged", asked_by="Michael, Sam, Claude",
        why="FR-49 (fundraising) is the same viability judgement, so it folds in. The "
            "trailing 'why are you running?' clause is removed - HK-02 already asks it. "
            "Candidates are now told how the answer is used: asking people to self-assess "
            "their odds and then quietly ranking them damages trust if it surfaces later. "
            "Asks for a range rather than a number, since Elections BC financing "
            "disclosures cover the exact figures after the fact.",
    ),
    dict(
        ref="HK-02", category="Housekeeping", origins=["FR-48"], graded=False,
        question="Why are you running for office? Maximum 400 characters. We may publish "
                 "this on our website.",
        options="", qtype="Short answer (400 characters)",
        change="Reworded", asked_by="Sam, Claude",
        why="Overlapped FR-47's trailing clause, which was removed there instead. Added a "
            "character limit and told candidates it may be published.",
    ),
]

# Questions that ship in neither tab, and the argument for cutting each.
DROPPED = [
    ("FR-17", "Housekeeping", "Michael, Sam, Claude",
     "'What is your favourite book about city building?' Charming, but not a policy "
     "question - it tests reading list and rewards name-dropping, and it spends candidate "
     "attention we need elsewhere. GEN-01 gives better colour for socials."),
    ("FR-39", "Walking", "Michael, Sam, Claude",
     "A 3m minimum sidewalk width is a design standard, not a policy question, and it was "
     "downtown-only. Easy to answer, just not worth asking; the funding version survives "
     "as WLK-03."),
    ("FR-41", "Transit", "Michael, Claude",
     "'Do you support the development of a regional traffic circulation plan?' has no "
     "opposing answer, and it is weak beside TRN-04's regional transportation authority."),
    ("FR-43", "Transit", "Michael, Claude",
     "'Do you support allocating funding to short term transit improvement projects?' - "
     "nobody says no, and 'short term improvement' could mean a bus shelter or a bus lane. "
     "The sheet note asked for examples and costs that were never supplied."),
    ("FR-44", "Rolling & cycling", "Michael, Sam, Claude",
     "Pop-up cafes and food trucks on the regional trails. Peripheral - not why anyone "
     "opens a scorecard, and the first thing to cut when the questionnaire has to shrink."),
    ("FR-46", "Transit", "Michael, Sam, Claude",
     "Malahat transit cost-sharing, addressed to transit commissioners. A long preamble, "
     "requires knowing how VRTC cost-sharing works, and only a handful of candidates can "
     "answer it - let alone act on it. Keeping it means accepting a mostly blank column."),
    ("FR-51", "Housekeeping", "Michael, Claude",
     "'Take selfie with candidate' is not a question - it is a logistics task for us. "
     "Belongs in a run-of-show doc. Michael flagged that we should decide separately "
     "whether we still want to do this."),
    ("FR-52", "Housing", "Michael, Claude",
     "Unanswerable as written: it never says which District, and it asks candidates to "
     "recall one specific staff report by the date it went to council."),
    ("FR-54", "Housing", "Michael, Sam, Claude",
     "The preamble states a contested empirical finding as settled fact - the Terner paper "
     "models one Los Angeles programme - and then asks candidates to answer 'despite this'. "
     "BC only received inclusionary zoning authority in Bill 16 (2024). It also contradicts "
     "our own sheet, where HFL-04 and HFL-09 list inclusionary zoning as a neutral option. "
     "Sam, who submitted it, agreed. Now covered neutrally as an option of HFL-04 "
     "('Mandated requirements') and HFL-09 ('Mandating that affordable housing be built by "
     "developers')."),
]


# Why a question that is not in DROPPED still has no row of its own in the shipping set.
# These are the merges: the reason is never "we did not want it", it is "another question
# carries it", so each entry has to say which one and what was kept. Keyed by master ID.
#
# The destination row's `why` argues the merge from the surviving question's side. This
# argues it from the excluded one's, which is what somebody looking up their own
# submission wants to read. Falls back to the destination's `why` if a merge is added
# here without a reason, so a new merge degrades to a vaguer answer rather than none.
MERGED_WHY = {
    "FR-04":
        "Third of three open 'what would you do' prompts in the bank, and the vaguest of "
        "them. Caleb: 'possibly worthy of exclusion; this question is too vague.' Michael: "
        "'Merge into FR-02. Same shape, vaguer, and I can't grade \"ideas\" consistently "
        "across a full candidate field.' Sam ticked shouldn't-be-graded. FR-02 survives as "
        "WLK-02, rewritten to demand one concrete commitment rather than ideas.",
    "FR-07":
        "A yes/no on all-ages-and-abilities routes that almost nobody answers no to. "
        "Caleb: 'great question but lacks distinguishablilty broadly speaking.' Michael: "
        "'Everyone says yes. Merge into FR-10, which at least asks for funding and "
        "completion.' Claude wanted the scoring weight moved to the specific route "
        "questions. FR-10 ships as ROL-01, anchored to completing one missing link inside "
        "one term.",
    "FR-13":
        "The same question as HFL-05 in weaker wording. Claude: 'Duplicate of HFL-05, "
        "which spells out uses, heights and densities and closes the loophole where "
        "\"pre-zoning\" is answered loosely. Drop this, keep HFL-05.' Michael agreed. "
        "HFL-05 ships as submitted, under its own code.",
    "FR-14":
        "One of four questions asking about parking minimums (FR-14, FR-36, HFL-08, "
        "HFL-09). Every voter who commented said merge - Sam: 'should be combined with "
        "other car parking requirement questions'; Claude: 'Fold the land-use split into "
        "HFL-08 and cut the rest.' HFL-08 ships as submitted, so the merge stands but the "
        "fold does not: FR-14's split by land use is not in HFL-08's wording, and neither "
        "is Michael's note that Bill 47 already bars residential minimums near transit. "
        "What survives is HFL-08's conditional option, which captures the conditional "
        "supporter a yes/no cannot.",
    "FR-15":
        "One of three questions asking for the same list of tools for getting more "
        "non-market and affordable housing (FR-15, HFL-04, HFL-09). Michael: 'Merge into "
        "FR-15. Running both asks for the incentive list twice.' Its first clause - should "
        "non-market housing be incentivised? - gets a yes from everyone, so only the list "
        "was ever the question, and HFL-04 asks for that list. HFL-04 now ships as "
        "submitted, so the list is an open-ended option set rather than the municipal-tool "
        "options the committee had supplied.",
    "FR-16":
        "Duplicate of HFL-03. Sam: 'dupe of HfL Qs.' The disagreement was over which to "
        "keep, not whether: Michael preferred this one because '\"Maximum\" is a "
        "commitment; \"target\" is a wish', Claude preferred HFL-03 for its day-count "
        "tiers that can be scored. HFL-03 ships as submitted, so Claude's day-count tiers "
        "survive and Michael's 'maximum' does not.",
    "FR-19":
        "Tied the pedestrian share of the transport budget to the proportion of residents "
        "without a driver's licence. Michael: 'The licence-holder ratio is invented and no "
        "candidate can compute it.' Claude: 'Ask for the funding commitment and drop the "
        "formula ... prescribes a mechanism, and needs a statistic most candidates will "
        "not have.' Three of four voters flagged 'F: how'. The funding commitment survives "
        "as WLK-03, built on FR-18, with the ratio gone.",
    "FR-20":
        "A price point, an age, a licence test and two time windows in a single yes/no. "
        "Michael: 'Half price, 65+, no licence, 10-4 and after 7 is a fare schedule, not a "
        "question. And the VRTC sets fares.' Claude: it 'leaves no way to back discounted "
        "senior fares but not the off-peak restriction'. Sam wanted the off-peak window "
        "moved to 2:30pm. Folded into TRN-01, which asks the fare question as VRTC "
        "advocacy, the lever a councillor actually has. The fare schedule was dropped "
        "rather than corrected.",
    "FR-21":
        "Duplicate of FR-03 with the reasoning removed. Claude: 'Duplicate of FR-03, which "
        "asks for reasoning. Drop this one.' Michael: 'Merge into FR-03, which at least "
        "asks for reasoning.' FR-03 ships as TRN-01.",
    "FR-23":
        "One of four fossil-fuel questions competing for the same climate slots. Michael: "
        "'Merge into FR-22. Same gesture, two climate slots.' It won its own head-to-head "
        "against FR-31 in the comments (Claude: 'this one is unambiguously about the "
        "municipality') but lost the slot to the advertising version, FR-22, which ships "
        "as CLI-01 with sponsorship folded in as part of the same commitment.",
    "FR-24":
        "BC Transit advertising is decided by the VRTC, not by a council. Michael cut it "
        "on jurisdiction, and could not verify the submitter's '(this is illegal)' note: "
        "'Charter s.2(b) makes it contestable, not illegal.' Claude: as written 'it "
        "penalises candidates who know the law'. Sam: 'combine with FR-22'. It survives "
        "inside CLI-01 as an advocacy follow-up rather than a council commitment.",
    "FR-25":
        "Named a specific programme instead of asking what the municipality should do "
        "about wildfire risk, and was Victoria-scoped. Claude: 'Nobody opposes an "
        "awareness campaign.' Michael: 'FR-26 rewritten as an outcome covers this better.' "
        "Sam asked for teeth - 'bylaws on vegitation and cladding, and funding for "
        "retrofits' - and CLI-06, built on FR-26, carries them.",
    "FR-31":
        "Same substance as FR-23 and ambiguous about who is being asked. Claude: "
        "'Duplicate of FR-23, and ambiguous per the sheet note - candidate personally, or "
        "the municipality? Keep FR-23.' Michael: 'Same substance as FR-23. Merge into "
        "FR-22.' Sam: 'seems repetitive with the lobby ones'. All four voters who scored "
        "it ticked EXCLUDE - the only question in the bank that was unanimous on that at "
        "full turnout (RUSH-01 and RUSH-03 are too, but on a single vote each).",
    "FR-36":
        "Second of the four parking-minimum questions, and the only one that pre-declared "
        "its own grade. Michael: 'the text pre-declares the grade - \"A for yes, F for "
        "no\" cannot ship to candidates.' Claude: 'Drop; keep HFL-08.' Sam: 'needs to be "
        "merged with other parking Qs'. The substance is in HFL-08; the 2030 deadline is "
        "not, since HFL-08 asks what candidates support rather than by when.",
    "FR-49":
        "The same viability judgement as FR-47. Michael: 'Fold into FR-47 as one viability "
        "question. Candidates can answer it; many will decline.' Claude: 'Ask for a range, "
        "not a number. Candidates will under-report or skip it, and Elections BC financing "
        "disclosures cover the same ground after the fact.' HK-01 asks for a range, per "
        "that comment.",
    "FR-53":
        "Three commitments run together with slashes: raise property taxes, follow the "
        "asset replacement strategy, accelerate the timeline. Michael: 'Split the run-on. "
        "The question I want is the first clause.' Claude suggested reusing 'the HFL-12 "
        "\"select up to two\" format'. Sam: 'dupe of similar HfL question'. It folds into "
        "the HFL infrastructure block, which ships as HFL wrote it for the five "
        "municipalities they researched a figure for and as GOV-03-* for the other eight; "
        "its first clause is option (b) either way. Worth noting this is the strongest "
        "question on the excluded list - mean 4.08, status STRONG - and it is here because "
        "a better-formatted question asks the same thing, not because the committee "
        "thought little of it.",
    # No HFL-* entries: every one of the 25 ships under its own code. The merges the
    # committee had voted for - HFL-01 into HFL-06, HFL-04 into FR-15, HFL-09 split between
    # two rows - were reversed on 2026-08-13 and are recorded in the notes on those rows.
    "VU-07":
        "Not voted on: the Victori'Us resubmission of 2026-08-09 replaced this question "
        "after voting closed, so the reasoning is the committee's verdict on the version "
        "they did see. 'Would you support exploring ...' costs nothing to say yes to, and "
        "its tool menu - patient capital, community bonds, loan guarantees, collateral "
        "funds - is municipal-finance specialist vocabulary that most candidates would "
        "answer 'Unsure' to. Condensed into plain-language options inside ART-05.",
    "VU-10":
        "Not voted on: replaced by the 2026-08-09 resubmission after voting closed. The "
        "version the committee saw was a bare Yes / No / Unsure already covered by one of "
        "VU-06's options, which is why it was folded in. The resubmission turned it into a "
        "seven-option menu of development-linked tools, which is real content, so it ships "
        "as options (f) to (h) of ART-05 rather than as a row of its own.",
    "VU-11":
        "Not voted on: replaced by the 2026-08-09 resubmission after voting closed. VU-11 "
        "is VU-03 at a different horizon - first-year action against four-year outcome - "
        "so the two ship as one question, ART-02, which asks for both. Its list of outcome "
        "kinds and its 2000-character limit were carried across.",
}


def normalise_muni(value):
    """The master carries both 'All municipalities' and 'All Municipalities'.

    Tally routes candidates by this column, so the two spellings would build two
    separate question pools. Anything that is not a single named municipality is
    region-wide.
    """
    value = value.strip()
    if not value or value.lower().startswith("all "):
        return ALL
    return value if value in MUNICIPALITIES else ALL


def expand(final):
    """Expand the one municipality-templated block into a row per municipality.

    Only the infrastructure question is still templated, and only for the eight
    municipalities Homes for Living never wrote one for: HFL's own five ship verbatim from
    FINAL, as does every housing-target row. FR-35 and FR-53, which asked this region-wide,
    are absorbed here.
    """
    rows = list(final)

    infra = []
    for muni in MUNICIPALITIES:
        if muni in HFL_INFRA:
            continue
        figure = INFRA_FIGURES.get(muni, "")
        if figure:
            body = (f"In {muni}, {figure}. Which approaches would you prioritise to "
                    "address this infrastructure funding gap? Select up to two.")
            note = ""
        else:
            # Still names the municipality. Tally exports one CSV column per block, headed
            # by the question text, so eight identically-worded blocks would export as
            # eight indistinguishable columns.
            body = (f"Which approaches would you prioritise to address {muni}'s "
                    "infrastructure funding gap? Select up to two.")
            note = (f"FIGURE NEEDED for {muni} - add it to INFRA_FIGURES in finalize.py "
                    "and re-run. This generic version ships in the meantime so the "
                    "municipality is not a question short.")
        if muni in NO_TARGET:
            note = (f"{muni} received no provincial housing target order, so it gets this "
                    "question only - one municipality-specific question rather than two. "
                    + note)
        infra.append(dict(
            ref=f"GOV-03-{muni.replace(' ', '')}", category="Governance",
            municipality=muni, origins=["FR-35", "FR-53"],
            question="Municipal asset-management plans have identified substantial gaps "
                     "between current funding and the amount needed to maintain and "
                     "replace roads, water and sewer systems, public buildings and other "
                     "infrastructure. " + body,
            options=INFRA_OPTIONS, qtype="Multi-select (max 2)",
            change="Reworded + merged", asked_by="Michael, Sam, Claude",
            why="FR-35 asked for three steps toward 'a firmer financial footing' in a "
                "blank box; FR-53 ran three commitments together with slashes - raise "
                "property taxes, follow the asset replacement strategy, accelerate the "
                "timeline. Both ask what HFL's infrastructure block asks, with options "
                "that can be scored and where FR-53's first clause is already option (b), "
                "so this carries them for the eight municipalities HFL wrote no "
                "infrastructure question for. The other five ask it as HFL worded it.",
            note=note,
        ))

    at = next(i for i, r in enumerate(rows) if r["ref"] == "GOV-02") + 1
    rows[at:at] = infra
    return rows


def carry_over_ticks(sh):
    """Ref -> current 'Added To Tally Questionnaire' value, from the existing tab.

    The tab is rebuilt wholesale on every run, so without this a re-run would clear
    the build tracking - the one column here that holds work the sheet is the only
    record of. Rows are matched by Ref; a Ref that no longer exists drops its tick,
    which is the right outcome, since that question is no longer being shipped.
    """
    try:
        ws = sh.worksheet(FINALIZED)
    except gspread.WorksheetNotFound:
        return {}
    values = ws.get_all_values()
    if not values or TRACK_HEADER not in values[0]:
        return {}
    col = values[0].index(TRACK_HEADER)
    return {row[0].strip(): row[col].strip().upper() == "TRUE"
            for row in values[1:]
            if row and row[0].strip() and len(row) > col}


def write_tab(sh, title, headers, body, widths=None, wrap_from=0, bool_cols=()):
    """Replace a tab wholesale, as a frozen-header native table."""
    existing = {ws.title: ws for ws in sh.worksheets()}
    meta = sh.fetch_sheet_metadata()
    tables = {s["properties"]["sheetId"]: s.get("tables", []) for s in meta["sheets"]}

    if title in existing:
        ws = existing[title]
        for t in tables.get(ws.id, []):
            sh.batch_update({"requests": [{"deleteTable": {"tableId": t["tableId"]}}]})
        ws.clear()
        ws.resize(rows=max(len(body) + 10, 20), cols=len(headers))
        print(f"  rebuilt {title!r}")
    else:
        ws = sh.add_worksheet(title=title, rows=len(body) + 10, cols=len(headers))
        print(f"  created {title!r}")

    ws.update([headers] + body, "A1", value_input_option="RAW")

    table = {
        "name": title.replace(" ", ""),
        "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": len(body) + 1,
                  "startColumnIndex": 0, "endColumnIndex": len(headers)},
    }
    # Checkbox columns. Safe to set columnProperties here only because this table is
    # anchored at column A - see the addTable gotcha in the questionnaire README.
    if bool_cols:
        table["columnProperties"] = [
            {"columnIndex": i, "columnName": headers[i], "columnType": "BOOLEAN"}
            for i in bool_cols]
    reqs = [{"addTable": {"table": table}}]
    for i, w in enumerate(widths or []):
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": ws.id, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize",
        }})
    # Long prose columns wrap; the short ones stay on one line so the tab scans.
    reqs.append({"repeatCell": {
        "range": {"sheetId": ws.id, "startRowIndex": 1,
                  "startColumnIndex": wrap_from, "endColumnIndex": len(headers)},
        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP",
                                       "verticalAlignment": "TOP"}},
        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)",
    }})
    sh.batch_update({"requests": reqs})
    ws.freeze(rows=1, cols=1)
    return ws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="also write the Finalized Questions rows to this path")
    ap.add_argument("--dry-run", action="store_true", help="print counts, write nothing")
    args = ap.parse_args()

    sh = open_sheet()
    values = sh.worksheet(MASTER).get_all_values()
    master = {r[0]: r for r in values[1:] if r[0].strip()}
    # Stand-in for a row with no master origin, so every read below stays uniform instead
    # of special-casing a late question field by field.
    blank = [""] * len(values[0])

    rows = expand(FINAL)

    missing = sorted({o for r in rows for o in r["origins"]} - set(master))
    if missing:
        sys.exit(f"FATAL: origin IDs not in {MASTER}: {', '.join(missing)}")

    # An origin-less row has no master text to fall back on, so it ships blank rather than
    # wrong if these are left off.
    unsourced = [r["ref"] for r in rows
                 if not r["origins"] and not (r.get("question") and r.get("qtype"))]
    if unsourced:
        sys.exit(f"FATAL: these rows have no origin in {MASTER}, so they must carry their "
                 f"own question and qtype: {', '.join(unsourced)}")

    reworded_body, final_body = [], []
    for r in rows:
        origins = r["origins"]
        src = master[origins[0]] if origins else blank
        # Falling back to the master keeps every submitter email out of this repo.
        question = r.get("question") or src[3]
        options = r.get("options", src[4]) if "question" in r else src[4]
        qtype = r.get("qtype") or src[5]
        muni = normalise_muni(r.get("municipality") or src[8])
        # The DUPES notes aggregate.py stamps in ("Overlaps FR-21...") described merges
        # that this file has now carried out, so they would read as outstanding work.
        sheet_note = " | ".join(
            n for n in (master[o][9].strip() for o in origins)
            if n and not n.startswith(("Overlaps ", "Duplicate question text")))
        note = " | ".join(n for n in (r.get("note", ""), sheet_note) if n)
        graded = "No" if r.get("graded") is False else "Yes"
        submitters = " | ".join(dict.fromkeys(
            master[o][7] for o in origins if master[o][7])) or r.get("submitter", "")
        sources = " | ".join(dict.fromkeys(
            master[o][6] for o in origins)) or r.get("source", "")

        final_body.append([
            r["ref"], r["category"], muni, question, options, qtype,
            submitters, sources, graded, ", ".join(origins), note,
        ])

        if r["change"] == "Unchanged":
            continue
        reworded_body.append([
            r["ref"], r["category"], r["change"], ", ".join(origins),
            "\n\n".join(f"{o}: {master[o][3]}" for o in origins),
            question, options, qtype, r.get("asked_by", ""), r.get("why", ""),
        ])

    for qid, cat, who, why in DROPPED:
        reworded_body.append([
            "(dropped)", cat, "Dropped", qid, f"{qid}: {master[qid][3]}",
            "", "", "", who, why,
        ])

    # Every question that has no shipping row of its own: the nine in DROPPED, and the
    # ones absorbed into somebody else's row. Both are invisible in Finalized Questions,
    # and a submitter looking for their question needs to find out which happened.
    shipped, absorbed = {}, {}
    for r in rows:
        if not r["origins"]:
            continue
        shipped.setdefault(r["origins"][0], r)
        for o in r["origins"][1:]:
            absorbed.setdefault(o, []).append(r)
    dropped_by_id = {d[0]: d for d in DROPPED}

    # The tabs are not a filtered view of the master, so a question in neither the
    # shipping set nor DROPPED would disappear from all three without saying so.
    orphans = [q for q in master if q not in shipped and q not in absorbed
               and q not in dropped_by_id]
    if orphans:
        sys.exit(f"FATAL: these questions are in no FINAL row and not in DROPPED, so "
                 f"they would vanish silently: {', '.join(orphans)}")

    def cell(row, i):
        return row[i].strip() if len(row) > i else ""

    excluded_body = []
    for qid, src in master.items():
        if qid in shipped:
            continue
        if qid in dropped_by_id:
            _, _, who, why = dropped_by_id[qid]
            outcome, refs, kept = "Dropped", "", ""
        else:
            dest = absorbed[qid]
            outcome = "Merged"
            refs = ", ".join(dict.fromkeys(d["ref"] for d in dest))
            kept = dest[0]["origins"][0]
            who = dest[0].get("asked_by", "")
            why = MERGED_WHY.get(qid) or dest[0].get("why", "")
        excluded_body.append([
            qid, cell(src, 1), cell(src, 3), cell(src, 4), cell(src, 7), cell(src, 6),
            outcome, refs, kept, cell(src, 13), cell(src, 14), cell(src, 21),
            cell(src, 22), who, why, cell(src, 23),
        ])

    print(f"{len(final_body)} finalized rows, "
          f"{len(reworded_body) - len(DROPPED)} changed, {len(DROPPED)} dropped")
    merged = sum(1 for r in excluded_body if r[6] == "Merged")
    print(f"{len(excluded_body)} of {len(master)} questions have no row of their own "
          f"({len(DROPPED)} dropped, {merged} merged into another)")
    thin = [r[0] for r in excluded_body if not r[14]]
    if thin:
        print(f"  no reason recorded for: {', '.join(thin)}")
    region_wide = sum(1 for r in final_body if r[2] == ALL)
    graded = sum(1 for r in final_body if r[8] == "Yes")
    print(f"{graded} graded, {len(final_body) - graded} published unscored")
    print(f"{region_wide} region-wide questions, {len(MUNICIPALITIES)} municipal branches:")
    for muni in MUNICIPALITIES:
        extra = sum(1 for r in final_body if r[2] == muni)
        # Only the templated eight can be short a figure; HFL's five carry theirs in the
        # question text they submitted.
        needed = muni not in HFL_INFRA and not INFRA_FIGURES.get(muni)
        todo = "   <- FIGURE NEEDED" if needed else ""
        print(f"  {muni:18} {region_wide + extra} questions{todo}")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(FINAL_HEADERS)
            w.writerows(final_body)
        print(f"wrote {args.csv}")

    ticks = carry_over_ticks(sh)
    if ticks:
        print(f"{sum(ticks.values())} existing Tally ticks carried over")

    if args.dry_run:
        return

    write_tab(sh, REWORDED, REWORD_HEADERS, reworded_body,
              widths=[80, 110, 120, 110, 420, 420, 320, 150, 130, 420], wrap_from=4)
    write_tab(sh, FINALIZED, FINAL_HEADERS + [TRACK_HEADER],
              [row + [ticks.get(row[0], False)] for row in final_body],
              widths=[110, 120, 120, 460, 460, 170, 200, 140, 70, 130, 380, 190],
              wrap_from=3, bool_cols=[len(FINAL_HEADERS)])
    write_tab(sh, EXCLUDED, EXCLUDED_HEADERS, excluded_body,
              widths=[80, 130, 420, 320, 170, 150, 90, 150, 100, 80, 80, 90, 90, 140,
                      520, 520],
              wrap_from=2)
    print(f"done ({sum(1 for r in final_body if ticks.get(r[0]))} rows already "
          f"ticked as added to Tally)")


REWORD_HEADERS = [
    "Ref", "Category", "Change", "Origin IDs", "Original question(s)",
    "Reworded question", "Answers / options", "Question type",
    "Change requested by", "Why",
]

FINAL_HEADERS = [
    "Ref", "Category", "Municipality", "Question", "Answers / options", "Question type",
    "Submitter", "Source", "Graded", "Origin IDs", "Notes",
]

# Scores are carried across so a reader can see that most of these lost on the vote and
# a few, FR-53 above all, did not. "Kept from" is the master ID that ended up carrying
# the question, which is what a submitter asking "where did mine go" wants; "Shipped
# instead" is where to read it in Finalized Questions.
EXCLUDED_HEADERS = [
    "ID", "Category", "Question", "Answers / options", "Submitter", "Source",
    "Outcome", "Shipped instead", "Kept from", "Mean score", "Votes cast",
    "Exclude votes", "Status", "Decided by", "Why it is not in the questionnaire",
    "Voter comments",
]


if __name__ == "__main__":
    main()
