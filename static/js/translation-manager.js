/**
 * 翻译管理模块
 * 负责批量翻译、一键翻译等功能
 */

class TranslationManager {
    constructor() {
        this.currentOperationClientId = null;
        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        // 可以在这里绑定翻译相关的事件监听器
    }

    /**
     * 批量翻译功能
     */
    async batchTranslate() {
        if (!window.currentSubtitleProject) {
            if (window.showToast) window.showToast('请先上传SRT文件');
            return;
        }

        // 获取翻译配置
        const targetLanguage = document.getElementById('language').value;
        const groupId = document.getElementById('groupId').value;
        const apiKey = document.getElementById('apiKey').value;

        if (!groupId || !apiKey) {
            if (window.addLog) window.addLog('配置错误: 缺少Group ID或API Key');
            if (window.showToast) window.showToast('请先配置Group ID和API Key');
            return;
        }

        if (window.addLog) window.addLog(`开始批量翻译到${targetLanguage}...`);
        if (window.showToast) window.showToast('正在批量翻译，请稍候...');

        // 禁用批量翻译按钮
        const batchTranslateBtn = document.getElementById('batchTranslateBtn');
        const originalText = batchTranslateBtn.innerHTML;
        batchTranslateBtn.disabled = true;
        batchTranslateBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>正在翻译...';

        // 生成客户端ID用于日志
        const clientId = window.ttsGenerator ? window.ttsGenerator.generateClientId() : this.generateClientId();
        this.currentOperationClientId = clientId;

        // 开始实时日志更新
        if (window.startRealTimeLogUpdates) {
            window.startRealTimeLogUpdates(clientId);
        }

        try {
            const formData = new FormData();
            formData.append('targetLanguage', targetLanguage);
            formData.append('groupId', groupId);
            formData.append('apiKey', apiKey);
            formData.append('apiEndpoint', document.getElementById('apiEndpoint').value);
            formData.append('client_id', clientId);

            const response = await fetch(`/api/subtitle/${window.currentSubtitleProject.id}/batch-translate`, {
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
                    window.addLog(`批量翻译完成！成功: ${result.stats.success}, 失败: ${result.stats.failed}, 跳过: ${result.stats.skipped}`);
                    window.addLog(`总耗时: ${result.stats.total_time.toFixed(2)} 秒`);
                }
                if (window.showToast) window.showToast('批量翻译完成！');
                
                // 重新加载字幕段落以显示翻译结果
                if (window.subtitleEditor) {
                    window.subtitleEditor.loadSubtitleSegments();
                }
            } else {
                const errorMessage = result.message || '未知错误';
                if (window.addLog) window.addLog(`批量翻译失败: ${errorMessage}`);
                if (window.showToast) window.showToast('批量翻译失败: ' + errorMessage);
            }
        } catch (error) {
            console.error('批量翻译失败:', error);
            
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
            
            if (window.addLog) window.addLog(`批量翻译失败: ${errorMessage}`);
            if (window.showToast) window.showToast('批量翻译失败: ' + errorMessage);
        } finally {
            // 停止实时日志更新
            if (window.stopRealTimeLogUpdates) {
                window.stopRealTimeLogUpdates();
            }
            // 恢复按钮，清除客户端ID
            batchTranslateBtn.disabled = false;
            batchTranslateBtn.innerHTML = originalText;
            this.currentOperationClientId = null;
        }
    }

    /**
     * 一键翻译功能 - 自动按顺序执行翻译、TTS、合并
     */
    async oneClickTranslate() {
        console.log('一键翻译按钮被点击');
        if (!window.currentSubtitleProject) {
            if (window.showToast) window.showToast('请先上传SRT文件');
            return;
        }

        // 获取配置
        const targetLanguage = document.getElementById('language').value;
        const groupId = document.getElementById('groupId').value;
        const apiKey = document.getElementById('apiKey').value;

        if (!groupId || !apiKey) {
            if (window.addLog) window.addLog('配置错误: 缺少Group ID或API Key');
            if (window.showToast) window.showToast('请先配置Group ID和API Key');
            return;
        }

        if (window.addLog) window.addLog('🚀 开始一键翻译流程...');
        if (window.showToast) window.showToast('开始一键翻译，请耐心等待...');

        // 禁用一键翻译按钮
        const oneClickBtn = document.getElementById('oneClickTranslateBtn');
        const originalText = oneClickBtn.innerHTML;
        oneClickBtn.disabled = true;
        oneClickBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>正在处理...';

        try {
            // 步骤1: 批量翻译
            if (window.addLog) window.addLog('📝 步骤1: 开始批量翻译...');
            const translateResult = await this.executeBatchTranslate(targetLanguage, groupId, apiKey);
            
            if (!translateResult.success) {
                throw new Error(`翻译失败: ${translateResult.message}`);
            }
            
            if (window.addLog) window.addLog(`✅ 翻译完成: 成功${translateResult.stats.success}个, 失败${translateResult.stats.failed}个`);

            // 步骤2: 批量TTS生成
            if (window.addLog) window.addLog('🎤 步骤2: 开始批量TTS生成...');
            const ttsResult = await this.executeBatchTTS(groupId, apiKey);
            
            if (!ttsResult.success) {
                throw new Error(`TTS生成失败: ${ttsResult.message}`);
            }
            
            if (window.addLog) window.addLog(`✅ TTS生成完成: 成功${ttsResult.stats.success}个, 失败${ttsResult.stats.failed}个`);

            // 步骤3: 合并音频
            if (window.addLog) window.addLog('🎵 步骤3: 开始合并音频...');
            const mergeResult = await this.executeMergeAudio();
            
            if (!mergeResult.success) {
                throw new Error(`音频合并失败: ${mergeResult.message}`);
            }
            
            if (window.addLog) {
                window.addLog(`✅ 音频合并完成: 时长${mergeResult.duration}秒, 大小${(mergeResult.file_size/1024/1024).toFixed(2)}MB`);
                window.addLog('🎉 一键翻译流程全部完成！');
            }
            if (window.showToast) window.showToast('🎉 一键翻译流程全部完成！');

            // 显示合并结果
            if (window.audioProcessor) {
                window.audioProcessor.showMergeResult(mergeResult);
            }

        } catch (error) {
            console.error('一键翻译失败:', error);
            if (window.addLog) window.addLog(`❌ 一键翻译失败: ${error.message}`);
            if (window.showToast) window.showToast('一键翻译失败: ' + error.message);
        } finally {
            // 恢复按钮
            oneClickBtn.disabled = false;
            oneClickBtn.innerHTML = originalText;
        }
    }

