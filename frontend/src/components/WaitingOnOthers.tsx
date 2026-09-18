import React from 'react';
import type { BriefCommitmentItem } from '../api/types';
import { CommitmentCard } from './CommitmentCard';
import { ClockIcon } from './Icons';

interface WaitingOnOthersProps {
  commitments: BriefCommitmentItem[];
}

export const WaitingOnOthers: React.FC<WaitingOnOthersProps> = ({ commitments }) => {
  return (
    <section className="dashboard-section" id="waiting-on-others">
      <div className="section-header-row">
        <div className="section-title-lockup">
          <span className="section-icon-badge section-icon-amber">
            <ClockIcon size={16} />
          </span>
          <div>
            <h2 className="section-title">WAITING ON OTHERS</h2>
            <p className="section-subtitle">
              Deliverables and action items committed by colleagues where Arjun is counterpart or stakeholder
            </p>
          </div>
        </div>
        <span className="section-count-pill">{commitments?.length || 0}</span>
      </div>

      <div className="commitments-stack">
        {commitments && commitments.length > 0 ? (
          commitments.map((item) => (
            <CommitmentCard key={item.id} commitment={item} />
          ))
        ) : (
          <div className="empty-state">
            <ClockIcon size={24} />
            <p>No external deliverables currently pending.</p>
          </div>
        )}
      </div>
    </section>
  );
};
