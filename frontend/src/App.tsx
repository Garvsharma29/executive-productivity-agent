import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import { Header } from './components/Header';
import { SummaryCards } from './components/SummaryCards';
import { NeedsAttention } from './components/NeedsAttention';
import { MyActions } from './components/MyActions';
import { WaitingOnOthers } from './components/WaitingOnOthers';
import { CompletedSection } from './components/CompletedSection';
import { ScheduledToday } from './components/ScheduledToday';
import { AgentPanel } from './components/AgentPanel';
import { ShieldCheckIcon } from './components/Icons';
import type { DailyBriefResponse, AgentQueryResponse } from './api/types';
import { fetchDailyBrief, queryAgent } from './api/client';

export const App: React.FC = () => {
  const [asOfDate, setAsOfDate] = useState<string>('2026-09-23');
  const [brief, setBrief] = useState<DailyBriefResponse | null>(null);
  const [briefLoading, setBriefLoading] = useState<boolean>(true);
  const [briefError, setBriefError] = useState<string | null>(null);

  const [agentLoading, setAgentLoading] = useState<boolean>(false);
  const [agentResponse, setAgentResponse] = useState<AgentQueryResponse | null>(null);
  const [agentError, setAgentError] = useState<string | null>(null);

  // Load Daily Brief whenever asOfDate changes
  const loadBrief = useCallback(async (date: string) => {
    setBriefLoading(true);
    setBriefError(null);
    try {
      const data = await fetchDailyBrief(date);
      setBrief(data);
    } catch (err: unknown) {
      console.error('Failed to load daily brief:', err);
      setBriefError(
        err instanceof Error
          ? err.message
          : 'Could not connect to backend. Please ensure the backend server is running on port 8000.'
      );
    } finally {
      setBriefLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBrief(asOfDate);
  }, [asOfDate, loadBrief]);

  // Handle Natural Language Agent Query
  const handleQuery = async (query: string) => {
    setAgentLoading(true);
    setAgentError(null);
    try {
      const result = await queryAgent(query, asOfDate);
      setAgentResponse(result);
    } catch (err: unknown) {
      console.error('Agent query failed:', err);
      setAgentError(
        err instanceof Error
          ? err.message
          : 'Query execution failed. Please verify the backend connection.'
      );
    } finally {
      setAgentLoading(false);
    }
  };

  const scrollToSection = (sectionId: string) => {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="app-container">
      {/* 1. Header & Assessment Timeline Switcher */}
      <Header
        asOfDate={asOfDate}
        onDateChange={setAsOfDate}
        isLoading={briefLoading}
      />

      {/* 2. Executive Metric Summary Cards */}
      <SummaryCards brief={brief} onCardClick={scrollToSection} />

      {/* Backend Error Banner if any */}
      {briefError && (
        <div className="agent-error-banner">
          <strong>Backend Connection Error:</strong> {briefError}
        </div>
      )}

      {/* 3. Main Two-Column Dashboard Layout */}
      <main className="dashboard-grid">
        {/* Left Column: Action Commitments */}
        <div className="main-column">
          {/* Needs Attention Section (Overdue, Due Today, Unclear Ownership) */}
          <NeedsAttention commitments={brief?.needs_attention || []} />

          {/* My Actions (Arjun Malhotra Accountable) */}
          <MyActions commitments={brief?.my_actions || []} />

          {/* Waiting On Others (Colleagues Accountable) */}
          <WaitingOnOthers commitments={brief?.waiting_on_others || []} />

          {/* Completed Deliverables */}
          <CompletedSection commitments={brief?.completed || []} />
        </div>

        {/* Right Column: Natural Language Agent & Calendar Context */}
        <aside className="side-column">
          {/* Natural Language Agent Panel with Quick Chips & Grounded Evidence */}
          <AgentPanel
            onQuery={handleQuery}
            isLoading={agentLoading}
            response={agentResponse}
            error={agentError}
          />

          {/* Scheduled Today with Explicit Disclaimer */}
          <ScheduledToday
            events={brief?.scheduled_today || []}
            asOfDate={asOfDate}
          />
        </aside>
      </main>

      {/* 4. Footer & Grounding Proof */}
      <footer className="footer-container">
        <div className="footer-brand">
          <ShieldCheckIcon size={14} />
          <span>
            Executive Productivity Agent • AIONOS Assessment Data Pack Benchmark
          </span>
        </div>
        <div>
          <span>
            Temporal Reference: <strong>{asOfDate}</strong> • Strict Evidence Grounding Enabled
          </span>
        </div>
      </footer>
    </div>
  );
};

export default App;
