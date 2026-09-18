export type OwnershipType = 'ARJUN' | 'OTHER_PERSON' | 'UNCLEAR'
export type CommitmentStatus = 'OPEN' | 'COMPLETED'
export type DeadlinePrecision = 'EXACT' | 'APPROXIMATE' | 'RELATIVE_UNRESOLVED' | 'NONE'

export interface EvidenceItem {
  source_id: string
  source_type: string
  source_reference: string
  occurred_at: string | null
  evidence_text: string
  extraction_method?: string | null
  confidence?: number | null
}

export interface BriefCommitmentItem {
  id: string
  action: string
  raw_action: string
  topic?: string | null
  ownership_type: OwnershipType
  owner_name?: string | null
  counterpart_name?: string | null
  deadline_raw?: string | null
  deadline_date?: string | null
  deadline_precision: DeadlinePrecision
  status: CommitmentStatus
  is_overdue: boolean
  evidence_count: number
  evidence: EvidenceItem[]
}

export interface CalendarEventItem {
  id: string
  title: string
  start_time: string
  end_time?: string | null
  description?: string | null
  attendees?: string[] | null
}

export interface DailyBriefResponse {
  as_of_date: string
  generated_at: string
  executive_name: string
  executive_role: string
  summary_counts: {
    my_actions: number
    waiting_on_others: number
    needs_attention: number
    completed: number
    scheduled_today: number
  }
  my_actions: BriefCommitmentItem[]
  waiting_on_others: BriefCommitmentItem[]
  needs_attention: BriefCommitmentItem[]
  completed: BriefCommitmentItem[]
  scheduled_today: CalendarEventItem[]
}

export interface AgentQueryRequest {
  query: string
  as_of_date?: string | null
}

export interface AgentQueryResponse {
  query: string
  as_of_date: string
  intent: string
  answer: string
  commitments: BriefCommitmentItem[]
  evidence: EvidenceItem[]
}
