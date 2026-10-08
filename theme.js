export const CSS = `
  * { box-sizing: border-box; }
  .ao-root { min-height: 100%; padding: 16px clamp(10px, 2.5vw, 28px) 24px; background: var(--bg); color: var(--text); font-family: var(--font); }
  .ao-muted { color: var(--muted); }
  .ao-layout { display: grid; gap: 14px; grid-template-columns: minmax(0, 1fr); align-items: start; max-width: 1400px; margin: 0 auto; }
  .ao-main { min-width: 0; }
  .ao-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; padding: 10px 12px; border-radius: 14px 14px 0 0; background: var(--surface); border: 1px solid var(--border); border-bottom: none; }
  .ao-level { display: flex; align-items: center; gap: 8px; font-size: 13px; }
  .ao-xp { display: inline-block; width: 90px; height: 6px; border-radius: 3px; background: var(--surface-2); overflow: hidden; }
  .ao-xp.ao-wide { width: 100%; }
  .ao-xp > span { display: block; height: 100%; background: var(--accent); }
  .ao-counts { display: flex; flex-wrap: wrap; gap: 6px; flex: 1; }
  .ao-chip { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; padding: 3px 9px; border-radius: 999px; background: var(--surface-2); }
  .ao-stale { background: color-mix(in srgb, #f5a524 22%, var(--surface-2)); }
  .ao-dot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
  .ao-tools { display: flex; gap: 8px; }
  .ao-btn { all: unset; box-sizing: border-box; position: relative; overflow: hidden; display: inline-flex; align-items: center; gap: 6px; min-height: 44px; padding: 0 14px; border-radius: 10px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); font-size: 13px; font-weight: 600; cursor: pointer; user-select: none; -webkit-user-select: none; touch-action: none; }
  .ao-btn:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  .ao-swordbtn { min-width: 120px; justify-content: center; } /* same width with or without "on" */
  .ao-swordbtn[aria-pressed="true"] { background: #e5484d; border-color: #e5484d; color: #fff; }
  .ao-scene { position: relative; border: 1px solid var(--border); border-radius: 0 0 14px 14px; overflow: hidden; background: #f4f1fb; }
  .ao-svg { display: block; width: 100%; height: auto; max-height: 62vh; touch-action: none; user-select: none; -webkit-user-select: none; }
  .ao-hit:focus { outline: none; }
  .ao-hit:focus-visible { stroke: #6d5dfc; stroke-width: 2; }
  .ao-ring { fill: none; stroke: #e5484d; stroke-width: 3.5; stroke-linecap: round; stroke-dasharray: 100; stroke-dashoffset: 100; animation: ao-fill var(--ao-hold, 900ms) linear forwards; pointer-events: none; }
  .ao-ring-warn { stroke: #f5a524; }
  @keyframes ao-fill { to { stroke-dashoffset: 0; } }
  .ao-banner { display: flex; align-items: center; justify-content: space-between; gap: 12px; max-width: 1400px; margin: 0 auto 12px; padding: 8px 12px; border-radius: 12px; background: color-mix(in srgb, #f5a524 16%, var(--surface)); border: 1px solid color-mix(in srgb, #f5a524 45%, var(--border)); font-weight: 600; font-size: 14px; }
  .ao-empty { position: absolute; left: 50%; top: 42%; transform: translate(-50%, -50%); display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 18px 22px; border-radius: 16px; background: rgba(42,35,64,.9); color: #fff; text-align: center; max-width: min(420px, 90%); font-size: 15px; line-height: 1.45; }
  .ao-empty .ao-btn { background: #fff; color: #2a2340; border-color: #fff; }
  .ao-screen { display: grid; place-items: center; min-height: 60vh; }
  .ao-card { display: flex; flex-direction: column; gap: 12px; padding: 16px; border-radius: 14px; background: var(--surface); border: 1px solid var(--border); }
  .ao-card h2 { margin: 2px 0 0; font-size: 17px; line-height: 1.25; }
  .ao-card p { margin: 0; line-height: 1.5; }
  .ao-role { font-size: 12.5px; color: var(--muted); }
  .ao-state { display: inline-flex; align-items: center; gap: 7px; font-size: 13.5px; font-weight: 600; }
  .ao-danger { border-color: color-mix(in srgb, #e5484d 60%, var(--border)); }
  .ao-holdfill { position: absolute; inset: 0; background: rgba(229,72,77,.32); transform-origin: left center; transform: scaleX(0); animation-name: ao-grow; animation-timing-function: linear; animation-fill-mode: forwards; pointer-events: none; }
  @keyframes ao-grow { to { transform: scaleX(1); } }
  .ao-warn { display: flex; flex-direction: column; gap: 6px; font-size: 13px; line-height: 1.45; padding: 9px 11px; border-radius: 10px; background: color-mix(in srgb, #f5a524 16%, var(--surface)); border: 1px solid color-mix(in srgb, #f5a524 45%, var(--border)); }
  .ao-btn[disabled] { opacity: .5; cursor: default; }
  .ao-qr { display: flex; flex-direction: column; gap: 10px; }
  .ao-qr-questions { display: flex; flex-direction: column; gap: 12px; }
  .ao-qr-q { display: flex; flex-direction: column; gap: 8px; min-width: 0; margin: 0; padding: 0; border: none; }
  .ao-qr-q legend { margin-bottom: 8px; padding: 0; font-size: 14px; font-weight: 600; line-height: 1.4; }
  .ao-qr-opt { all: unset; box-sizing: border-box; display: flex; flex-direction: column; gap: 4px; min-height: 48px; padding: 11px 14px; border-radius: 14px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); font-size: 14px; cursor: pointer; transition: border-color .15s, background .15s; }
  .ao-qr-opt:hover:not(:disabled) { border-color: color-mix(in srgb, var(--accent) 55%, var(--border)); }
  .ao-qr-opt b { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-weight: 650; line-height: 1.3; }
  .ao-qr-opt span { color: var(--muted); font-size: 12.5px; font-weight: 400; line-height: 1.45; }
  .ao-qr-rec { border-color: color-mix(in srgb, var(--accent) 60%, var(--border)); background: color-mix(in srgb, var(--accent) 10%, var(--surface-2)); }
  .ao-qr-badge { font-style: normal; font-size: 11px; font-weight: 700; letter-spacing: .02em; padding: 2px 8px; border-radius: 999px; background: var(--accent); color: #fff; }
  .ao-qr-opt[aria-pressed="true"] { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 18%, var(--surface-2)); }
  .ao-qr-opt:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  .ao-qr-q:disabled .ao-qr-opt { opacity: .6; cursor: default; }
  .ao-qr-primary { background: var(--accent); border-color: var(--accent); color: #fff; justify-content: center; }
  .ao-qr-done, .ao-qr-problem { margin: 0; padding: 9px 12px; border-radius: 10px; font-size: 13px; line-height: 1.45; }
  .ao-qr-done { background: color-mix(in srgb, #3fcf8e 16%, var(--surface)); border: 1px solid color-mix(in srgb, #3fcf8e 45%, var(--border)); }
  .ao-qr-problem { background: color-mix(in srgb, #e5484d 14%, var(--surface)); border: 1px solid color-mix(in srgb, #e5484d 45%, var(--border)); }
  .ao-card p.ao-small-note { font-size: 12.5px; line-height: 1.4; margin-top: -4px; }

  /* The selected character's card, below the office (2026-10-07). */
  .ao-hintbar { padding: 12px 16px; border-radius: 14px; border: 1px dashed var(--border); color: var(--muted); font-size: 14px; text-align: center; }
  .ao-detail { gap: 14px; padding: 16px 18px; }
  .ao-dhead { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; }
  .ao-avatar { width: 38px; height: 38px; flex: none; border-radius: 50%; border: 5px solid; box-shadow: 0 0 0 2px var(--surface); }
  .ao-dtitle { min-width: 0; margin-right: auto; }
  .ao-dtitle h2 { margin: 0; font-size: 18px; line-height: 1.2; }
  .ao-pill { display: inline-flex; align-items: center; gap: 7px; padding: 5px 11px; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border); font-size: 13px; font-weight: 600; white-space: nowrap; }
  .ao-pill-ask { background: color-mix(in srgb, #ffc53d 16%, var(--surface-2)); border-color: color-mix(in srgb, #ffc53d 55%, var(--border)); }
  .ao-pill-small { padding: 3px 9px; font-size: 12.5px; font-weight: 500; }
  .ao-dlevel { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; }
  .ao-dlevel .ao-xp { width: 72px; }
  .ao-now { font-size: 14px; }
  .ao-team { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 6px; }
  .ao-qr-cols { display: grid; gap: 16px; grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 760px) { .ao-qr-cols { grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr); align-items: start; } }
  .ao-qr-said, .ao-qr-ask { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .ao-qr-label { color: var(--muted); font-size: 11.5px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
  .ao-qr-bubble { position: relative; padding: 12px 14px; border-radius: 4px 16px 16px 16px; background: var(--surface-2); border: 1px solid var(--border); font-size: 14px; line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere; }
  .ao-qr-bubble .ao-clamped { display: -webkit-box; -webkit-line-clamp: 6; -webkit-box-orient: vertical; overflow: hidden; }
  .ao-linkbtn { all: unset; align-self: flex-start; min-height: 32px; display: inline-flex; align-items: center; color: var(--accent); font-size: 13px; font-weight: 600; cursor: pointer; }
  .ao-linkbtn:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; border-radius: 6px; }
  .ao-qr-opts { display: grid; gap: 8px; grid-template-columns: minmax(0, 1fr); }
  @media (min-width: 760px) { .ao-qr-opts { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .ao-composer { display: flex; align-items: flex-end; gap: 8px; padding: 6px 6px 6px 14px; border-radius: 22px; border: 1px solid var(--border); background: var(--surface-2); }
  .ao-composer:focus-within { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 30%, transparent); }
  .ao-composer textarea { flex: 1; min-width: 0; min-height: 32px; max-height: 140px; padding: 6px 0; border: none; outline: none; resize: none; background: transparent; color: var(--text); font: inherit; font-size: 16px; line-height: 1.4; } /* 16 px: iPhones zoom into smaller text fields */
  .ao-send { all: unset; box-sizing: border-box; display: grid; place-items: center; width: 44px; height: 44px; flex: none; border-radius: 50%; background: var(--accent); color: #fff; cursor: pointer; }
  .ao-send:disabled { opacity: .4; cursor: default; }
  .ao-send:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  .ao-detail .ao-actions { align-items: center; padding-top: 4px; border-top: 1px solid var(--border); }
  .ao-detail .ao-actions .ao-btn { margin-top: 10px; }
  .ao-detail .ao-small-note { flex-basis: 100%; margin: 0; }
  .ao-lv { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
  .ao-lvrow { display: flex; justify-content: space-between; gap: 8px; }
  .ao-team { display: flex; flex-direction: column; gap: 5px; font-size: 13px; }
  .ao-state.ao-small { font-weight: 500; font-size: 13px; }
  .ao-actions { display: flex; flex-wrap: wrap; gap: 8px; }
  .ao-hint { position: absolute; top: 10px; left: 50%; transform: translateX(-50%); width: max-content; max-width: calc(100% - 20px); padding: 6px 12px; border-radius: 14px; background: rgba(42,35,64,.92); color: #fff; font-size: 12.5px; line-height: 1.35; text-align: center; pointer-events: none; }
  .ao-internet { cursor: pointer; }
  .ao-internet:focus-visible { outline: 2px solid #ff6b6b; outline-offset: 2px; }
  .ao-internet-off { position: absolute; top: 10px; left: 50%; transform: translateX(-50%); width: max-content; max-width: calc(100% - 20px); display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px 14px; border-radius: 14px; background: rgba(58,18,24,.94); border: 1px solid rgba(255,107,107,.35); color: #fff; text-align: center; pointer-events: none; box-shadow: 0 6px 20px rgba(0,0,0,.3); }
  .ao-internet-off b { font-size: 14px; letter-spacing: .02em; }
  .ao-internet-off span { font-size: 12px; color: #f3c6c9; }
  .ao-toast-wrap { position: absolute; left: 12px; right: 12px; bottom: 12px; display: flex; justify-content: center; pointer-events: none; }
  .ao-toast { max-width: 560px; padding: 10px 14px; border-radius: 12px; background: #2a2340; color: #fff; font-size: 13.5px; line-height: 1.4; box-shadow: 0 6px 20px rgba(0,0,0,.25); }
  .ao-leaving { animation: ao-leave .65s ease-in both; transform-box: fill-box; transform-origin: 50% 100%; }
  @keyframes ao-leave { 0% { opacity: 1; transform: translateY(0) scale(1); } 30% { transform: translateY(-4px) scale(1.08); } 100% { opacity: 0; transform: translateY(-16px) scale(.5); } }
  .ao-poof { animation: ao-poof .75s ease-out both; transform-box: fill-box; transform-origin: center; }
  @keyframes ao-poof { 0% { opacity: 0; transform: scale(.3); } 25% { opacity: .95; transform: scale(1); } 100% { opacity: 0; transform: scale(1.5); } }
  .ao-walking { animation: ao-walk 3.2s ease-in-out 1.2s both; }
  @keyframes ao-walk { 0% { transform: translate(0, 0); opacity: 1; } 88% { opacity: 1; } 100% { transform: translate(var(--dx), var(--dy)); opacity: 0; } }
  .ao-recap { position: fixed; inset: 0; z-index: 10; display: grid; place-items: center; padding: 16px; background: rgba(20,16,36,.45); }
  .ao-recap-card { width: min(420px, 100%); box-shadow: 0 12px 40px rgba(0,0,0,.3); }
  .ao-recap-list { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; line-height: 1.45; }
  .ao-pulse { animation: ao-pulse 1.4s ease-in-out infinite; }
  @keyframes ao-pulse { 0%, 100% { opacity: 1 } 50% { opacity: .78 } }
  @media (prefers-reduced-motion: reduce) { .ao-pulse, .ao-walking { animation: none; } .ao-leaving { animation: none; opacity: 0; } .ao-poof { display: none; } }
`
