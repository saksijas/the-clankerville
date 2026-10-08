/* The sample office shown only on request ("Show demo", or ui.json {demo:true}).
   Same shape as the back room's snapshot; desks follow office.py's pod layout. */

const look = (hair, shirt, skin) => ({ hair, shirt, skin })

const chat = (id, name, short, state, level, desk, lookValue, extra = {}) => ({
  id, kind: 'chat', chat_id: id, name, short, state, level, xp_progress: 0.4, queued: 0, desk, look: lookValue, dismissable: true, ...extra,
})

const helper = (id, lead, name, state, desk, lookValue, dismissable = true) => ({
  id, kind: 'helper', chat_id: lead, lead_id: lead, parent_id: null, name, short: name, state, desk, look: lookValue, dismissable,
})

export const DEMO_SNAPSHOT = {
  ok: true,
  generated_at: '2026-09-28T17:00:00+00:00',
  office: { level: 4, xp: 320, level_start_xp: 300, next_level_xp: 500 },
  counts: { working: 3, needs_you: 1, error: 1, watching: 0, on_break: 1 },
  room: { width: 13, depth: 9 },
  characters: [
    chat('demo-lead', 'Agent office brainstorm', 'Brainstorm', 'working', 3, { x: 1.9, y: 0.7 }, look('#3b2a20', '#6d5dfc', '#f2c9a0'), { step: 'Drawing office mockups' }),
    helper('demo-h1', 'demo-lead', 'pixel-sketcher', 'busy', { x: 0.6, y: 2.1 }, look('#d9a441', '#2fb3a3', '#e0ac7e')),
    helper('demo-h2', 'demo-lead', 'spec-reviewer', 'on_hold', { x: 3.2, y: 0.7 }, look('#1f1f28', '#f08a5d', '#8d5a3b')),
    // Finished: shows its green check, then walks out of the door (spec §5.4).
    helper('demo-h3', 'demo-lead', 'test-runner', 'done', { x: 3.2, y: 2.1 }, look('#2d2d2d', '#9bc53d', '#f2c9a0'), false),
    chat('demo-budget', 'Budget sheet', 'Budget sheet', 'working', 5, { x: 5.9, y: 0.7 }, look('#7a3e2b', '#4c9be8', '#f5d1b5'), { step: 'Running tests' }),
    chat('demo-tasks', 'Tasks app tweaks', 'Tasks app', 'needs_you', 2, { x: 9.9, y: 0.7 }, look('#2d2d2d', '#e85d75', '#c68a62')),
    chat('demo-trip', 'Trip planner', 'Trip planner', 'error', 2, { x: 1.9, y: 3.7 }, look('#b05a2c', '#7c8a9e', '#f0c8a8')),
    chat('demo-report', 'Weekly report', 'Weekly report', 'working', 1, { x: 5.9, y: 3.7 }, look('#1f1f28', '#9bc53d', '#e8b793'), { step: 'Editing report.md' }),
    chat('demo-new', 'New chat', 'New chat', 'on_break', 1, { x: 9.9, y: 3.7 }, look('#5a4632', '#2fb3a3', '#e8b793')),
  ],
  teams: [{ lead_id: 'demo-lead', member_ids: ['demo-h1', 'demo-h2', 'demo-h3'] }],
}
