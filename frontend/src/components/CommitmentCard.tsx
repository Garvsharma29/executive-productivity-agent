import React, { useState } from 'react';
import type { BriefCommitmentItem, EvidenceItem } from '../api/types';
import { 
  ChevronDownIcon, 
  ChevronUpIcon, 
  MailIcon, 
  MicIcon, 
  UsersIcon, 
  CalendarIcon, 
  AlertTriangleIcon,
  ShieldCheckIcon,
  CheckIcon,
  ClockIcon
} from './Icons';

interface CommitmentCardProps {
  commitment: BriefCommitmentItem;
  highlightAttention?: boolean;
}

export const CommitmentCard: React.FC<CommitmentCardProps> = ({ 
  commitment,
  highlightAttention = false 
}) => {
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  // Source icon helper
  const getSourceIcon = (sourceType: string) => {
    switch (sourceType?.toUpperCase()) {
      case 'EMAIL':
        return <MailIcon size={14} />;
      case 'VOICE_NOTE':
        return <MicIcon size={14} />;
      case 'MEETING':
      case 'TRANSCRIPT':
        return <UsersIcon size={14} />;
      case 'CALENDAR':
        return <CalendarIcon size={14} />;
      default:
        return <ShieldCheckIcon size={14} />;
    }
  };

  // Status badge styling
  const isCompleted = commitment.status?.toUpperCase() === 'COMPLETED';
  const isOverdue = commitment.is_overdue;
  const isUnclear = commitment.ownership_type === 'UNCLEAR';

  const renderDueBadge = () => {
    if (isCompleted) {
      return (
        <span className="badge badge-completed">
          <CheckIcon size={12} /> Completed
        </span>
      );
    }
    if (isOverdue) {
      return (
        <span className="badge badge-overdue">
          <AlertTriangleIcon size={12} /> Overdue
        </span>
      );
    }
    if (commitment.deadline_date) {
      return (
        <span className="badge badge-normal">
          <ClockIcon size={12} /> Due {new Date(commitment.deadline_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
        </span>
      );
    }
    if (commitment.deadline_raw) {
      return (
        <span className="badge badge-subtle">
          <ClockIcon size={12} /> {commitment.deadline_raw}
        </span>
      );
    }
    return <span className="badge badge-subtle">No deadline</span>;
  };

  return (
    <div 
      className={`commitment-card ${isOverdue ? 'is-overdue' : ''} ${isUnclear ? 'is-unclear' : ''} ${isCompleted ? 'is-completed' : ''} ${highlightAttention ? 'highlight-border' : ''}`}
    >
      <div className="card-top-meta">
        <div className="status-badges">
          {renderDueBadge()}
          {isUnclear ? (
            <span className="badge badge-unclear">
              <AlertTriangleIcon size={12} /> Ownership Unclear
            </span>
          ) : (
            <span className="badge badge-owner">
              Owner: {commitment.owner_name || 'Unassigned'}
            </span>
          )}
        </div>

        <div className="counterpart-info">
          {commitment.counterpart_name && (
            <span className="counterpart-badge">
              To: {commitment.counterpart_name}
            </span>
          )}
        </div>
      </div>

      <h3 className="commitment-title">{commitment.action}</h3>
      {commitment.topic && (
        <p className="commitment-desc">{commitment.topic}</p>
      )}

      {/* Explicit callout for unclear ownership */}
      {isUnclear && (
        <div className="unclear-notice">
          <AlertTriangleIcon size={16} />
          <div className="unclear-text">
            <strong>Ownership Ambiguity:</strong> Ownership was unassigned in the leadership sync transcript (Facilities vs VP Sales). Not attributed to Arjun without explicit confirmation.
          </div>
        </div>
      )}

      {/* Card footer with deadline and evidence toggle */}
      <div className="card-footer">
        <div className="meta-dates">
          {commitment.deadline_date ? (
            <span className="meta-date-item">
              <strong>Deadline:</strong> {new Date(commitment.deadline_date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
            </span>
          ) : commitment.deadline_raw ? (
            <span className="meta-date-item">
              <strong>Deadline:</strong> {commitment.deadline_raw}
            </span>
          ) : null}
        </div>

        {commitment.evidence && commitment.evidence.length > 0 && (
          <button
            type="button"
            className="evidence-toggle-btn"
            onClick={() => setEvidenceOpen(!evidenceOpen)}
            aria-expanded={evidenceOpen}
          >
            <ShieldCheckIcon size={14} />
            <span>Evidence Sources ({commitment.evidence.length})</span>
            {evidenceOpen ? <ChevronUpIcon size={14} /> : <ChevronDownIcon size={14} />}
          </button>
        )}
      </div>

      {/* Expandable Evidence Drawer */}
      {evidenceOpen && commitment.evidence && commitment.evidence.length > 0 && (
        <div className="evidence-drawer">
          <div className="evidence-drawer-header">
            <span>GROUNDED CITATIONS & PROVENANCE</span>
          </div>
          <div className="evidence-list">
            {commitment.evidence.map((ev: EvidenceItem, idx: number) => (
              <div key={`${ev.source_id}-${idx}`} className="evidence-item">
                <div className="evidence-item-header">
                  <span className="source-type-tag">
                    {getSourceIcon(ev.source_type)}
                    {ev.source_type}
                  </span>
                  <span className="source-title">{ev.source_reference || ev.source_id}</span>
                  {ev.occurred_at && (
                    <span className="source-time">
                      {new Date(ev.occurred_at).toLocaleString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  )}
                </div>
                {ev.evidence_text && (
                  <blockquote className="evidence-quote">
                    "{ev.evidence_text}"
                  </blockquote>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
