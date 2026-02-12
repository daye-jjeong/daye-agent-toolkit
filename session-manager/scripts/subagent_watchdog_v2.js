#!/usr/bin/env node
/**
 * Subagent Watchdog v2 - 완료된 세션 필터링 및 자동 정리
 * 
 * PURPOSE: 
 * - 완료된 subagent 세션은 알림 제외
 * - 완료 후 15분 경과한 세션 자동 정리 (JSONL rename)
 * - Gateway 재시작 감지 및 stuck 세션 통지
 * 
 * USAGE: Cron으로 매 5분 실행
 * 
 * FEATURES:
 * A) 완료 판정: 마지막 run이 stop/finished, tool call 없음, 3분+ inactive
 * B) 완료된 세션은 알림 스킵
 * C) Gateway 재시작 감지 → 최근 N분 내 시작한 subagent를 stuck 처리
 * D) 중복 알림 방지 (state 파일, cooldown 30분)
 * E) 완료 후 15분 경과 시 JSONL 자동 정리
 * 
 * CONFIG:
 * - Stuck 기준: 10분
 * - 완료 기준: 3분 inactive + tool call 없음
 * - 정리 기준: 완료 후 15분
 * - 알림: Telegram DM (Daye)
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const CONFIG = {
  STATE_FILE: path.join(__dirname, '../vault/state/subagent-watchdog-state.json'),
  SESSIONS_DIR: path.join(process.env.HOME, '.clawdbot/agents/main/sessions'),
  GATEWAY_PID_FILE: '/tmp/clawdbot-gateway.pid',
  STUCK_THRESHOLD_MS: 10 * 60 * 1000, // 10분
  COMPLETION_THRESHOLD_MS: 3 * 60 * 1000, // 3분 (완료 판정)
  CLEANUP_THRESHOLD_MS: 15 * 60 * 1000, // 15분 (정리 기준)
  GATEWAY_RESTART_WINDOW_MS: 15 * 60 * 1000, // Gateway 재시작 후 15분 이내 세션 체크
  DUPLICATE_ALERT_COOLDOWN_MS: 30 * 60 * 1000, // 30분 (동일 세션에 대해)
  TELEGRAM_USER_ID: '8514441011', // Daye
  DRY_RUN: process.argv.includes('--dry-run'), // 드라이런 모드
  VERBOSE: process.argv.includes('--verbose'), // 상세 로그
};

// Logging
function log(message, level = 'INFO') {
  const timestamp = new Date().toISOString();
  const prefix = CONFIG.DRY_RUN ? '[DRY-RUN] ' : '';
  
  if (level === 'DEBUG' && !CONFIG.VERBOSE) {
    return; // Skip debug logs unless verbose
  }
  
  console.log(`${prefix}[${timestamp}] [WATCHDOG-V2] [${level}] ${message}`);
}

// Load state
function loadState() {
  try {
    if (!fs.existsSync(CONFIG.STATE_FILE)) {
      return {
        lastGatewayPid: null,
        lastGatewayCheckAt: null,
        stuckSessions: {}, // sessionId -> { lastAlertAt, retryCount, lastRetryAt }
        completedSessions: {}, // sessionId -> { completedAt, lastCleanupAttempt }
      };
    }
    
    const data = fs.readFileSync(CONFIG.STATE_FILE, 'utf8');
    const state = JSON.parse(data);
    
    // Ensure completedSessions exists
    if (!state.completedSessions) {
      state.completedSessions = {};
    }
    
    return state;
  } catch (error) {
    log(`Failed to load state: ${error.message}`, 'ERROR');
    return {
      lastGatewayPid: null,
      lastGatewayCheckAt: null,
      stuckSessions: {},
      completedSessions: {},
    };
  }
}

// Save state
function saveState(state) {
  try {
    const dir = path.dirname(CONFIG.STATE_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    if (CONFIG.DRY_RUN) {
      log(`Would save state: ${JSON.stringify(state, null, 2)}`, 'DEBUG');
      return;
    }
    
    fs.writeFileSync(CONFIG.STATE_FILE, JSON.stringify(state, null, 2));
    log('State saved', 'DEBUG');
  } catch (error) {
    log(`Failed to save state: ${error.message}`, 'ERROR');
  }
}

// Get Gateway PID
function getGatewayPid() {
  try {
    const result = execSync('ps aux | grep clawdbot-gateway | grep -v grep | awk \'{print $2}\' | head -1', { encoding: 'utf8' }).trim();
    return result || null;
  } catch (error) {
    return null;
  }
}

// Check if Gateway restarted
function checkGatewayRestart(state) {
  const currentPid = getGatewayPid();
  
  if (!currentPid) {
    log('Gateway is not running', 'WARN');
    return { restarted: false, currentPid: null };
  }
  
  if (!state.lastGatewayPid) {
    log(`Gateway PID initialized: ${currentPid}`, 'DEBUG');
    return { restarted: false, currentPid };
  }
  
  if (state.lastGatewayPid !== currentPid) {
    log(`Gateway restarted! Old PID: ${state.lastGatewayPid}, New PID: ${currentPid}`, 'WARN');
    return { restarted: true, currentPid };
  }
  
  return { restarted: false, currentPid };
}

// Get all sessions
function getSessions() {
  try {
    const output = execSync('clawdbot sessions list --json', { encoding: 'utf8' });
    const data = JSON.parse(output);
    return data.sessions || [];
  } catch (error) {
    log(`Failed to get sessions: ${error.message}`, 'ERROR');
    return [];
  }
}

// Filter subagent sessions
function filterSubagentSessions(sessions) {
  return sessions.filter(s => 
    s.key && s.key.startsWith('agent:main:subagent:')
  );
}

// Check if session is completed
function isSessionCompleted(session, now) {
  const sessionId = session.sessionId || session.key;
  const lastUpdate = session.updatedAt || 0;
  const inactiveMs = now - lastUpdate;
  
  // Must be inactive for at least COMPLETION_THRESHOLD_MS
  if (inactiveMs < CONFIG.COMPLETION_THRESHOLD_MS) {
    log(`Session ${sessionId} still active (${Math.round(inactiveMs / 1000)}s ago)`, 'DEBUG');
    return false;
  }
  
  // Check JSONL for last message
  const jsonlPath = path.join(CONFIG.SESSIONS_DIR, `${sessionId}.jsonl`);
  
  if (!fs.existsSync(jsonlPath)) {
    log(`JSONL not found for ${sessionId}, treating as completed`, 'DEBUG');
    return true;
  }
  
  try {
    // Read last few lines (more efficient than reading entire file)
    const content = fs.readFileSync(jsonlPath, 'utf8');
    const lines = content.trim().split('\n');
    const recentLines = lines.slice(-10); // Last 10 messages
    
    // Check for pending tool calls
    for (let i = recentLines.length - 1; i >= 0; i--) {
      try {
        const msg = JSON.parse(recentLines[i]);
        
        // If last message has tool_use without tool_result, it's pending
        if (msg.type === 'message' && msg.role === 'assistant' && msg.content) {
          const hasToolUse = Array.isArray(msg.content) && 
            msg.content.some(c => c.type === 'tool_use');
          
          if (hasToolUse) {
            // Check if there's a tool_result after this
            const hasToolResult = recentLines.slice(i + 1).some(line => {
              try {
                const nextMsg = JSON.parse(line);
                return nextMsg.type === 'message' && nextMsg.role === 'user' &&
                  Array.isArray(nextMsg.content) &&
                  nextMsg.content.some(c => c.type === 'tool_result');
              } catch {
                return false;
              }
            });
            
            if (!hasToolResult) {
              log(`Session ${sessionId} has pending tool call`, 'DEBUG');
              return false;
            }
          }
        }
        
        // Check for stop_reason
        if (msg.type === 'message' && msg.role === 'assistant' && msg.stop_reason) {
          const stopReason = msg.stop_reason;
          if (stopReason === 'end_turn' || stopReason === 'stop_sequence') {
            log(`Session ${sessionId} completed (stop_reason: ${stopReason})`, 'DEBUG');
            return true;
          }
        }
      } catch (e) {
        // Skip invalid JSON lines
        continue;
      }
    }
    
    // If no definitive completion signal, consider it completed if inactive long enough
    log(`Session ${sessionId} completed (inactive ${Math.round(inactiveMs / 60000)}min)`, 'DEBUG');
    return true;
    
  } catch (error) {
    log(`Error checking completion for ${sessionId}: ${error.message}`, 'ERROR');
    return false;
  }
}

// Check if session is stuck
function isSessionStuck(session, now) {
  const lastUpdate = session.updatedAt || 0;
  const ageMs = now - lastUpdate;
  return ageMs >= CONFIG.STUCK_THRESHOLD_MS;
}

// Check if recently started (within gateway restart window)
function isRecentlyStarted(session, now) {
  const lastUpdate = session.updatedAt || 0;
  const ageMs = now - lastUpdate;
  return ageMs <= CONFIG.GATEWAY_RESTART_WINDOW_MS;
}

// Should skip alert (duplicate prevention)
function shouldSkipAlert(sessionId, state) {
  const sessionState = state.stuckSessions[sessionId];
  
  if (!sessionState || !sessionState.lastAlertAt) {
    return false;
  }
  
  const timeSinceLastAlert = Date.now() - new Date(sessionState.lastAlertAt).getTime();
  
  if (timeSinceLastAlert < CONFIG.DUPLICATE_ALERT_COOLDOWN_MS) {
    log(`Skipping alert for ${sessionId} (cooldown: ${Math.round(timeSinceLastAlert / 60000)}min ago)`, 'DEBUG');
    return true;
  }
  
  return false;
}

// Send Telegram alert
function sendTelegramAlert(message) {
  try {
    if (CONFIG.DRY_RUN) {
      log(`Would send Telegram: ${message}`, 'INFO');
      return;
    }
    
    const sanitized = message.replace(/`/g, "'");
    const tmpFile = '/tmp/subagent_watchdog_msg.txt';
    fs.writeFileSync(tmpFile, sanitized);
    
    execSync(
      `clawdbot message send -t "${CONFIG.TELEGRAM_USER_ID}" -m "$(cat ${tmpFile})"`,
      { encoding: 'utf8', stdio: 'pipe' }
    );
    
    fs.unlinkSync(tmpFile);
    log('Telegram alert sent', 'INFO');
  } catch (error) {
    log(`Failed to send Telegram alert: ${error.message}`, 'ERROR');
  }
}

// Handle stuck session
function handleStuckSession(session, reason, state) {
  const sessionId = session.sessionId || session.key;
  const sessionKey = session.key;
  const ageMinutes = Math.round((Date.now() - session.updatedAt) / 60000);
  
  log(`Stuck session detected: ${sessionKey} (${ageMinutes}min, reason: ${reason})`, 'WARN');
  
  if (shouldSkipAlert(sessionId, state)) {
    return;
  }
  
  const sessionState = state.stuckSessions[sessionId] || { retryCount: 0 };
  const retryCount = sessionState.retryCount || 0;
  
  let message = `🔴 **Subagent 무응답 감지**\n\n` +
    `**세션:** \`${sessionKey}\`\n` +
    `**세션 ID:** \`${sessionId}\`\n` +
    `**무응답 시간:** ${ageMinutes}분\n` +
    `**원인:** ${reason}\n` +
    `**모델:** ${session.model || 'unknown'}\n` +
    `**Label:** ${session.label || 'none'}\n` +
    `**시각:** ${new Date().toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })}`;
  
  sendTelegramAlert(message);
  
  state.stuckSessions[sessionId] = {
    lastAlertAt: new Date().toISOString(),
    retryCount: retryCount + 1,
    sessionKey,
    reason,
  };
}

// Clean up completed session JSONL
function cleanupCompletedSession(sessionId, state) {
  const jsonlPath = path.join(CONFIG.SESSIONS_DIR, `${sessionId}.jsonl`);
  
  if (!fs.existsSync(jsonlPath)) {
    log(`JSONL already cleaned: ${sessionId}`, 'DEBUG');
    return true;
  }
  
  try {
    if (CONFIG.DRY_RUN) {
      log(`Would rename JSONL: ${jsonlPath} -> ${jsonlPath}.deleted.*`, 'INFO');
      return true;
    }
    
    const timestamp = new Date().toISOString().replace(/:/g, '-');
    const newPath = `${jsonlPath}.deleted.${timestamp}`;
    
    fs.renameSync(jsonlPath, newPath);
    log(`Cleaned JSONL: ${sessionId}`, 'INFO');
    
    // Update state
    if (!state.completedSessions[sessionId]) {
      state.completedSessions[sessionId] = {};
    }
    state.completedSessions[sessionId].lastCleanupAttempt = new Date().toISOString();
    
    return true;
  } catch (error) {
    log(`Failed to clean JSONL for ${sessionId}: ${error.message}`, 'ERROR');
    return false;
  }
}

// Clean up resolved sessions from state
function cleanupResolvedSessions(state, activeSessions) {
  const activeSessionIds = new Set(activeSessions.map(s => s.sessionId || s.key));
  
  let cleaned = 0;
  for (const sessionId in state.stuckSessions) {
    if (!activeSessionIds.has(sessionId)) {
      delete state.stuckSessions[sessionId];
      cleaned++;
    }
  }
  
  // Also clean old completed sessions (7+ days)
  const sevenDaysAgo = Date.now() - (7 * 24 * 60 * 60 * 1000);
  for (const sessionId in state.completedSessions) {
    const completedAt = new Date(state.completedSessions[sessionId].completedAt || 0).getTime();
    if (completedAt < sevenDaysAgo) {
      delete state.completedSessions[sessionId];
      cleaned++;
    }
  }
  
  if (cleaned > 0) {
    log(`Cleaned ${cleaned} resolved/old sessions from state`, 'DEBUG');
  }
}

// Main execution
function main() {
  log('Starting subagent watchdog check (v2)...', 'INFO');
  
  if (CONFIG.DRY_RUN) {
    log('DRY-RUN MODE: No actual changes will be made', 'INFO');
  }
  
  const state = loadState();
  const now = Date.now();
  
  // Step 1: Check if Gateway restarted
  const { restarted: gatewayRestarted, currentPid } = checkGatewayRestart(state);
  
  if (currentPid) {
    state.lastGatewayPid = currentPid;
    state.lastGatewayCheckAt = new Date().toISOString();
  }
  
  // Step 2: Get all sessions
  const allSessions = getSessions();
  log(`Found ${allSessions.length} total sessions`, 'DEBUG');
  
  const subagentSessions = filterSubagentSessions(allSessions);
  log(`Found ${subagentSessions.length} subagent sessions`, 'INFO');
  
  if (subagentSessions.length === 0) {
    log('No subagent sessions to monitor', 'INFO');
    saveState(state);
    return;
  }
  
  // Step 3: Check for completed and stuck sessions
  let stuckCount = 0;
  let completedCount = 0;
  let cleanedCount = 0;
  
  for (const session of subagentSessions) {
    const sessionId = session.sessionId || session.key;
    
    // Check if completed first
    if (isSessionCompleted(session, now)) {
      completedCount++;
      
      // Mark as completed in state
      if (!state.completedSessions[sessionId]) {
        state.completedSessions[sessionId] = {
          completedAt: new Date().toISOString(),
          sessionKey: session.key,
        };
        log(`Marked session as completed: ${sessionId}`, 'INFO');
      }
      
      // Check if should be cleaned (15+ minutes after completion)
      const completedAt = new Date(state.completedSessions[sessionId].completedAt).getTime();
      const timeSinceCompletion = now - completedAt;
      
      if (timeSinceCompletion >= CONFIG.CLEANUP_THRESHOLD_MS) {
        if (cleanupCompletedSession(sessionId, state)) {
          cleanedCount++;
        }
      } else {
        log(`Session ${sessionId} completed ${Math.round(timeSinceCompletion / 60000)}min ago, cleanup in ${Math.round((CONFIG.CLEANUP_THRESHOLD_MS - timeSinceCompletion) / 60000)}min`, 'DEBUG');
      }
      
      // Skip stuck check for completed sessions
      continue;
    }
    
    // Check 1: Gateway restart + recently started session
    if (gatewayRestarted && isRecentlyStarted(session, now)) {
      handleStuckSession(session, 'Gateway 재시작 감지 + 최근 시작된 세션', state);
      stuckCount++;
      continue;
    }
    
    // Check 2: General stuck (no update for 10+ minutes)
    if (isSessionStuck(session, now)) {
      handleStuckSession(session, '10분+ 업데이트 없음', state);
      stuckCount++;
    }
  }
  
  // Step 4: Clean up resolved sessions
  cleanupResolvedSessions(state, subagentSessions);
  
  // Step 5: Save state
  saveState(state);
  
  log(`Watchdog check complete. Subagents: ${subagentSessions.length} | Completed: ${completedCount} | Stuck: ${stuckCount} | Cleaned: ${cleanedCount}`, 'INFO');
}

// Run
try {
  main();
} catch (error) {
  log(`Unexpected error: ${error.message}`, 'ERROR');
  console.error(error.stack);
  process.exit(1);
}
