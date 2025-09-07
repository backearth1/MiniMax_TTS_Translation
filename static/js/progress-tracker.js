/**
 * 进度跟踪器
 * 解析WebSocket日志并显示批量翻译、TTS进度
 */

class ProgressTracker {
    constructor() {
        this.translationProgress = {
            current: 0,
            total: 0,
            active: false
        };
        
        this.ttsProgress = {
            current: 0,
            total: 0,
            active: false
        };
        
        this.mergeProgress = {
            current: 0,
            total: 0,
            active: false
        };
        
        this.init();
    }

    init() {
        // 创建进度条容器
        this.createProgressBars();
        
        // 监听日志消息
        this.attachLogListener();
    }

    createProgressBars() {
        // 创建进度条HTML
        const progressHTML = `
            <div id="progressTracker" class="progress-tracker">
                <div class="container-fluid">
                    <div class="progress-main-row">
                        <!-- 一键翻译按钮 -->
                        <div class="one-click-section">
                            <button class="btn btn-danger btn-sm one-click-btn" onclick="oneClickTranslate()" id="oneClickTranslateBtn">
                                <i class="bi bi-magic me-1"></i>一键翻译
                            </button>
                        </div>
                        
                        <!-- 进度条区域 -->
                        <div class="progress-row">
                            <!-- 批量翻译 -->
                            <div class="progress-item">
                                <div class="progress-header">
                                    <span class="progress-text" id="translationProgressText">准备就绪</span>
                                </div>
                                <div class="progress mb-2" style="height: 8px;">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                         id="translationProgressBar" 
                                         role="progressbar" 
                                         style="width: 0%"></div>
                                </div>
                                <button class="btn btn-secondary btn-sm progress-button" 
                                        onclick="batchTranslate()" id="batchTranslateBtn">
                                    <i class="bi bi-translate me-1"></i>批量翻译
                                </button>
                            </div>

                            <!-- 批量TTS -->
                            <div class="progress-item">
                                <div class="progress-header">
                                    <span class="progress-text" id="ttsProgressText">准备就绪</span>
                                </div>
                                <div class="progress mb-2" style="height: 8px;">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                         id="ttsProgressBar" 
                                         role="progressbar" 
                                         style="width: 0%"></div>
                                </div>
                                <button class="btn btn-info btn-sm progress-button" 
                                        onclick="batchGenerateTTS()" id="batchTTSBtn">
                                    <i class="bi bi-music-note-list me-1"></i>批量TTS
                                </button>
                            </div>

                            <!-- 拼接音频 -->
                            <div class="progress-item">
                                <div class="progress-header">
                                    <span class="progress-text" id="mergeProgressText">准备就绪</span>
                                </div>
                                <div class="progress mb-2" style="height: 8px;">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                         id="mergeProgressBar" 
                                         role="progressbar" 
                                         style="width: 0%"></div>
                                </div>
                                <button class="btn btn-success btn-sm progress-button" 
                                        onclick="mergeAudio()" id="mergeBtn">
                                    <i class="bi bi-soundwave me-1"></i>拼接音频
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 插入到页面顶部（导航栏下方）
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            navbar.insertAdjacentHTML('afterend', progressHTML);
        }
    }

    attachLogListener() {
        // 监听日志消息
        if (typeof addLog === 'function') {
            // 保存原始的addLog函数
            const originalAddLog = window.addLog;
            
            // 重写addLog函数，添加进度解析
            window.addLog = (message, type = 'info') => {
                // 调用原始函数
                originalAddLog(message, type);
                
                // 解析进度信息
                this.parseLogMessage(message);
            };
        }
    }

    parseLogMessage(message) {
        try {
            // 解析翻译进度
            this.parseTranslationProgress(message);
            
            // 解析TTS进度
            this.parseTTSProgress(message);
            
            // 检查任务完成状态
            this.checkTaskCompletion(message);
            
        } catch (error) {
            console.error('解析日志消息失败:', error);
        }
    }

    parseTranslationProgress(message) {
        // 匹配开始翻译消息
        if (message.includes('=== 开始一键翻译流程 ===') || 
            message.includes('开始批量翻译:')) {
            this.showTranslationProgress();
            return;
        }

        // 匹配翻译进度: "翻译进度: 处理段落 1/3"
        const progressMatch = message.match(/翻译进度[：:]\s*处理段落\s*(\d+)\/(\d+)/);
        if (progressMatch) {
            const current = parseInt(progressMatch[1]);
            const total = parseInt(progressMatch[2]);
            
            this.updateTranslationProgress(current, total);
            return;
        }

        // 匹配成功消息: "段落 1 翻译成功"
        const successMatch = message.match(/段落\s*(\d+)\s*翻译成功/);
        if (successMatch) {
            const current = parseInt(successMatch[1]);
            this.updateTranslationProgress(current, this.translationProgress.total);
            return;
        }
    }

    parseTTSProgress(message) {
        // 匹配开始TTS消息
        if (message.includes('开始批量TTS生成') || 
            message.includes('步骤2: 开始批量TTS')) {
            this.showTTSProgress();
            return;
        }

        // 匹配TTS总数: "开始批量TTS生成: 共 3 个段落"
        const totalMatch = message.match(/开始批量TTS生成[：:]\s*共\s*(\d+)\s*个段落/);
        if (totalMatch) {
            const total = parseInt(totalMatch[1]);
            this.updateTTSProgress(0, total);
            return;
        }

        // 匹配TTS进度: "处理段落 1/3"
        const progressMatch = message.match(/处理段落\s*(\d+)\/(\d+)/);
        if (progressMatch && this.ttsProgress.active) {
            const current = parseInt(progressMatch[1]);
            const total = parseInt(progressMatch[2]);
            
            this.updateTTSProgress(current - 1, total); // 显示正在处理的
            return;
        }

        // 匹配完成消息: "段落 1/3 完成"
        const completeMatch = message.match(/段落\s*(\d+)\/(\d+)\s*完成/);
        if (completeMatch) {
            const current = parseInt(completeMatch[1]);
            const total = parseInt(completeMatch[2]);
            
            this.updateTTSProgress(current, total);
            return;
        }
    }

    parseMergeProgress(message) {
        // 匹配开始拼接消息
        if (message.includes('开始拼接音频') || 
            message.includes('步骤3: 开始拼接音频')) {
            this.showMergeProgress();
            this.updateMergeProgress(0, 1);
            return;
        }

        // 匹配拼接进度消息
        if (message.includes('正在拼接音频') || 
            message.includes('拼接音频中')) {
            this.updateMergeProgress(1, 1);
            return;
        }
    }

    checkTaskCompletion(message) {
        // 检查翻译完成
        if (message.includes('批量翻译完成') || 
            message.includes('步骤1: 批量翻译完成')) {
            this.hideTranslationProgress();
        }

        // 检查TTS完成
        if (message.includes('步骤2: 批量TTS完成') || 
            message.includes('批量TTS完成')) {
            this.hideTTSProgress();
        }

        // 检查拼接音频进度
        this.parseMergeProgress(message);

        // 检查整个流程完成
        if (message.includes('步骤3: 拼接音频完成') || 
            message.includes('音频拼接完成')) {
            this.hideMergeProgress();
            this.hideAllProgress();
        }
    }

    showTranslationProgress() {
        this.translationProgress.active = true;
        this.translationProgress.current = 0;
        this.translationProgress.total = 0;
        
        const container = document.getElementById('translationProgressContainer');
        
        if (container) {
            container.classList.add('show');
        }
        
        this.updateTranslationProgress(0, 0);
    }

    showTTSProgress() {
        this.ttsProgress.active = true;
        this.ttsProgress.current = 0;
        this.ttsProgress.total = 0;
        
        const container = document.getElementById('ttsProgressContainer');
        
        if (container) {
            container.classList.add('show');
        }
        
        this.updateTTSProgress(0, 0);
    }

    updateTranslationProgress(current, total) {
        this.translationProgress.current = current;
        if (total > 0) this.translationProgress.total = total;
        
        const progressBar = document.getElementById('translationProgressBar');
        const progressText = document.getElementById('translationProgressText');
        
        if (progressBar && this.translationProgress.total > 0) {
            const percentage = (current / this.translationProgress.total) * 100;
            progressBar.style.width = percentage + '%';
            progressBar.setAttribute('aria-valuenow', percentage);
        }
        
        if (progressText) {
            progressText.textContent = `正在处理 ${current}/${this.translationProgress.total}`;
        }
    }

    updateTTSProgress(current, total) {
        this.ttsProgress.current = current;
        if (total > 0) this.ttsProgress.total = total;
        
        const progressBar = document.getElementById('ttsProgressBar');
        const progressText = document.getElementById('ttsProgressText');
        
        if (progressBar && this.ttsProgress.total > 0) {
            const percentage = (current / this.ttsProgress.total) * 100;
            progressBar.style.width = percentage + '%';
            progressBar.setAttribute('aria-valuenow', percentage);
        }
        
        if (progressText) {
            progressText.textContent = `正在处理 ${current}/${this.ttsProgress.total}`;
        }
    }

    hideTranslationProgress() {
        this.translationProgress.active = false;
        
        // 延迟隐藏，让用户看到100%完成状态
        setTimeout(() => {
            const container = document.getElementById('translationProgressContainer');
            if (container) {
                container.classList.remove('show');
            }
        }, 2000);
    }

    hideTTSProgress() {
        this.ttsProgress.active = false;
        
        // 延迟隐藏，让用户看到100%完成状态
        setTimeout(() => {
            const container = document.getElementById('ttsProgressContainer');
            if (container) {
                container.classList.remove('show');
            }
        }, 2000);
    }

    showMergeProgress() {
        this.mergeProgress.active = true;
        this.mergeProgress.current = 0;
        this.mergeProgress.total = 1;
        
        this.updateMergeProgress(0, 1);
    }

    updateMergeProgress(current, total) {
        this.mergeProgress.current = current;
        if (total > 0) this.mergeProgress.total = total;
        
        const progressBar = document.getElementById('mergeProgressBar');
        const progressText = document.getElementById('mergeProgressText');
        
        if (progressBar && this.mergeProgress.total > 0) {
            const percentage = (current / this.mergeProgress.total) * 100;
            progressBar.style.width = percentage + '%';
            progressBar.setAttribute('aria-valuenow', percentage);
        }
        
        if (progressText) {
            if (current === 0) {
                progressText.textContent = '准备中...';
            } else if (current === total) {
                progressText.textContent = '拼接完成';
            } else {
                progressText.textContent = '正在拼接...';
            }
        }
    }

    hideMergeProgress() {
        this.mergeProgress.active = false;
        
        // 延迟隐藏，让用户看到100%完成状态
        setTimeout(() => {
            const progressText = document.getElementById('mergeProgressText');
            if (progressText) {
                progressText.textContent = '准备就绪';
            }
            
            const progressBar = document.getElementById('mergeProgressBar');
            if (progressBar) {
                progressBar.style.width = '0%';
            }
        }, 2000);
    }

    hideAllProgress() {
        this.translationProgress.active = false;
        this.ttsProgress.active = false;
        this.mergeProgress.active = false;
        
        setTimeout(() => {
            // 重置所有进度条到初始状态
            const translationText = document.getElementById('translationProgressText');
            const ttsText = document.getElementById('ttsProgressText'); 
            const mergeText = document.getElementById('mergeProgressText');
            
            if (translationText) translationText.textContent = '准备就绪';
            if (ttsText) ttsText.textContent = '准备就绪';
            if (mergeText) mergeText.textContent = '准备就绪';
            
            const translationBar = document.getElementById('translationProgressBar');
            const ttsBar = document.getElementById('ttsProgressBar');
            const mergeBar = document.getElementById('mergeProgressBar');
            
            if (translationBar) translationBar.style.width = '0%';
            if (ttsBar) ttsBar.style.width = '0%';
            if (mergeBar) mergeBar.style.width = '0%';
        }, 2000);
    }

    checkIfAllHidden() {
        // 由于进度条现在固定显示，不需要隐藏整个tracker
        // 只需要确保各个进度容器正确隐藏即可
    }

    // 手动控制进度（供外部调用）
    setTranslationProgress(current, total) {
        this.showTranslationProgress();
        this.updateTranslationProgress(current, total);
    }

    setTTSProgress(current, total) {
        this.showTTSProgress();
        this.updateTTSProgress(current, total);
    }

    // 重置所有进度
    reset() {
        this.hideAllProgress();
        this.translationProgress = { current: 0, total: 0, active: false };
        this.ttsProgress = { current: 0, total: 0, active: false };
    }

    // 测试函数 - 手动显示进度条
    testProgress() {
        console.log('测试进度条显示...');
        
        // 测试翻译进度
        this.updateTranslationProgress(2, 5);
        
        setTimeout(() => {
            // 测试TTS进度
            this.updateTTSProgress(1, 3);
        }, 1500);
        
        setTimeout(() => {
            // 测试拼接进度
            this.showMergeProgress();
            this.updateMergeProgress(1, 1);
        }, 3000);
        
        setTimeout(() => {
            // 重置所有进度
            this.hideAllProgress();
        }, 6000);
    }
}

// 创建全局进度跟踪器实例
let progressTracker = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    progressTracker = new ProgressTracker();
});

// 导出给外部使用
window.ProgressTracker = ProgressTracker;

// 全局测试函数
window.testProgressTracker = function() {
    if (progressTracker) {
        progressTracker.testProgress();
    } else {
        console.error('进度跟踪器未初始化');
    }
};