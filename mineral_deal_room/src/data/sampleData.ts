import type {
  Target,
  Evidence,
  DealScore,
  AuditEntry,
  ProjectCommandRecord,
  HoldRecord,
  DefectRecord,
  SimulatedJob,
  ApprovalRequest,
  WellRecord,
  ConflictRecord,
  VerificationReceipt
} from '../types'

export const SEEDED_PROJECTS: ProjectCommandRecord[] = [
  {
    projectId: 'SEED-HORIZON-32',
    displayName: 'Horizon 32 (SYNTHETIC)',
    standsInFor: 'Horizon Section 32',
    jurisdiction: { state: 'ZZ', county: 'Sandhill' },
    legalDescription: {
      section: '32',
      township: '11N',
      range: '25W',
      text: 'SECTION 32, TOWNSHIP 11 NORTH, RANGE 25 WEST — SYNTHETIC LAND ONLY'
    },
    lifecycleState: 'EXAMINER_REVIEW',
    releaseState: 'FOR_REVIEW_HOLD_NO_EXTERNAL_RELEASE',
    holds: [
      {
        holdId: 'HOLD-SEED-32-001',
        kind: 'INTERNAL_REVIEW_CONTROL',
        scope: 'PROJECT_AND_ALL_ARTIFACTS',
        clearableBy: 'AUTHENTICATED_HUMAN_ONLY',
        clearableByAutomation: false,
        reason: 'Internal review control. No external release.',
        setAt: '2026-08-01T00:00:00Z',
        setBy: 'tournament-director'
      }
    ],
    defects: [
      {
        defectId: 'DEF-SEED-32-SIZE-001',
        type: 'SIZE_ANOMALY',
        severity: 'RED',
        summary: 'Candidate workbook byte size deviates from the approved template baseline beyond tolerance.',
        observed: { candidateBytes: 1418240, templateBytes: 262144, tolerancePct: 25 },
        expectedBehaviour: 'Block release. Quarantine candidate. Require human examiner decision. Do not auto-repair.',
        resolutionState: 'OPEN_REQUIRES_HUMAN'
      }
    ],
    tracts: [
      { tractId: 'SEED-32-T1', label: 'Tract 1 (NE/4)', grossAcres: '160', note: 'SYNTHETIC' },
      { tractId: 'SEED-32-T2', label: 'Tract 2 (NW/4)', grossAcres: '160', note: 'SYNTHETIC' }
    ]
  },
  {
    projectId: 'SEED-PENTERRA-20',
    displayName: 'Penterra 20 (SYNTHETIC)',
    standsInFor: 'Penterra Section 20',
    jurisdiction: { state: 'ZZ', county: 'Sandhill' },
    legalDescription: {
      section: '20',
      township: '9N',
      range: '22W',
      text: 'SECTION 20, TOWNSHIP 9 NORTH, RANGE 22 WEST — SYNTHETIC LAND ONLY'
    },
    lifecycleState: 'INTERNAL_REVIEW',
    releaseState: 'FOR_REVIEW_HOLD_NO_EXTERNAL_RELEASE',
    holds: [
      {
        holdId: 'HOLD-SEED-20-001',
        kind: 'INTERNAL_REVIEW_CONTROL',
        scope: 'PROJECT_AND_ALL_ARTIFACTS',
        clearableBy: 'AUTHENTICATED_HUMAN_ONLY',
        clearableByAutomation: false,
        reason: 'Internal review control. No external release.',
        setAt: '2026-08-01T00:00:00Z',
        setBy: 'tournament-director'
      }
    ],
    defects: [],
    tracts: [
      { tractId: 'SEED-20-T1', label: 'Tract 1 (E/2)', grossAcres: '320', note: 'SYNTHETIC' }
    ]
  },
  {
    projectId: 'SEED-PENTERRA-17',
    displayName: 'Penterra 17 (SYNTHETIC)',
    standsInFor: 'Penterra Section 17',
    jurisdiction: { state: 'ZZ', county: 'Sandhill' },
    legalDescription: {
      section: '17',
      township: '9N',
      range: '22W',
      text: 'SECTION 17, TOWNSHIP 9 NORTH, RANGE 22 WEST — SYNTHETIC LAND ONLY'
    },
    lifecycleState: 'INTERNAL_REVIEW',
    releaseState: 'FOR_REVIEW_HOLD_NO_EXTERNAL_RELEASE',
    holds: [
      {
        holdId: 'HOLD-SEED-17-001',
        kind: 'INTERNAL_REVIEW_CONTROL',
        scope: 'PROJECT_AND_ALL_ARTIFACTS',
        clearableBy: 'AUTHENTICATED_HUMAN_ONLY',
        clearableByAutomation: false,
        reason: 'Internal review control. No external release.',
        setAt: '2026-08-01T00:00:00Z',
        setBy: 'tournament-director'
      }
    ],
    defects: [
      {
        defectId: 'DEF-SEED-17-LEASE-001',
        type: 'LEASE_VALIDITY_QUESTION',
        severity: 'YELLOW',
        summary: 'Synthetic lease A-10 has an unresolved habendum/HBP question pending examiner review.',
        expectedBehaviour: 'Surface as open review item with evidence gap. No automated conclusion.',
        resolutionState: 'OPEN_REQUIRES_HUMAN'
      }
    ],
    tracts: [
      { tractId: 'SEED-17-T1', label: 'Tract 1 (All Sec 17)', grossAcres: '640', note: 'SYNTHETIC' }
    ]
  }
]

