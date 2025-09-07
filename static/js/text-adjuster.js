/**
 * 文本长度调整器
 * 为SRT字幕段落提供缩短/加长功能
 */

class TextAdjuster {
    constructor() {
        this.config = null;
        this.loadConfig();
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/text-adjuster/config');
            this.config = await response.json();
        } catch (error) {
            console.error('加载文本调整器配置失败:', error);
        }
    }

    /**
     * 创建文本调整按钮
     * @param {string} segmentId - 段落ID
     * @param {string} projectId - 项目ID
     * @param {boolean} hasTranslation - 是否有译文
     * @returns {HTMLElement} 按钮容器
     */
    createAdjustmentButtons(segmentId, projectId, hasTranslation) {
        const container = document.createElement('div');
        container.className = 'text-adjustment-buttons d-inline-flex gap-1 ms-2';
        
        if (!hasTranslation) {
            // 没有译文时显示提示
            container.innerHTML = `
                <small class="text-muted fst-italic">需要先翻译</small>
            `;
            return container;
        }

        container.innerHTML = `
            <button type="button" class="btn btn-outline-primary btn-sm text-adjust-btn" 
                    data-segment-id="${segmentId}" 
                    data-project-id="${projectId}"
                    data-adjustment-type="shorten"
                    title="缩短译文约20%">
                <i class="bi bi-arrow-down-circle me-1"></i>缩短
            </button>
            <button type="button" class="btn btn-outline-success btn-sm text-adjust-btn"
                    data-segment-id="${segmentId}"
                    data-project-id="${projectId}" 
                    data-adjustment-type="lengthen"
                    title="加长译文约20%">
                <i class="bi bi-arrow-up-circle me-1"></i>加长
            </button>
        `;

        // 绑定点击事件
        container.querySelectorAll('.text-adjust-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleAdjustment(e));
        });

        return container;
    }

    /**
     * 处理文本调整请求
     * @param {Event} event - 点击事件
     */
    async handleAdjustment(event) {
        const button = event.currentTarget;
        const segmentId = button.dataset.segmentId;
        const projectId = button.dataset.projectId;
        const adjustmentType = button.dataset.adjustmentType;
        
        // 获取当前配置
        const groupId = document.getElementById('groupId')?.value;
        const apiKey = document.getElementById('apiKey')?.value;
        const targetLanguage = document.getElementById('languageSelect')?.value;
        const apiEndpoint = document.getElementById('apiEndpoint')?.value || 'domestic';

        if (!groupId || !apiKey) {
            showAlert('请先填写API配置信息', 'warning');
            return;
        }

        if (!targetLanguage) {
            showAlert('请先选择目标语言', 'warning');
            return;
        }

        // 禁用按钮，显示加载状态
        const originalText = button.innerHTML;
        const allButtons = button.parentElement.querySelectorAll('.text-adjust-btn');
        allButtons.forEach(btn => btn.disabled = true);
        
        const actionText = adjustmentType === 'shorten' ? '缩短' : '加长';
        button.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${actionText}中...`;

        try {
            // 准备表单数据
            const formData = new FormData();
            formData.append('adjustment_type', adjustmentType);
            formData.append('groupId', groupId);
            formData.append('apiKey', apiKey);
            formData.append('target_language', targetLanguage);
            formData.append('apiEndpoint', apiEndpoint);

            // 发送调整请求
            const response = await fetch(`/api/subtitle/${projectId}/segment/${segmentId}/adjust-text`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                // 显示成功消息
                const changeInfo = result.length_change;
                const changeText = changeInfo.change_percentage > 0 ? 
                    `增加${changeInfo.change_percentage}%` : 
                    `减少${Math.abs(changeInfo.change_percentage)}%`;
                
                showAlert(
                    `文本${actionText}成功！长度变化：${changeInfo.original_length} → ${changeInfo.new_length} 字 (${changeText})`,
                    'success'
                );

                // 刷新段落显示
                await this.refreshSegmentDisplay(projectId, segmentId, result.adjusted_text);
                
                // 记录到日志（如果有WebSocket连接）
                if (typeof addLog === 'function') {
                    addLog(`段落 ${segmentId} 文本${actionText}成功：${changeInfo.original_length} → ${changeInfo.new_length} 字`, 'success');
                }
            } else {
                throw new Error(result.message || `文本${actionText}失败`);
            }

        } catch (error) {
            console.error(`文本${actionText}失败:`, error);
            showAlert(`文本${actionText}失败：${error.message}`, 'danger');
        } finally {
            // 恢复按钮状态
            allButtons.forEach(btn => btn.disabled = false);
            button.innerHTML = originalText;
        }
    }

    /**
     * 刷新段落显示
     * @param {string} projectId - 项目ID
     * @param {string} segmentId - 段落ID  
     * @param {string} newTranslation - 新的译文
     */
    async refreshSegmentDisplay(projectId, segmentId, newTranslation) {
        try {
            // 查找并更新译文显示
            const translationElement = document.querySelector(`[data-segment-id="${segmentId}"] .translation-text`);
            if (translationElement) {
                translationElement.textContent = newTranslation;
                
                // 添加更新动画效果
                translationElement.classList.add('text-updated');
                setTimeout(() => {
                    translationElement.classList.remove('text-updated');
                }, 2000);
            }

            // 如果有详细视图，也需要更新
            const detailTranslationElement = document.querySelector(`#translation_${segmentId}`);
            if (detailTranslationElement) {
                detailTranslationElement.value = newTranslation;
            }

        } catch (error) {
            console.error('刷新段落显示失败:', error);
        }
    }

    /**
     * 批量添加调整按钮到页面中的所有段落
     */
    addButtonsToAllSegments() {
        // 查找所有段落容器
        document.querySelectorAll('[data-segment-id]').forEach(segmentElement => {
            const segmentId = segmentElement.dataset.segmentId;
            const projectId = getCurrentProjectId(); // 需要获取当前项目ID的函数
            
            // 查找译文容器
            const translationContainer = segmentElement.querySelector('.translation-container');
            if (translationContainer && !translationContainer.querySelector('.text-adjustment-buttons')) {
                // 检查是否有译文
                const translationText = translationContainer.querySelector('.translation-text');
                const hasTranslation = translationText && translationText.textContent.trim() !== '';
                
                // 创建并添加调整按钮
                const buttons = this.createAdjustmentButtons(segmentId, projectId, hasTranslation);
                translationContainer.appendChild(buttons);
            }
        });
    }

    /**
     * 移除所有调整按钮
     */
    removeAllButtons() {
        document.querySelectorAll('.text-adjustment-buttons').forEach(element => {
            element.remove();
        });
    }

    /**
     * 更新按钮状态（当译文状态改变时调用）
     * @param {string} segmentId - 段落ID
     * @param {boolean} hasTranslation - 是否有译文
     */
    updateButtonsForSegment(segmentId, hasTranslation) {
        const segmentElement = document.querySelector(`[data-segment-id="${segmentId}"]`);
        if (segmentElement) {
            const existingButtons = segmentElement.querySelector('.text-adjustment-buttons');
            if (existingButtons) {
                const projectId = getCurrentProjectId();
                const newButtons = this.createAdjustmentButtons(segmentId, projectId, hasTranslation);
                existingButtons.replaceWith(newButtons);
            }
        }
    }
}

