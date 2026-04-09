# daye-agent-toolkit Makefile
# Usage:
#   make install       # 플러그인 등록 + 규칙 심링크
#   make clean         # 플러그인 해제 + 심링크 제거
#   make status        # 설치 상태 확인

REPO_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RULES_DIR := $(HOME)/.claude/rules
MARKETPLACE_KEY := daye-agent-toolkit
PLUGINS := media-fetch,life-management,finance,dev-tools
MANAGE := python3 $(REPO_DIR)/scripts/manage_plugins.py

.PHONY: install clean status help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: _register-plugins _symlink-rules ## Install plugins + rules
	@echo ""
	@echo "Done. Run 'make status' to verify."

_register-plugins:
	@$(MANAGE) register $(MARKETPLACE_KEY) $(PLUGINS) $(REPO_DIR)

_symlink-rules:
	@echo "=== Symlink rules ==="
	@mkdir -p $(RULES_DIR)
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; \
		elif [ -e "$$dest" ]; then echo "  ! SKIPPED $$name (exists, not symlink)"; continue; \
		fi; \
		ln -s "$(REPO_DIR)/$$rule_file" "$$dest"; \
		echo "  + $$name"; \
	done

clean: ## Remove plugins + rules
	@$(MANAGE) unregister $(MARKETPLACE_KEY) $(PLUGINS)
	@echo ""
	@echo "=== Remove rules symlinks ==="
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; echo "  - removed $$name"; fi; \
	done

status: ## Show installation status
	@$(MANAGE) status $(MARKETPLACE_KEY) $(PLUGINS)
	@echo ""
	@echo "=== Rules ==="
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  + $$name"; \
		else echo "  x $$name (not installed)"; fi; \
	done
