"""DPR request workflow -- "send me today's DPR" (#16 Daily Report Generation).

Read-only, like workflows/labour_query and workflows/activity_query: the
node only produces status text (pending_prompt). The PDF document itself is
NOT sent through this graph -- runtime/inbound_journey.py's post-reply
delivery step sends it as a WhatsApp document once collected_fields carries
a ready object key from runtime/dpr_request_query.py's seeding.
"""