// 添加CSS样式
const style = document.createElement('style');
style.textContent = `
    .text-adjustment-buttons {
        flex-wrap: nowrap;
    }
    
    .text-adjust-btn {
        font-size: 0.75rem;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        transition: all 0.2s ease;
    }
    
    .text-adjust-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .text-adjust-btn:disabled {
        transform: none;
        box-shadow: none;
    }
    
    .text-updated {
        background-color: #d4edda !important;
        border: 1px solid #c3e6cb !important;
        border-radius: 0.25rem;
        padding: 0.25rem;
        transition: all 0.3s ease;
    }
    
    .text-adjustment-buttons .btn {
        white-space: nowrap;
    }
    
    @media (max-width: 768px) {
        .text-adjust-btn {
            font-size: 0.7rem;
            padding: 0.2rem 0.4rem;
        }
        
        .text-adjust-btn i {
            display: none;
        }
    }
`;
document.head.appendChild(style);

// 创建全局文本调整器实例
let textAdjuster = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    textAdjuster = new TextAdjuster();
});

// 导出给外部使用
window.TextAdjuster = TextAdjuster;

// 全局辅助函数
window.refreshTextAdjusterButtons = function() {
    if (textAdjuster) {
        textAdjuster.removeAllButtons();
        textAdjuster.addButtonsToAllSegments();
    }
};

window.updateTextAdjusterForSegment = function(segmentId, hasTranslation) {
    if (textAdjuster) {
        textAdjuster.updateButtonsForSegment(segmentId, hasTranslation);
    }
};