export const SEEDED_WELLS: WellRecord[] = [
  {
    wellId: 'W-SEED-0001',
    api: '99-999-00001',
    name: 'SANDHILL 32-1H (SYNTHETIC)',
    operatorName: 'Northfork Synthetic Energy LLC',
    surfaceLocation: 'Sec 32-11N-25W (Sandhill Co., ZZ)',
    wellboreType: 'HORIZONTAL',
    status: 'PRODUCING',
    spudDate: '2024-03-11',
    completionDate: '2024-07-02',
    formation: 'SYNTHETIC SHALE A',
    linkedTracts: ['SEED-32-T1'],
    linkConfidence: 'HIGH',
    monthlyProduction: [
      { period: '2024-08', oilBbl: 18400, gasMcf: 41200, waterBbl: 9100, source: 'SEED-OFFICIAL-FEED', restated: false },
      { period: '2024-09', oilBbl: 15100, gasMcf: 36800, waterBbl: 8800, source: 'SEED-OFFICIAL-FEED', restated: false },
      { period: '2024-10', oilBbl: 12950, gasMcf: 33100, waterBbl: 8400, source: 'SEED-OFFICIAL-FEED', restated: true, restatementNote: 'Superseded by corrected filing 2025-02-03 (CF-2)' }
    ]
  },
  {
    wellId: 'W-SEED-0002',
    api: '99-999-00002',
    name: 'SANDHILL 20-2H (SYNTHETIC)',
    operatorName: 'Blue Mesa Fictional Resources Inc',
    surfaceLocation: 'Sec 20-9N-22W (Sandhill Co., ZZ)',
    wellboreType: 'HORIZONTAL',
    status: 'SHUT_IN',
    spudDate: '2023-09-01',
    completionDate: '2023-12-19',
    formation: 'SYNTHETIC SHALE B',
    linkedTracts: ['SEED-20-T1'],
    linkConfidence: 'HIGH',
    monthlyProduction: [
      { period: '2024-01', oilBbl: 9800, gasMcf: 22400, waterBbl: 5100, source: 'SEED-OFFICIAL-FEED', restated: false }
    ]
  },
  {
    wellId: 'W-SEED-0003',
    api: '99-999-00003',
    name: 'SANDHILL 17-3H (SYNTHETIC)',
    operatorName: 'Blue Mesa Fictional Resources Inc',
    surfaceLocation: 'Sec 17-9N-22W (Sandhill Co., ZZ)',
    wellboreType: 'HORIZONTAL',
    status: 'PERMITTED_NOT_SPUD',
    formation: 'SYNTHETIC SHALE B',
    linkedTracts: ['SEED-17-T1', 'SEED-20-T1'],
    linkConfidence: 'AMBIGUOUS',
    ambiguityNote: 'Lateral crosses synthetic unit boundary; tract attribution is unresolved. Exercises RT-24.'
  }
]

