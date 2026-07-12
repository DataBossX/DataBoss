# Leasehold Calculations

`title_interest.py` uses exact rational arithmetic for supported values. Working interest (WI), royalty burden, net revenue interest (NRI), and net leasehold acres must each carry evidence references and an accepted evidence status.

For a gross-production burden, `NRI = WI - royalty`. For a burden expressed against working interest, `NRI = WI × (1 - royalty)`. `net leasehold acres = WI × gross tract acres`. The burden basis is an explicit input; the software does not infer it safely from ambiguous lease prose.

Missing citations, ambiguous fractions, assumed values, negative results, unsupported terms, and inconsistent acreage block approval. Pooling, depth/formation limits, overrides, carried interests, farmouts, elections, unitization, and jurisdiction-specific clauses require examiner/counsel interpretation unless separately modeled and tested. Synthetic arithmetic tests are not validation of Section 32 interests.
