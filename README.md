# The Clankerville

A live isometric pixel office of your Möbius chats. Every chat is a character at a desk: it
types while it works, waves when it needs you, smokes when something broke, and heads to the
coffee corner when it's on a break. Chats that start helpers sit together as a team. (Formerly
Agent Office; the app id stays `agent-office`.)

- **Tap anyone** to see what they're doing and what they last said. Answer a waiting question
  with a tap (sent exactly as the chat's own card would), or send a quick reply. Secret and
  restart cards always stay in the full chat. On a wide screen, **Open chat** puts the full chat
  in a pane beside the office.
- **Progress.** Finished turns, returning helpers and shipped apps earn XP; chats and the office
  level up, and a recap tells you what happened yesterday.
- **The sword.** Press and hold someone: a chat is deleted (Möbius keeps it recoverable for 7 days
  and sends a Recover notification), a helper is dismissed.
- **The Internet** (an IT Crowd joke): the black box with the red light in the coffee corner.
  It's a hidden switch: the first press only makes its light flare, and a deliberate second press
  within 6 s (a quick double-click doesn't count) turns it off. Every chat that is working is
  stopped; Möbius's Stop also cancels that chat's helpers and drops its queued messages, while
  chats waiting on you are left alone. The office shows "You turned off the Internet" and how many
  chats stopped. One more press turns it back on and sends each stopped chat "The Internet is back
  on. Please continue where you left off."; any that can't take the message are named so you can
  tell them yourself.
- **Floors** (added 2026-10-08). The office is a 4-floor building with 8 desks a floor. Agents who need you or
  are working get floor 1; idle ones move up, and helpers sit with their lead. Agents of equal rank keep their
  floor. The strip says which floor you're on, and a red dot marks a floor where someone needs you.
- **You.** Your own character, in a white shirt with a red tie and glasses. Tap the floor or hold an arrow key to
  walk. Walk into the elevator (or tap it) to pick a floor. Tapping an agent still opens its card.
- **A surprise on every floor:** floor 2's watercooler sets off gossip, floor 3's phone asks "Have you tried
  turning it off and on again?", and floor 4 has a fire ("0118 999 881 999 119 725… 3"). These are just for fun.
- **The CR desk** (Clanker Resources), in floor 1's lobby. Tap the applicants' papers, give the new hire a name
  and a first message, and press Hire. A real chat starts, named as you typed.
- **Demo mode** shows a sample office when you have no chats yet.

## What it does with your access

The Clankerville acts with your owner access on your own Möbius: its service reads Möbius's owner
key (`/data/service-token.txt`) on every call, so it can do anything you can. No narrower permission
covers seeing and steering agents yet, so the manifest's empty permissions list does not show this;
review updates before installing them. It reads your chats and helpers to draw the office, and it
stops, deletes or messages a chat only when you use the sword, a quick reply or the Internet box,
and it starts a new chat only when you hire at the CR desk. It talks only to your own Möbius, never
to another server. `feed.py` is the single module that reads the key and calls Möbius; it never logs
it. The office keeps small state files in its own storage: desk places; progress (XP, levels, and
chat titles for the recap; a deleted chat's title is forgotten once its 60 recap days are over);
while the Internet is off, the stopped chats' ids and titles; and logs of sword swings, replies,
Internet switches and hires, which never hold names or message text and are kept for 30 days.

## Development

- Service (Python): `service.py` (routes), `feed.py` (Möbius owner API), `office.py` (states,
  desks, teams), `progress.py` (XP, levels, recap), `quick_reply.py`, `store.py`.
- Screen (React): `index.jsx`, `api.js`, `domain.js`, `theme.js`, `demo.js`, `ui/`.
- Tests: `python3 -m pytest tests -q` and `node --test tests/*.test.mjs`.

MIT licensed; see `LICENSE`.
