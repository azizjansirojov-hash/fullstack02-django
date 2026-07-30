#!/usr/bin/env node
/**
 * Free Libro.UZ local-dev ports before starting `npm run dev`.
 *
 * On Windows, aborted/killed concurrently sessions often leave orphan
 * node (Vite :5173) and python (Django :8000) listeners. Vite uses
 * strictPort, so a stale listener makes the next `npm run dev` fail hard.
 *
 * Usage: node scripts/free-dev-ports.mjs
 * Wired as npm `predev` so it runs automatically before `dev`.
 */
import { execFileSync } from 'node:child_process'
import process from 'node:process'

const PORTS = (process.env.LIBRO_DEV_PORTS || '5173,8000')
  .split(',')
  .map((p) => Number(p.trim()))
  .filter((n) => Number.isInteger(n) && n > 0)

function uniq(ids) {
  return [...new Set(ids.filter((id) => Number.isInteger(id) && id > 0))]
}

function pidsListeningOnWindows(port) {
  let out = ''
  try {
    out = execFileSync('netstat', ['-ano', '-p', 'TCP'], {
      encoding: 'utf8',
      windowsHide: true,
    })
  } catch {
    return []
  }
  const pids = []
  for (const line of out.split(/\r?\n/)) {
    if (!line.includes('LISTENING')) continue
    // e.g. "  TCP    127.0.0.1:5173    0.0.0.0:0    LISTENING    12345"
    const parts = line.trim().split(/\s+/)
    if (parts.length < 5) continue
    const local = parts[1] || ''
    const pid = Number(parts[parts.length - 1])
    if (!local.endsWith(`:${port}`)) continue
    if (Number.isInteger(pid) && pid > 0) pids.push(pid)
  }
  return uniq(pids)
}

function pidsListeningOnUnix(port) {
  try {
    const out = execFileSync('lsof', ['-ti', `TCP:${port}`, '-sTCP:LISTEN'], {
      encoding: 'utf8',
    })
    return uniq(
      out
        .split(/\s+/)
        .map((s) => Number(s.trim()))
        .filter(Boolean),
    )
  } catch {
    return []
  }
}

function killWindows(pid) {
  try {
    execFileSync('taskkill', ['/F', '/T', '/PID', String(pid)], {
      encoding: 'utf8',
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    return true
  } catch {
    return false
  }
}

function killUnix(pid) {
  try {
    process.kill(pid, 'SIGTERM')
    return true
  } catch {
    try {
      process.kill(pid, 'SIGKILL')
      return true
    } catch {
      return false
    }
  }
}

function freePort(port) {
  const isWin = process.platform === 'win32'
  const pids = isWin ? pidsListeningOnWindows(port) : pidsListeningOnUnix(port)
  if (!pids.length) {
    console.log(`[free-dev-ports] :${port} already free`)
    return
  }
  for (const pid of pids) {
    // Never kill our own process tree parent by accident (unlikely on these ports).
    if (pid === process.pid || pid === process.ppid) continue
    const ok = isWin ? killWindows(pid) : killUnix(pid)
    console.log(
      ok
        ? `[free-dev-ports] freed :${port} (killed pid ${pid})`
        : `[free-dev-ports] could not kill pid ${pid} on :${port}`,
    )
  }
}

for (const port of PORTS) {
  freePort(port)
}
