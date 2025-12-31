// LiveToken Monitor - WebSocket 客户端和 UI 更新

class LiveTokenMonitor {
    constructor() {
        this.ws = null;
        this.activeRequests = new Map();
        this.history = [];
        this.maxDisplay = 20;
        this.reconnectDelay = 2000;
        this.connect();
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            this.reconnectDelay = 2000;
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleEvent(data);
            } catch (e) { }
        };

        this.ws.onclose = () => {
            setTimeout(() => this.connect(), this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
        };

        this.ws.onerror = () => { };
    }

    handleEvent(data) {
        switch (data.type) {
            case 'started':
                this.activeRequests.set(data.request_id, { ...data, startTime: Date.now() });
                break;
            case 'first_token':
            case 'progress':
                const req = this.activeRequests.get(data.request_id);
                if (req) Object.assign(req, data);
                break;
            case 'complete':
                const completeReq = this.activeRequests.get(data.request_id);
                if (completeReq) {
                    Object.assign(completeReq, data);
                    this.activeRequests.delete(data.request_id);
                    this.history.unshift(completeReq);
                    if (this.history.length > this.maxDisplay) this.history.pop();
                } else {
                    this.history.unshift(data);
                    if (this.history.length > this.maxDisplay) this.history.pop();
                }
                break;
            case 'error':
                const errReq = this.activeRequests.get(data.request_id);
                if (errReq) {
                    Object.assign(errReq, data, { error: true });
                    this.activeRequests.delete(data.request_id);
                    this.history.unshift(errReq);
                }
                break;
        }
        this.render();
        this.updateStats();
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    truncateModel(model) {
        if (!model) return 'unknown';
        if (model.length > 25) return model.slice(0, 22) + '...';
        return model;
    }

    formatTime(timestamp) {
        if (!timestamp) return '--';
        const date = new Date(timestamp * 1000);
        const hh = String(date.getHours()).padStart(2, '0');
        const mm = String(date.getMinutes()).padStart(2, '0');
        const ss = String(date.getSeconds()).padStart(2, '0');
        return `${hh}:${mm}:${ss}`;
    }

    renderRow(data, isActive) {
        const apiType = data.api_type || 'anthropic';
        const apiLabel = apiType === 'anthropic' ? 'ANT' : 'OAI';
        const ttft = data.ttft !== null && data.ttft !== undefined ? data.ttft.toFixed(2) : '--';
        const speed = data.speed ? data.speed.toFixed(1) : '0';
        const tokens = data.tokens || 0;
        const inputTokens = data.input_tokens || 0;
        const tokensEstimated = data.tokens_estimated !== false;
        const tokenClass = tokensEstimated ? 'tokens-estimated' : 'tokens-accurate';

        let statusHtml = '';
        if (data.error) {
            statusHtml = '<span class="status-error">错误</span>';
        } else if (isActive) {
            statusHtml = '<span class="status-active">进行中</span>';
        } else {
            statusHtml = '<span class="status-done">完成</span>';
        }

        const inputPart = inputTokens ? ` <span style="color:#8b949e;font-size:10px">(in:${inputTokens})</span>` : '';

        // 时间列：开始时间 ~ 结束时间
        const startTime = this.formatTime(data.start_time);
        const endTime = this.formatTime(data.end_time);
        const timeDisplay = isActive ? startTime : `${startTime} ~ ${endTime}`;

        return `
            <tr class="${apiType}" data-request-id="${this.escapeHtml(data.request_id)}">
                <td class="col-id">
                    <span class="badge ${apiType}">${apiLabel}</span>
                    ${this.escapeHtml(data.request_id)}
                </td>
                <td class="col-model">${this.escapeHtml(this.truncateModel(data.model))}</td>
                <td class="col-status">${statusHtml}</td>
                <td class="col-time">${timeDisplay}</td>
                <td>${ttft}s</td>
                <td class="${tokenClass}">${tokens}${inputPart}</td>
                <td class="col-speed">${speed} t/s</td>
            </tr>
        `;
    }

    render() {
        const tbody = document.getElementById('requests-body');

        const allRequests = [
            ...Array.from(this.activeRequests.values()).map(r => ({ ...r, isActive: true })),
            ...this.history.map(r => ({ ...r, isActive: false }))
        ];

        if (allRequests.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty">暂无请求</td></tr>';
            return;
        }

        tbody.innerHTML = allRequests.map(req => this.renderRow(req, req.isActive)).join('');

        // 绑定点击事件
        tbody.querySelectorAll('tr[data-request-id]').forEach(row => {
            row.style.cursor = 'pointer';
            row.onclick = () => showDetail(row.dataset.requestId);
        });
    }

    updateStats() {
        const total = this.history.length;
        const completed = this.history.filter(r => r.ttft !== null && r.ttft !== undefined);

        const avgTtft = completed.length > 0
            ? (completed.reduce((sum, r) => sum + (r.ttft || 0), 0) / completed.length).toFixed(2)
            : '0';

        const avgSpeed = total > 0
            ? (this.history.reduce((sum, r) => sum + (r.speed || 0), 0) / total).toFixed(1)
            : '0';

        document.getElementById('total-requests').textContent = total;
        document.getElementById('avg-ttft').textContent = avgTtft;
        document.getElementById('avg-speed').textContent = avgSpeed;
    }
}

