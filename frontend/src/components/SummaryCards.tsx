import React from 'react';
import type { DailyBriefResponse } from '../api/types';
import { 
  CheckIcon, 
  AlertTriangleIcon, 
  ClockIcon, 
  CalendarIcon 
} from './Icons';

interface SummaryCardsProps {
  brief: DailyBriefResponse | null;
  onCardClick?: (section: string) => void;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({ brief, onCardClick }) => {
  if (!brief) {
    return (
      <div className="summary-cards-grid">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="summary-card skeleton">
            <div className="skeleton-title" />
            <div className="skeleton-number" />
          </div>
        ))}
      </div>
    );
  }

  const counts = brief.summary_counts || {
    my_actions: brief.my_actions?.length || 0,
    waiting_on_others: brief.waiting_on_others?.length || 0,
    needs_attention: brief.needs_attention?.length || 0,
    completed: brief.completed?.length || 0,
    scheduled_today: brief.scheduled_today?.length || 0,
  };

  const cards = [
    {
      id: 'my-actions',
      title: 'My Actions',
      count: counts.my_actions,
      desc: 'Open commitments owned by Arjun',
      icon: <CheckIcon size={20} />,
      colorClass: 'card-accent-indigo',
    },
    {
      id: 'waiting-on-others',
      title: 'Waiting on Others',
      count: counts.waiting_on_others,
      desc: 'Pending counterpart deliverables',
      icon: <ClockIcon size={20} />,
      colorClass: 'card-accent-amber',
    },
    {
      id: 'needs-attention',
      title: 'Needs Attention',
      count: counts.needs_attention,
      desc: 'Overdue, imminent, or unclear',
      icon: <AlertTriangleIcon size={20} />,
      colorClass: 'card-accent-rose',
    },
    {
      id: 'completed',
      title: 'Completed',
      count: counts.completed,
      desc: 'Fulfilled deliverables',
      icon: <CheckIcon size={20} />,
      colorClass: 'card-accent-emerald',
    },
    {
      id: 'scheduled-today',
      title: 'Scheduled Today',
      count: counts.scheduled_today,
      desc: 'Calendar context (not obligations)',
      icon: <CalendarIcon size={20} />,
      colorClass: 'card-accent-slate',
    },
  ];

  return (
    <div className="summary-cards-grid">
      {cards.map((card) => (
        <div
          key={card.id}
          className={`summary-card ${card.colorClass}`}
          onClick={() => onCardClick && onCardClick(card.id)}
        >
          <div className="card-header-row">
            <span className="card-title">{card.title}</span>
            <span className="card-icon">{card.icon}</span>
          </div>
          <div className="card-count">{card.count}</div>
          <div className="card-desc">{card.desc}</div>
        </div>
      ))}
    </div>
  );
};
