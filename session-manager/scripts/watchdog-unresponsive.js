#!/usr/bin/env node
/**
 * Watchdog: Unresponsive Main Session Detector
 * 
 * PURPOSE: Detect if main agent session hasn't responded in >10 minutes
 * USAGE: Run via cron every 5 minutes
 * 
 * ALERTS:
 * - Telegram notification to JARVIS HQ
 * - Fallback log entry with WATCHDOG_UNRESPONSIVE code
 * 
 * MECHANISM:
 * - Checks vault/state/heartbeat-state.json for last heartbeat timestamp
 * - If >10 minutes ago → alert
 * - Prevents duplicate alerts within 30 minutes
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const CONFIG = {
  HEARTBEAT_STATE: path.join(__dirname, '../vault/state/heartbeat-state.json'),
  WATCHDOG_STATE: path.join(__dirname, '../vault/state/watchdog-state.json'),
  UNRESPONSIVE_THRESHOLD_MS: 10 * 60 * 1000, // 10 minutes
  DUPLICATE_ALERT_COOLDOWN_MS: 30 * 60 * 1000, // 30 minutes
  TELEGRAM_GROUP: '-1003242721592'
};

// Logging
function log(message, level = 'INFO') {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [WATCHDOG] [${level}] ${message}`);
}

// Load heartbeat state
function loadHeartbeatState() {
  try {
    if (!fs.existsSync(CONFIG.HEARTBEAT_STATE)) {
      log('No heartbeat state file found', 'WARN');
      return null;
    }
    
    const data = fs.readFileSync(CONFIG.HEARTBEAT_STATE, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    log(`Failed to load heartbeat state: ${error.message}`, 'ERROR');
    return null;
  }
}

// Load watchdog state (for duplicate prevention)
function loadWatchdogState() {
  try {
    if (!fs.existsSync(CONFIG.WATCHDOG_STATE)) {
      return { lastAlertAt: null };
    }
    
    const data = fs.readFileSync(CONFIG.WATCHDOG_STATE, 'utf8');
    return JSON.parse(data);
  } catch (error) {
    log(`Failed to load watchdog state: ${error.message}`, 'ERROR');
    return { lastAlertAt: null };
  }
}

// Save watchdog state
function saveWatchdogState(state) {
  try {
    fs.writeFileSync(CONFIG.WATCHDOG_STATE, JSON.stringify(state, null, 2));
  } catch (error) {
    log(`Failed to save watchdog state: ${error.message}`, 'ERROR');
  }
}

// Check if we should skip alert (duplicate prevention)
function shouldSkipAlert(watchdogState) {
  if (!watchdogState.lastAlertAt) {
    return false;
  }
  
  const timeSinceLastAlert = Date.now() - new Date(watchdogState.lastAlertAt).getTime();
  
  if (timeSinceLastAlert < CONFIG.DUPLICATE_ALERT_COOLDOWN_MS) {
    log(`Skipping alert (cooldown: ${Math.round(timeSinceLastAlert / 60000)}min ago)`, 'INFO');
    return true;
  }
  
  return false;
}

// Send unresponsive alert
function sendUnresponsiveAlert(lastHeartbeat, durationMinutes) {
  try {
    const message = `🚨 **Main Session Unresponsive**\n\n` +
      `**Duration:** ${durationMinutes} minutes\n` +
      `**Last Heartbeat:** ${lastHeartbeat}\n` +
      `**Time:** ${new Date().toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })}\n\n` +
      `*Possible causes: Crashed, hung, or network issue*`;
    
    // Send Telegram alert
    execSync(
      `clawdbot message send -t "${CONFIG.TELEGRAM_GROUP}" "${message.replace(/"/g, '\\"')}"`,
      { encoding: 'utf8', stdio: 'pipe' }
    );
    
    log('Sent Telegram alert', 'INFO');
    
    // Log to fallback system
    execSync(
      `node ${path.join(__dirname, 'fallback-alert.js')} WATCHDOG_UNRESPONSIVE "Main session unresponsive for ${durationMinutes} minutes" --severity=high`,
      { encoding: 'utf8', stdio: 'pipe' }
    );
    
    log('Logged to fallback system', 'INFO');
    
  } catch (error) {
    log(`Failed to send alert: ${error.message}`, 'ERROR');
  }
}

// Main execution
function main() {
  log('Starting unresponsive check...', 'INFO');
  
  // Step 1: Load heartbeat state
  const heartbeatState = loadHeartbeatState();
  
  if (!heartbeatState || !heartbeatState.lastHeartbeat) {
    log('No valid heartbeat state, skipping check', 'WARN');
    process.exit(0);
  }
  
  // Step 2: Check if heartbeat is stale
  const lastHeartbeatTime = new Date(heartbeatState.lastHeartbeat).getTime();
  const now = Date.now();
  const timeSinceHeartbeat = now - lastHeartbeatTime;
  
  log(`Last heartbeat: ${heartbeatState.lastHeartbeat} (${Math.round(timeSinceHeartbeat / 60000)}min ago)`, 'DEBUG');
  
  if (timeSinceHeartbeat < CONFIG.UNRESPONSIVE_THRESHOLD_MS) {
    log('Main session responsive, all good', 'INFO');
    
    // Clear watchdog state if session is responsive again
    saveWatchdogState({ lastAlertAt: null });
    
    process.exit(0);
  }
  
  // Step 3: Session is unresponsive - check if we should alert
  const watchdogState = loadWatchdogState();
  
  if (shouldSkipAlert(watchdogState)) {
    process.exit(0);
  }
  
  // Step 4: Send alert
  const durationMinutes = Math.round(timeSinceHeartbeat / 60000);
  log(`Main session unresponsive for ${durationMinutes} minutes!`, 'ERROR');
  
  sendUnresponsiveAlert(heartbeatState.lastHeartbeat, durationMinutes);
  
  // Step 5: Update watchdog state
  saveWatchdogState({ lastAlertAt: new Date().toISOString() });
  
  log('Watchdog check complete', 'INFO');
}

// Run
main();
