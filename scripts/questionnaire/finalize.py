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

from aggregate import MASTER, open_sheet

REWORDED = "Reworded Questions"
FINALIZED = "Finalized Questions"

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

# Municipality-specific figures, lifted from the HFL source rows they came in on. Both
# blocks were submitted as one question repeated per municipality with the numbers swapped;
# they are templated here so the wording cannot drift again the way HFL-18's did.
#
# The province's housing target orders cover 10 of the 13. Sooke, Highlands and Metchosin
# were never ordered, so they skip this question rather than being asked a hollow version
# of it.
HOUSING_TARGETS = {
    "Victoria": ("4,902", "HFL-11"),
    "Saanich": ("4,610", "HFL-13"),
    "Oak Bay": ("664", "HFL-15"),
    "Central Saanich": ("588", "HFL-17"),
    "Esquimalt": ("754", "HFL-18"),
    "Sidney": ("468", "HFL-20"),
    "Langford": ("2,993", "HFL-21"),
    "View Royal": ("585", "HFL-22"),
    "North Saanich": ("419", "HFL-23"),
    "Colwood": ("940", "HFL-24"),
}

# Every municipality gets this question, so every municipality needs its own figure. Only
# five had been researched when voting closed; the rest are marked FIGURE NEEDED below and
# ship a generic version until their number lands, so the gap shows up in the sheet rather
# than silently producing an unbalanced questionnaire.
#
# Each entry is a clause that reads after "In <muni>, ...", plus the master row it came
# from ("" for municipalities that had no HFL source row).
INFRA_FIGURES = {
    "Victoria": ("the 2024 Corporate Asset Management Strategy identified $570 million "
                 "worth of infrastructure in poor or very poor condition", "HFL-12"),
    "Saanich": ("the 2023 Asset Management Strategy identified a $697 million "
                "infrastructure deficit, and the 2025 State of Asset Report estimates a "
                "shortfall of $51 million per year", "HFL-14"),
    "Oak Bay": ("the 2024-2028 Financial Plan estimated the infrastructure deficit at "
                "$463.5 million", "HFL-16"),
    "Esquimalt": ("the 2026-2030 Workforce Plan estimated the infrastructure deficit at "
                  "$35.8 million, with current funding at 40% of sustainable levels",
                  "HFL-19"),
    "Colwood": ("the 2024 Sustainable Infrastructure Replacement Plan estimates the "
                "100-year infrastructure funding gap at $530 million", "HFL-25"),
    # FIGURE NEEDED - fill in the same shape as the five above, citing the document and
    # year the number comes from. Until then these ship the generic wording.
    "Central Saanich": ("", ""),
    "Sidney": ("", ""),
    "Langford": ("", ""),
    "View Royal": ("", ""),
    "North Saanich": ("", ""),
    "Sooke": ("", ""),
    "Highlands": ("", ""),
    "Metchosin": ("", ""),
}

INFRA_OPTIONS = (
    "a) Allow substantially more housing and commercial development to grow the tax base "
    "and help fund infrastructure renewal. "
    "b) Increase property taxes or introduce a dedicated infrastructure levy. "
    "c) Increase development cost charges, amenity contributions, or other fees imposed "
    "on new housing and development. "
    "d) Reduce or defer infrastructure projects, service levels, or replacement standards. "
    "e) Seek additional provincial or federal funding."
)

TARGET_OPTIONS = (
    "a) Fewer homes than the target (the target is too high) "
    "b) About that many homes (the target is approximately right) "
    "c) More homes than the target (the target is too low)"
)

