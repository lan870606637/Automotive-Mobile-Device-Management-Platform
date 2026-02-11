// 手机端后台管理 - 公共脚本

// 当前编辑的设备
let currentDevice = null;
let currentEditType = '';
let longPressTimer = null;
let users = [];

// 加载用户列表
async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        users = await response.json();
    } catch (error) {
        console.error('加载用户列表失败', error);
    }
}

// 显示借出弹窗
async function showBorrowModal(deviceId, event) {
    if (event) event.stopPropagation();

    const device = devices.find(d => d.id === deviceId);
    if (!device) return;

    currentDevice = device;

    // 加载用户列表
    await loadUsers();

    // 显示借出弹窗（使用编辑弹窗）
    const editModal = document.getElementById('editModal');
    const editTitle = document.getElementById('editModalTitle');
    const editBody = document.getElementById('editModalBody');

    editTitle.textContent = '📤 录入登记（借出设备）';

    editBody.innerHTML = `
        <div class="form-field">
            <label>选择借用人 <span class="required">*</span></label>
            <input type="text" id="editBorrowUser" list="userList" placeholder="搜索或输入借用人姓名..." autocomplete="off">
            <datalist id="userList">
                ${users.map(u => `<option value="${u.borrower_name}">${u.borrower_name} ${u.weixin_name ? '(' + u.weixin_name + ')' : ''}</option>`).join('')}
            </datalist>
        </div>
        <div class="form-field">
            <label>借出天数 <span class="required">*</span></label>
            <input type="number" id="editBorrowDays" value="1" min="1" max="365">
        </div>
        <div class="form-field">
            <label>借出备注</label>
            <textarea id="editBorrowRemarks" placeholder="可选：填写借出备注..."></textarea>
        </div>
    `;

    currentEditType = 'borrow';
    editModal.classList.add('show');
}

// 显示归还弹窗
function showReturnModal(deviceId, event) {
    if (event) event.stopPropagation();

    const device = devices.find(d => d.id === deviceId);
    if (!device) return;

    currentDevice = device;

    const editModal = document.getElementById('editModal');
    const editTitle = document.getElementById('editModalTitle');
    const editBody = document.getElementById('editModalBody');

    editTitle.textContent = '📥 强制归还设备';

    editBody.innerHTML = `
        <div class="confirm-message">
            <p>确认强制归还该设备吗？</p>
            <p class="hint">设备将回到在库状态，并记录操作日志。</p>
        </div>
    `;

    currentEditType = 'return';
    editModal.classList.add('show');
}

// 显示转借弹窗
async function showTransferModal(deviceId, event) {
    if (event) event.stopPropagation();

    const device = devices.find(d => d.id === deviceId);
    if (!device) return;

    currentDevice = device;

    // 加载用户列表
    await loadUsers();

    const editModal = document.getElementById('editModal');
    const editTitle = document.getElementById('editModalTitle');
    const editBody = document.getElementById('editModalBody');

    editTitle.textContent = '🔄 转借设备';

    editBody.innerHTML = `
        <div class="form-field">
            <label>新借用人 <span class="required">*</span></label>
            <input type="text" id="editTransferUser" list="userList" placeholder="搜索或输入新借用人..." autocomplete="off">
            <datalist id="userList">
                ${users.map(u => `<option value="${u.borrower_name}">${u.borrower_name} ${u.weixin_name ? '(' + u.weixin_name + ')' : ''}</option>`).join('')}
            </datalist>
        </div>
        <div class="form-field">
            <label>转借备注</label>
            <textarea id="editTransferRemarks" placeholder="可选：填写转借备注..."></textarea>
        </div>
    `;

    currentEditType = 'transfer';
    editModal.classList.add('show');
}

// 显示编辑弹窗
function showEditModal(deviceId, event) {
    if (event) event.stopPropagation();

    const device = devices.find(d => d.id === deviceId);
    if (!device) return;

    currentDevice = device;

    const editModal = document.getElementById('editModal');
    const editTitle = document.getElementById('editModalTitle');
    const editBody = document.getElementById('editModalBody');

    editTitle.textContent = '✏️ 编辑设备';

    editBody.innerHTML = `
        <div class="form-field">
            <label>设备名称</label>
            <input type="text" id="editDeviceName" value="${device.device_name}" disabled>
        </div>
        <div class="form-field">
            <label>型号</label>
            <input type="text" id="editDeviceModel" value="${device.model || ''}">
        </div>
        <div class="form-field">
            <label>柜号/保管人</label>
            <input type="text" id="editDeviceCabinet" value="${device.cabinet || ''}">
        </div>
        <div class="form-field">
            <label>设备备注</label>
            <textarea id="editDeviceRemarks">${device.remarks || ''}</textarea>
        </div>
    `;

    currentEditType = 'edit';
    editModal.classList.add('show');
}

