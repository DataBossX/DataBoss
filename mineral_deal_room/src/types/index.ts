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