export const SEEDED_CONFLICTS: ConflictRecord[] = [
  {
    id: 'CF-1',
    exercises: 'RT-22',
    type: 'CONTRADICTORY_OWNERSHIP',
    tractId: 'SEED-32-T1',
    title: 'Contradictory Undivided 1/4 Mineral Conveyance',
    description: 'Same undivided 1/4 conveyed to Meridian Synthetic Trust and Hollis Fictional Family LP, recorded on same day (1998-04-14).',
    requiredBehavior: 'Preserve both claims. Open conflict. Do NOT pick winner by AI vote or recency. Route to human review.',
    claims: [
      {
        claimId: 'CL-1a',
        party: 'MERIDIAN SYNTHETIC TRUST',
        interestType: 'MINERAL',
        fraction: '1/4',
        source: 'Instrument INS-SEED-0101 (Bk SYN-100, Pg 221, Rec 1998-04-14)',
        confidence: 'HIGH'
      },
      {
        claimId: 'CL-1b',
        party: 'HOLLIS FICTIONAL FAMILY LP',
        interestType: 'MINERAL',
        fraction: '1/4',
        source: 'Instrument INS-SEED-0117 (Bk SYN-104, Pg 008, Rec 1998-04-14)',
        confidence: 'HIGH'
      }
    ],
    status: 'OPEN_CONFLICT'
  },
  {
    id: 'CF-2',
    exercises: 'RT-23',
    type: 'CORRECTED_FILING',
    tractId: 'SEED-32-T1',
    title: 'Amended Monthly Production Restatement',
    description: 'Well W-SEED-0001 (Period 2024-10) original filing restated by operator amended report on 2025-02-03.',
    requiredBehavior: 'Retain original marked SUPERSEDED. Do not overwrite history. Recompute derived numbers.',
    status: 'RECONCILED_SUPERSEDED'
  },
  {
    id: 'CF-3',
    exercises: 'RT-24',
    type: 'AMBIGUOUS_PROPERTY_MAPPING',
    tractId: 'SEED-17-T1',
    title: 'Cross-Unit Horizontal Lateral Allocation Ambiguity',
    description: 'Well W-SEED-0003 lateral crosses unit boundary between Sec 17 and Sec 20. Attribution unproven.',
    requiredBehavior: 'Mark link AMBIGUOUS. Downstream revenue & lease impact flagged as conditional.',
    status: 'FLAGGED_AMBIGUOUS'
  },
  {
    id: 'CF-4',
    exercises: 'RT-25',
    type: 'LICENCE_RESTRICTED_SOURCE',
    tractId: 'GLOBAL',
    title: 'Licensed Commercial Feed Ingestion Boundary',
    description: 'Synthetic commercial dataset declared terms: CACHE_ONLY_30_DAYS, no redistribution.',
    requiredBehavior: 'Refuse durable store ingestion without verified rights. Zero client artifact exposure.',
    status: 'QUARANTINED_RESTRICTED'
  },
  {
    id: 'CF-5',
    exercises: 'RT-26',
    type: 'UNSUPPORTED_MODEL_CONCLUSION',
    tractId: 'SEED-32-T1',
    title: 'Unsupported AI Precise Valuation Claim',
    description: 'Model emitted unbacked statement "$1,284,500 net mineral value" with 0 supporting spans.',
    requiredBehavior: 'Reject as fact. Flag as unconfirmed speculation. Require probabilistic confidence range.',
    status: 'REJECTED_FABRICATION'
  }
]

