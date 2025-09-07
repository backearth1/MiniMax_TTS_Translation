/**
 * 项目管理模块
 * 处理项目列表、切换、删除等功能
 */

class ProjectManager {
    constructor() {
        this.currentProjectId = null;
        this.projects = [];
        this.isVisible = false;
    }

    // 切换项目管理面板显示/隐藏
    togglePanel() {
        const panel = document.getElementById('projectManagerPanel');
        const toggle = document.getElementById('projectManagerToggle');
        
        if (!panel) return;
        
        this.isVisible = !this.isVisible;
        panel.style.display = this.isVisible ? 'block' : 'none';
        
        if (toggle) {
            const icon = toggle.querySelector('i');
            if (icon) {
                icon.className = this.isVisible ? 'bi bi-folder2 me-1' : 'bi bi-folder2-open me-1';
            }
        }
        
        // 如果打开面板，自动加载项目列表
        if (this.isVisible) {
            this.loadProjectList();
        }
    }

    // 加载项目列表
    async loadProjectList() {
        try {
            const response = await fetch('/api/projects');
            const data = await response.json();
            
            if (data.success) {
                this.projects = data.projects;
                this.renderProjectList();
                this.updateProjectCount();
            } else {
                console.error('加载项目列表失败:', data.message);
                this.showError('加载项目列表失败');
            }
        } catch (error) {
            console.error('加载项目列表失败:', error);
            this.showError('网络请求失败');
        }
    }

