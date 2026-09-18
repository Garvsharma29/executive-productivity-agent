import React from 'react';
import type { BriefCommitmentItem } from '../api/types';
import { CommitmentCard } from './CommitmentCard';
import { AlertTriangleIcon } from './Icons';

interface NeedsAttentionProps {
  commitments: BriefCommitmentItem[];
}

export const NeedsAttention: React.FC<NeedsAttentionProps> = ({ commitments }) => {
  if (!commitments || commitments.length === 0) {
    return null;
  }

  return (
    <section className="dashboard-section section-attention" id="needs-attention">
      <div className="section-header-banner">
        <div className="section-title-lockup">
          <span className="section-alert-icon">
            <AlertTriangleIcon size={18} />
          </span>
          <div>
            <h2 className="section-title">NEEDS ATTENTION</h2>
            <p className="section-subtitle">
              Overdue deliverables, immediate deadlines, and ambiguous ownership requiring executive decision
            </p>
          </div>
        </div>
        <span className="attention-counter-badge">{commitments.length} ITEMS</span>
      </div>

      <div className="commitments-stack">
        {commitments.map((item) => (
          <CommitmentCard 
            key={item.id} 
            commitment={item} 
            highlightAttention={true} 
          />
        ))}
      </div>
    </section>
  );
};