# Every question in the shipping set, in the order candidates will see it.
#
#   ref        stable ID for the final questionnaire
#   origins    the master IDs this row came from; the first is the row we inherit
#              submitter / source / municipality from
#   change     "Unchanged" | "Reworded" | "Merged" | "Reworded + merged" | "Recategorised"
#   asked_by   who called for the change, from the voter comments
#   why        the argument for it, condensed from those comments
#   graded     False for questions we publish but do not score
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
             "signal. Sam asked for links to each municipality's budget alongside it.",
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
            "ceiling. Adjacent to HSG-03, not a duplicate - process versus built form.",
    ),
    dict(
        ref="HSG-02", category="Housing", origins=["HFL-05", "FR-13"],
        change="Merged", asked_by="Michael, Claude",
        why="FR-13 asked the same question in weaker wording. HFL-05 names uses, heights "
            "and densities, which closes the loophole where 'pre-zoning' gets answered "
            "loosely, so FR-13 folds in and HFL-05's text is kept as submitted.",
        note="Bill 44 already bars public hearings on OCP-consistent residential "
             "rezonings, so part of this is compliance with existing law. Several "
             "municipalities have already done it (Sam).",
    ),
    dict(
        ref="HSG-03", category="Housing", origins=["HFL-06", "HFL-01"],
        question="Beyond the three to four units Bill 44 already requires, what is the "
                 "most housing you think should be legal to build by right - without "
                 "rezoning - in traditional single-family areas of your municipality? "
                 "Select one. Then: which kinds of housing does your municipality most "
                 "need more of? Select up to three.",
        options="Select one: a) Nothing beyond the provincial minimum b) Small-scale "
                "multi-unit housing (up to 6 units) c) Multi-lot townhouse developments "
                "(strata or freehold) d) Small apartments (up to 3 storeys) e) Mid-rise "
                "apartments (up to 6 storeys). "
                "Select up to three: a) Supportive housing for people who need mental "
                "health and substance use support b) Publicly funded accessible housing "
                "for elderly and/or disabled people c) Non-market affordable housing "
                "d) Small homes (under 500 sq. ft.) e) Market rental housing "
                "f) Family-suitable housing (3+ bedrooms, over 1200 sq. ft.) g) Market "
                "ownership housing (condos, townhouses)",
        qtype="Single choice + multi-select (max 3)",
        change="Reworded + merged", asked_by="Michael, Sam, Claude",
        why="HFL-01 asked what housing a municipality needs more of; HFL-06 asks the same "
            "thing with teeth, so it folds in as the follow-up. Added 'beyond the SSMUH "
            "minimum' and made the ladder explicitly select-one, or the ordinal score "
            "breaks. Dropped HFL-01's 'luxury housing' option - nobody ticks it and its "
            "presence telegraphs the answer we want.",
    ),
    dict(
        ref="HSG-04", category="Housing", origins=["HFL-07"],
        question="A housing proposal consistent with the Official Community Plan has been "
                 "reviewed by staff, who recommend approval. It still requires rezoning "
                 "because the zoning has not been updated to match the OCP. If it faces "
                 "substantial public opposition, how would you generally vote?",
        options="a) Support it if opposing comments have been considered by staff. "
                "b) Support it only if it includes additional affordability or community "
                "benefits. c) Decide case by case, with public opposition being an "
                "important consideration. d) Generally oppose it if there is substantial "
                "public opposition.",
        qtype="Single choice",
        change="Reworded", asked_by="Michael, Sam",
        why="Highest-scoring question in the bank - it forces the exact trade-off a "
            "councillor faces. Two edits only, both Sam's: state that the proposal is "
            "OCP-compliant, and drop 'neighbourhood', which implies only nearby residents "
            "count.",
    ),
    dict(
        ref="HSG-05", category="Housing", origins=["HFL-03", "FR-16"],
        question="Do you support setting a maximum approval time for multifamily housing "
                 "applications in your municipality - a deadline, not a target?",
        options="a) Yes - under 30 days for projects under six units, 180 days for "
                "projects over six units. b) Yes - under 60 days / 365 days. c) Yes - "
                "under 90 days / 545 days. d) No.",
        qtype="Single choice",
        change="Reworded + merged", asked_by="Michael, Sam, Claude",
        why="Both questions ask the same thing. FR-16's 'maximum' is a commitment where "
            "HFL-03's 'target' is a wish, but HFL-03 carries the day-count tiers that can "
            "actually be scored. Merged: FR-16's framing, HFL-03's tiers.",
    ),
    dict(
        ref="HSG-06", category="Housing", origins=["HFL-08", "FR-14", "FR-36", "HFL-09"],
        question="Bill 47 already bars residential parking minimums in transit-oriented "
                 "areas. Beyond that, where do you support eliminating minimum off-street "
                 "parking requirements in your municipality? Select all that apply.",
        options="a) All residential development b) Residential development under 12 units "
                "c) Small-scale commercial d) All commercial e) Only where alternatives "
                "are provided for residents (secure bike storage, car share, e-bike "
                "charging, transit passes) f) None - keep the current minimums",
        qtype="Multi-select",
        change="Reworded + merged", asked_by="Michael, Sam, Claude",
        why="Four questions asked this: FR-14 (tiered by land use), FR-36 (all land uses "
            "by 2030), HFL-08 and HFL-09 (identical text). Every voter who commented said "
            "merge. HFL-08's conditional option captures the conditional supporter that "
            "the yes/no versions cannot; FR-14's land-use tiers add the rest of the "
            "signal.",
        note="FR-36's text contained '(A for yes, F for no)' - a grading instruction that "
             "leaked into the question and could not have shipped to candidates.",
    ),
    dict(
        ref="HSG-07", category="Housing", origins=["FR-15", "HFL-04", "HFL-09"],
        question="Which municipal tools would you support to get more non-market and "
                 "affordable housing built? Select up to three.",
        options="a) Pre-zoning b) Bonus height or density c) Relaxing setbacks, form and "
                "character, or other zoning restrictions d) Removing or reducing municipal "
                "fees, levies and development cost charges e) Expedited review "
                "f) Donating or leasing municipal land g) Directly building, or partnering "
                "with non-profit developers h) Requiring affordable units in market "
                "projects (inclusionary zoning) i) None of the above",
        qtype="Multi-select (max 3)",
        change="Reworded + merged", asked_by="Michael, Sam, Claude, sheet note",
        why="FR-15, HFL-04 and HFL-09 all ask for the incentive list. FR-15's first clause "
            "('should non-market housing be incentivised?') gets a yes from everyone, so "
            "the list becomes the question; scoped to municipal-level tools per the sheet "
            "note and supplied as options, because an open 'list the incentives' is "
            "uncomparable and penalises candidates who are less fluent in policy jargon.",
        note="HFL-09 is a broken source row: its question text is copy-pasted from HFL-08 "
             "but its options are affordable-housing delivery tools. Those options are "
             "recovered here, which is where they belonged.",
    ),
    dict(
        ref="HSG-08", category="Housing", origins=["HFL-02"],
        question="Which of the following do you support to minimise tenant displacement "
                 "and maintain or grow the supply of affordable housing? Select up to "
                 "three.",
        options="a) Award bonus density to affordable housing developments. b) Redirect "
                "development pressure away from existing older multifamily by allowing "
                "new multifamily in more low-density areas. c) Municipality-wide tenant "
                "assistance policies that let existing tenants keep their current rent "
                "after redevelopment. d) Working with the province on province-wide tenant "
                "assistance policies. e) Identify and acquire land for non-market housing. "
                "f) Temporarily exempt existing rental buildings from property taxes to "
                "fund retrofits. g) Exempt below-market housing from municipal fees and "
                "levies. h) Target a higher rental vacancy rate. i) None of the above.",
        qtype="Multi-select (max 3)",
        change="Reworded", asked_by="Claude",
        why="Nine options, each a full policy concept, means candidates tick everything "
            "and the question stops separating. Capped at three.",
    ),
    dict(ref="HSG-09", category="Housing", origins=["HFL-10"], change="Unchanged"),
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
            "stripped, scope broadened.",
        note="Score the follow-up, not the yes/no.",
    ),
    dict(
        ref="ART-02", category="Arts", origins=["VU-03", "VU-11"], municipality=ALL,
        question="If elected, what specific action will you commit to in your first year "
                 "to strengthen your municipality's arts and cultural sector, and what "
                 "measurable outcome should residents expect by the end of your four-year "
                 "term?",
        options="", qtype="Open response (1500 characters), scored 0-3",
        change="Reworded + merged", asked_by="Michael, Sam, Claude",
        why="VU-11 is VU-03 at a different horizon. Merged into one question covering both "
            "and reworded away from 'Victoria's arts sector' so it reaches the region.",
        note="Rubric: 0 = no commitment or vague support, 1 = identifies a general "
             "priority, 2 = identifies a specific policy action, 3 = specific action with "
             "a measurable outcome or timeline. VU-11 referenced a global rubric at the "
             "bottom of the source sheet that did not survive the import - check whether "
             "anything else depended on it.",
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
                "barriers affecting cultural uses f) Reporting publicly on progress "
                "g) I do not support such a framework",
        qtype="Multi-select (max 3)",
        change="Reworded", asked_by="Michael, Claude",
        why="'Would you support timelines and accountability' is a free yes, and it was "
            "Victoria-scoped. Six components that all sound reasonable meant most "
            "candidates would tick most boxes, so it is capped at three and an opposing "
            "option was added.",
    ),
    dict(
        ref="ART-04", category="Arts", origins=["VU-05"], municipality=ALL,
        question="Arts organisations and event producers identify permitting, zoning and "
                 "regulatory requirements as barriers to cultural activity. What would you "
                 "commit to? Select all that apply.",
        options="a) Clear, published service standards for permit decisions b) A dedicated "
                "review of cultural and event permitting processes and policies "
                "c) Simplified requirements for small-scale events d) Better coordination "
                "between municipal departments e) A single point of coordination for "
                "cultural and event permits f) Reviewing zoning barriers for cultural uses "
                "g) Reviewing requirements that impose disproportionate costs on "
                "non-profits h) None - current processes are working",
        qtype="Multi-select",
        change="Reworded", asked_by="Michael, Sam, Claude",
        why="Unopposable by construction: no candidate defends unnecessary barriers, and "
            "neither the question nor any of the seven options had an opposing answer. "
            "Reordered to lead with measurable service standards, widened to 'processes "
            "and policies' per Sam, and given an opt-out option.",
    ),
    dict(
        ref="ART-05", category="Arts", origins=["VU-06", "VU-07", "VU-10"],
        municipality=ALL,
        question="Preserving cultural venues costs money. Which funding and ownership "
                 "approaches would you support? Select all that apply.",
        options="a) Reallocating existing municipal resources b) Increasing property taxes "
                "or a dedicated levy c) Development contributions or amenity fees (e.g. "
                "~1% of capital project budgets to public art) d) Municipal incentives for "
                "landlords and developers who maintain affordable cultural space e) A "
                "cultural land trust or non-profit ownership model f) Municipal loan "
                "guarantees or financing partnerships g) Long-term municipal leases for "
                "cultural use h) I do not support additional municipal investment",
        qtype="Multi-select",
        change="Reworded + merged", asked_by="Michael, Claude",
        why="VU-06 is the one arts question that makes candidates choose. VU-07 ('would "
            "you support exploring...') costs nothing to say yes to, and VU-10 was a free "
            "yes already covered by one of VU-06's options. Both fold in as options here.",
        note="VU-07's full tool menu - patient capital, community bonds, loan guarantees, "
             "collateral funds - is municipal-finance specialist vocabulary; most "
             "candidates would have picked 'Unsure'. Condensed to two plain-language "
             "options.",
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
     "Sam, who submitted it, agreed. Now covered neutrally as option (h) of HSG-07."),
]


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
    """Expand the municipality-templated blocks into one row per municipality."""
    rows = list(final)
    housing = [
        dict(
            ref=f"HSG-11-{muni.replace(' ', '')}", category="Housing", municipality=muni,
            origins=[origin],
            question=f"The BC government set a housing target for {muni} of {homes} homes "
                     "over five years, which represents 75% of the estimated housing need "
                     "for that period. Regardless of provincial requirements or penalties, "
                     "do you believe your municipality should aim to build:",
            options=TARGET_OPTIONS, qtype="Single choice",
            change="Reworded", asked_by="Claude",
            why="Ten near-identical municipality variants whose wording had already "
                "drifted - HFL-18 numbered its options 1/2/3 where every sibling used "
                "a/b/c - and all ten said 'the city', which does not fit every "
                "municipality. Templated from one master so it cannot drift again.",
            note="Option order changed to fewer / about right / more so the scale reads in "
                 "order. Targets: "
                 "https://www2.gov.bc.ca/gov/content/housing-tenancy/local-governments-and-"
                 "housing/housing-targets/orders",
        )
        for muni, (homes, origin) in HOUSING_TARGETS.items()
    ]

    infra = []
    for muni in MUNICIPALITIES:
        figure, origin = INFRA_FIGURES.get(muni, ("", ""))
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
        if muni not in HOUSING_TARGETS:
            note = (f"{muni} received no provincial housing target order, so it gets this "
                    "question only - one municipality-specific question rather than two. "
                    + note)
        infra.append(dict(
            ref=f"GOV-03-{muni.replace(' ', '')}", category="Governance",
            municipality=muni, origins=[o for o in (origin, "FR-35", "FR-53") if o],
            question="Municipal asset-management plans have identified substantial gaps "
                     "between current funding and the amount needed to maintain and "
                     "replace roads, water and sewer systems, public buildings and other "
                     "infrastructure. " + body,
            options=INFRA_OPTIONS, qtype="Multi-select (max 2)",
            change="Reworded + merged", asked_by="Michael, Sam, Claude",
            why="FR-35 asked for three steps toward 'a firmer financial footing' in a "
                "blank box; FR-53 ran three commitments together with slashes - raise "
                "property taxes, follow the asset replacement strategy, accelerate the "
                "timeline. Both fold into the HFL infrastructure block, which asks the "
                "same thing with options that can be scored and where FR-53's first "
                "clause is already option (b).",
            note=note,
        ))

    at = next(i for i, r in enumerate(rows) if r["ref"] == "HSG-10") + 1
    rows[at:at] = housing
    at = next(i for i, r in enumerate(rows) if r["ref"] == "GOV-02") + 1
    rows[at:at] = infra
    return rows


