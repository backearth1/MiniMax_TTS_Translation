/**
 * TTS生成模块
 * 负责文本转语音功能，包括单个和批量TTS生成
 */

class TTSGenerator {
    constructor() {
        this.currentOperationClientId = null;
        this.init();
    }

    init() {
        // 绑定事件监听器
        this.bindEvents();
    }

    bindEvents() {
        // 可以在这里绑定TTS相关的事件监听器
    }

    /**
     * 生成客户端ID
     */
    generateClientId() {
        return 'client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * 获取语音映射配置
     */
    getVoiceMapping() {
        const mapping = {};
        
        // 获取预定义的语音映射
        const speakerElements = document.querySelectorAll('[id^="speaker_"]');
        speakerElements.forEach(element => {
            const speakerId = element.id.replace('speaker_', '');
            mapping[speakerId] = element.value;
        });
        
        // 获取自定义语音映射
        const customElements = document.querySelectorAll('[id^="customSpeaker_"]');
        customElements.forEach(element => {
            const speakerId = element.id.replace('customSpeaker_', '');
            if (element.value) {
                mapping[speakerId] = element.value;
            }
        });
        
        return mapping;
    }

    /**
     * 生成单个段落的TTS
     */
    async generateTTS(segmentId) {
        if (!window.currentSubtitleProject) {
            if (window.showToast) window.showToast('请先上传SRT文件');
            return;
        }

        const segment = window.segments ? window.segments.find(s => s.id === segmentId) : null;
        if (!segment) {
            if (window.showToast) window.showToast('找不到指定的段落');
            return;
        }

        if (window.addLog) window.addLog(`开始生成TTS: 段落${segmentId}`);

        try {
            // 获取当前配置
            const groupId = document.getElementById('groupId').value;
            const apiKey = document.getElementById('apiKey').value;
            const model = document.getElementById('voiceModel').value;
            const language = document.getElementById('language').value;
            
            // 获取voiceMapping（从动态生成的元素中）
            const voiceMapping = this.getVoiceMapping();

            if (!groupId || !apiKey) {
                if (window.addLog) window.addLog('配置错误: 缺少Group ID或API Key');
                if (window.showToast) window.showToast('请先配置Group ID和API Key');
                return;
            }

            if (window.addLog) window.addLog(`调用TTS API: 模型=${model}, 说话人=${segment.speaker}, 情绪=${segment.emotion}`);
            if (window.showToast) window.showToast('正在生成TTS...');

            const formData = new FormData();
            formData.append('groupId', groupId);
            formData.append('apiKey', apiKey);
            formData.append('apiEndpoint', document.getElementById('apiEndpoint').value);
            formData.append('model', model);
            formData.append('language', language);
            formData.append('voiceMapping', JSON.stringify(voiceMapping));

            const response = await fetch(`/api/subtitle/${window.currentSubtitleProject.id}/segment/${segmentId}/generate-tts`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                const traceInfo = result.trace_id ? `, trace_id=${result.trace_id}` : '';
                const ratioInfo = result.duration_ratio ? `, 比例=${result.duration_ratio.toFixed(2)}` : '';
                if (window.addLog) window.addLog(`TTS生成成功: 段落${segmentId}${traceInfo}${ratioInfo}`);
                if (window.showToast) window.showToast('TTS生成成功！');
                
                // 重新加载段落以更新状态
                if (window.subtitleEditor) {
                    window.subtitleEditor.loadSubtitleSegments();
                }
            } else {
                // 生成失败，记录详细信息但不更新界面
                const traceInfo = result.trace_id ? `, trace_id=${result.trace_id}` : '';
                const ratioInfo = result.duration_ratio ? `, 比例=${result.duration_ratio.toFixed(2)}` : '';
                const durationInfo = result.target_duration && result.current_duration ? 
                    `, 目标时长=${result.target_duration}ms, 当前时长=${result.current_duration}ms` : '';
                
                if (window.addLog) {
                    window.addLog(`TTS生成失败: 段落${segmentId}${traceInfo}${ratioInfo}${durationInfo}`);
                    window.addLog(`失败原因: ${result.message}`);
                }
                if (window.showToast) window.showToast('TTS生成失败: ' + result.message);
            }
        } catch (error) {
            console.error('TTS生成失败:', error);
            if (window.addLog) window.addLog(`TTS生成失败: 段落${segmentId}, 错误=${error.message}`);
            if (window.showToast) window.showToast('TTS生成失败: ' + error.message);
        }
    }

    /**
     * 批量生成TTS
     */
    async batchGenerateTTS() {
        if (!window.currentSubtitleProject) {
            if (window.showToast) window.showToast('请先上传SRT文件');
            return;
        }

        // 获取当前配置
        const groupId = document.getElementById('groupId').value;
        const apiKey = document.getElementById('apiKey').value;
        const model = document.getElementById('voiceModel').value;
        const language = document.getElementById('language').value;

        if (!groupId || !apiKey) {
            if (window.addLog) window.addLog('配置错误: 缺少Group ID或API Key');
            if (window.showToast) window.showToast('请先配置Group ID和API Key');
            return;
        }

        if (window.addLog) window.addLog('开始批量TTS生成...');
        if (window.showToast) window.showToast('正在批量生成TTS，请稍候...');

        // 获取voiceMapping
        const voiceMapping = this.getVoiceMapping();

        // 禁用批量TTS按钮
        const batchTTSBtn = document.getElementById('batchTTSBtn');
        const originalText = batchTTSBtn.innerHTML;
        batchTTSBtn.disabled = true;
        batchTTSBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>正在生成...';

        // 生成客户端ID用于日志
        const clientId = this.generateClientId();
        this.currentOperationClientId = clientId;

        // 开始实时日志更新
        if (window.startRealTimeLogUpdates) {
            window.startRealTimeLogUpdates(clientId);
        }

        try {
            const formData = new FormData();
            formData.append('groupId', groupId);
            formData.append('apiKey', apiKey);
            formData.append('apiEndpoint', document.getElementById('apiEndpoint').value);
            formData.append('model', model);
            formData.append('language', language);
            formData.append('voiceMapping', JSON.stringify(voiceMapping));
            formData.append('client_id', clientId);

            const response = await fetch(`/api/subtitle/${window.currentSubtitleProject.id}/batch-generate-tts`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            // 停止实时日志更新
            if (window.stopRealTimeLogUpdates) {
                window.stopRealTimeLogUpdates();
            }

            if (result.success) {
                if (window.addLog) {
                    window.addLog(`批量TTS生成完成！成功: ${result.stats.success}, 失败: ${result.stats.failed}, 跳过: ${result.stats.skipped}`);
                    window.addLog(`总耗时: ${result.stats.total_time.toFixed(2)} 秒`);
                }
                if (window.showToast) window.showToast('批量TTS生成完成！');
                
                // 重新加载字幕段落以更新播放按钮和trace_id
                if (window.subtitleEditor) {
                    window.subtitleEditor.loadSubtitleSegments();
                }
            } else {
                if (window.addLog) window.addLog(`批量TTS生成失败: ${result.message}`);
                if (window.showToast) window.showToast('批量TTS生成失败: ' + result.message);
            }
        } catch (error) {
            console.error('批量TTS生成失败:', error);
            
            // 停止实时日志更新
            if (window.stopRealTimeLogUpdates) {
                window.stopRealTimeLogUpdates();
            }
            
            let errorMessage = '未知错误';
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                errorMessage = '网络连接错误，请检查网络连接';
            } else if (error.message) {
                errorMessage = error.message;
            }
            
            if (window.addLog) window.addLog(`批量TTS生成失败: ${errorMessage}`);
            if (window.showToast) window.showToast('批量TTS生成失败: ' + errorMessage);
        } finally {
            // 停止实时日志更新
            if (window.stopRealTimeLogUpdates) {
                window.stopRealTimeLogUpdates();
            }
            // 恢复按钮，清除客户端ID
            batchTTSBtn.disabled = false;
            batchTTSBtn.innerHTML = originalText;
            this.currentOperationClientId = null;
        }
    }

    /**
     * 中断当前任务
     */
    async interruptCurrentTask() {
        if (!this.currentOperationClientId) {
            if (window.showToast) window.showToast('当前没有正在进行的任务');
            return;
        }

        if (window.addLog) window.addLog('正在中断当前任务...');
        if (window.showToast) window.showToast('正在中断任务，请稍候...');

        try {
            const response = await fetch('/api/interrupt-task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ client_id: this.currentOperationClientId })
            });

            const result = await response.json();

            if (result.success) {
                if (window.addLog) window.addLog('任务已成功中断');
                if (window.showToast) window.showToast('任务已中断');
            } else {
                if (window.addLog) window.addLog(`中断失败: ${result.message}`);
                if (window.showToast) window.showToast('中断失败: ' + result.message);
            }
        } catch (error) {
            console.error('中断任务失败:', error);
            if (window.addLog) window.addLog(`中断任务失败: ${error.message}`);
            if (window.showToast) window.showToast('中断任务失败: ' + error.message);
        } finally {
            // 清除客户端ID
            this.currentOperationClientId = null;
            
            // 停止实时日志更新
            if (window.stopRealTimeLogUpdates) {
                window.stopRealTimeLogUpdates();
            }
            
            // 恢复所有相关按钮
            const batchTTSBtn = document.getElementById('batchTTSBtn');
            if (batchTTSBtn) {
                batchTTSBtn.disabled = false;
                batchTTSBtn.innerHTML = '<i class="bi bi-soundwave me-2"></i>批量TTS';
            }
            
            const batchTranslateBtn = document.getElementById('batchTranslateBtn');
            if (batchTranslateBtn) {
                batchTranslateBtn.disabled = false;
                batchTranslateBtn.innerHTML = '<i class="bi bi-translate me-2"></i>批量翻译';
            }
            
            const oneClickBtn = document.getElementById('oneClickTranslateBtn');
            if (oneClickBtn) {
                oneClickBtn.disabled = false;
                oneClickBtn.innerHTML = '<i class="bi bi-magic me-2"></i>一键翻译';
            }
        }
    }

    /**
     * 获取当前操作的客户端ID
     */
    getCurrentClientId() {
        return this.currentOperationClientId;
    }
}

// 创建全局实例
const ttsGenerator = new TTSGenerator();

// 导出供外部使用
window.ttsGenerator = ttsGenerator;

// 兼容性函数，保持向后兼容
window.generateTTS = (segmentId) => ttsGenerator.generateTTS(segmentId);
window.batchGenerateTTS = () => ttsGenerator.batchGenerateTTS();
window.generateClientId = () => ttsGenerator.generateClientId();
window.getVoiceMapping = () => ttsGenerator.getVoiceMapping();
window.interruptCurrentTask = () => ttsGenerator.interruptCurrentTask();