    /**
     * 执行批量翻译
     */
    async executeBatchTranslate(targetLanguage, groupId, apiKey) {
        const clientId = window.ttsGenerator ? window.ttsGenerator.generateClientId() : this.generateClientId();
        
        if (window.startRealTimeLogUpdates) {
            window.startRealTimeLogUpdates(clientId);
        }

        try {
            const formData = new FormData();
            formData.append('targetLanguage', targetLanguage);
            formData.append('groupId', groupId);
            formData.append('apiKey', apiKey);
            formData.append('apiEndpoint', document.getElementById('apiEndpoint').value);
            formData.append('client_id', clientId);

            const response = await fetch(`/api/subtitle/${window.currentSubtitleProject.id}/batch-translate`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (result.success) {
                if (window.subtitleEditor) {
                    window.subtitleEditor.loadSubtitleSegments(); // 重新加载以显示翻译结果
                }
            }
            
            return result;
        } finally {
            if (window.stopRealTimeLogUpdates) {
                window.stopRealTimeLogUpdates();
            }
        }
    }

    /**
     * 执行批量TTS生成
     */
    async executeBatchTTS(groupId, apiKey) {
        const clientId = window.ttsGenerator ? window.ttsGenerator.generateClientId() : this.generateClientId();
        
        if (window.startRealTimeLogUpdates) {
            window.startRealTimeLogUpdates(clientId);
        }

        try {
            const voiceMapping = window.ttsGenerator ? window.ttsGenerator.getVoiceMapping() : {};
            
            const formData = new FormData();
            formData.append('groupId', groupId);
            formData.append('apiKey', apiKey);
            formData.append('apiEndpoint', document.getElementById('apiEndpoint').value);
            formData.append('model', document.getElementById('voiceModel').value);
            formData.append('language', document.getElementById('language').value);
            formData.append('voiceMapping', JSON.stringify(voiceMapping));
            formData.append('client_id', clientId);

            const response = await fetch(`/api/subtitle/${window.currentSubtitleProject.id}/batch-generate-tts`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (result.success) {
                if (window.subtitleEditor) {
                    window.subtitleEditor.loadSubtitleSegments(); // 重新加载以显示TTS结果
                }
            }
            
            return result;
        } finally {
            if (window.stopRealTimeLogUpdates) {
                window.stopRealTimeLogUpdates();
            }
        }
    }

    /**
     * 执行音频合并
     */
    async executeMergeAudio() {
        try {
            const response = await fetch(`/api/subtitle/${window.currentSubtitleProject.id}/merge-audio`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const result = await response.json();
            return result;
        } catch (error) {
            console.error('合并音频失败:', error);
            throw error;
        }
    }

    /**
     * 生成客户端ID
     */
    generateClientId() {
        return 'client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * 获取当前操作的客户端ID
     */
    getCurrentClientId() {
        return this.currentOperationClientId;
    }
}

// 创建全局实例
const translationManager = new TranslationManager();

// 导出供外部使用
window.translationManager = translationManager;

// 兼容性函数，保持向后兼容
window.batchTranslate = () => translationManager.batchTranslate();
window.oneClickTranslate = () => translationManager.oneClickTranslate();
window.executeBatchTranslate = (targetLanguage, groupId, apiKey) => translationManager.executeBatchTranslate(targetLanguage, groupId, apiKey);
window.executeBatchTTS = (groupId, apiKey) => translationManager.executeBatchTTS(groupId, apiKey);
window.executeMergeAudio = () => translationManager.executeMergeAudio();