export const INITIAL_SIMULATED_JOBS: SimulatedJob[] = [
  {
    jobId: 'JOB-SIM-001',
    idempotencyKey: 'IDEMP-SCAN-32-20260830-A',
    projectId: 'SEED-HORIZON-32',
    taskType: 'INVENTORY_AND_HASH',
    workerId: 'worker-local-alpha',
    state: 'COMPLETED',
    priority: 10,
    payloadSummary: 'Scan 24 local synthetic instruments and verify SHA-256 digests',
    simulated: true,
    createdAt: '2026-08-30T02:15:00Z',
    completedAt: '2026-08-30T02:15:04Z',
    resultHash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
  },
  {
    jobId: 'JOB-SIM-002',
    idempotencyKey: 'IDEMP-RECONCILE-32-20260830-B',
    projectId: 'SEED-HORIZON-32',
    taskType: 'FRACTION_INTEREST_MATH',
    workerId: 'worker-exact-math-01',
    state: 'READY',
    priority: 20,
    payloadSummary: 'Deterministic Fraction(numerator, denominator) chain recalculation',
    simulated: true,
    createdAt: '2026-08-30T02:30:00Z'
  },
  {
    jobId: 'JOB-SIM-003',
    idempotencyKey: 'IDEMP-WELL-AUDIT-20260830-C',
    projectId: 'SEED-PENTERRA-20',
    taskType: 'WELL_PRODUCTION_RESTATION',
    workerId: 'worker-well-brain-02',
    state: 'READY',
    priority: 30,
    payloadSummary: 'Verify OCC state feed vs operator amended filing for Sandhill 20-2H',
    simulated: true,
    createdAt: '2026-08-30T02:45:00Z'
  }
]

export const INITIAL_APPROVALS: ApprovalRequest[] = [
  {
    approvalId: 'APPR-2026-001',
    projectId: 'SEED-HORIZON-32',
    title: 'Examine & Reconcile Size-Anomaly Defect on Section 32 Candidate',
    action: 'DISMISS_DEFECT_AND_RESTORE_TEMPLATE',
    artifactHash: 'ad0cf2cfde55726d4a6ef36681693a399cf2835465c05bda36624aed73b8b19f',
    requestedBy: 'System QA Guard',
    scope: 'EXAMINER_REVIEW',
    state: 'PENDING',
    expiresAt: '2026-09-06T00:00:00Z',
    createdAt: '2026-08-30T02:00:00Z'
  },
  {
    approvalId: 'APPR-2026-002',
    projectId: 'SEED-PENTERRA-17',
    title: 'Review Habendum & HBP Lease Gap on Tract SEED-17-T1',
    action: 'FLAG_AFFIDAVIT_NON_PRODUCTION_REQUIRED',
    artifactHash: '92a5a128a4bf2d8ff5fe0768456b7ae3633662be9a45de9a954dea08bec1498f',
    requestedBy: 'Title Chain Analyzer',
    scope: 'LEGAL_CURATIVE',
    state: 'PENDING',
    expiresAt: '2026-09-10T00:00:00Z',
    createdAt: '2026-08-30T02:20:00Z'
  }
]

export const INITIAL_RECEIPTS: VerificationReceipt[] = [
  {
    receiptId: 'VR-DBX-20260830-001',
    projectId: 'SEED-HORIZON-32',
    timestamp: '2026-08-30T02:50:00Z',
    actor: 'CHALLENGER_CURSOR_HARNESS',
    target: 'Gate 0 Fail-Closed Sentinel Verification',
    inputHash: 'AD0CF2CFDE55726D4A6EF36681693A399CF2835465C05BDA36624AED73B8B19F',
    outputHash: 'AD0CF2CFDE55726D4A6EF36681693A399CF2835465C05BDA36624AED73B8B19F',
    status: 'VERIFIED_PASS',
    details: 'Byte-for-byte readback verified. Claim token deliberately unconsumed. Hold active.'
  }
]