def write_tab(sh, title, headers, body, widths=None, wrap_from=0):
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

    reqs = [{"addTable": {"table": {
        "name": title.replace(" ", ""),
        "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": len(body) + 1,
                  "startColumnIndex": 0, "endColumnIndex": len(headers)},
    }}}]
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
    master = {r[0]: r for r in sh.worksheet(MASTER).get_all_values()[1:] if r[0].strip()}

    rows = expand(FINAL)

    missing = sorted({o for r in rows for o in r["origins"]} - set(master))
    if missing:
        sys.exit(f"FATAL: origin IDs not in {MASTER}: {', '.join(missing)}")

    reworded_body, final_body = [], []
    for r in rows:
        origins = r["origins"]
        src = master[origins[0]]
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
        submitters = " | ".join(dict.fromkeys(master[o][7] for o in origins if master[o][7]))
        sources = " | ".join(dict.fromkeys(master[o][6] for o in origins))

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

    print(f"{len(final_body)} finalized rows, "
          f"{len(reworded_body) - len(DROPPED)} changed, {len(DROPPED)} dropped")
    region_wide = sum(1 for r in final_body if r[2] == ALL)
    graded = sum(1 for r in final_body if r[8] == "Yes")
    print(f"{graded} graded, {len(final_body) - graded} published unscored")
    print(f"{region_wide} region-wide questions, {len(MUNICIPALITIES)} municipal branches:")
    for muni in MUNICIPALITIES:
        extra = sum(1 for r in final_body if r[2] == muni)
        todo = "" if INFRA_FIGURES.get(muni, ("", ""))[0] else "   <- FIGURE NEEDED"
        print(f"  {muni:18} {region_wide + extra} questions{todo}")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(FINAL_HEADERS)
            w.writerows(final_body)
        print(f"wrote {args.csv}")

    if args.dry_run:
        return

    write_tab(sh, REWORDED, REWORD_HEADERS, reworded_body,
              widths=[80, 110, 120, 110, 420, 420, 320, 150, 130, 420], wrap_from=4)
    write_tab(sh, FINALIZED, FINAL_HEADERS, final_body,
              widths=[110, 120, 120, 460, 460, 170, 200, 140, 70, 130, 380], wrap_from=3)
    print("done")


REWORD_HEADERS = [
    "Ref", "Category", "Change", "Origin IDs", "Original question(s)",
    "Reworded question", "Answers / options", "Question type",
    "Change requested by", "Why",
]

FINAL_HEADERS = [
    "Ref", "Category", "Municipality", "Question", "Answers / options", "Question type",
    "Submitter", "Source", "Graded", "Origin IDs", "Notes",
]


if __name__ == "__main__":
    main()
