/* 教师端页面交互。 */
(function () {
  'use strict';

  const page = document.body.dataset.page;
  const state = {
    materialsSubject: '数学',
    homeworkSubject: '数学',
    submissions: [],
    skills: [],
    audit: { page: 1, page_size: 20, skill: '', status: '' }
  };

  function init() {
    if (page === 'teacher-dashboard') initDashboard();
    else if (page === 'teacher-lectures') initLectures();
    else if (page === 'teacher-assistant') initAssistant();
    else if (page === 'teacher-homework') initHomework();
    else if (page === 'teacher-audit') initAudit();
  }

  /* ===== 本班首页 ===== */
  async function initDashboard() {
    try {
      const data = await CC.api('/api/teacher/dashboard');
      const stats = data.stats || {};
      setText('stat-students', stats.students);
      setText('stat-assignments', stats.assignments);
      setText('stat-submissions', stats.submissions);
      setText('stat-pending', stats.pending);
      setText('stat-skill-calls', stats.skill_calls);

      const bars = document.getElementById('mastery-bars');
      if (bars) {
        bars.innerHTML = Object.keys(stats.mastery || {}).map(function (subject) {
          const value = stats.mastery[subject];
          const width = value == null ? 0 : Math.max(0, Math.min(100, value));
          const display = value == null ? '暂无数据' : value + ' 分';
          return '<div class="bar-row">' +
            '<div class="bar-label">' + CC.escape(subject) + '</div>' +
            '<div class="bar-track"><div class="bar-fill' + (value == null ? ' empty' : '') +
            '" style="width:' + width + '%"></div></div>' +
            '<div class="bar-value">' + CC.escape(display) + '</div>' +
            '</div>';
        }).join('');
      }

      const recent = document.getElementById('recent-list');
      if (recent) {
        const items = data.recent || [];
        if (!items.length) {
          recent.innerHTML = CC.emptyRow('暂无已批改提交');
        } else {
          recent.innerHTML = items.map(function (item) {
            return '<div class="list-row">' +
              '<div><div class="list-title">' + CC.escape(item.student_name || '学生') + ' · ' +
              CC.escape(item.assignment_title || '作业') + '</div>' +
              '<div class="list-desc">' + CC.escape(CC.truncate(item.content, 60)) + '</div>' +
              '<div class="meta">' + CC.fmtDate(item.graded_at || item.created_at) + '</div></div>' +
              '<div class="row gap-8">' +
              '<span class="badge badge-brand">终评 ' + CC.fmtScore(item.final_score) + '</span>' +
              (item.teacher_score != null ? '<span class="badge badge-ok">教师终评</span>' :
                '<span class="badge badge-neutral">AI 初评</span>') +
              '</div></div>';
          }).join('');
        }
      }
    } catch (error) {
      CC.toast(error.message, 'error');
    }
  }

  /* ===== 讲义管理 ===== */
  function initLectures() {
    const tabs = CC.setSubjectTabs('material-tabs', state.materialsSubject, function (subject) {
      state.materialsSubject = subject;
      loadMaterials();
    });
    state.materialsSubject = tabs.get();
    loadMaterials();

    const openBtn = document.getElementById('material-upload-open');
    const saveBtn = document.getElementById('material-save');
    if (openBtn) {
      openBtn.addEventListener('click', function () {
        document.getElementById('material-subject').value = state.materialsSubject;
        document.getElementById('material-title').value = '';
        document.getElementById('material-content').value = '';
        CC.openModal('material-modal');
      });
    }
    if (saveBtn) {
      saveBtn.addEventListener('click', async function () {
        const title = document.getElementById('material-title').value.trim();
        const content = document.getElementById('material-content').value.trim();
        if (!title || title.length > 200) {
          CC.toast('讲义标题必须为 1—200 字符', 'error');
          return;
        }
        if (!content) {
          CC.toast('讲义正文不能为空', 'error');
          return;
        }
        saveBtn.disabled = true;
        try {
          await CC.api('/api/teacher/materials', {
            method: 'POST',
            body: { subject: state.materialsSubject, title: title, content: content }
          });
          CC.closeModal('material-modal');
          CC.toast('讲义已上传并完成切片入库', 'ok');
          loadMaterials();
        } catch (error) {
          CC.toast(error.message, 'error');
        } finally {
          saveBtn.disabled = false;
        }
      });
    }
  }

  async function loadMaterials() {
    const list = document.getElementById('material-list');
    if (!list) return;
    list.innerHTML = '<div class="muted small">加载中…</div>';
    try {
      const data = await CC.api('/api/teacher/materials?subject=' + encodeURIComponent(state.materialsSubject));
      if (!data.items.length) {
        list.innerHTML = CC.emptyRow('该学科暂无讲义，点击右上角上传');
        return;
      }
      list.innerHTML = data.items.map(function (item) {
        return '<div class="list-row">' +
          '<div><div class="list-title">' + CC.escape(item.title) + '</div>' +
          '<div class="meta">' + CC.escape(item.subject) + ' · ' + item.chunk_count +
          ' 个知识库片段 · ' + CC.fmtDate(item.created_at) + '</div></div>' +
          '<button class="btn btn-outline btn-sm" data-delete-material="' + item.id + '">删除</button>' +
          '</div>';
      }).join('');
      list.querySelectorAll('[data-delete-material]').forEach(function (button) {
        button.addEventListener('click', async function () {
          if (!window.confirm('确定删除该讲义？对应知识库片段也会一并删除。')) return;
          try {
            await CC.api('/api/teacher/materials/' + button.dataset.deleteMaterial, { method: 'DELETE' });
            CC.toast('讲义已删除', 'ok');
            loadMaterials();
          } catch (error) {
            CC.toast(error.message, 'error');
          }
        });
      });
    } catch (error) {
      list.innerHTML = '<div class="muted small">' + CC.escape(error.message) + '</div>';
    }
  }

  /* ===== 助手配置 ===== */
  async function initAssistant() {
    try {
      const config = await CC.api('/api/teacher/config');
      setText('api-key-value', config.api_key_masked);
      const mode = document.getElementById('ai-mode');
      if (mode) {
        mode.textContent = config.ai_mode === 'gateway' ? '在线网关' : '本地演示';
        mode.className = 'badge ' + (config.ai_mode === 'gateway' ? 'badge-ok' : 'badge-warn');
      }
    } catch (error) {
      CC.toast(error.message, 'error');
    }

    loadSkills();
    loadMcpServers();

    const mcpOpen = document.getElementById('mcp-add-open');
    if (mcpOpen) {
      mcpOpen.addEventListener('click', function () {
        document.getElementById('mcp-name').value = '';
        document.getElementById('mcp-url').value = '';
        CC.openModal('mcp-modal');
      });
    }
    const mcpSave = document.getElementById('mcp-save');
    if (mcpSave) {
      mcpSave.addEventListener('click', async function () {
        const name = document.getElementById('mcp-name').value.trim();
        const url = document.getElementById('mcp-url').value.trim();
        if (!name || !url) {
          CC.toast('请填写服务器名称与地址', 'error');
          return;
        }
        mcpSave.disabled = true;
        try {
          await CC.api('/api/teacher/mcp-servers', { method: 'POST', body: { name: name, url: url } });
          CC.closeModal('mcp-modal');
          CC.toast('MCP 服务器已添加并连接', 'ok');
          loadMcpServers();
        } catch (error) {
          CC.toast(error.message, 'error');
        } finally {
          mcpSave.disabled = false;
        }
      });
    }

    const skillSave = document.getElementById('skill-save');
    if (skillSave) {
      skillSave.addEventListener('click', async function () {
        const key = document.getElementById('skill-key').value;
        const payload = {
          prompt: document.getElementById('skill-prompt').value,
          trigger_condition: document.getElementById('skill-trigger').value,
          behavior: document.getElementById('skill-behavior').value,
          enabled: document.getElementById('skill-enabled').checked
        };
        skillSave.disabled = true;
        try {
          await CC.api('/api/teacher/skills/' + encodeURIComponent(key), { method: 'PUT', body: payload });
          CC.closeModal('skill-modal');
          CC.toast('技能配置已保存', 'ok');
          loadSkills();
        } catch (error) {
          CC.toast(error.message, 'error');
        } finally {
          skillSave.disabled = false;
        }
      });
    }
  }

  async function loadSkills() {
    const list = document.getElementById('skill-list');
    if (!list) return;
    list.innerHTML = '<div class="muted small">加载中…</div>';
    try {
      const data = await CC.api('/api/teacher/skills');
      state.skills = data.items || [];
      if (!state.skills.length) {
        list.innerHTML = CC.emptyRow('暂无技能');
        return;
      }
      list.innerHTML = state.skills.map(function (skill) {
        const disabled = skill.required ? ' disabled' : '';
        const toggleClass = skill.required ? ' toggle-disabled' : '';
        return '<div class="skill-item">' +
          '<div class="skill-main">' +
          '<div class="skill-name">' + CC.escape(skill.name) +
          (skill.required ? ' <span class="badge badge-danger">必做</span>' : '') +
          ' <span class="badge ' + (skill.enabled ? 'badge-ok' : 'badge-neutral') + '">' +
          (skill.enabled ? '已启用' : '已停用') + '</span></div>' +
          '<div class="skill-meta">键：' + CC.escape(skill.skill_key) + '</div>' +
          '<div class="skill-meta">触发条件：' + CC.escape(skill.trigger_condition || '—') + '</div>' +
          '<div class="skill-meta">行为说明：' + CC.escape(skill.behavior || '—') + '</div>' +
          '</div>' +
          '<label class="toggle' + toggleClass + '">' +
          '<input type="checkbox" data-toggle-skill="' + CC.escape(skill.skill_key) + '"' +
          (skill.enabled ? ' checked' : '') + disabled + '>' +
          '<span class="toggle-track"><span class="toggle-thumb"></span></span></label>' +
          '<button class="btn btn-outline btn-sm" data-edit-skill="' + CC.escape(skill.skill_key) + '">编辑</button>' +
          '</div>';
      }).join('');

      list.querySelectorAll('[data-toggle-skill]').forEach(function (input) {
        input.addEventListener('change', async function () {
          const key = input.dataset.toggleSkill;
          try {
            await CC.api('/api/teacher/skills/' + encodeURIComponent(key), {
              method: 'PUT',
              body: { enabled: input.checked }
            });
            CC.toast('技能状态已更新', 'ok');
            loadSkills();
          } catch (error) {
            input.checked = !input.checked;
            CC.toast(error.message, 'error');
          }
        });
      });
      list.querySelectorAll('[data-edit-skill]').forEach(function (button) {
        button.addEventListener('click', function () {
          openSkill(button.dataset.editSkill);
        });
      });
    } catch (error) {
      list.innerHTML = '<div class="muted small">' + CC.escape(error.message) + '</div>';
    }
  }

  function openSkill(key) {
    const skill = state.skills.find(function (item) { return item.skill_key === key; });
    if (!skill) return;
    document.getElementById('skill-key').value = skill.skill_key;
    document.getElementById('skill-modal-title').textContent = '编辑技能 · ' + skill.name;
    document.getElementById('skill-name').value = skill.name;
    document.getElementById('skill-trigger').value = skill.trigger_condition || '';
    document.getElementById('skill-behavior').value = skill.behavior || '';
    document.getElementById('skill-prompt').value = skill.prompt || '';
    document.getElementById('skill-enabled').checked = !!skill.enabled;
    document.getElementById('skill-enabled').disabled = !!skill.required;
    document.getElementById('skill-required-tip').textContent = skill.required
      ? '该技能为必做技能，可编辑提示词，但不能停用。'
      : '技能开关由教师控制，学生端只能查看名称与触发条件。';
    CC.openModal('skill-modal');
  }

  async function loadMcpServers() {
    const grid = document.getElementById('mcp-grid');
    if (!grid) return;
    grid.innerHTML = '<div class="muted small">加载中…</div>';
    try {
      const data = await CC.api('/api/teacher/mcp-servers');
      if (!data.items.length) {
        grid.innerHTML = CC.emptyRow('尚未添加 MCP 服务器');
        return;
      }
      grid.innerHTML = data.items.map(function (server) {
        const connected = server.status === 'connected';
        return '<div class="mcp-card' + (connected ? ' connected' : '') + '">' +
          '<div class="mcp-head"><strong>' + CC.escape(server.name) + '</strong>' +
          '<span class="badge ' + (connected ? 'badge-ok' : 'badge-neutral') + '">' +
          CC.escape(server.status) + '</span></div>' +
          '<div class="mcp-url">' + CC.escape(server.url) + '</div>' +
          '<div class="mcp-tools">' + (server.tools.length
            ? server.tools.map(function (tool) { return '<span class="tag">' + CC.escape(tool) + '</span>'; }).join('')
            : '<span class="muted small">未发现工具</span>') + '</div>' +
          '<div class="row gap-8">' +
          (connected
            ? '<button class="btn btn-outline btn-sm" data-disconnect="' + server.id + '">断开</button>'
            : '<button class="btn btn-outline btn-sm" data-connect="' + server.id + '">连接</button>') +
          '<button class="btn btn-outline btn-sm" data-delete-mcp="' + server.id + '">删除</button>' +
          '</div></div>';
      }).join('');

      grid.querySelectorAll('[data-connect]').forEach(function (button) {
        button.addEventListener('click', function () { mcpAction(button.dataset.connect, 'connect'); });
      });
      grid.querySelectorAll('[data-disconnect]').forEach(function (button) {
        button.addEventListener('click', function () { mcpAction(button.dataset.disconnect, 'disconnect'); });
      });
      grid.querySelectorAll('[data-delete-mcp]').forEach(function (button) {
        button.addEventListener('click', async function () {
          if (!window.confirm('确定删除该 MCP 服务器？')) return;
          try {
            await CC.api('/api/teacher/mcp-servers/' + button.dataset.deleteMcp, { method: 'DELETE' });
            CC.toast('MCP 服务器已删除', 'ok');
            loadMcpServers();
          } catch (error) {
            CC.toast(error.message, 'error');
          }
        });
      });
    } catch (error) {
      grid.innerHTML = '<div class="muted small">' + CC.escape(error.message) + '</div>';
    }
  }

  async function mcpAction(id, action) {
    try {
      await CC.api('/api/teacher/mcp-servers/' + id + '/' + action, { method: 'POST' });
      CC.toast(action === 'connect' ? '已连接' : '已断开', 'ok');
      loadMcpServers();
    } catch (error) {
      CC.toast(error.message, 'error');
    }
  }

  /* ===== 作业与改分 ===== */
  function initHomework() {
    const tabs = CC.setSubjectTabs('submission-tabs', state.homeworkSubject, function (subject) {
      state.homeworkSubject = subject;
      loadSubmissions();
    });
    state.homeworkSubject = tabs.get();
    loadSubmissions();

    const gradeSave = document.getElementById('grade-save');
    if (gradeSave) gradeSave.addEventListener('click', saveGrade);
    const markBtn = document.getElementById('grade-mark-wrong');
    if (markBtn) markBtn.addEventListener('click', markWrong);
    const undoBtn = document.getElementById('grade-undo-wrong');
    if (undoBtn) undoBtn.addEventListener('click', undoMarkWrong);
    const assignOpen = document.getElementById('assignment-open');
    if (assignOpen) {
      assignOpen.addEventListener('click', function () {
        document.getElementById('assignment-subject').value = state.homeworkSubject;
        document.getElementById('assignment-title').value = '';
        document.getElementById('assignment-description').value = '';
        document.getElementById('assignment-deadline').value = '';
        document.getElementById('assignment-error').classList.add('hidden');
        CC.openModal('assignment-modal');
      });
    }
    const assignSave = document.getElementById('assignment-save');
    if (assignSave) assignSave.addEventListener('click', createAssignment);
  }

  async function loadSubmissions() {
    const body = document.getElementById('submission-table-body');
    const empty = document.getElementById('submission-empty');
    const total = document.getElementById('submission-total');
    if (!body) return;
    body.innerHTML = '<tr><td colspan="6" class="muted small">加载中…</td></tr>';
    try {
      const data = await CC.api('/api/teacher/submissions?subject=' +
        encodeURIComponent(state.homeworkSubject));
      state.submissions = data.items || [];
      if (total) total.textContent = '共 ' + data.total + ' 条';
      if (!state.submissions.length) {
        body.innerHTML = '';
        empty.classList.remove('hidden');
        return;
      }
      empty.classList.add('hidden');
      body.innerHTML = state.submissions.map(function (item) {
        return '<tr>' +
          '<td><strong>' + CC.escape(item.student_name || item.student_id) + '</strong><div class="muted small">' +
          CC.fmtDate(item.created_at) + '</div></td>' +
          '<td class="table-answer">' + CC.escape(CC.truncate(item.content, 80)) + '</td>' +
          '<td>' + CC.statusBadge(item.status) + '</td>' +
          '<td>' + CC.fmtScore(item.ai_score) + '</td>' +
          '<td>' + (item.teacher_score == null
            ? '<span class="muted small">—</span>'
            : '<strong>' + item.teacher_score + '</strong><div class="muted small">教师终评</div>') + '</td>' +
          '<td><div class="row gap-8">' +
          '<button class="btn btn-outline btn-sm" data-grade="' + item.id + '">改分</button>' +
          (item.status === 'failed'
            ? '<button class="btn btn-outline btn-sm" data-retry="' + item.id + '">重试</button>'
            : '') +
          '</div></td></tr>';
      }).join('');

      body.querySelectorAll('[data-grade]').forEach(function (button) {
        button.addEventListener('click', function () { openGrade(button.dataset.grade); });
      });
      body.querySelectorAll('[data-retry]').forEach(function (button) {
        button.addEventListener('click', function () { retrySubmission(button.dataset.retry); });
      });
    } catch (error) {
      body.innerHTML = '<tr><td colspan="6" class="muted small">' + CC.escape(error.message) + '</td></tr>';
    }
  }

  function openGrade(id) {
    const item = state.submissions.find(function (entry) { return String(entry.id) === String(id); });
    if (!item) return;
    const tip = document.getElementById('grade-status-tip');
    const disabled = item.status !== 'graded';
    document.getElementById('grade-submission-id').value = item.id;
    document.getElementById('grade-content').textContent = item.content;
    document.getElementById('grade-ai-score').textContent = CC.fmtScore(item.ai_score) + ' 分';
    document.getElementById('grade-ai-comment').textContent = item.ai_comment || '暂无评语';
    const evidence = item.ai_evidence || [];
    document.getElementById('grade-evidence').innerHTML = evidence.length
      ? '依据：' + evidence.map(function (hit) {
        return '<span class="tag">' + CC.escape(hit.material_title) + ' · 段' + hit.chunk_no + '</span>';
      }).join(' ')
      : '依据：本班知识库未命中讲义，未引用来源。';
    document.getElementById('grade-score').value = item.teacher_score == null ? (item.ai_score == null ? '' : item.ai_score) : item.teacher_score;
    document.getElementById('grade-comment').value = item.teacher_comment || '';
    document.getElementById('grade-error').classList.add('hidden');

    if (disabled) {
      tip.className = 'notice notice-warn';
      tip.textContent = '该提交尚未完成 AI 批改，暂不能写入终评。';
    } else {
      tip.className = 'notice notice-info';
      tip.textContent = 'AI 初评已保存，教师终评将写入独立字段，不会覆盖 AI 原始结果。';
    }
    document.getElementById('grade-save').disabled = disabled;
    document.getElementById('grade-mark-wrong').classList.toggle('hidden', disabled || item.is_wrong);
    document.getElementById('grade-undo-wrong').classList.toggle('hidden', disabled || !item.is_wrong);
    CC.openModal('grade-modal');
  }

  async function saveGrade() {
    const id = document.getElementById('grade-submission-id').value;
    const errorBox = document.getElementById('grade-error');
    const raw = document.getElementById('grade-score').value.trim();
    const score = Number(raw);
    if (!raw || !Number.isInteger(score) || score < 0 || score > 100) {
      showGradeError('终评分数必须为 0—100 的整数');
      return;
    }
    const comment = document.getElementById('grade-comment').value;
    if (comment.length > 500) {
      showGradeError('终评评语不能超过 500 字符');
      return;
    }
    const button = document.getElementById('grade-save');
    button.disabled = true;
    try {
      await CC.api('/api/submissions/' + id + '/score', {
        method: 'PATCH',
        body: { teacher_score: score, teacher_comment: comment }
      });
      CC.closeModal('grade-modal');
      CC.toast('教师终评已保存，学生端刷新后可见', 'ok');
      loadSubmissions();
    } catch (error) {
      showGradeError(error.message);
    } finally {
      button.disabled = false;
    }
  }

  function showGradeError(message) {
    const box = document.getElementById('grade-error');
    box.textContent = message;
    box.classList.remove('hidden');
  }

  async function markWrong() {
    const id = document.getElementById('grade-submission-id').value;
    try {
      await CC.api('/api/submissions/' + id + '/mark-wrong', { method: 'POST' });
      CC.closeModal('grade-modal');
      CC.toast('已标记为错，学生错题页将出现该题', 'ok');
      loadSubmissions();
    } catch (error) {
      showGradeError(error.message);
    }
  }

  async function undoMarkWrong() {
    const id = document.getElementById('grade-submission-id').value;
    try {
      await CC.api('/api/submissions/' + id + '/mark-wrong', { method: 'DELETE' });
      CC.closeModal('grade-modal');
      CC.toast('已撤销判错，错题记录与讲解一并失效', 'ok');
      loadSubmissions();
    } catch (error) {
      showGradeError(error.message);
    }
  }

  async function retrySubmission(id) {
    try {
      await CC.api('/api/teacher/submissions/' + id + '/retry', { method: 'POST' });
      CC.toast('已重新加入批改队列', 'ok');
      loadSubmissions();
    } catch (error) {
      CC.toast(error.message, 'error');
    }
  }

  async function createAssignment() {
    const errorBox = document.getElementById('assignment-error');
    const title = document.getElementById('assignment-title').value.trim();
    const description = document.getElementById('assignment-description').value.trim();
    const deadlineRaw = document.getElementById('assignment-deadline').value;
    errorBox.classList.add('hidden');
    if (!title) {
      errorBox.textContent = '请填写作业标题';
      errorBox.classList.remove('hidden');
      return;
    }
    if (!deadlineRaw) {
      errorBox.textContent = '请选择截止时间';
      errorBox.classList.remove('hidden');
      return;
    }
    const deadline = new Date(deadlineRaw);
    if (Number.isNaN(deadline.getTime())) {
      errorBox.textContent = '截止时间格式不合法';
      errorBox.classList.remove('hidden');
      return;
    }
    const button = document.getElementById('assignment-save');
    button.disabled = true;
    try {
      await CC.api('/api/assignments', {
        method: 'POST',
        body: {
          subject: document.getElementById('assignment-subject').value,
          title: title,
          description: description,
          deadline: deadline.toISOString()
        }
      });
      CC.closeModal('assignment-modal');
      CC.toast('作业已发布', 'ok');
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.classList.remove('hidden');
    } finally {
      button.disabled = false;
    }
  }

  /* ===== 审计与统计 ===== */
  async function initAudit() {
    await loadAuditSummary();
    await loadAuditLogs();
    const skillFilter = document.getElementById('audit-filter-skill');
    const statusFilter = document.getElementById('audit-filter-status');
    const refresh = document.getElementById('audit-refresh');
    if (skillFilter) {
      skillFilter.addEventListener('change', function () {
        state.audit.skill = skillFilter.value;
        state.audit.page = 1;
        loadAuditLogs();
      });
    }
    if (statusFilter) {
      statusFilter.addEventListener('change', function () {
        state.audit.status = statusFilter.value;
        state.audit.page = 1;
        loadAuditLogs();
      });
    }
    if (refresh) {
      refresh.addEventListener('click', function () {
        loadAuditSummary();
        loadAuditLogs();
      });
    }
    const prev = document.getElementById('audit-prev');
    const next = document.getElementById('audit-next');
    if (prev) {
      prev.addEventListener('click', function () {
        if (state.audit.page > 1) {
          state.audit.page -= 1;
          loadAuditLogs();
        }
      });
    }
    if (next) {
      next.addEventListener('click', function () {
        state.audit.page += 1;
        loadAuditLogs();
      });
    }
    checkAuditHealth();
  }

  async function loadAuditSummary() {
    try {
      const data = await CC.api('/api/teacher/audit/summary');
      const overall = data.overall || {};
      setText('stat-total', overall.total);
      setText('stat-failures', overall.failures);
      setText('stat-tokens', overall.tokens == null ? '暂无数据' : overall.tokens);
      setText('stat-skills', (overall.skills || []).length);

      const body = document.getElementById('skill-summary-body');
      const empty = document.getElementById('skill-summary-empty');
      const skills = data.skills || [];
      if (!skills.length) {
        body.innerHTML = '';
        empty.classList.remove('hidden');
      } else {
        empty.classList.add('hidden');
        body.innerHTML = skills.map(function (row) {
          return '<tr><td>' + CC.escape(CC.skillLabel(row.skill)) + '</td>' +
            '<td>' + row.count + '</td>' +
            '<td>' + CC.fmtRate(row.fail_rate) + '</td>' +
            '<td>' + (row.tokens == null ? '<span class="muted small">暂无数据</span>' : row.tokens) + '</td></tr>';
        }).join('');
      }

      const select = document.getElementById('audit-filter-skill');
      if (select) {
        const current = select.value;
        select.innerHTML = '<option value="">全部技能</option>' + (data.overall.skills || []).map(function (key) {
          return '<option value="' + CC.escape(key) + '">' + CC.escape(CC.skillLabel(key)) + '</option>';
        }).join('');
        select.value = current;
      }
    } catch (error) {
      CC.toast(error.message, 'error');
    }
  }

  async function loadAuditLogs() {
    const body = document.getElementById('audit-table-body');
    const empty = document.getElementById('audit-empty');
    if (!body) return;
    body.innerHTML = '<tr><td colspan="7" class="muted small">加载中…</td></tr>';
    const params = new URLSearchParams();
    params.set('page', state.audit.page);
    params.set('page_size', state.audit.page_size);
    if (state.audit.skill) params.set('skill', state.audit.skill);
    if (state.audit.status) params.set('status', state.audit.status);
    try {
      const data = await CC.api('/api/teacher/audit?' + params.toString());
      const items = data.items || [];
      if (!items.length) {
        body.innerHTML = '';
        empty.classList.remove('hidden');
      } else {
        empty.classList.add('hidden');
        body.innerHTML = items.map(function (item) {
          const summary = CC.truncate(JSON.stringify(item.params || {}), 80);
          return '<tr>' +
            '<td class="muted small">' + CC.fmtDate(item.created_at) + '</td>' +
            '<td>' + CC.escape(item.user_name || item.user_id || '未登录') + '</td>' +
            '<td>' + CC.escape(item.action || '—') + '</td>' +
            '<td>' + CC.escape(item.skill ? CC.skillLabel(item.skill) : '—') + '</td>' +
            '<td>' + statusBadgeForAudit(item.status) + '</td>' +
            '<td class="muted small">' + (item.duration_ms == null ? '—' : item.duration_ms + ' ms') + '</td>' +
            '<td class="muted small">' + CC.escape(summary) + '</td></tr>';
        }).join('');
      }
      const totalPages = Math.max(1, Math.ceil((data.total || 0) / (data.page_size || state.audit.page_size)));
      document.getElementById('audit-page-info').textContent =
        '第 ' + data.page + ' / ' + totalPages + ' 页 · 共 ' + data.total + ' 条';
      document.getElementById('audit-prev').disabled = data.page <= 1;
      document.getElementById('audit-next').disabled = data.page >= totalPages;
      state.audit.page = data.page;
    } catch (error) {
      body.innerHTML = '<tr><td colspan="7" class="muted small">' + CC.escape(error.message) + '</td></tr>';
    }
  }

  function statusBadgeForAudit(status) {
    const map = {
      success: 'badge-ok',
      failed: 'badge-danger',
      error: 'badge-danger',
      timeout: 'badge-warn'
    };
    return '<span class="badge ' + (map[status] || 'badge-neutral') + '">' + CC.escape(status || '—') + '</span>';
  }

  async function checkAuditHealth() {
    try {
      const response = await fetch('/healthz', { credentials: 'same-origin' });
      const data = await response.json();
      if (data.audit_failures > 0) {
        const page = document.querySelector('.page');
        const notice = document.createElement('div');
        notice.className = 'notice notice-danger mt-16';
        notice.textContent = '审计数据可能不完整：已有 ' + data.audit_failures +
          ' 次审计写入失败，请检查数据库连接。';
        if (page && page.children.length > 1) page.insertBefore(notice, page.children[1]);
      }
    } catch (error) {
      /* 健康检查不可用时不影响页面主流程 */
    }
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value == null ? '—' : String(value);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