// 显示字段编辑弹窗
function showEditFieldModal(deviceId, fieldType, event) {
    if (event) event.stopPropagation();

    const device = devices.find(d => d.id === deviceId);
    if (!device) return;

    currentDevice = device;

    const editModal = document.getElementById('editModal');
    const editTitle = document.getElementById('editModalTitle');
    const editBody = document.getElementById('editModalBody');

    const fieldLabels = {
        'borrower': '借用人',
        'cabinet': '柜号',
        'keeper': '保管人',
        'status': '状态'
    };

    editTitle.textContent = `✏️ 更改${fieldLabels[fieldType]}`;

    let fieldContent = '';

    switch (fieldType) {
        case 'borrower':
            fieldContent = `
                <div class="form-field">
                    <label>借用人</label>
                    <input type="text" id="editFieldValue" value="${device.borrower || ''}" placeholder="输入借用人姓名...">
                </div>
            `;
            break;
        case 'cabinet':
            fieldContent = `
                <div class="form-field">
                    <label>柜号</label>
                    <input type="text" id="editFieldValue" value="${device.cabinet || ''}" placeholder="输入柜号...">
                </div>
            `;
            break;
        case 'keeper':
            fieldContent = `
                <div class="form-field">
                    <label>保管人</label>
                    <input type="text" id="editFieldValue" value="${device.cabinet || ''}" placeholder="输入保管人...">
                </div>
            `;
            break;
        case 'status':
            fieldContent = `
                <div class="form-field">
                    <label>状态</label>
                    <select id="editFieldValue">
                        <option value="在库" ${device.status === '在库' ? 'selected' : ''}>在库</option>
                        <option value="已寄出" ${device.status === '已寄出' ? 'selected' : ''}>已寄出</option>
                        <option value="维修中" ${device.status === '维修中' ? 'selected' : ''}>维修中</option>
                        <option value="已损坏" ${device.status === '已损坏' ? 'selected' : ''}>已损坏</option>
                        <option value="报废" ${device.status === '报废' ? 'selected' : ''}>报废</option>
                        <option value="流通" ${device.status === '流通' ? 'selected' : ''}>流通</option>
                        <option value="封存" ${device.status === '封存' ? 'selected' : ''}>封存</option>
                        <option value="无柜号" ${device.status === '无柜号' ? 'selected' : ''}>无柜号</option>
                    </select>
                </div>
            `;
            break;
    }

    editBody.innerHTML = fieldContent;
    currentEditType = 'field_' + fieldType;
    editModal.classList.add('show');
}

// 关闭编辑弹窗
function closeEditModal() {
    document.getElementById('editModal').classList.remove('show');
    currentDevice = null;
    currentEditType = '';
}

// 确认编辑
async function confirmEdit() {
    if (!currentDevice) return;

    try {
        let result;

        switch (currentEditType) {
            case 'borrow':
                const user = document.getElementById('editBorrowUser').value.trim();
                const days = document.getElementById('editBorrowDays').value;
                const remarks = document.getElementById('editBorrowRemarks').value.trim();

                if (!user) {
                    showToast('请选择借用人');
                    return;
                }

                result = await fetch(`/api/devices/${currentDevice.id}/borrow`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user, days: parseInt(days), remarks })
                });
                break;

            case 'return':
                result = await fetch(`/api/devices/${currentDevice.id}/return`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                break;

            case 'transfer':
                const transferUser = document.getElementById('editTransferUser').value.trim();
                const transferRemarks = document.getElementById('editTransferRemarks').value.trim();

                if (!transferUser) {
                    showToast('请选择新借用人');
                    return;
                }

                result = await fetch(`/api/devices/${currentDevice.id}/transfer`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user: transferUser, remarks: transferRemarks })
                });
                break;

            case 'edit':
                const model = document.getElementById('editDeviceModel').value.trim();
                const cabinet = document.getElementById('editDeviceCabinet').value.trim();
                const remarks = document.getElementById('editDeviceRemarks').value.trim();

                result = await fetch(`/api/devices/${currentDevice.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model, cabinet, remarks })
                });
                break;

            case 'field_borrower':
            case 'field_cabinet':
            case 'field_keeper':
            case 'field_status':
                const fieldValue = document.getElementById('editFieldValue').value.trim();
                const fieldName = currentEditType.replace('field_', '');

                result = await fetch(`/api/devices/${currentDevice.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ [fieldName]: fieldValue })
                });
                break;
        }

        const response = await result.json();

        if (response.success) {
            showToast('操作成功');
            closeEditModal();
            loadDevices();
        } else {
            showToast(response.message || '操作失败');
        }
    } catch (error) {
        showToast('网络错误');
    }
}

// 显示Toast提示
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2000);
}