    // 渲染项目列表
    renderProjectList() {
        const listContainer = document.getElementById('projectList');
        if (!listContainer) return;

        if (this.projects.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="bi bi-inbox fs-1"></i>
                    <p class="mt-2 mb-0">暂无项目</p>
                    <small>上传SRT文件创建新项目</small>
                </div>
            `;
            return;
        }

        const projectCards = this.projects.map(project => this.createProjectCard(project)).join('');
        listContainer.innerHTML = projectCards;
    }

    // 创建项目卡片HTML
    createProjectCard(project) {
        const isActive = this.currentProjectId === project.id;
        const updatedAt = new Date(project.updated_at).toLocaleString('zh-CN');
        
        return `
            <div class="project-card mb-2 p-2 border rounded ${isActive ? 'border-primary bg-primary bg-opacity-10' : 'border-light'}" 
                 data-project-id="${project.id}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1" style="min-width: 0;">
                        <div class="d-flex align-items-center mb-1">
                            <i class="bi bi-file-earmark-text me-2 text-primary"></i>
                            <strong class="text-truncate" title="${project.filename}">${project.filename}</strong>
                            ${isActive ? '<span class="badge bg-primary ms-2">当前</span>' : ''}
                        </div>
                        <div class="small text-muted">
                            <i class="bi bi-clock me-1"></i>${updatedAt}
                            <span class="ms-2">
                                <i class="bi bi-list-ol me-1"></i>${project.total_segments} 段落
                            </span>
                        </div>
                    </div>
                    <div class="dropdown">
                        <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" 
                                data-bs-toggle="dropdown" aria-expanded="false">
                            <i class="bi bi-three-dots"></i>
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end">
                            ${!isActive ? `
                                <li><a class="dropdown-item" href="#" onclick="projectManager.switchToProject('${project.id}')">
                                    <i class="bi bi-arrow-right-circle me-2"></i>切换到此项目
                                </a></li>
                            ` : ''}
                            <li><a class="dropdown-item text-danger" href="#" onclick="projectManager.deleteProject('${project.id}', '${project.filename}')">
                                <i class="bi bi-trash me-2"></i>删除项目
                            </a></li>
                        </ul>
                    </div>
                </div>
            </div>
        `;
    }

    // 更新项目数量显示
    updateProjectCount() {
        const badge = document.getElementById('projectCountBadge');
        if (badge) {
            badge.textContent = `${this.projects.length}/5`;
            badge.className = this.projects.length >= 5 ? 'badge bg-warning ms-2' : 'badge bg-primary ms-2';
        }
    }

    // 切换到指定项目
    async switchToProject(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/switch`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentProjectId = projectId;
                this.renderProjectList(); // 重新渲染以更新当前项目状态
                
                // 加载项目段落
                if (typeof loadProjectSegments === 'function') {
                    await loadProjectSegments(projectId);
                }
                
                this.showSuccess(`已切换到项目: ${data.project.filename}`);
                
                // 添加到日志
                if (typeof addLog === 'function') {
                    addLog(`✅ 已切换到项目: ${data.project.filename}`);
                }
            } else {
                this.showError('切换项目失败: ' + (data.message || '未知错误'));
            }
        } catch (error) {
            console.error('切换项目失败:', error);
            this.showError('切换项目失败: 网络请求失败');
        }
    }

    // 删除项目
    async deleteProject(projectId, filename) {
        if (!confirm(`确定要删除项目 "${filename}" 吗？此操作无法撤销。`)) {
            return;
        }

        try {
            const response = await fetch(`/api/projects/${projectId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                // 从本地列表中移除
                this.projects = this.projects.filter(p => p.id !== projectId);
                
                // 如果删除的是当前项目，清除当前项目ID
                if (this.currentProjectId === projectId) {
                    this.currentProjectId = null;
                    
                    // 如果还有其他项目，切换到最新的
                    if (this.projects.length > 0) {
                        await this.switchToProject(this.projects[0].id);
                    } else {
                        // 没有项目了，加载示例文件
                        if (typeof loadSampleSrt === 'function') {
                            loadSampleSrt();
                        }
                    }
                }
                
                this.renderProjectList();
                this.updateProjectCount();
                this.showSuccess(data.message);
                
                // 添加到日志
                if (typeof addLog === 'function') {
                    addLog(`🗑️ ${data.message}`);
                }
            } else {
                this.showError('删除失败: ' + (data.message || '未知错误'));
            }
        } catch (error) {
            console.error('删除项目失败:', error);
            this.showError('删除项目失败: 网络请求失败');
        }
    }

    // 清理旧项目
    async cleanupOldProjects() {
        if (!confirm('确定要清理旧项目吗？将只保留最近的3个项目，其余项目会被删除。')) {
            return;
        }

        try {
            const response = await fetch('/api/projects/cleanup?keep_count=3', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess(data.message);
                
                // 重新加载项目列表
                await this.loadProjectList();
                
                // 添加到日志
                if (typeof addLog === 'function') {
                    addLog(`🧹 ${data.message}`);
                }
            } else {
                this.showError('清理失败: ' + (data.message || '未知错误'));
            }
        } catch (error) {
            console.error('清理项目失败:', error);
            this.showError('清理项目失败: 网络请求失败');
        }
    }

    // 刷新项目列表
    async refreshProjectList() {
        await this.loadProjectList();
        this.showSuccess('项目列表已刷新');
    }

    // 显示成功消息
    showSuccess(message) {
        if (typeof showToast === 'function') {
            showToast(message, 'success');
        } else {
            console.log('✅', message);
        }
    }

    // 显示错误消息
    showError(message) {
        if (typeof showToast === 'function') {
            showToast(message, 'error');
        } else {
            console.error('❌', message);
        }
    }

    // 设置当前项目ID
    setCurrentProjectId(projectId) {
        this.currentProjectId = projectId;
        if (this.isVisible) {
            this.renderProjectList();
        }
    }

    // 获取项目数量
    getProjectCount() {
        return this.projects.length;
    }

    // 检查是否可以创建新项目
    canCreateNewProject() {
        return this.projects.length < 5;
    }
}

// 创建全局项目管理器实例
const projectManager = new ProjectManager();

// 全局函数，供HTML调用
function toggleProjectManager() {
    projectManager.togglePanel();
}

function refreshProjectList() {
    projectManager.refreshProjectList();
}

function cleanupOldProjects() {
    projectManager.cleanupOldProjects();
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 如果全局变量 currentProjectId 存在，设置到项目管理器
    if (typeof window.currentProjectId !== 'undefined' && window.currentProjectId) {
        projectManager.setCurrentProjectId(window.currentProjectId);
    }
});