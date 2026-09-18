import React from 'react';
import type { CalendarEventItem } from '../api/types';
import { CalendarIcon, ClockIcon, UsersIcon } from './Icons';

interface ScheduledTodayProps {
  events: CalendarEventItem[];
  asOfDate: string;
}

export const ScheduledToday: React.FC<ScheduledTodayProps> = ({ events, asOfDate }) => {
  const formatTime = (isoString?: string | null) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch {
      return isoString;
    }
  };

  return (
    <section className="dashboard-section section-calendar" id="scheduled-today">
      <div className="section-header-row">
        <div className="section-title-lockup">
          <span className="section-icon-badge section-icon-slate">
            <CalendarIcon size={16} />
          </span>
          <div>
            <h2 className="section-title">SCHEDULED TODAY ({asOfDate})</h2>
            <p className="section-subtitle">
              Calendar schedule for temporal reference
            </p>
          </div>
        </div>
        <span className="section-count-pill">{events?.length || 0}</span>
      </div>

      {/* Critical Grounding Disclaimer */}
      <div className="calendar-context-banner">
        <span className="banner-tag">GROUNDING PRINCIPLE</span>
        <span className="banner-text">
          Calendar Context • <strong>Calendar event ≠ commitment</strong> (Meetings provide temporal context; commitments require explicit promise or deliverable).
        </span>
      </div>

      <div className="events-grid">
        {events && events.length > 0 ? (
          events.map((evt) => (
            <div key={evt.id} className="calendar-event-card">
              <div className="event-time-row">
                <span className="event-time">
                  <ClockIcon size={12} />
                  {formatTime(evt.start_time)}
                  {evt.end_time ? ` – ${formatTime(evt.end_time)}` : ''}
                </span>
              </div>
              <h4 className="event-title">{evt.title}</h4>
              {evt.description && (
                <div className="event-meta-location">
                  <span>{evt.description}</span>
                </div>
              )}
              {evt.attendees && evt.attendees.length > 0 && (
                <div className="event-attendees">
                  <UsersIcon size={12} />
                  <span>{evt.attendees.join(', ')}</span>
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="empty-state">
            <CalendarIcon size={24} />
            <p>No calendar events scheduled for this day.</p>
          </div>
        )}
      </div>
    </section>
  );
};