export const SAMPLE_TARGETS: Target[] = [
  {
    id: 'T001',
    ownerName: 'Harlan D. McBride Estate',
    county: 'Garfield',
    section: '14',
    township: '23N',
    range: '7W',
    interestType: 'Mineral',
    nma: 40.0,
    dealScore: 87,
    status: 'Under Review',
    titleClearance: 'Needs Curative',
    estimatedValue: 128000,
    assignedTo: 'R. Gille',
    lastContact: '2026-05-10',
    notes: 'Probate closed 2021. Two heirs identified, one minor. Need guardian appointment.',
    curativesNeeded: ['Guardian Appointment – Minor Heir', 'Heirship Affidavit from Living Heirs'],
    evidenceCount: 4,
    createdAt: '2026-03-15',
    wellsProducing: 3,
    royaltyRate: '3/16',
  },
  {
    id: 'T002',
    ownerName: 'Viola Jean Strickland',
    county: 'Garfield',
    section: '22',
    township: '23N',
    range: '7W',
    interestType: 'Mineral',
    nma: 20.0,
    dealScore: 94,
    status: 'Offer Sent',
    titleClearance: 'Clean',
    estimatedValue: 74000,
    assignedTo: 'R. Gille',
    lastContact: '2026-05-18',
    notes: 'Clean title. Single owner. Responsive to calls. Price gap ~$8K.',
    curativesNeeded: [],
    evidenceCount: 2,
    createdAt: '2026-03-20',
    wellsProducing: 2,
    royaltyRate: '1/8',
  },
  {
    id: 'T003',
    ownerName: 'Cletus R. Dawson Jr.',
    county: 'Dewey',
    section: '5',
    township: '17N',
    range: '18W',
    interestType: 'Royalty',
    nma: 15.5,
    dealScore: 72,
    status: 'Contacted',
    titleClearance: 'Clean',
    estimatedValue: 38750,
    assignedTo: 'R. Gille',
    lastContact: '2026-04-30',
    notes: 'Royalty only. Owner reluctant. Has competing offer from Roan Resources.',
    curativesNeeded: [],
    evidenceCount: 1,
    createdAt: '2026-04-01',
    wellsProducing: 1,
    royaltyRate: '3/16',
  },
  {
    id: 'T004',
    ownerName: 'Blanche Fern Tullock Trust',
    county: 'Blaine',
    section: '33',
    township: '19N',
    range: '12W',
    interestType: 'Mineral',
    nma: 80.0,
    dealScore: 61,
    status: 'Identified',
    titleClearance: 'Probate Pending',
    estimatedValue: 192000,
    assignedTo: 'Unassigned',
    lastContact: '',
    notes: 'Trust terminated 2023. Settlor deceased. Court-supervised distribution underway in Blaine Co. Probate Case No. 2023-P-0441.',
    curativesNeeded: [
      'Wait for Probate Distribution Order',
      'Identify Current Title Holders Post-Probate',
    ],
    evidenceCount: 0,
    createdAt: '2026-04-10',
    wellsProducing: 4,
    royaltyRate: '1/5',
  },
  {
    id: 'T005',
    ownerName: 'Norval K. Prentiss',
    county: 'Garfield',
    section: '9',
    township: '24N',
    range: '6W',
    interestType: 'Working Interest',
    nma: 5.0,
    dealScore: 45,
    status: 'Passed',
    titleClearance: 'Needs Curative',
    estimatedValue: 11000,
    assignedTo: 'R. Gille',
    lastContact: '2026-03-28',
    notes: 'Working interest only. Owner wants $90K. Overpriced by 8x. Passed.',
    curativesNeeded: ['Unresolved Surface Damage Claim'],
    evidenceCount: 1,
    createdAt: '2026-03-01',
    wellsProducing: 1,
    royaltyRate: 'N/A',
  },
  {
    id: 'T006',
    ownerName: 'Doris Annette Rutherford',
    county: 'Major',
    section: '18',
    township: '21N',
    range: '15W',
    interestType: 'Mineral',
    nma: 32.5,
    dealScore: 81,
    status: 'Under Review',
    titleClearance: 'Clean',
    estimatedValue: 97500,
    assignedTo: 'R. Gille',
    lastContact: '2026-05-02',
    notes: 'Clean mineral deed from 1984. Producing well on section, Continental is operator. Needs division order review.',
    curativesNeeded: [],
    evidenceCount: 3,
    createdAt: '2026-04-15',
    wellsProducing: 2,
    royaltyRate: '3/16',
  }
]

