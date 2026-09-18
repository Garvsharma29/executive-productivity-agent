import React, { useState } from 'react';
import type { BriefCommitmentItem } from '../api/types';
import { CommitmentCard } from './CommitmentCard';
import { CheckIcon, ChevronDownIcon, ChevronUpIcon } from './Icons';

interface CompletedSectionProps {
  commitments: BriefCommitmentItem[];
}

export const CompletedSection: React.FC<CompletedSectionProps> = ({ commitments }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!commitments || commitments.length === 0) {
    return null;
  }

  return (
    <section className="dashboard-section section-completed" id="completed">
      <div 
        className="section-header-row clickable-header" 
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="section-title-lockup">
          <span className="section-icon-badge section-icon-emerald">
            <CheckIcon size={16} />
          </span>
          <div>
            <h2 className="section-title">COMPLETED DELIVERABLES</h2>
            <p className="section-subtitle">
              Verified fulfilled commitments with archival evidence trail
            </p>
          </div>
        </div>
        <div className="section-right-controls">
          <span className="section-count-pill pill-emerald">{commitments.length}</span>
          <button 
            type="button" 
            className="collapse-btn" 
            aria-label="Toggle completed section"
          >
            {isExpanded ? <ChevronUpIcon size={18} /> : <ChevronDownIcon size={18} />}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="commitments-stack mt-3">
          {commitments.map((item) => (
            <CommitmentCard key={item.id} commitment={item} />
          ))}
        </div>
      )}
    </section>
  );
};
