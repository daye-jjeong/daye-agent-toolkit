# daye-agent-toolkit Makefile
# Usage:
#   make install       # 플러그인 등록 + rules 심링크
#   make clean         # 등록 해제 + 심링크 제거
#   make status        # 설치 상태 확인

REPO_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RULES_DIR := $(HOME)/.claude/rules
SETTINGS := $(HOME)/.claude/settings.json
MARKETPLACE_NAME := daye-agent-toolkit
PLUGINS := life-management finance dev-tools media-fetch

.PHONY: install clean status help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: _register-marketplace _enable-plugins _symlink-rules ## Install plugins + rules
	@echo ""
	@echo "Done. Run 'make status' to verify."

_register-marketplace:
	@echo "=== Register local marketplace ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('$(SETTINGS)'); \
d = json.load(open(p)) if os.path.exists(p) else {}; \
m = d.setdefault('extraKnownMarketplaces', {}); \
m['$(MARKETPLACE_NAME)'] = {'source': {'source': 'directory', 'path': '$(REPO_DIR)'}}; \
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False); \
print('  ✓ $(MARKETPLACE_NAME) registered (path: $(REPO_DIR))')"

_enable-plugins:
	@echo "=== Enable plugins ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('$(SETTINGS)'); \
d = json.load(open(p)); \
ep = d.setdefault('enabledPlugins', {}); \
plugins = '$(PLUGINS)'.split(); \
for name in plugins: \
    key = f'{name}@$(MARKETPLACE_NAME)'; \
    ep[key] = True; \
    print(f'  ✓ {key}'); \
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False)"

_symlink-rules:
	@echo "=== Symlink rules ==="
	@mkdir -p $(RULES_DIR)
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; \
		elif [ -e "$$dest" ]; then echo "  ⚠ SKIPPED $$name (exists, not symlink)"; continue; \
		fi; \
		ln -s "$(REPO_DIR)/$$rule_file" "$$dest"; \
		echo "  ✓ $$name"; \
	done

clean: ## Remove plugins + rules
	@echo "=== Disable plugins ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('$(SETTINGS)'); \
d = json.load(open(p)) if os.path.exists(p) else {}; \
ep = d.get('enabledPlugins', {}); \
plugins = '$(PLUGINS)'.split(); \
for name in plugins: \
    key = f'{name}@$(MARKETPLACE_NAME)'; \
    if key in ep: del ep[key]; print(f'  ✓ removed {key}'); \
m = d.get('extraKnownMarketplaces', {}); \
if '$(MARKETPLACE_NAME)' in m: del m['$(MARKETPLACE_NAME)']; print('  ✓ marketplace removed'); \
json.dump(d, open(p, 'w'), indent=2, ensure_ascii=False)"
	@echo ""
	@echo "=== Remove rules symlinks ==="
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; echo "  ✓ removed $$name"; fi; \
	done
	@echo ""
	@echo "Note: Plugin hooks are auto-deregistered when plugins are disabled."

status: ## Show installation status
	@echo "=== Marketplace ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('$(SETTINGS)'); \
d = json.load(open(p)) if os.path.exists(p) else {}; \
m = d.get('extraKnownMarketplaces', {}); \
print('  ✓ registered' if '$(MARKETPLACE_NAME)' in m else '  ✗ not registered')"
	@echo ""
	@echo "=== Plugins ==="
	@python3 -c "\
import json, os; \
p = os.path.expanduser('$(SETTINGS)'); \
d = json.load(open(p)) if os.path.exists(p) else {}; \
ep = d.get('enabledPlugins', {}); \
plugins = '$(PLUGINS)'.split(); \
[print(f'  ✓ {n}' if ep.get(f'{n}@$(MARKETPLACE_NAME)') else f'  ✗ {n}') for n in plugins]"
	@echo ""
	@echo "=== Rules ==="
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  ✓ $$name"; \
		else echo "  ✗ $$name (not installed)"; fi; \
	done
