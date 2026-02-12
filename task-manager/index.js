#!/usr/bin/env node
/**
 * Task Manager - Auto-Resume System with Adaptive Model Selection
 * 
 * PURPOSE: Resume failed/interrupted tasks with appropriate model based on complexity
 * 
 * MODEL SELECTION:
 * - simple → gemini-flash or haiku (cheap, fast)
 * - moderate → sonnet (with user-quiet check)
 * - complex → opus (always, VIP lane protected)
 * 
 * VIP LANE: Max 3 concurrent tasks, system load safeguard (80% threshold)
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const CONFIG = {
  PENDING_TASKS_FILE: path.join(__dirname, '../../vault/state/pending_tasks.json'),
  LOCK_FILE: path.join(__dirname, '../../vault/state/task-manager.lock'),
  MAX_CONCURRENT_TASKS: 3, // VIP Lane protection (increased for parallel work)
  
  // Model selection by complexity
  MODELS: {
    simple: ['google-gemini-flash', 'claude-haiku-4-5'],
    moderate: 'claude-sonnet-4-5',
    complex: 'claude-opus-4-5' // Opus tier for complex work
  },
  
  MAX_LOAD_THRESHOLD: 80, // System load safeguard (percentage)
  
  // Retry logic with exponential backoff
  MAX_RETRY_ATTEMPTS: 3,
  RETRY_BACKOFF_BASE_MS: 60000, // 1 minute base delay
  RETRY_BACKOFF_MULTIPLIER: 2, // Exponential: 1min, 2min, 4min
};

// Logging utility
function log(message, level = 'INFO') {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [${level}] ${message}`);
}

// Check if another instance is running
function acquireLock() {
  if (fs.existsSync(CONFIG.LOCK_FILE)) {
    const lockAge = Date.now() - fs.statSync(CONFIG.LOCK_FILE).mtimeMs;
    if (lockAge < 60000) { // Lock valid for 1 minute
      log('Another task manager instance is running (lock exists)', 'WARN');
      return false;
    }
    log('Stale lock file detected, removing...', 'WARN');
    fs.unlinkSync(CONFIG.LOCK_FILE);
  }
  
  fs.writeFileSync(CONFIG.LOCK_FILE, String(process.pid));
  return true;
}

function releaseLock() {
  if (fs.existsSync(CONFIG.LOCK_FILE)) {
    fs.unlinkSync(CONFIG.LOCK_FILE);
  }
}

// Mock system load check (can be replaced with real metrics)
function checkSystemLoad() {
  const mockLoad = Math.random() * 100;
  log(`System load: ${mockLoad.toFixed(1)}%`, 'DEBUG');
  return mockLoad < CONFIG.MAX_LOAD_THRESHOLD;
}

// Count active background sessions
function getActiveSessions() {
  try {
    const output = execSync('clawdbot sessions --active 30 2>/dev/null || echo ""', { 
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'ignore']
    });
    
    // Count sessions (simple heuristic: count session lines)
    const sessionLines = output.split('\n').filter(line => 
      line.includes('agent:') && !line.includes('agent:main:main')
    );
    
    const count = sessionLines.length;
    log(`Active background sessions: ${count}`, 'DEBUG');
    return count;
  } catch (error) {
    log(`Failed to get sessions: ${error.message}`, 'ERROR');
    return 0;
  }
}

// Load pending tasks
function loadPendingTasks() {
  try {
    if (!fs.existsSync(CONFIG.PENDING_TASKS_FILE)) {
      log('No pending tasks file found, creating...', 'INFO');
      fs.writeFileSync(CONFIG.PENDING_TASKS_FILE, '[]');
      return [];
    }
    
    const data = fs.readFileSync(CONFIG.PENDING_TASKS_FILE, 'utf8');
    const tasks = JSON.parse(data);
    
    // Filter out tasks that are waiting for retry (nextRetryAt in future)
    const now = Date.now();
    const readyTasks = tasks.filter(task => {
      if (task.nextRetryAt && new Date(task.nextRetryAt).getTime() > now) {
        return false; // Still cooling down
      }
      return true;
    });
    
    log(`Loaded ${tasks.length} total task(s), ${readyTasks.length} ready now`, 'INFO');
    return readyTasks;
  } catch (error) {
    log(`Failed to load pending tasks: ${error.message}`, 'ERROR');
    return [];
  }
}

// Save pending tasks
function savePendingTasks(tasks) {
  try {
    fs.writeFileSync(
      CONFIG.PENDING_TASKS_FILE, 
      JSON.stringify(tasks, null, 2)
    );
    log(`Saved ${tasks.length} pending task(s)`, 'DEBUG');
  } catch (error) {
    log(`Failed to save pending tasks: ${error.message}`, 'ERROR');
  }
}

// Check if user is quiet (no recent activity in main session)
function isUserQuiet() {
  try {
    const output = execSync('clawdbot sessions --active 5 2>/dev/null || echo ""', { 
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'ignore']
    });
    
    // Check if main session has recent activity
    const hasMainActivity = output.includes('agent:main:main');
    log(`User quiet check: ${!hasMainActivity}`, 'DEBUG');
    return !hasMainActivity;
  } catch (error) {
    log(`User quiet check failed: ${error.message}`, 'DEBUG');
    return false; // Assume user is active if check fails
  }
}

// Select model based on task complexity
function selectModel(complexity) {
  const normalizedComplexity = (complexity || 'simple').toLowerCase();
  
  switch (normalizedComplexity) {
    case 'simple':
      // Use cheapest models
      return CONFIG.MODELS.simple[0]; // gemini-flash
      
    case 'moderate':
      // Use sonnet only if user is quiet
      if (isUserQuiet()) {
        log('Moderate task + user quiet → using sonnet', 'INFO');
        return CONFIG.MODELS.moderate;
      } else {
        log('Moderate task + user active → downgrading to simple model', 'INFO');
        return CONFIG.MODELS.simple[0];
      }
      
    case 'complex':
      // Always use opus (VIP lane protected)
      log('Complex task → using opus (VIP lane)', 'INFO');
      return CONFIG.MODELS.complex;
      
    default:
      log(`Unknown complexity "${complexity}", defaulting to simple`, 'WARN');
      return CONFIG.MODELS.simple[0];
  }
}

// Calculate next retry time with exponential backoff
function calculateNextRetry(attempts) {
  const backoffMs = CONFIG.RETRY_BACKOFF_BASE_MS * Math.pow(CONFIG.RETRY_BACKOFF_MULTIPLIER, attempts);
  return new Date(Date.now() + backoffMs).toISOString();
}

// Mark task as failed and schedule retry
function handleTaskFailure(task, error) {
  const attempts = (task.attempts || 0) + 1;
  const maxAttempts = task.maxAttempts || CONFIG.MAX_RETRY_ATTEMPTS;
  
  if (attempts >= maxAttempts) {
    log(`Task exceeded max attempts (${maxAttempts}), sending fallback alert`, 'ERROR');
    
    // Send fallback alert
    try {
      execSync(
        `node ${path.join(__dirname, '../../scripts/fallback-alert.js')} TASK_FAILED "${error}" --severity=high`,
        { encoding: 'utf8', stdio: 'pipe' }
      );
    } catch (alertError) {
      log(`Failed to send fallback alert: ${alertError.message}`, 'ERROR');
    }
    
    return null; // Remove from queue
  }
  
  // Schedule retry with exponential backoff
  const nextRetryAt = calculateNextRetry(attempts);
  
  log(`Task failed (attempt ${attempts}/${maxAttempts}), next retry: ${nextRetryAt}`, 'WARN');
  
  return {
    ...task,
    attempts: attempts,
    maxAttempts: maxAttempts,
    nextRetryAt: nextRetryAt,
    lastError: error
  };
}

// Get task recommendation for main agent
function getTaskRecommendation(task) {
  const prompt = task.prompt || task.description || task.task;
  
  if (!prompt) {
    return null;
  }
  
  const complexity = task.complexity || 'simple';
  const model = selectModel(complexity);
  
  // Initialize retry fields if not present
  const attempts = task.attempts || 0;
  const maxAttempts = task.maxAttempts || CONFIG.MAX_RETRY_ATTEMPTS;
  
  return {
    model: model,
    prompt: prompt,
    complexity: complexity,
    metadata: task.metadata || {},
    priority: task.priority || 1,
    attempts: attempts,
    maxAttempts: maxAttempts,
    lastError: task.lastError || null
  };
}

// Main execution
function main() {
  log('=== Task Manager: Auto-Resume System ===', 'INFO');
  
  // Step 1: Acquire lock
  if (!acquireLock()) {
    log('Cannot acquire lock, exiting', 'WARN');
    process.exit(0);
  }
  
  try {
    // Step 2: Load pending tasks
    const tasks = loadPendingTasks();
    
    if (tasks.length === 0) {
      log('No pending tasks to process', 'INFO');
      return;
    }
    
    // Step 3: Check system load (VIP Lane protection)
    if (!checkSystemLoad()) {
      log('System load too high, deferring task resume', 'WARN');
      return;
    }
    
    // Step 4: Check active sessions (concurrency limit)
    const activeCount = getActiveSessions();
    
    if (activeCount >= CONFIG.MAX_CONCURRENT_TASKS) {
      log(`Max concurrent tasks reached (${activeCount}/${CONFIG.MAX_CONCURRENT_TASKS})`, 'WARN');
      log('VIP Lane protected: deferring new tasks', 'INFO');
      
      // Output recommendation JSON for main agent
      console.log(JSON.stringify({
        status: 'DEFERRED',
        reason: 'concurrency_limit',
        pending_count: tasks.length,
        active_sessions: activeCount
      }));
      return;
    }
    
    // Step 5: Get task recommendation for main agent
    const taskToRun = tasks[0];
    log(`Processing task: ${JSON.stringify(taskToRun)}`, 'DEBUG');
    
    const recommendation = getTaskRecommendation(taskToRun);
    
    if (recommendation) {
      // Output recommendation for main agent to spawn
      console.log(JSON.stringify({
        status: 'READY',
        recommendation: recommendation,
        pending_count: tasks.length,
        message: `Ready to spawn task with ${recommendation.model}`
      }));
      
      log(`Recommendation ready: ${recommendation.model}`, 'INFO');
    } else {
      log('No valid task recommendation', 'ERROR');
    }
    
  } finally {
    releaseLock();
    log('=== Task Manager Complete ===', 'INFO');
  }
}

// Run if executed directly
if (require.main === module) {
  main();
}

module.exports = { 
  main, 
  loadPendingTasks, 
  savePendingTasks, 
  handleTaskFailure,
  calculateNextRetry 
};
