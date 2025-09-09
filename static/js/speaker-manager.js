/**
 * 角色管理模块
 * 负责自定义角色的增删改查功能
 */

class SpeakerManager {
    constructor() {
        this.customSpeakers = [];
        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        // 可以在这里绑定角色管理相关的事件监听器
    }

    /**
     * 显示添加角色模态框
     */
    showAddSpeakerModal() {
        // 清空表单
        const voiceIdInput = document.getElementById('speakerVoiceId');
        if (voiceIdInput) {
            voiceIdInput.value = '';
        }
        
        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('addSpeakerModal'));
        modal.show();
    }

    /**
     * 添加自定义角色
     */
    async addCustomSpeaker() {
        const voiceIdInput = document.getElementById('speakerVoiceId');
        const voiceId = voiceIdInput.value.trim();
        
        if (!voiceId) {
            if (window.showToast) window.showToast('请输入语音ID');
            return;
        }

        try {
            const response = await fetch('/api/custom-speakers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ voice_id: voiceId })
            });

            const result = await response.json();
            
            if (result.success) {
                if (window.showToast) window.showToast(`成功添加角色: ${result.speaker_name}`);
                
                // 关闭模态框
                const modal = bootstrap.Modal.getInstance(document.getElementById('addSpeakerModal'));
                modal.hide();
                
                // 刷新自定义角色列表
                await this.loadCustomSpeakers();
                
                // 更新说话人选择器
                await this.updateSpeakerSelectors();
            } else {
                if (window.showToast) window.showToast('添加失败: ' + result.message);
            }
        } catch (error) {
            console.error('添加自定义角色失败:', error);
            if (window.showToast) window.showToast('添加失败: ' + error.message);
        }
    }

    /**
     * 加载自定义角色列表
     */
    async loadCustomSpeakers() {
        try {
            const response = await fetch('/api/custom-speakers');
            const result = await response.json();
            
            if (result.success) {
                this.customSpeakers = result.speakers;
                this.renderCustomSpeakers(result.speakers);
            } else {
                console.error('加载自定义角色失败:', result.message);
            }
        } catch (error) {
            console.error('加载自定义角色失败:', error);
        }
    }

    /**
     * 渲染自定义角色列表
     */
    renderCustomSpeakers(speakers) {
        const container = document.getElementById('customSpeakersContainer');
        if (!container) return;

        if (!speakers || speakers.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="bi bi-person-plus fs-4"></i>
                    <p class="mt-2 mb-0">暂无自定义角色</p>
                    <small>点击上方按钮添加</small>
                </div>
            `;
            return;
        }

        const speakersHtml = speakers.map(speaker => `
            <div class="row g-2 align-items-center mb-2 p-2 border rounded bg-light">
                <div class="col-3">
                    <strong>${speaker.speaker_name}</strong>
                </div>
                <div class="col-5">
                    <input type="text" class="form-control form-control-sm" 
                           id="customSpeaker_${speaker.speaker_name}" 
                           value="${speaker.voice_id}" 
                           onchange="speakerManager.updateCustomSpeakerVoice('${speaker.speaker_name}', this.value)"
                           placeholder="语音ID">
                </div>
                <div class="col-4">
                    <button type="button" class="btn btn-danger btn-sm w-100" 
                            onclick="speakerManager.deleteCustomSpeaker('${speaker.speaker_name}', '${speaker.speaker_name}')">
                        <i class="bi bi-trash"></i> 删除
                    </button>
                </div>
            </div>
        `).join('');

        container.innerHTML = speakersHtml;
    }

    /**
     * 更新自定义角色的语音ID
     */
    async updateCustomSpeakerVoice(speakerId, voiceId) {
        if (!voiceId.trim()) {
            if (window.showToast) window.showToast('语音ID不能为空');
            return;
        }

        try {
            const response = await fetch(`/api/custom-speakers/${speakerId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ voice_id: voiceId.trim() })
            });

            const result = await response.json();
            
            if (result.success) {
                if (window.showToast) window.showToast(`${speakerId} 语音ID已更新`);
                // 保存配置到本地存储
                this.saveCustomSpeakersConfig();
            } else {
                if (window.showToast) window.showToast('更新失败: ' + result.message);
            }
        } catch (error) {
            console.error('更新自定义角色失败:', error);
            if (window.showToast) window.showToast('更新失败: ' + error.message);
        }
    }

    /**
     * 删除自定义角色
     */
    async deleteCustomSpeaker(speakerId, speakerName) {
        if (!confirm(`确定要删除角色 ${speakerName} 吗？`)) {
            return;
        }

        try {
            const response = await fetch(`/api/custom-speakers/${speakerId}`, {
                method: 'DELETE'
            });

            const result = await response.json();
            
            if (result.success) {
                if (window.showToast) window.showToast(`已删除角色: ${speakerName}`);
                
                // 刷新自定义角色列表
                await this.loadCustomSpeakers();
                
                // 更新说话人选择器
                await this.updateSpeakerSelectors();
            } else {
                if (window.showToast) window.showToast('删除失败: ' + result.message);
            }
        } catch (error) {
            console.error('删除自定义角色失败:', error);
            if (window.showToast) window.showToast('删除失败: ' + error.message);
        }
    }

    /**
     * 更新说话人选择器
     */
    async updateSpeakerSelectors() {
        try {
            const response = await fetch('/api/custom-speakers');
            const result = await response.json();
            
            if (result.success) {
                // 更新批量修改说话人的选择器
                const batchSpeakerSelect = document.getElementById('batchSpeakerSelect');
                if (batchSpeakerSelect) {
                    // 保存当前选中的值
                    const currentValue = batchSpeakerSelect.value;
                    
                    // 清空现有选项（保留第一个默认选项）
                    const defaultOption = batchSpeakerSelect.querySelector('option[value=""]');
                    batchSpeakerSelect.innerHTML = '';
                    if (defaultOption) {
                        batchSpeakerSelect.appendChild(defaultOption);
                    }
                    
                    // 添加预定义角色
                    for (let i = 0; i <= 5; i++) {
                        const option = document.createElement('option');
                        option.value = `SPEAKER_${i.toString().padStart(2, '0')}`;
                        option.textContent = `SPEAKER_${i.toString().padStart(2, '0')}`;
                        batchSpeakerSelect.appendChild(option);
                    }
                    
                    // 添加自定义角色
                    result.speakers.forEach(speaker => {
                        const option = document.createElement('option');
                        option.value = speaker.speaker_name;
                        option.textContent = `${speaker.speaker_name} (自定义)`;
                        batchSpeakerSelect.appendChild(option);
                    });
                    
                    // 恢复之前选中的值
                    batchSpeakerSelect.value = currentValue;
                }
            }
        } catch (error) {
            console.error('更新说话人选择器失败:', error);
        }
    }

    /**
     * 保存自定义角色配置到本地存储
     */
    saveCustomSpeakersConfig() {
        try {
            const config = {};
            const customElements = document.querySelectorAll('[id^="customSpeaker_"]');
            customElements.forEach(element => {
                const speakerId = element.id.replace('customSpeaker_', '');
                config[speakerId] = {
                    voice_id: element.value
                };
            });
            
            localStorage.setItem('customSpeakersConfig', JSON.stringify(config));
        } catch (error) {
            console.error('保存自定义角色配置失败:', error);
        }
    }

    /**
     * 从本地存储加载自定义角色配置
     */
    loadCustomSpeakersConfig() {
        try {
            const saved = localStorage.getItem('customSpeakersConfig');
            if (saved) {
                const config = JSON.parse(saved);
                
                Object.keys(config).forEach(speakerId => {
                    const input = document.getElementById(`customSpeaker_${speakerId}`);
                    if (input && config[speakerId].voice_id) {
                        input.value = config[speakerId].voice_id;
                    }
                });
            }
        } catch (error) {
            console.error('加载自定义角色配置失败:', error);
        }
    }

    /**
     * 获取自定义角色列表
     */
    getCustomSpeakers() {
        return this.customSpeakers;
    }
}

// 创建全局实例
const speakerManager = new SpeakerManager();

// 导出供外部使用
window.speakerManager = speakerManager;

// 兼容性函数，保持向后兼容
window.showAddSpeakerModal = () => speakerManager.showAddSpeakerModal();
window.addCustomSpeaker = () => speakerManager.addCustomSpeaker();
window.loadCustomSpeakers = () => speakerManager.loadCustomSpeakers();
window.renderCustomSpeakers = (speakers) => speakerManager.renderCustomSpeakers(speakers);
window.updateCustomSpeakerVoice = (speakerId, voiceId) => speakerManager.updateCustomSpeakerVoice(speakerId, voiceId);
window.deleteCustomSpeaker = (speakerId, speakerName) => speakerManager.deleteCustomSpeaker(speakerId, speakerName);
window.updateSpeakerSelectors = () => speakerManager.updateSpeakerSelectors();
window.saveCustomSpeakersConfig = () => speakerManager.saveCustomSpeakersConfig();
window.loadCustomSpeakersConfig = () => speakerManager.loadCustomSpeakersConfig();