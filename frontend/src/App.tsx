import './App.css'

function App() {
  return (
    <div className="app">
      <header className="header">
        <div className="logo-mark">EPA</div>
        <h1>Executive Productivity Agent</h1>
        <p className="tagline">
          Messy inputs → structured daily action brief
        </p>
      </header>

      <main className="status-card">
        <h2>Project Status</h2>
        <div className="status-grid">
          <StatusItem label="Backend API" status="ready" detail="FastAPI + health endpoint" />
          <StatusItem label="Frontend" status="ready" detail="React + TypeScript + Vite" />
          <StatusItem label="Database" status="ready" detail="PostgreSQL via Docker" />
          <StatusItem label="Ingestion Pipeline" status="pending" detail="Not started" />
          <StatusItem label="Commitment Extraction" status="pending" detail="Not started" />
          <StatusItem label="Daily Brief" status="pending" detail="Not started" />
        </div>
      </main>

      <footer className="footer">
        <p>Scaffold v0.1.0 &middot; No features are implemented yet</p>
      </footer>
    </div>
  )
}

function StatusItem({ label, status, detail }: { label: string; status: 'ready' | 'pending'; detail: string }) {
  return (
    <div className={`status-item ${status}`}>
      <span className="indicator">{status === 'ready' ? '✓' : '○'}</span>
      <div>
        <strong>{label}</strong>
        <small>{detail}</small>
      </div>
    </div>
  )
}

export default App
