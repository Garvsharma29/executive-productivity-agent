import React from 'react';
import { CalendarIcon, ShieldCheckIcon } from './Icons';

interface HeaderProps {
  asOfDate: string;
  onDateChange: (date: string) => void;
  isLoading?: boolean;
}

const ASSESSMENT_DATES = [
  { date: '2026-09-21', label: 'Mon, Sep 21' },
  { date: '2026-09-22', label: 'Tue, Sep 22' },
  { date: '2026-09-23', label: 'Wed, Sep 23', default: true },
  { date: '2026-09-24', label: 'Thu, Sep 24' },
  { date: '2026-09-25', label: 'Fri, Sep 25' },
];

export const Header: React.FC<HeaderProps> = ({ asOfDate, onDateChange, isLoading }) => {
  return (
    <header className="header-container">
      <div className="header-top">
        <div className="brand-lockup">
          <div className="brand-badge-row">
            <span className="brand-tag">
              <ShieldCheckIcon size={14} /> GROUNDED INTELLIGENCE
            </span>
            <span className="executive-tag">Arjun Malhotra • VP Sales</span>
          </div>
          <h1 className="brand-title">EXECUTIVE INTELLIGENCE</h1>
          <p className="brand-subtitle">
            Grounded executive productivity assistant • Temporal reasoning as of {asOfDate}
          </p>
        </div>

        <div className="date-selector-wrapper">
          <div className="date-selector-header">
            <CalendarIcon size={14} />
            <span>ASSESSMENT TIMELINE</span>
            {isLoading && <span className="updating-pulse">Syncing...</span>}
          </div>
          <div className="date-pills" role="tablist" aria-label="Select Date">
            {ASSESSMENT_DATES.map((item) => {
              const isActive = asOfDate === item.date;
              return (
                <button
                  key={item.date}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  className={`date-pill ${isActive ? 'active' : ''}`}
                  onClick={() => onDateChange(item.date)}
                >
                  <span className="pill-date">{item.label}</span>
                  {item.default && <span className="pill-tag">DATA PACK</span>}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </header>
  );
};
