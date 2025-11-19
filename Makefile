# ZWeb Service Makefile
.PHONY: install uninstall status enable disable

SERVICE_NAME := zweb
SERVICE_FILE := $(SERVICE_NAME).service
USER_SYSTEMD_DIR := $(HOME)/.config/systemd/user
INSTALL_DIR := $(HOME)/.local/bin
APP_DIR := $(HOME)/Zotero/zotero-web

# 检测 uv 路径
UV_PATH := $(shell which uv)

ifeq ($(UV_PATH),)
    UV_PATH := /usr/bin/uv
endif

# 检查 UV_PATH 指向的文件是否存在且可执行
ifneq ($(shell test -x "$(UV_PATH)" && echo exists), exists)
    $(error uv not found. Please install uv (https://github.com/astral-sh/uv) and ensure it's in PATH or at $(UV_PATH))
endif

# 生成服务文件内容
define SERVICE_CONTENT
[Unit]
Description=ZWeb Service
After=network.target

[Service]
Type=simple
ExecStart=$(UV_PATH) run python app.py
WorkingDirectory=$(APP_DIR)
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=default.target
endef

export SERVICE_CONTENT

install:
	@echo "正在安装 ZWeb 服务..."
	
	# 检查前置条件
	@if [ ! -d "$(APP_DIR)" ]; then \
		echo "错误: 应用目录 $(APP_DIR) 不存在"; \
		exit 1; \
	fi
	
	@if [ ! -f "$(APP_DIR)/app.py" ]; then \
		echo "错误: 在 $(APP_DIR) 中找不到 app.py"; \
		exit 1; \
	fi
	
	@if [ ! -x "$(UV_PATH)" ]; then \
		echo "警告: uv 命令不存在或不可执行，路径: $(UV_PATH)"; \
		echo "请先安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	
	# 创建必要的目录
	@mkdir -p $(USER_SYSTEMD_DIR)
	
	# 生成服务文件
	@echo "$$SERVICE_CONTENT" > $(USER_SYSTEMD_DIR)/$(SERVICE_FILE)
	
	# 重新加载 systemd
	@systemctl --user daemon-reload
	
	# 启用 linger（确保用户未登录时服务也能运行）
	@loginctl enable-linger $(USER) 2>/dev/null || true
	
	@echo "ZWeb 服务安装完成"
	@echo ""
	@echo "接下来可以运行:"
	@echo "  make enable    # 启用并启动服务"
	@echo "  make status    # 查看服务状态"

enable:
	@systemctl --user enable --now $(SERVICE_NAME)
	@echo "ZWeb 服务已启用并启动"

disable:
	@systemctl --user disable --now $(SERVICE_NAME) 2>/dev/null || true
	@echo "ZWeb 服务已禁用并停止"

status:
	@systemctl --user status $(SERVICE_NAME)

start:
	@systemctl --user start $(SERVICE_NAME)
	@echo "ZWeb 服务已启动"

stop:
	@systemctl --user stop $(SERVICE_NAME)
	@echo "ZWeb 服务已停止"

restart:
	@systemctl --user restart $(SERVICE_NAME)
	@echo "ZWeb 服务已重启"

logs:
	@journalctl --user-unit=$(SERVICE_NAME) -f

uninstall:
	@echo "正在卸载 ZWeb 服务..."
	@-systemctl --user stop $(SERVICE_NAME) 2>/dev/null
	@-systemctl --user disable $(SERVICE_NAME) 2>/dev/null
	@-rm -f $(USER_SYSTEMD_DIR)/$(SERVICE_FILE)
	@systemctl --user daemon-reload
	@echo "ZWeb 服务已卸载"

# 显示帮助信息
help:
	@echo "ZWeb 服务管理 Makefile"
	@echo ""
	@echo "可用命令:"
	@echo "  make install    - 安装服务（但不启用）"
	@echo "  make enable     - 启用并启动服务"
	@echo "  make disable    - 禁用并停止服务"
	@echo "  make uninstall  - 完全卸载服务"
	@echo "  make start      - 启动服务"
	@echo "  make stop       - 停止服务"
	@echo "  make restart    - 重启服务"
	@echo "  make status     - 查看服务状态"
	@echo "  make logs       - 查看服务日志"
	@echo "  make help       - 显示此帮助信息"