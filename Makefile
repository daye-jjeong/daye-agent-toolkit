# daye-agent-toolkit Makefile
# Usage:
#   make install       # 플러그인 등록 + 규칙 심링크
#   make clean         # 플러그인 해제 + 심링크 제거
#   make status        # 설치 상태 확인

REPO_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RULES_DIR := $(HOME)/.claude/rules
SKILLS_CC := $(HOME)/.claude/skills
SKILLS_CODEX := $(HOME)/.codex/skills
STANDALONE_SKILLS := mabinogi-mml
MARKETPLACE_KEY := daye-agent-toolkit
PLUGINS := media-fetch,life-management,finance,dev-tools
MANAGE := python3 $(REPO_DIR)/scripts/manage_plugins.py

.PHONY: install clean status help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: _register-plugins _symlink-rules _symlink-skills ## Install plugins + rules + skills
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

_symlink-skills:
	@echo "=== Symlink standalone skills (CC + Codex) ==="
	@for tgt in "$(SKILLS_CC)" "$(SKILLS_CODEX)"; do \
		mkdir -p "$$tgt"; \
		for s in $(STANDALONE_SKILLS); do \
			dest="$$tgt/$$s"; src="$(REPO_DIR)/skills/$$s"; \
			if [ -L "$$dest" ]; then rm "$$dest"; \
			elif [ -e "$$dest" ]; then echo "  ! CONFLICT $$s in $$tgt (exists, not symlink) — manual fix needed"; continue; \
			fi; \
			ln -s "$$src" "$$dest"; echo "  + $$s -> $$tgt"; \
		done; \
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
	@echo "=== Remove standalone skill symlinks ==="
	@for tgt in "$(SKILLS_CC)" "$(SKILLS_CODEX)"; do \
		for s in $(STANDALONE_SKILLS); do \
			dest="$$tgt/$$s"; \
			if [ -L "$$dest" ]; then rm "$$dest"; echo "  - removed $$s ($$tgt)"; fi; \
		done; \
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
	@echo "=== Standalone skills ==="
	@for tgt in "$(SKILLS_CC)" "$(SKILLS_CODEX)"; do \
		for s in $(STANDALONE_SKILLS); do \
			dest="$$tgt/$$s"; \
			if [ -L "$$dest" ]; then echo "  + $$s ($$tgt)"; \
			elif [ -e "$$dest" ]; then echo "  x $$s ($$tgt) — CONFLICT, not symlink"; \
			else echo "  x $$s ($$tgt) — not installed"; fi; \
		done; \
	done
