import React from 'react';
import type { BriefCommitmentItem } from '../api/types';
import { CommitmentCard } from './CommitmentCard';
import { CheckIcon } from './Icons';

interface MyActionsProps {
  commitments: BriefCommitmentItem[];
}

export const MyActions: React.FC<MyActionsProps> = ({ commitments }) => {
  return (
    <section className="dashboard-section" id="my-actions">
      <div className="section-header-row">
        <div className="section-title-lockup">
          <span className="section-icon-badge section-icon-indigo">
            <CheckIcon size={16} />
          </span>
          <div>
            <h2 className="section-title">MY ACTIONS</h2>
            <p className="section-subtitle">
              Active commitments where Arjun Malhotra is the directly accountable owner
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
            <CheckIcon size={24} />
            <p>No active commitments pending for Arjun as of this date.</p>
          </div>
        )}
      </div>
    </section>
  );
};
