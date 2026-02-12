#!/bin/bash
# Add a task to the pending queue
# Usage: ./add-task.sh "Task description or prompt"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASKS_FILE="$SCRIPT_DIR/../../vault/state/pending_tasks.json"

if [ $# -eq 0 ]; then
  echo "Usage: $0 \"task prompt\""
  exit 1
fi

PROMPT="$1"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Read existing tasks
if [ ! -f "$TASKS_FILE" ]; then
  echo "[]" > "$TASKS_FILE"
fi

# Add new task using Node.js
node -e "
const fs = require('fs');
const tasks = JSON.parse(fs.readFileSync('$TASKS_FILE', 'utf8'));
tasks.push({
  prompt: '$PROMPT',
  priority: 1,
  added_at: '$TIMESTAMP',
  metadata: {
    source: 'manual',
    retry_count: 0
  }
});
fs.writeFileSync('$TASKS_FILE', JSON.stringify(tasks, null, 2));
console.log('✅ Task added to queue');
console.log('Total pending:', tasks.length);
"
