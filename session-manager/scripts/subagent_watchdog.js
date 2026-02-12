#!/usr/bin/env node
/**
 * Subagent Watchdog - Subagent 무응답 감지 및 자동 복구
 * 
 * PURPOSE: 
 * - Gateway 크래시/무응답 시 진행 중인 subagent 감지 및 통지
 * - Subagent 무응답(10분+ 업데이트 없음) 감지 및 알림/재시도
 * 
 * USAGE: Cron으로 매 1분 실행
 * 
 * FEATURES:
 * A) Gateway 재시작 감지 → 최근 N분 내 시작한 subagent를 stuck 처리
 * B) Subagent 무응답 타임아웃 → 알림 + 자동 재시도(선택)
 * C) 중복 알림 방지 (state 파일)
 * 
 * CONFIG:
 * - Stuck 기준: 10분
 * - 알림: Telegram DM (Daye)
 * - 자동 재시도: ON (최대 1회)
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const CONFIG = {
  STATE_FILE: path.join(__dirname, '../vault/state/subagent-watchdog-state.json'),
  GATEWAY_PID_FILE: '/tmp/clawdbot-gateway.pid', // Gateway PID 추적용
  STUCK_THRESHOLD_MS: 10 * 60 * 1000, // 10분
  GATEWAY_RESTART_WINDOW_MS: 15 * 60 * 1000, // Gateway 재시작 후 15분 이내 세션 체크
  DUPLICATE_ALERT_COOLDOWN_MS: 30 * 60 * 1000, // 30분 (동일 세션에 대해)
  TELEGRAM_USER_ID: '8514441011', // Daye
  AUTO_RETRY: true, // 자동 재시도 여부
  MAX_RETRIES: 1, // 최대 재시도 횟수
  DRY_RUN: process.argv.includes('--dry-run'), // 드라이런 모드
};

// Logging
function log(message, level = 'INFO') {
  const timestamp = new Date().toISOString();
  const prefix = CONFIG.DRY_RUN ? '[DRY-RUN] ' : '';
  console.log(`${prefix}[${timestamp}] [SUBAGENT-WATCHDOG] [${level}] ${message}`);
}

// Load state
function loadState() {
  try {
    if (!fs.existsSync(CONFIG.STATE_FILE)) {
      return {
        lastGatewayPid: null,
        lastGatewayCheckAt: null,
        stuckSessions: {}, // sessionId -> { lastAlertAt, retryCount, lastRetryAt }
      };
    }
    
    const data = fs.readFileSync(CONFIG.STATE_FILE, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    log(`Failed to load state: ${error.message}`, 'ERROR');
    return {
      lastGatewayPid: null,
      lastGatewayCheckAt: null,
      stuckSessions: {},
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
    // macOS에서 pgrep이 제대로 작동하지 않으므로 ps 사용
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
    // 첫 실행 - PID 저장
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
    
    // Backtick을 작은따옴표로 대체 (shell 이스케이핑 문제 방지)
    const sanitized = message.replace(/`/g, "'");
    
    // 임시 파일에 메시지 작성
    const tmpFile = '/tmp/subagent_watchdog_msg.txt';
    fs.writeFileSync(tmpFile, sanitized);
    
    // clawdbot message send 실행
    execSync(
      `clawdbot message send -t "${CONFIG.TELEGRAM_USER_ID}" -m "$(cat ${tmpFile})"`,
      { encoding: 'utf8', stdio: 'pipe' }
    );
    
    // 임시 파일 삭제
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
  
  // Check if should skip alert
  if (shouldSkipAlert(sessionId, state)) {
    return;
  }
  
  // Get retry count
  const sessionState = state.stuckSessions[sessionId] || { retryCount: 0 };
  const retryCount = sessionState.retryCount || 0;
  
  // Build alert message
  let message = `🔴 **Subagent 무응답 감지**\n\n` +
    `**세션:** \`${sessionKey}\`\n` +
    `**세션 ID:** \`${sessionId}\`\n` +
    `**무응답 시간:** ${ageMinutes}분\n` +
    `**원인:** ${reason}\n` +
    `**모델:** ${session.model || 'unknown'}\n` +
    `**시각:** ${new Date().toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })}`;
  
  // Auto-retry logic
  if (CONFIG.AUTO_RETRY && retryCount < CONFIG.MAX_RETRIES) {
    message += `\n\n🔄 자동 재시도 중... (${retryCount + 1}/${CONFIG.MAX_RETRIES})`;
    
    // TODO: 실제 재스폰은 구현 복잡도가 높아서 일단 보류
    // 재스폰하려면: 원래 subagent의 task label/context를 알아야 함
    // 현재는 알림만 발송
    
    message += `\n\n⚠️ *자동 재시도는 현재 지원되지 않습니다. 수동으로 확인해주세요.*`;
  } else if (retryCount >= CONFIG.MAX_RETRIES) {
    message += `\n\n⛔️ **최대 재시도 횟수 초과** (${CONFIG.MAX_RETRIES}회)\n` +
      `*수동 확인이 필요합니다.*`;
  } else {
    message += `\n\n*재시도 기능이 비활성화되어 있습니다.*`;
  }
  
  // Send alert
  sendTelegramAlert(message);
  
  // Update state
  state.stuckSessions[sessionId] = {
    lastAlertAt: new Date().toISOString(),
    retryCount: retryCount + (CONFIG.AUTO_RETRY && retryCount < CONFIG.MAX_RETRIES ? 1 : 0),
    lastRetryAt: CONFIG.AUTO_RETRY && retryCount < CONFIG.MAX_RETRIES ? new Date().toISOString() : null,
    sessionKey,
    reason,
  };
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
  
  if (cleaned > 0) {
    log(`Cleaned ${cleaned} resolved sessions from state`, 'DEBUG');
  }
}

// Main execution
function main() {
  log('Starting subagent watchdog check...', 'INFO');
  
  if (CONFIG.DRY_RUN) {
    log('DRY-RUN MODE: No actual changes will be made', 'INFO');
  }
  
  // Load state
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
  
  // Step 3: Check for stuck sessions
  let stuckCount = 0;
  
  for (const session of subagentSessions) {
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
  
  log(`Watchdog check complete. Stuck sessions: ${stuckCount}/${subagentSessions.length}`, 'INFO');
}

// Run
try {
  main();
} catch (error) {
  log(`Unexpected error: ${error.message}`, 'ERROR');
  console.error(error.stack);
  process.exit(1);
}