export const SAMPLE_DEAL_SCORES: DealScore[] = [
  {
    targetId: 'T001',
    overallScore: 87,
    recommendation: 'Strong Buy',
    scoredAt: '2026-05-12',
    scoredBy: 'R. Gille',
    notes: 'Solid acreage in active drilling corridor. Curative straightforward.',
    components: [
      { name: 'Title Clearance', score: 18, maxScore: 25, rationale: 'Probate complete; guardian order needed for 1 minor heir.' },
      { name: 'Offset Well Activity', score: 24, maxScore: 25, rationale: '3 producing horizontal wells in section; 1 newly permitted.' },
      { name: 'Royalty & Terms', score: 22, maxScore: 25, rationale: '3/16 royalty, no burdensome post-production deductions.' },
      { name: 'Valuation & Upside', score: 23, maxScore: 25, rationale: 'Asking $3,200/NMA; recent comps at $4,100/NMA.' }
    ]
  },
  {
    targetId: 'T002',
    overallScore: 94,
    recommendation: 'Strong Buy',
    scoredAt: '2026-05-19',
    scoredBy: 'R. Gille',
    notes: 'Prime candidate. Clean title, high motivation, low complexity.',
    components: [
      { name: 'Title Clearance', score: 25, maxScore: 25, rationale: 'Zero title defects. Direct deed lineage from patent.' },
      { name: 'Offset Well Activity', score: 23, maxScore: 25, rationale: '2 active horizontal producers, Devon permitted 2 additional.' },
      { name: 'Royalty & Terms', score: 22, maxScore: 25, rationale: 'Standard 1/8 lease, HBP.' },
      { name: 'Valuation & Upside', score: 24, maxScore: 25, rationale: 'Target asking price leaves 28% IRR buffer.' }
    ]
  }
]

export const SAMPLE_EVIDENCE: Evidence[] = [
  {
    id: 'E001',
    targetId: 'T001',
    type: 'Warranty Deed',
    fileName: 'Garfield_WD_Bk412_Pg88.pdf',
    uploadedAt: '2026-03-16',
    county: 'Garfield',
    book: '412',
    page: '88',
    instrumentNumber: '1988-004521',
    grantors: ['Arthur M. McBride', 'Evelyn McBride'],
    grantees: ['Harlan D. McBride'],
    recordingDate: '1988-06-14',
    instrumentDate: '1988-06-01',
    legalDescription: 'NE/4 Section 14-23N-7W (160 acres)',
    confidence: 0.98,
    status: 'Reviewed',
    notes: 'Conveys undivided 1/4 mineral interest.',
    section: '14',
    township: '23N',
    range: '7W',
    interestConveyed: '1/4 Mineral'
  },
  {
    id: 'E002',
    targetId: 'T001',
    type: 'Oil & Gas Lease',
    fileName: 'Garfield_OGL_Bk889_Pg201.pdf',
    uploadedAt: '2026-03-18',
    county: 'Garfield',
    book: '889',
    page: '201',
    instrumentNumber: '2014-011234',
    grantors: ['Harlan D. McBride'],
    grantees: ['Continental Resources Inc.'],
    recordingDate: '2014-03-10',
    instrumentDate: '2014-02-15',
    legalDescription: 'NE/4 Section 14-23N-7W',
    confidence: 0.94,
    status: 'Reviewed',
    notes: '3-year primary term, 3/16 royalty. Currently HBP by McBride 1-14H.',
    section: '14',
    township: '23N',
    range: '7W',
    interestConveyed: '3/16 Royalty'
  }
]

export const SAMPLE_AUDIT: AuditEntry[] = [
  {
    id: 'A001',
    timestamp: '2026-08-30T02:50:00Z',
    action: 'Gate 0 Sentinel Verified',
    targetId: 'SEED-HORIZON-32',
    targetName: 'Horizon 32 (SYNTHETIC)',
    user: 'challenger-cursor',
    category: 'System',
    details: 'Hold verified fail-closed; non-executable provenance preserved. Output matched 1376 bytes digest.'
  },
  {
    id: 'A002',
    timestamp: '2026-08-30T02:40:00Z',
    action: 'Red-Team RT-20 Hold Test',
    targetId: 'SEED-HORIZON-32',
    targetName: 'Horizon 32 (SYNTHETIC)',
    user: 'automated-worker',
    category: 'System',
    details: 'Automated attempt to clear HOLD-SEED-32-001 rejected. Fail-closed hold preserved.'
  },
  {
    id: 'A003',
    timestamp: '2026-08-30T02:30:00Z',
    action: 'Conflict Traps Verified',
    targetId: 'SEED-32-T1',
    targetName: 'Contradictory Conveyance CF-1',
    user: 'challenger-cursor',
    category: 'Score',
    details: 'RT-22 passed: dual claims preserved with 100% provenance and 0% forced balance.'
  }
]
