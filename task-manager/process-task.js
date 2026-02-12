#!/usr/bin/env node
/**
 * Process Task - Helper to remove a task after spawning
 * Called by main agent after successfully spawning a task
 */

const fs = require('fs');
const path = require('path');

const PENDING_TASKS_FILE = path.join(__dirname, '../../vault/state/pending_tasks.json');

function removeFirstTask() {
  try {
    const data = fs.readFileSync(PENDING_TASKS_FILE, 'utf8');
    const tasks = JSON.parse(data);
    
    if (tasks.length === 0) {
      console.log('No tasks to remove');
      return;
    }
    
    const removed = tasks.shift();
    fs.writeFileSync(PENDING_TASKS_FILE, JSON.stringify(tasks, null, 2));
    
    console.log(`Removed task: ${removed.prompt?.substring(0, 50)}...`);
    console.log(`Remaining tasks: ${tasks.length}`);
  } catch (error) {
    console.error(`Failed to remove task: ${error.message}`);
    process.exit(1);
  }
}

removeFirstTask();
