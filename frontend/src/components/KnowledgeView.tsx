import { useEffect, useState } from 'react'
import { FileText, FolderPlus, RefreshCw, Search, Trash2 } from 'lucide-react'
import { api } from '../api'

export function KnowledgeView() {
  const [folders, setFolders] = useState<string[]>([])
  const [files, setFiles] = useState<{ path: string; size: number; chunk_count: number; indexed_at: string }[]>([])
  const [newFolder, setNewFolder] = useState('')
  const [query, setQuery] = useState('')
  const [matches, setMatches] = useState<{ file_name: string; file_path: string; chunk_index: number; snippet: string }[]>([])
  const [busy, setBusy] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')

  const load = async () => {
    const res = await api.getKbFiles()
    setFolders(res.folders)
    setFiles(res.files)
  }

  useEffect(() => {
    load().catch(() => {})
  }, [])

  const addFolder = async () => {
    if (!newFolder.trim()) return
    setBusy(true)
    setStatusMsg('')
    try {
      const res = await api.addKbFolder(newFolder.trim())
      setNewFolder('')
      setStatusMsg(`Indexed ${res.index_result.indexed_files ?? 0} file(s).`)
      await load()
    } finally {
      setBusy(false)
    }
  }

  const removeFolder = async (folder: string) => {
    setBusy(true)
    try {
      await api.removeKbFolder(folder)
      await load()
    } finally {
      setBusy(false)
    }
  }

  const reindex = async () => {
    setBusy(true)
    try {
      const res = await api.reindexKb()
      setStatusMsg(`Re-index complete: ${res.indexed_files ?? 0} updated, ${res.total_files ?? 0} total indexed.`)
      await load()
    } finally {
      setBusy(false)
    }
  }

  const runSearch = async () => {
    if (!query.trim()) return
    const res = await api.searchKb(query.trim())
    setMatches(res.matches)
  }

  return (
    <div className="page-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <strong>Personal Files & Document Q&A</strong>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Add local Windows folders (.txt, .md, .pdf, .docx, .csv, .json, code) so Lael can answer questions with citations.
            </div>
          </div>
          <button className="btn" onClick={reindex} disabled={busy}>
            <RefreshCw size={15} /> {busy ? 'Indexing...' : 'Re-index All'}
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="input"
            placeholder="e.g. C:\Users\mulis\Documents"
            value={newFolder}
            onChange={(e) => setNewFolder(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addFolder()}
          />
          <button className="btn btn-primary" onClick={addFolder} disabled={busy}>
            <FolderPlus size={16} /> Add Folder
          </button>
        </div>

        {statusMsg && <div style={{ fontSize: '0.84rem', color: 'var(--secondary)' }}>{statusMsg}</div>}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {folders.map((f) => (
            <div key={f} className="tag" style={{ padding: '5px 10px', gap: 8 }}>
              <span>{f}</span>
              <Trash2 size={13} style={{ cursor: 'pointer' }} onClick={() => removeFolder(f)} />
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <strong>Instant Knowledge Search</strong>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="input"
            placeholder="Test searching your indexed files..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runSearch()}
          />
          <button className="btn btn-primary" onClick={runSearch}>
            <Search size={16} /> Search
          </button>
        </div>
        {matches.map((m, i) => (
          <div key={i} style={{ padding: 10, borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(0,0,0,0.18)' }}>
            <div style={{ fontWeight: 600, fontSize: '0.88rem', marginBottom: 4 }}>
              {m.file_name} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>({m.file_path})</span>
            </div>
            <div style={{ fontSize: '0.83rem', color: 'var(--text-muted)', whiteSpace: 'pre-wrap' }}>{m.snippet}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <strong style={{ display: 'block', marginBottom: 10 }}>Indexed Files ({files.length})</strong>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 320, overflowY: 'auto' }}>
          {files.map((f) => (
            <div key={f.path} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.84rem' }}>
              <FileText size={14} color="var(--secondary)" />
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.path}</span>
              <span className="tag">{f.chunk_count} chunks</span>
            </div>
          ))}
          {files.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: '0.86rem' }}>No files indexed yet.</div>}
        </div>
      </div>
    </div>
  )
}