// 启动监控
const monitor = new LiveTokenMonitor();

// 清除历史
async function clearHistory() {
    try {
        const res = await fetch('/api/clear-history', { method: 'POST' });
        const data = await res.json();
        monitor.history = [];
        monitor.render();
        monitor.updateStats();
    } catch (e) {
        alert('清除失败');
    }
}

// 显示详情
async function showDetail(requestId) {
    const modal = document.getElementById('modal');
    const modalBody = document.getElementById('modal-body');

    modalBody.innerHTML = '<p style="text-align:center;color:#8b949e;">加载中...</p>';
    modal.classList.add('show');

    try {
        const res = await fetch(`/api/request/${requestId}`);
        if (!res.ok) {
            modalBody.innerHTML = `<p style="text-align:center;color:#f85149;">请求不存在 (ID: ${escapeHtml(requestId)})</p>`;
            return;
        }

        const data = await res.json();

        // 格式化请求体（解析视图）
        let requestText = '';
        if (data.request_body) {
            const requestBody = data.request_body;

            // 先显示 system prompt（如果有）
            if (requestBody.system && requestBody.system.length > 0) {
                const systemContent = requestBody.system.map(item => {
                    if (typeof item === 'string') {
                        return `<div class="msg-block"><div class="msg-header">系统提示</div><div class="msg-simple-content">${escapeHtml(item)}</div></div>`;
                    } else if (typeof item === 'object') {
                        const type = item.type || 'text';
                        const text = item.text || '';
                        const cacheControl = item.cache_control ? ` <span class="msg-meta">(ephemeral)</span>` : '';
                        return `<div class="msg-block"><div class="msg-header">系统提示</div><table class="msg-table"><tbody><tr><td class="msg-meta">type</td><td class="msg-meta">${escapeHtml(type)}</td></tr></tbody></table><div class="msg-content">${escapeHtml(text)}${cacheControl}</div></div>`;
                    }
                }).join('');
                requestText = systemContent;
            }

            // 然后显示 messages
            if (requestBody.messages) {
                // 以 HTML 表格形式展示 messages
                const messagesHtml = requestBody.messages.map((m) => {
                    const role = m.role || 'unknown';
                    const roleLabel = role === 'user' ? '用户' : role === 'assistant' ? '助手' : role;
                    const content = m.content;

                    // 如果 content 是数组（多模态）
                    if (Array.isArray(content)) {
                        const contentParts = content.map(item => {
                            const type = item.type || 'text';
                            if (type === 'text') {
                                const text = item.text || '';
                                const cacheControl = item.cache_control ? ` <span class="msg-meta">(ephemeral)</span>` : '';
                                return `<table class="msg-table"><tbody><tr><td class="msg-meta">type</td><td class="msg-meta">text</td></tr></tbody></table><div class="msg-content">${escapeHtml(text)}${cacheControl}</div>`;
                            } else if (type === 'thinking') {
                                const thinking = item.thinking || '';
                                const signature = item.signature ? ` <span class="msg-meta">sig: ${escapeHtml(item.signature).slice(0, 8)}</span>` : '';
                                return `<table class="msg-table"><tbody><tr><td class="msg-meta">type</td><td class="msg-meta">thinking</td></tr></tbody></table><div class="msg-content msg-thinking">${escapeHtml(thinking)}${signature}</div>`;
                            } else if (type === 'image') {
                                const source = item.source || {};
                                return `<table class="msg-table"><tbody><tr><td class="msg-meta">type</td><td class="msg-meta">image</td></tr></tbody></table><div class="msg-content msg-meta-text">${escapeHtml(JSON.stringify(source))}</div>`;
                            } else {
                                return `<table class="msg-table"><tbody><tr><td class="msg-meta">type</td><td class="msg-meta">${escapeHtml(type)}</td></tr></tbody></table><div class="msg-content msg-meta-text">${escapeHtml(JSON.stringify(item))}</div>`;
                            }
                        }).join('');
                        return `<div class="msg-block"><div class="msg-header">${roleLabel}</div>${contentParts}</div>`;
                    } else {
                        // 简单文本内容
                        return `<div class="msg-block"><div class="msg-header">${roleLabel}</div><div class="msg-simple-content">${escapeHtml(String(content))}</div></div>`;
                    }
                }).join('');
                requestText += messagesHtml;
            } else if (requestBody.prompt) {
                requestText += `<div class="msg-simple-content">${escapeHtml(requestBody.prompt)}</div>`;
            } else {
                requestText += `<pre class="msg-json">${escapeHtml(JSON.stringify(requestBody, null, 2))}</pre>`;
            }
        }

        // 响应文本
        const responseText = data.response_text || '(无)';

        // 原始 JSON
        const requestRaw = data.request_body ? JSON.stringify(data.request_body, null, 2) : '{}';
        const responseRaw = data.response_text || '(无)';

        // 元数据
        const metaGrid = `
            <div class="detail-grid">
                <div class="detail-row"><span>请求 ID:</span><span>${escapeHtml(data.request_id)}</span></div>
                <div class="detail-row"><span>API 类型:</span><span>${data.api_type}</span></div>
                <div class="detail-row"><span>模型:</span><span>${escapeHtml(data.model)}</span></div>
                <div class="detail-row"><span>TTFT:</span><span>${data.ttft || '--'}s</span></div>
                <div class="detail-row"><span>耗时:</span><span>${data.duration}s</span></div>
                <div class="detail-row"><span>速度:</span><span>${data.speed} t/s</span></div>
                <div class="detail-row"><span>输入 Tokens:</span><span>${data.input_tokens || 0}</span></div>
                <div class="detail-row"><span>输出 Tokens:</span><span>${data.output_tokens || 0} ${data.tokens_estimated ? '(估算)' : '(精确)'}</span></div>
            </div>
        `;

        // 渲染请求头和响应头
        const requestHeadersHtml = renderHeaders(data.request_headers, '请求头');
        const responseHeadersHtml = renderHeaders(data.response_headers, '响应头');

        modalBody.innerHTML = `
            <div class="modal-layout">
                <div class="modal-left">
                    ${requestHeadersHtml}
                    ${responseHeadersHtml}
                </div>
                <div class="modal-resizer"></div>
                <div class="modal-right">
                    <div class="detail-section">
                        <div class="detail-label">元数据</div>
                        ${metaGrid}
                    </div>
                    <div class="detail-section">
                        <div class="detail-label-with-toggle">
                            <span>输入</span>
                            <button class="view-toggle" data-type="request">查看 Raw</button>
                        </div>
                        <div class="detail-content" id="request-input">${requestText}</div>
                    </div>
                    <div class="detail-section">
                        <div class="detail-label-with-toggle">
                            <span>输出</span>
                            <button class="view-toggle" data-type="response">查看 Raw</button>
                        </div>
                        <div class="detail-content" id="response-output">${escapeHtml(responseText)}</div>
                    </div>
                </div>
            </div>
        `;

        // 将完整数据存储在模态框元素上（不是 HTML 属性）
        modalBody._requestData = {
            requestRaw,
            requestText,
            responseRaw,
            responseText
        };

        // 绑定切换按钮事件
        modalBody.querySelectorAll('.view-toggle').forEach(btn => {
            btn.addEventListener('click', () => {
                const type = btn.dataset.type;
                const data = modalBody._requestData;
                const isRaw = btn.classList.contains('active');

                if (type === 'request') {
                    const content = document.getElementById('request-input');
                    if (isRaw) {
                        content.innerHTML = data.requestText;
                        btn.classList.remove('active');
                        btn.textContent = '查看 Raw';
                    } else {
                        content.textContent = data.requestRaw;
                        btn.classList.add('active');
                        btn.textContent = '查看解析';
                    }
                } else {
                    const content = document.getElementById('response-output');
                    if (isRaw) {
                        content.textContent = data.responseText;
                        btn.classList.remove('active');
                        btn.textContent = '查看 Raw';
                    } else {
                        content.textContent = data.responseRaw;
                        btn.classList.add('active');
                        btn.textContent = '查看解析';
                    }
                }
            });
        });

        // 分隔条拖动功能
        const resizer = modalBody.querySelector('.modal-resizer');
        const leftPanel = modalBody.querySelector('.modal-left');
        const layout = modalBody.querySelector('.modal-layout');

        if (resizer && leftPanel && layout) {
            let isResizing = false;

            resizer.addEventListener('mousedown', () => {
                isResizing = true;
                resizer.classList.add('active');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';
            });

            document.addEventListener('mousemove', (e) => {
                if (!isResizing) return;

                const rect = layout.getBoundingClientRect();
                const newWidth = e.clientX - rect.left;

                // 限制最小/最大宽度
                if (newWidth >= 200 && newWidth <= rect.width - 400) {
                    leftPanel.style.width = newWidth + 'px';
                }
            });

            document.addEventListener('mouseup', () => {
                if (isResizing) {
                    isResizing = false;
                    resizer.classList.remove('active');
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';
                }
            });
        }

    } catch (e) {
        modalBody.innerHTML = '<p style="text-align:center;color:#f85149;">加载失败</p>';
    }
}

// 关闭模态框
function closeModal() {
    document.getElementById('modal').classList.remove('show');
}

// 点击背景关闭
document.getElementById('modal').addEventListener('click', (e) => {
    if (e.target.id === 'modal') closeModal();
});

// ESC 关闭
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 渲染请求头/响应头表格
function renderHeaders(headers, label) {
    if (!headers || Object.keys(headers).length === 0) {
        return '';
    }

    const rows = Object.entries(headers).map(([key, value]) => {
        const escapedKey = escapeHtml(key);
        const escapedValue = escapeHtml(String(value));
        return `
            <tr class="header-row">
                <td class="header-key">${escapedKey}</td>
                <td class="header-value">${escapedValue}</td>
            </tr>
        `;
    }).join('');

    return `
        <div class="detail-section">
            <div class="detail-label">${label} <span class="header-count">(${Object.keys(headers).length})</span></div>
            <table class="headers-table">
                <thead>
                    <tr>
                        <th>名称</th>
                        <th>值</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}
