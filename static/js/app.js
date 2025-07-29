// FastAPI 多人配音生成器 - 前端应用

class VoiceGeneratorApp {
    constructor() {
        this.websocket = null;
        this.clientId = null;
        this.isGenerating = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.config = null;
        this.init();
    }

    init() {
        this.generateClientId();
        this.bindEvents();
        // this.loadSampleFiles(); // 已移除样例文件区域
        this.loadConfig();
        this.setupWebSocket();
        this.updateStatus('准备就绪', 'success');
        
        // 添加页面卸载时的清理逻辑
        window.addEventListener('beforeunload', () => {
            console.log('页面即将卸载，清理资源...');
            if (this.websocket) {
                this.websocket.close();
            }
        });
        
        // 添加页面隐藏时的清理逻辑（移动端）
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') {
                console.log('页面隐藏，准备清理...');
                if (this.websocket) {
                    this.websocket.close();
                }
            }
        });
    }

    generateClientId() {
        this.clientId = 'client_' + Math.random().toString(36).substr(2, 9);
    }

    async loadConfig() {
        try {
            console.log('开始加载配置...');
            const response = await fetch('/api/config');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            this.config = await response.json();
            console.log('配置加载成功:', this.config);
            
            this.renderLanguageOptions();
            this.renderVoiceMapping();
            this.addLog('info', '配置加载完成', `支持 ${this.config.languages.length} 种语言，${Object.keys(this.config.voices || {}).length} 个角色配置`);
        } catch (error) {
            console.error('配置加载失败:', error);
            this.addLog('error', '配置加载失败', error.message);
            // 添加默认语言选项
            this.setDefaultLanguageOptions();
            // 添加默认语音映射
            this.setDefaultVoiceMapping();
        }
    }

    renderLanguageOptions() {
        const languageSelect = document.getElementById('language');
        if (!languageSelect) {
            console.error('未找到语言选择元素');
            return;
        }
        
        languageSelect.innerHTML = '';
        
        if (!this.config || !this.config.languages) {
            console.error('配置数据不完整');
            this.setDefaultLanguageOptions();
            return;
        }
        
        this.config.languages.forEach(lang => {
            const option = document.createElement('option');
            option.value = lang;
            option.textContent = lang;
            if (lang === 'auto') {
                option.selected = true;
            }
            languageSelect.appendChild(option);
        });
        
        console.log(`已添加 ${this.config.languages.length} 种语言选项`);
    }

    setDefaultLanguageOptions() {
        const languageSelect = document.getElementById('language');
        if (!languageSelect) return;
        
        const defaultLanguages = ['auto', 'Chinese', 'English', 'Japanese', 'Korean'];
        languageSelect.innerHTML = '';
        
        defaultLanguages.forEach(lang => {
            const option = document.createElement('option');
            option.value = lang;
            option.textContent = lang;
            if (lang === 'auto') {
                option.selected = true;
            }
            languageSelect.appendChild(option);
        });
        
        this.addLog('warning', '使用默认语言选项', `已添加 ${defaultLanguages.length} 种语言`);
    }

    renderVoiceMapping() {
        // 角色语音配置现在使用静态HTML，不需要动态生成
        console.log('角色语音配置使用静态HTML，跳过动态生成');
    }

    createVoiceMappingRow(speaker, voiceId) {
        const row = document.createElement('div');
        row.className = 'row mb-3 voice-mapping-row align-items-center';
        
        row.innerHTML = `
            <div class="col-3">
                <span class="badge speaker-badge w-100 text-center">${speaker}</span>
            </div>
            <div class="col-9">
                <input type="text" class="form-control voice-input" 
                       value="${voiceId}" 
                       placeholder="输入语音ID"
                       data-speaker="${speaker}">
            </div>
        `;
        
        return row;
    }

    setDefaultVoiceMapping() {
        // 角色语音配置现在使用静态HTML，不需要动态生成
        console.log('角色语音配置使用静态HTML，跳过默认配置生成');
    }

    bindEvents() {
        // 表单提交事件
        document.getElementById('configForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startGeneration();
        });

        // 生成按钮事件
        document.getElementById('generateBtn').addEventListener('click', (e) => {
            e.preventDefault();
            this.startGeneration();
        });

        // 清空日志事件
        document.getElementById('clearLogsBtn').addEventListener('click', () => {
            this.clearLogs();
        });

        // 下载按钮事件
        document.getElementById('downloadBtn').addEventListener('click', () => {
            this.downloadAudio();
        });

        // 文件选择事件（隐藏的文件输入）
        const subtitleFileInput = document.getElementById('subtitleFile');
        if (subtitleFileInput) {
            subtitleFileInput.addEventListener('change', (e) => {
                this.handleFileSelect(e);
            });
        }

        // 角色配置折叠事件（如果存在的话）
        const toggleVoiceMapping = document.getElementById('toggleVoiceMapping');
        if (toggleVoiceMapping) {
            toggleVoiceMapping.addEventListener('click', () => {
                this.toggleVoiceMapping();
            });
        }

        // 日志搜索事件（如果存在的话）
        const logSearch = document.getElementById('logSearch');
        if (logSearch) {
            logSearch.addEventListener('input', (e) => {
                this.filterLogs();
            });
        }

        // 日志过滤事件（如果存在的话）
        const logFilter = document.getElementById('logFilter');
        if (logFilter) {
            logFilter.addEventListener('change', (e) => {
                this.filterLogs();
            });
        }
    }

    setupWebSocket() {
        if (this.websocket) {
            this.websocket.close();
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.clientId}`;
        
        try {
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('WebSocket连接成功');
                this.addLog('success', 'WebSocket连接成功', '实时日志已启用');
                this.reconnectAttempts = 0;
            };

            this.websocket.onclose = (event) => {
                console.log('WebSocket连接断开', event);
                this.addLog('warning', 'WebSocket断开', '实时日志已禁用');
                
                // 自动重连
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    setTimeout(() => {
                        this.addLog('info', '尝试重连', `第 ${this.reconnectAttempts} 次重连`);
                        this.setupWebSocket();
                    }, 3000 * this.reconnectAttempts);
                }
            };

            this.websocket.onerror = (error) => {
                console.error('WebSocket错误:', error);
                this.addLog('error', 'WebSocket错误', '连接失败');
            };

            this.websocket.onmessage = (event) => {
                try {
                    // 处理心跳ping消息
                    if (event.data === 'ping') {
                        this.websocket.send('pong');
                        return;
                    }
                    
                    const logData = JSON.parse(event.data);
                    this.handleWebSocketMessage(logData);
                } catch (error) {
                    console.error('解析WebSocket消息失败:', error);
                }
            };

        } catch (error) {
            console.error('创建WebSocket连接失败:', error);
            this.addLog('error', 'WebSocket连接失败', error.message);
        }
    }

    handleWebSocketMessage(logData) {
        const level = logData.level || 'info';
        const message = logData.message || '';
        const details = logData.details || '';
        
        this.addLog(level, message, details);
        
        // 如果有进度信息，更新进度
        if (logData.progress !== undefined) {
            this.updateProgress(logData.progress, message);
        }
    }

    updateProgress(progress, statusText = '') {
        const progressCard = document.getElementById('progressCard');
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        const progressStatus = document.getElementById('progressStatus');
        
        // 检查progress是否为有效数字
        if (progress !== null && progress !== undefined && !isNaN(progress) && progress >= 0 && progress <= 100) {
            // 显示进度卡片
            progressCard.style.display = 'block';
            
            // 更新进度条
            progressBar.style.width = `${progress}%`;
            progressText.textContent = `${progress}%`;
            
            // 更新状态文本
            if (statusText) {
                progressStatus.textContent = statusText;
            }
            
            // 更新顶部状态 - 只有当progress不为null和undefined时才显示
            if (progress !== null && progress !== undefined && !isNaN(progress)) {
                this.updateStatus(`进度: ${progress}%`, 'primary');
            }
            
            // 如果完成，自动隐藏进度卡片
            if (progress >= 100) {
                setTimeout(() => {
                    progressCard.style.display = 'none';
                }, 3000);
            }
        }
    }

    /* 已移除样例文件功能
    async loadSampleFiles() {
        try {
            const response = await fetch('/api/sample-files');
            const data = await response.json();
            
            if (data.files && data.files.length > 0) {
                this.renderSampleFiles(data.files);
                this.addLog('info', '样例文件加载', `找到 ${data.files.length} 个样例文件`);
            } else {
                this.addLog('warning', '样例文件', '没有可用的样例文件');
            }
        } catch (error) {
            this.addLog('error', '加载样例文件失败', error.message);
        }
    }

    renderSampleFiles(files) {
        const container = document.getElementById('sampleFiles');
        container.innerHTML = '';

        files.forEach(file => {
            const button = document.createElement('a');
            button.href = file.url;
            button.download = file.name;
            button.className = 'btn btn-outline-secondary btn-sm sample-file-btn';
            button.innerHTML = `<i class="bi bi-download me-1"></i>${file.description}`;
            button.title = `下载 ${file.name} (${this.formatFileSize(file.size)})`;
            
            container.appendChild(button);
        });
    }
    */

    async startGeneration() {
        console.log('startGeneration called'); // 调试用
        this.addLog('info', '调试：开始生成函数被调用', '开始执行生成流程');
        
        if (this.isGenerating) {
            this.addLog('warning', '生成中', '请等待当前任务完成');
            return;
        }

        // 验证表单
        this.addLog('info', '调试：开始验证表单', '检查必填字段');
        if (!this.validateForm()) {
            this.addLog('error', '调试：表单验证失败', '停止执行');
            return;
        }
        this.addLog('info', '调试：表单验证通过', '继续执行');

        this.isGenerating = true;
        this.updateStatus('生成中...', 'warning');
        this.disableGenerateButton(true);
        this.showProgress(0, '准备开始...');
        this.addLog('info', '开始生成', '正在准备参数...');

        try {
            const formData = this.getFormData();
            
            // 调试信息：检查文件是否正确选择
            const fileInput = document.getElementById('subtitleFile');
            const selectedFile = fileInput.files[0];
            if (selectedFile) {
                this.addLog('info', '文件确认', `文件名: ${selectedFile.name}, 大小: ${this.formatFileSize(selectedFile.size)}`);
            } else {
                this.addLog('error', '文件选择错误', '没有检测到选择的文件');
                return;
            }

            const response = await fetch('/api/generate-audio', {
                method: 'POST',
                body: formData
            });

            // 检查响应状态
            if (!response.ok) {
                // 尝试解析错误信息
                let errorMessage = `HTTP ${response.status} ${response.statusText}`;
                try {
                    const errorResult = await response.json();
                    errorMessage = errorResult.detail || errorResult.message || errorMessage;
                } catch (jsonError) {
                    // 如果无法解析JSON，尝试获取文本内容
                    try {
                        const errorText = await response.text();
                        if (errorText) {
                            errorMessage = errorText;
                        }
                    } catch (textError) {
                        // 如果连文本都无法获取，使用默认错误信息
                    }
                }
                this.handleGenerationError(errorMessage);
                return;
            }

            const result = await response.json();

            if (result.success) {
                this.updateProgress(100, '处理完成');
                this.handleGenerationSuccess(result);
            } else {
                this.handleGenerationError(result.detail || result.message || '未知错误');
            }
        } catch (error) {
            this.handleGenerationError(error.message);
        } finally {
            this.isGenerating = false;
            this.disableGenerateButton(false);
            this.updateStatus('准备就绪', 'success');
        }
    }

    showProgress(progress, statusText) {
        this.updateProgress(progress, statusText);
    }

    validateForm() {
        const groupId = document.getElementById('groupId').value.trim();
        const apiKey = document.getElementById('apiKey').value.trim();
        const subtitleFile = document.getElementById('subtitleFile').files[0];
        const voiceModel = document.getElementById('voiceModel').value.trim();

        if (!groupId) {
            this.addLog('error', '验证失败', '请输入Group ID');
            document.getElementById('groupId').focus();
            return false;
        }

        if (!apiKey) {
            this.addLog('error', '验证失败', '请输入API Key');
            document.getElementById('apiKey').focus();
            return false;
        }

        if (!voiceModel) {
            this.addLog('error', '验证失败', '请输入语音模型');
            document.getElementById('voiceModel').focus();
            return false;
        }

        if (!subtitleFile) {
            this.addLog('error', '验证失败', '请选择字幕文件');
            document.getElementById('subtitleFile').focus();
            return false;
        }

        const fileName = subtitleFile.name.toLowerCase();
        if (!fileName.endsWith('.srt') && !fileName.endsWith('.txt')) {
            this.addLog('error', '文件格式错误', '只支持.srt和.txt格式的字幕文件');
            return false;
        }

        // 检查文件大小 (10MB)
        if (subtitleFile.size > 10 * 1024 * 1024) {
            this.addLog('error', '文件过大', '文件大小不能超过10MB');
            return false;
        }

        return true;
    }

    getFormData() {
        const formData = new FormData();
        
        // API配置
        formData.append('groupId', document.getElementById('groupId').value.trim());
        formData.append('apiKey', document.getElementById('apiKey').value.trim());
        
        // 基本配置
        formData.append('model', document.getElementById('voiceModel').value.trim());
        formData.append('language', document.getElementById('language').value);
        
        // 字幕文件
        const subtitleFile = document.getElementById('subtitleFile').files[0];
        formData.append('file', subtitleFile);
        
        // 语音映射
        const voiceMapping = this.getVoiceMapping();
        formData.append('voiceMapping', JSON.stringify(voiceMapping));
        
        // 客户端ID
        formData.append('clientId', this.clientId);

        return formData;
    }

    getVoiceMapping() {
        const mapping = {};
        const rows = document.querySelectorAll('.voice-mapping-row');
        
        rows.forEach(row => {
            const speakerBadge = row.querySelector('.badge');
            const voiceInput = row.querySelector('.voice-input');
            
            if (speakerBadge && voiceInput) {
                const speaker = speakerBadge.textContent.trim();
                const voice = voiceInput.value.trim();
                
                if (speaker && voice) {
                    mapping[speaker] = voice;
                }
            }
        });

        return mapping;
    }

    handleGenerationSuccess(result) {
        this.addLog('success', '生成完成!', `文件: ${result.output_file}`);
        this.showAudioResult(result.download_url, result.output_file);
        
        // 显示统计信息
        if (result.statistics) {
            const stats = result.statistics;
            this.addLog('info', '统计信息', 
                `总段落: ${stats.total_segments}, 平均长度: ${Math.round(stats.average_segment_length)} 字符`);
            
            // 显示速度调整信息
            if (stats.speed_adjustments > 0) {
                this.addLog('info', '速度调整统计', 
                    `共 ${stats.speed_adjustments} 个段落需要调整, 失败: ${stats.failed_segments} 个`);
                
                // 显示详细的速度调整列表
                if (stats.speed_details && Object.keys(stats.speed_details).length > 0) {
                    const speedDetails = Object.entries(stats.speed_details)
                        .map(([index, adjustment]) => `${index}  ${adjustment}`)
                        .join('\n');
                    this.addLog('info', '速度调整详情', speedDetails);
                }
            } else {
                this.addLog('success', '时长匹配', '所有段落均无需调整速度');
            }
        }
    }

    handleGenerationError(error) {
        this.addLog('error', '生成失败', error);
        // 隐藏进度卡片
        document.getElementById('progressCard').style.display = 'none';
    }

    showAudioResult(audioUrl, filename) {
        // 使用新的音频播放器结构
        const mergeResultCard = document.getElementById('mergeResultCard');
        const downloadAudioBtn = document.getElementById('downloadAudioBtn');
        const mergePlayBtn = document.getElementById('mergePlayBtn');
        const audioStatus = document.getElementById('audioStatus');
        const mergeDownloadBtn = document.getElementById('mergeDownloadBtn');

        if (!mergeResultCard || !downloadAudioBtn || !mergePlayBtn || !audioStatus) {
            console.error('音频播放器元素未找到');
            return;
        }

        // 显示音频结果卡片
        mergeResultCard.style.display = 'block';

        // 设置隐藏的下载链接
        if (mergeDownloadBtn) {
            mergeDownloadBtn.href = audioUrl;
            mergeDownloadBtn.download = filename;
        }

        // 启用下载按钮
        downloadAudioBtn.disabled = false;

        // 设置播放按钮
        mergePlayBtn.disabled = false;

        // 更新状态信息
        audioStatus.innerHTML = `
            <small class="text-success">
                <i class="bi bi-check-circle me-1"></i>
                音频文件已生成: ${filename}
            </small>
        `;

        // 创建结果对象，模拟merge API的返回格式
        const result = {
            output_file: filename,
            download_url: audioUrl,
            segments_count: 1, // 默认值
            total_duration_ms: 0 // 默认值
        };

        // 调用HTML中的showMergeResult函数（如果存在）
        if (typeof showMergeResult === 'function') {
            showMergeResult(result);
        }

        // 滚动到音频区域
        mergeResultCard.scrollIntoView({ behavior: 'smooth' });
        
        this.addLog('success', '音频文件就绪', `文件: ${filename}, 下载地址: ${audioUrl}`);
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.addLog('info', '文件选择', `已选择: ${file.name} (${this.formatFileSize(file.size)})`);
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    disableGenerateButton(disabled) {
        const generateBtn = document.getElementById('generateBtn');
        generateBtn.disabled = disabled;
        
        if (disabled) {
            generateBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>生成中...';
            generateBtn.classList.add('loading');
        } else {
            generateBtn.innerHTML = '<i class="bi bi-play-circle-fill me-2"></i>开始生成配音';
            generateBtn.classList.remove('loading');
        }
    }

    toggleVoiceMapping() {
        const container = document.getElementById('voiceMappingContainer');
        const icon = document.getElementById('voiceMappingIcon');
        
        if (container.classList.contains('show')) {
            container.classList.remove('show');
            icon.classList.add('rotated');
        } else {
            container.classList.add('show');
            icon.classList.remove('rotated');
        }
    }

    addLog(level, message, details = '') {
        const container = document.getElementById('logContainer');
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${level}`;
        
        const time = new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        // 简化日志格式，保留原始内容
        const cleanMessage = this.formatLogMessage(message);
        const cleanDetails = details ? this.formatLogMessage(details) : '';
        
        // 构建简化的日志HTML
        let logHTML = `
            <div class="log-content">
                <span class="log-time">[${time}]</span>
                <span class="log-level">[${level.toUpperCase()}]</span>
                <span class="log-message">${cleanMessage}</span>
                ${cleanDetails ? `<div class="log-details">${cleanDetails}</div>` : ''}
            </div>
        `;
        
        logEntry.innerHTML = logHTML;
        container.appendChild(logEntry);
        
        // 添加高亮效果（新日志）
        logEntry.classList.add('highlight');
        setTimeout(() => {
            logEntry.classList.remove('highlight');
        }, 800);
        
        // 平滑滚动到底部
        setTimeout(() => {
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });
        }, 50);

        // 增加日志条数限制（保持更多日志）
        const maxLogs = 500;
        const logs = container.querySelectorAll('.log-entry');
        if (logs.length > maxLogs) {
            for (let i = 0; i < logs.length - maxLogs; i++) {
                logs[i].remove();
            }
        }
        
        // 更新日志统计
        this.updateLogStats();
    }
    
    formatLogMessage(message) {
        if (!message) return '';
        
        // 确保message是字符串类型
        if (typeof message !== 'string') {
            message = String(message);
        }
        
        // 转义HTML字符
        message = message.replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;')
                        .replace(/'/g, '&#039;');
        
        // 保留所有原始内容，包括emoji
        // 只进行基本的高亮处理
        message = message.replace(/(\d+\/\d+)/g, '<span class="text-primary fw-bold">$1</span>');
        message = message.replace(/(\d+\.\d+x)/g, '<span class="text-success fw-bold">$1</span>');
        message = message.replace(/(\d+样本)/g, '<span class="text-info">$1</span>');
        message = message.replace(/(\d+\.\d+s)/g, '<span class="text-warning">$1</span>');
        
        // 高亮URL和文件路径
        message = message.replace(/(https?:\/\/[^\s]+)/g, '<span class="text-info">$1</span>');
        message = message.replace(/(\/[^\s]+\.(mp3|srt|txt))/g, '<span class="text-secondary">$1</span>');
        
        return message;
    }
    
    updateLogStats() {
        const container = document.getElementById('logContainer');
        const logs = container.querySelectorAll('.log-entry');
        const errorLogs = container.querySelectorAll('.log-error');
        const warningLogs = container.querySelectorAll('.log-warning');
        
        // 更新状态徽章
        if (errorLogs.length > 0) {
            this.updateStatus(`${errorLogs.length} 错误`, 'danger');
        } else if (warningLogs.length > 0) {
            this.updateStatus(`${warningLogs.length} 警告`, 'warning');
        } else if (logs.length > 5 && this.isGenerating) {
            this.updateStatus('处理中...', 'primary');
        } else if (!this.isGenerating) {
            this.updateStatus('准备就绪', 'success');
        }
    }

    clearLogs() {
        const container = document.getElementById('logContainer');
        container.innerHTML = `
            <div class="log-entry log-info">
                <div class="d-flex align-items-start">
                    <span class="log-time">[${new Date().toLocaleTimeString('zh-CN')}]</span>
                    <div class="flex-grow-1">
                        <div class="log-message">日志已清空</div>
                    </div>
                </div>
            </div>
        `;
        this.updateStatus('准备就绪', 'success');
    }

    filterLogs() {
        const searchTerm = document.getElementById('logSearch').value.toLowerCase();
        const filterType = document.getElementById('logFilter').value;
        const logs = document.querySelectorAll('.log-entry');
        
        let visibleCount = 0;
        
        logs.forEach(log => {
            const message = log.textContent.toLowerCase();
            const logClass = log.className;
            
            // 检查搜索条件
            const matchesSearch = !searchTerm || message.includes(searchTerm);
            
            // 检查过滤条件
            let matchesFilter = false;
            if (filterType === 'all') {
                matchesFilter = true;
            } else {
                matchesFilter = logClass.includes(`log-${filterType}`);
            }
            
            // 显示或隐藏日志
            if (matchesSearch && matchesFilter) {
                log.style.display = 'block';
                visibleCount++;
            } else {
                log.style.display = 'none';
            }
        });
        
        // 更新过滤状态
        this.updateFilterStatus(visibleCount, logs.length);
    }
    
    updateFilterStatus(visibleCount, totalCount) {
        const container = document.getElementById('logContainer');
        let statusEl = container.querySelector('.filter-status');
        
        if (visibleCount < totalCount) {
            if (!statusEl) {
                statusEl = document.createElement('div');
                statusEl.className = 'filter-status alert alert-info py-1 px-2 m-1 small';
                container.insertBefore(statusEl, container.firstChild);
            }
            statusEl.textContent = `已过滤：显示 ${visibleCount} / ${totalCount} 条日志`;
        } else if (statusEl) {
            statusEl.remove();
        }
    }
    
    updateStatus(message, type = 'secondary') {
        const badge = document.getElementById('statusBadge');
        badge.className = `badge bg-${type}`;
        badge.textContent = message;
    }

    downloadAudio() {
        const audioPlayer = document.getElementById('audioPlayer');
        if (audioPlayer.src) {
            const link = document.createElement('a');
            link.href = audioPlayer.src;
            link.download = document.getElementById('audioInfo').textContent.replace('文件: ', '');
            link.click();
            
            this.addLog('info', '下载音频', '音频文件下载已开始');
        }
    }
}

// 工具函数
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;

    // 添加到页面
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }

    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();

    // 自动移除
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// 拖拽功能已移除，界面已简化为按钮上传

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.app = new VoiceGeneratorApp(); // 构造函数中已经调用了this.init()
    
    // 启用工具提示
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
    console.log('FastAPI 多人配音生成器已启动');
}); 