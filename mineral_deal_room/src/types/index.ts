export type InterestType = 'Mineral' | 'Royalty' | 'Working Interest' | 'ORRI';
export type TargetStatus =
  | 'Identified'
  | 'Contacted'
  | 'Under Review'
  | 'Offer Sent'
  | 'Signed'
  | 'Passed'
  | 'On Hold';
export type TitleClearance = 'Clean' | 'Needs Curative' | 'Probate Pending' | 'Unknown';
export type EvidenceType =
  | 'Warranty Deed'
  | 'Oil & Gas Lease'
  | 'Probate'
  | 'Affidavit of Heirship'
  | 'Court Record'
  | 'Division Order'
  | 'Assignment'
  | 'Quit Claim Deed'
  | 'Mineral Deed'
  | 'Release';
export type EvidenceStatus = 'Pending Review' | 'Reviewed' | 'Flagged';
export type AuditCategory = 'Target' | 'Evidence' | 'Score' | 'Export' | 'System';

export interface Target {
  id: string;
  ownerName: string;
  county: string;
  section: string;
  township: string;
  range: string;
  interestType: InterestType;
  nma: number;
  dealScore: number;
  status: TargetStatus;
  titleClearance: TitleClearance;
  estimatedValue: number;
  assignedTo: string;
  lastContact: string;
  notes: string;
  curativesNeeded: string[];
  evidenceCount: number;
  createdAt: string;
  wellsProducing: number;
  royaltyRate: string;
  instrumentType?: string;
}

export interface ScoreComponent {
  name: string;
  score: number;
  maxScore: number;
  rationale: string;
}

export interface DealScore {
  targetId: string;
  components: ScoreComponent[];
  overallScore: number;
  recommendation: 'Strong Buy' | 'Buy' | 'Hold' | 'Pass';
  scoredAt: string;
  scoredBy: string;
  notes: string;
}

export interface Evidence {
  id: string;
  targetId: string;
  type: EvidenceType;
  fileName: string;
  uploadedAt: string;
  county: string;
  book: string;
  page: string;
  instrumentNumber: string;
  grantors: string[];
  grantees: string[];
  recordingDate: string;
  instrumentDate: string;
  legalDescription: string;
  confidence: number;
  status: EvidenceStatus;
  notes: string;
  section: string;
  township: string;
  range: string;
  interestConveyed: string;
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  action: string;
  targetId?: string;
  targetName?: string;
  user: string;
  details: string;
  category: AuditCategory;
}

export interface PipelineSummary {
  total: number;
  identified: number;
  contacted: number;
  underReview: number;
  offerSent: number;
  signed: number;
  passed: number;
  onHold: number;
  totalNMA: number;
  totalEstimatedValue: number;
  avgScore: number;
}

// -------------------------------------------------------------
// TOURNAMENT COMMAND CENTER DOMAIN TYPES (P-1 to P-21)
// -------------------------------------------------------------

export interface HoldRecord {
  holdId: string;
  kind: string;
  scope: string;
  clearableBy: 'AUTHENTICATED_HUMAN_ONLY' | 'AUTOMATION';
  clearableByAutomation: boolean;
  reason: string;
  setAt: string;
  setBy: string;
}

export interface DefectRecord {
  defectId: string;
  type: string;
  severity: 'RED' | 'YELLOW' | 'GREEN';
  summary: string;
  observed?: {
    candidateBytes?: number;
    templateBytes?: number;
    tolerancePct?: number;
  };
  expectedBehaviour: string;
  resolutionState: 'OPEN_REQUIRES_HUMAN' | 'RESOLVED_BY_EXAMINER';
}

export interface TractRecord {
  tractId: string;
  label: string;
  grossAcres: string;
  note: string;
}

export interface ProjectCommandRecord {
  projectId: string;
  displayName: string;
  standsInFor: string;
  jurisdiction: { state: string; county: string };
  legalDescription: {
    section: string;
    township: string;
    range: string;
    text: string;
  };
  lifecycleState: 'EXAMINER_REVIEW' | 'INTERNAL_REVIEW' | 'APPROVED';
  releaseState: 'FOR_REVIEW_HOLD_NO_EXTERNAL_RELEASE' | 'RELEASE_READY';
  holds: HoldRecord[];
  defects: DefectRecord[];
  tracts: TractRecord[];
}

export interface SimulatedJob {
  jobId: string;
  idempotencyKey: string;
  projectId: string;
  taskType: string;
  workerId: string;
  state: 'READY' | 'RUNNING' | 'COMPLETED' | 'QUARANTINED' | 'FAILED';
  priority: number;
  payloadSummary: string;
  simulated: true;
  createdAt: string;
  completedAt?: string;
  resultHash?: string;
}

export interface ApprovalRequest {
  approvalId: string;
  projectId: string;
  title: string;
  action: string;
  artifactHash: string;
  requestedBy: string;
  scope: string;
  state: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED';
  expiresAt: string;
  createdAt: string;
}

export interface MonthlyProduction {
  period: string;
  oilBbl: number;
  gasMcf: number;
  waterBbl: number;
  source: string;
  restated: boolean;
  restatementNote?: string;
}

export interface WellRecord {
  wellId: string;
  api: string;
  name: string;
  operatorName: string;
  surfaceLocation: string;
  wellboreType: string;
  status: 'PRODUCING' | 'SHUT_IN' | 'PERMITTED_NOT_SPUD';
  spudDate?: string;
  completionDate?: string;
  formation: string;
  linkedTracts: string[];
  linkConfidence: 'HIGH' | 'AMBIGUOUS';
  ambiguityNote?: string;
  monthlyProduction?: MonthlyProduction[];
}

export interface ConflictClaim {
  claimId: string;
  party: string;
  interestType: string;
  fraction: string;
  source: string;
  confidence: string;
}

export interface ConflictRecord {
  id: string;
  exercises: string;
  type: string;
  tractId: string;
  title: string;
  description: string;
  requiredBehavior: string;
  claims?: ConflictClaim[];
  status: 'OPEN_CONFLICT' | 'RECONCILED_SUPERSEDED' | 'FLAGGED_AMBIGUOUS' | 'QUARANTINED_RESTRICTED' | 'REJECTED_FABRICATION';
}

export interface VerificationReceipt {
  receiptId: string;
  projectId: string;
  timestamp: string;
  actor: string;
  target: string;
  inputHash: string;
  outputHash: string;
  status: 'VERIFIED_PASS' | 'DEFECT_QUARANTINED';
  details: string;
}
