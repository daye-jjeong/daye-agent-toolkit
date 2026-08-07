# daye-agent-toolkit Makefile
# Usage:
#   make install       # 플러그인 등록 + 규칙 심링크
#   make clean         # 플러그인 해제 + 심링크 제거
#   make status        # 설치 상태 확인

REPO_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RULES_DIR := $(HOME)/.claude/rules
COMMANDS_DIR := $(HOME)/.claude/commands
HOOKS_DIR := $(HOME)/.claude/hooks
SKILLS_CC := $(HOME)/.claude/skills
SKILLS_CODEX := $(HOME)/.codex/skills
STANDALONE_SKILLS := mabinogi-mml
MARKETPLACE_KEY := daye-agent-toolkit
PLUGINS := media-fetch,life-management,finance,dev-tools
PLUGIN_CACHE := $(HOME)/.claude/plugins/cache/$(MARKETPLACE_KEY)
MANAGE := python3 $(REPO_DIR)/scripts/manage_plugins.py

.PHONY: install clean status help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: _register-plugins _purge-plugin-cache _symlink-rules _symlink-commands _symlink-hooks _symlink-skills ## Install plugins + rules + commands + hooks + skills
	@echo ""
	@echo "Done. Run 'make status' to verify."

_register-plugins:
	@$(MANAGE) register $(MARKETPLACE_KEY) $(PLUGINS) $(REPO_DIR)

# 플러그인 캐시는 원본의 복사본이고 원본을 따라오지 않는다(2026-08 실측: 4개월 낡음).
# 마켓플레이스가 source=directory 라 캐시가 없으면 CC가 레포 원본을 직접 읽는다.
# 그러니 만들지 않는 게 답이다 — 재생성되면 다음 make install 이 다시 지운다.
_purge-plugin-cache:
	@echo "=== Purge plugin cache ==="
	@if [ -d "$(PLUGIN_CACHE)" ]; then \
		rm -rf "$(PLUGIN_CACHE)"; \
		echo "  - removed $(PLUGIN_CACHE)"; \
	else \
		echo "  = no cache (CC reads repo directly)"; \
	fi

_symlink-rules:
	@echo "=== Symlink rules ==="
	@mkdir -p $(RULES_DIR)
	@for dest in $(RULES_DIR)/*.md; do \
		if [ -L "$$dest" ] && [ ! -e "$$dest" ]; then \
			rm "$$dest"; echo "  - $$(basename $$dest) (dangling)"; \
		fi; \
	done
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; \
		elif [ -e "$$dest" ]; then echo "  ! SKIPPED $$name (exists, not symlink)"; continue; \
		fi; \
		ln -s "$(REPO_DIR)/$$rule_file" "$$dest"; \
		echo "  + $$name"; \
	done

_symlink-commands:
	@echo "=== Symlink commands ==="
	@mkdir -p $(COMMANDS_DIR)
	@for dest in $(COMMANDS_DIR)/*.md; do \
		if [ -L "$$dest" ] && [ ! -e "$$dest" ]; then \
			rm "$$dest"; echo "  - $$(basename $$dest) (dangling)"; \
		fi; \
	done
	@for cmd_file in $$(find commands -name '*.md' 2>/dev/null); do \
		name=$$(basename $$cmd_file); \
		dest="$(COMMANDS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; \
		elif [ -e "$$dest" ]; then echo "  ! SKIPPED $$name (exists, not symlink)"; continue; \
		fi; \
		ln -s "$(REPO_DIR)/$$cmd_file" "$$dest"; \
		echo "  + $$name"; \
	done

_symlink-hooks:
	@echo "=== Symlink hooks ==="
	@mkdir -p $(HOOKS_DIR)
	@for dest in $(HOOKS_DIR)/*; do \
		if [ -L "$$dest" ] && [ ! -e "$$dest" ]; then \
			rm "$$dest"; echo "  - $$(basename $$dest) (dangling)"; \
		fi; \
	done
	@for hook_file in $$(find hooks -type f 2>/dev/null); do \
		name=$$(basename $$hook_file); \
		dest="$(HOOKS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; \
		elif [ -e "$$dest" ]; then echo "  ! SKIPPED $$name (exists, not symlink)"; continue; \
		fi; \
		ln -s "$(REPO_DIR)/$$hook_file" "$$dest"; \
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
	@echo "=== Remove command symlinks ==="
	@for cmd_file in $$(find commands -name '*.md' 2>/dev/null); do \
		name=$$(basename $$cmd_file); \
		dest="$(COMMANDS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then rm "$$dest"; echo "  - removed $$name"; fi; \
	done
	@echo "=== Remove hook symlinks ==="
	@for hook_file in $$(find hooks -type f 2>/dev/null); do \
		name=$$(basename $$hook_file); \
		dest="$(HOOKS_DIR)/$$name"; \
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
	@echo "=== Plugin cache ==="
	@if [ -d "$(PLUGIN_CACHE)" ]; then \
		echo "  x cache exists — stale copy shadows the repo. Run 'make install'"; \
		ls "$(PLUGIN_CACHE)" | sed 's/^/    /'; \
	else \
		echo "  + none (CC reads repo directly)"; \
	fi
	@echo ""
	@echo "=== Rules ==="
	@for rule_file in $$(find rules -name '*.md' 2>/dev/null); do \
		name=$$(basename $$rule_file); \
		dest="$(RULES_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  + $$name"; \
		else echo "  x $$name (not installed)"; fi; \
	done
	@echo "=== Commands ==="
	@for cmd_file in $$(find commands -name '*.md' 2>/dev/null); do \
		name=$$(basename $$cmd_file); \
		dest="$(COMMANDS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  + $$name"; \
		elif [ -e "$$dest" ]; then echo "  x $$name — CONFLICT, not symlink"; \
		else echo "  x $$name (not installed)"; fi; \
	done
	@echo "=== Hooks ==="
	@for hook_file in $$(find hooks -type f 2>/dev/null); do \
		name=$$(basename $$hook_file); \
		dest="$(HOOKS_DIR)/$$name"; \
		if [ -L "$$dest" ]; then echo "  + $$name"; \
		elif [ -e "$$dest" ]; then echo "  x $$name — CONFLICT, not symlink"; \
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
