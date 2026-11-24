import { useEffect, useState } from 'react'
import { Bell, CheckCircle2, Circle, Pin, Plus, StickyNote, Trash2 } from 'lucide-react'
import { api } from '../api'
import type { NoteItem, ReminderItem, TaskItem } from '../types'

export function ProductivityView() {
  const [tab, setTab] = useState<'tasks' | 'notes' | 'reminders'>('tasks')
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [notes, setNotes] = useState<NoteItem[]>([])
  const [reminders, setReminders] = useState<ReminderItem[]>([])

  const [taskTitle, setTaskTitle] = useState('')
  const [taskPriority, setTaskPriority] = useState<'low' | 'medium' | 'high'>('medium')
  const [taskDue, setTaskDue] = useState('')

  const [noteTitle, setNoteTitle] = useState('')
  const [noteContent, setNoteContent] = useState('')
  const [noteQuery, setNoteQuery] = useState('')

  const [remTitle, setRemTitle] = useState('')
  const [remAt, setRemAt] = useState('')
  const [remRepeat, setRemRepeat] = useState<'none' | 'daily' | 'weekly'>('none')

  const loadAll = async () => {
    const [t, n, r] = await Promise.all([api.listTasks('all'), api.listNotes(noteQuery), api.listReminders()])
    setTasks(t)
    setNotes(n)
    setReminders(r)
  }

  useEffect(() => {
    loadAll().catch(() => {})
  }, [])

  const addTask = async () => {
    if (!taskTitle.trim()) return
    await api.createTask({ title: taskTitle.trim(), priority: taskPriority, due_date: taskDue })
    setTaskTitle('')
    setTaskDue('')
    setTasks(await api.listTasks('all'))
  }

  const toggleTask = async (t: TaskItem) => {
    await api.updateTask(t.id, { status: t.status === 'done' ? 'open' : 'done' })
    setTasks(await api.listTasks('all'))
  }

  const removeTask = async (id: string) => {
    await api.deleteTask(id)
    setTasks(await api.listTasks('all'))
  }

  const addNote = async () => {
    if (!noteTitle.trim() && !noteContent.trim()) return
    await api.createNote({ title: noteTitle.trim() || 'Quick Note', content: noteContent.trim() })
    setNoteTitle('')
    setNoteContent('')
    setNotes(await api.listNotes(noteQuery))
  }

  const togglePin = async (n: NoteItem) => {
    await api.updateNote(n.id, { pinned: !n.pinned })
    setNotes(await api.listNotes(noteQuery))
  }

  const removeNote = async (id: string) => {
    await api.deleteNote(id)
    setNotes(await api.listNotes(noteQuery))
  }

  const addReminder = async () => {
    if (!remTitle.trim() || !remAt) return
    await api.createReminder({ title: remTitle.trim(), remind_at: remAt, repeat: remRepeat })
    setRemTitle('')
    setReminders(await api.listReminders())
  }

  const removeReminder = async (id: string) => {
    await api.deleteReminder(id)
    setReminders(await api.listReminders())
  }

  return (
    <div className="page-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className={`btn ${tab === 'tasks' ? 'btn-primary' : ''}`} onClick={() => setTab('tasks')}>
          Tasks ({tasks.filter((t) => t.status === 'open').length})
        </button>
        <button className={`btn ${tab === 'notes' ? 'btn-primary' : ''}`} onClick={() => setTab('notes')}>
          Notes ({notes.length})
        </button>
        <button className={`btn ${tab === 'reminders' ? 'btn-primary' : ''}`} onClick={() => setTab('reminders')}>
          Reminders ({reminders.filter((r) => !r.triggered).length})
        </button>
      </div>

      {tab === 'tasks' && (
        <>
          <div className="card" style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <input
              className="input"
              style={{ flex: 2, minWidth: 200 }}
              placeholder="Add a new task..."
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addTask()}
            />
            <select
              className="select"
              style={{ width: 130 }}
              value={taskPriority}
              onChange={(e) => setTaskPriority(e.target.value as 'low' | 'medium' | 'high')}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
            <input
              className="input"
              type="date"
              style={{ width: 160 }}
              value={taskDue}
              onChange={(e) => setTaskDue(e.target.value)}
            />
            <button className="btn btn-primary" onClick={addTask}>
              <Plus size={16} /> Add Task
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {tasks.length === 0 && (
              <div className="card" style={{ color: 'var(--text-muted)' }}>
                No tasks yet. Add one above or ask Lael in chat to create tasks for you.
              </div>
            )}
            {tasks.map((t) => (
              <div
                key={t.id}
                className="card"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  opacity: t.status === 'done' ? 0.62 : 1,
                }}
              >
                <button className="btn btn-icon" onClick={() => toggleTask(t)}>
                  {t.status === 'done' ? <CheckCircle2 size={18} color="var(--success)" /> : <Circle size={18} />}
                </button>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, textDecoration: t.status === 'done' ? 'line-through' : 'none' }}>
                    {t.title}
                  </div>
                  {t.notes && <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>{t.notes}</div>}
                </div>
                <span
                  className="tag"
                  style={{
                    background:
                      t.priority === 'high'
                        ? 'rgba(244,63,94,0.22)'
                        : t.priority === 'low'
                          ? 'rgba(16,185,129,0.2)'
                          : undefined,
                  }}
                >
                  {t.priority}
                </span>
                {t.due_date && <span className="tag">{t.due_date}</span>}
                <button className="btn btn-icon" onClick={() => removeTask(t.id)}>
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'notes' && (
        <>
          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', gap: 10 }}>
              <input
                className="input"
                placeholder="Note title..."
                value={noteTitle}
                onChange={(e) => setNoteTitle(e.target.value)}
              />
              <input
                className="input"
                placeholder="Search notes..."
                value={noteQuery}
                onChange={async (e) => {
                  setNoteQuery(e.target.value)
                  setNotes(await api.listNotes(e.target.value))
                }}
              />
            </div>
            <textarea
              className="textarea"
              rows={3}
              placeholder="Write your note..."
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
            />
            <div>
              <button className="btn btn-primary" onClick={addNote}>
                <StickyNote size={16} /> Save Note
              </button>
            </div>
          </div>

          <div className="grid-2">
            {notes.map((n) => (
              <div key={n.id} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <strong>{n.title}</strong>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button className="btn btn-icon" onClick={() => togglePin(n)} title="Pin note">
                      <Pin size={14} color={n.pinned ? 'var(--secondary)' : undefined} />
                    </button>
                    <button className="btn btn-icon" onClick={() => removeNote(n.id)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                  {n.content}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'reminders' && (
        <>
          <div className="card" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              className="input"
              style={{ flex: 2, minWidth: 200 }}
              placeholder="Remind me to..."
              value={remTitle}
              onChange={(e) => setRemTitle(e.target.value)}
            />
            <input
              className="input"
              type="datetime-local"
              style={{ width: 220 }}
              value={remAt}
              onChange={(e) => setRemAt(e.target.value)}
            />
            <select
              className="select"
              style={{ width: 120 }}
              value={remRepeat}
              onChange={(e) => setRemRepeat(e.target.value as 'none' | 'daily' | 'weekly')}
            >
              <option value="none">Once</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
            </select>
            <button className="btn btn-primary" onClick={addReminder}>
              <Bell size={16} /> Schedule
            </button>
            <button className="btn" onClick={() => api.testNotification()}>
              Test Windows Toast
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {reminders.map((r) => (
              <div
                key={r.id}
                className="card"
                style={{ display: 'flex', alignItems: 'center', gap: 12, opacity: r.triggered ? 0.55 : 1 }}
              >
                <Bell size={18} color={r.triggered ? 'var(--text-muted)' : 'var(--secondary)'} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600 }}>{r.title}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {r.remind_at} · repeat: {r.repeat} {r.triggered ? '· triggered' : ''}
                  </div>
                </div>
                <button className="btn btn-icon" onClick={() => removeReminder(r.id)}>
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
