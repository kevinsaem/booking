/* static/js/booking.js */
/* 예약 페이지 전용 JavaScript */
/* 단계별 전환: 날짜 → 시간 → 멘토 (각 단계에서 이전 단계를 접음) */

// ===== 상태 관리 =====
var bookingState = {
    date: null,
    time: null,
    roomIdx: null,
    teacherId: null,
    teacherName: null,
    settleCode: (typeof currentSettleCode !== 'undefined') ? currentSettleCode : 0
};

// ===== 날짜 선택 =====
function selectDate(date, element) {
    // 이전 선택 해제
    document.querySelectorAll('.cal-day.selected').forEach(function(el) {
        el.classList.remove('selected', 'bg-nv-500', 'text-white', 'font-bold', 'shadow-md');
        el.classList.add('bg-nv-50', 'text-nv-700', 'font-medium');
    });

    // 새 선택
    element.classList.remove('bg-nv-50', 'text-nv-700', 'font-medium');
    element.classList.add('selected', 'bg-nv-500', 'text-white', 'font-bold', 'shadow-md');

    bookingState.date = date;
    bookingState.time = null;
    bookingState.roomIdx = null;
    bookingState.teacherId = null;

    // 캘린더 보이기, 시간 영역 보이기, 멘토 영역 숨기기
    showSection('calendar-section', true);
    showSection('time-slots-area', true);
    showSection('teacher-list-area', false);
    document.getElementById('teacher-list-area').innerHTML = '';
    hideSelectedSummary();

    // 시간 슬롯 로드 (HTMX) - settle_code 포함
    htmx.ajax('GET', '/booking/partials/time-slots?date=' + date + '&settle_code=' + bookingState.settleCode, {
        target: '#time-slots-area',
        swap: 'innerHTML'
    });

    updateStep('시간 선택', '3/7', 42);
    updateNextButton();
}

// ===== 시간 선택 =====
function selectTime(time, roomIdx, element) {
    bookingState.time = time;
    bookingState.roomIdx = roomIdx;
    bookingState.teacherId = null;

    // 캘린더 + 시간 목록 숨기고, 선택 요약 + 멘토 목록 표시
    showSection('calendar-section', false);
    showSection('time-slots-area', false);
    showSection('teacher-list-area', true);
    showSelectedSummary(bookingState.date, time);

    // 멘토 목록 로드 (HTMX) - settle_code 포함
    htmx.ajax('GET', '/booking/partials/teacher-list?date=' + bookingState.date + '&time=' + encodeURIComponent(time) + '&room_idx=' + roomIdx + '&settle_code=' + bookingState.settleCode, {
        target: '#teacher-list-area',
        swap: 'innerHTML'
    });

    updateStep('멘토 선택', '4/7', 57);
    updateNextButton();

    // 상단으로 스크롤
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ===== 멘토 선택 =====
function selectTeacher(teacherId, teacherName, element) {
    // 이전 선택 해제
    document.querySelectorAll('.teacher-card.selected').forEach(function(el) {
        el.classList.remove('selected', 'ring-2', 'ring-nv-400');
        var check = el.querySelector('.teacher-check');
        if (check) {
            check.innerHTML = '';
            check.classList.remove('bg-nv-500', 'border-nv-500');
            check.classList.add('border-g-300');
        }
    });

    // 새 선택
    element.classList.add('selected', 'ring-2', 'ring-nv-400');
    var check = element.querySelector('.teacher-check');
    if (check) {
        check.innerHTML = '&#10003;';
        check.classList.remove('border-g-300');
        check.classList.add('bg-nv-500', 'border-nv-500');
    }

    bookingState.teacherId = teacherId;
    bookingState.teacherName = teacherName;

    // 폼 값 설정
    document.getElementById('selected-date').value = bookingState.date;
    document.getElementById('selected-time').value = bookingState.time;
    document.getElementById('selected-room-idx').value = bookingState.roomIdx;
    document.getElementById('selected-teacher-id').value = teacherId;

    updateStep('멘토 선택', '4/7', 57);
    updateNextButton();
}

// ===== 선택 요약 표시/숨기기 =====
function showSelectedSummary(date, time) {
    var el = document.getElementById('selected-summary');
    if (!el) return;
    // 날짜 포맷
    var parts = date.split('-');
    var d = new Date(parts[0], parts[1] - 1, parts[2]);
    var days = ['일', '월', '화', '수', '목', '금', '토'];
    var label = parts[1].replace(/^0/, '') + '/' + parts[2].replace(/^0/, '') + ' (' + days[d.getDay()] + ') ' + time;
    el.innerHTML = '<div class="bg-nv-50 rounded-xl p-3 flex items-center gap-3 mb-3">' +
        '<div class="w-9 h-9 bg-nv-100 rounded-lg flex items-center justify-center">' +
        '<svg width="16" height="16" viewBox="0 0 24 24" stroke="#43A047" stroke-width="1.5" fill="none"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></div>' +
        '<span class="text-[14px] font-bold text-nv-700">' + label + '</span>' +
        '<button onclick="bookingBack()" class="ml-auto text-[12px] text-g-400 underline">변경</button></div>';
    el.style.display = 'block';
}

function hideSelectedSummary() {
    var el = document.getElementById('selected-summary');
    if (el) {
        el.innerHTML = '';
        el.style.display = 'none';
    }
}

// ===== 섹션 표시/숨기기 =====
function showSection(id, show) {
    var el = document.getElementById(id);
    if (el) {
        el.style.display = show ? '' : 'none';
    }
}

// ===== UI 업데이트 =====
function updateStep(title, num, progress) {
    document.getElementById('step-title').textContent = title;
    document.getElementById('step-num').textContent = num;
    document.getElementById('progress-bar').style.width = progress + '%';
}

function updateNextButton() {
    var btn = document.getElementById('next-btn');
    if (bookingState.teacherId) {
        btn.disabled = false;
        btn.textContent = '다음 단계 \u2192';
        btn.classList.remove('bg-g-200', 'text-g-400');
        btn.classList.add('bg-nv-600', 'text-white');
    } else if (bookingState.time) {
        btn.disabled = true;
        btn.textContent = '멘토를 선택하세요';
        btn.classList.remove('bg-nv-600', 'text-white');
        btn.classList.add('bg-g-200', 'text-g-400');
    } else if (bookingState.date) {
        btn.disabled = true;
        btn.textContent = '시간을 선택하세요';
        btn.classList.remove('bg-nv-600', 'text-white');
        btn.classList.add('bg-g-200', 'text-g-400');
    } else {
        btn.disabled = true;
        btn.textContent = '날짜를 선택하세요';
        btn.classList.remove('bg-nv-600', 'text-white');
        btn.classList.add('bg-g-200', 'text-g-400');
    }
}

// ===== 뒤로가기 (단계별 롤백) =====
function bookingBack() {
    if (bookingState.teacherId) {
        // 멘토 선택 해제
        bookingState.teacherId = null;
        bookingState.teacherName = null;
        document.querySelectorAll('.teacher-card.selected').forEach(function(el) {
            el.classList.remove('selected', 'ring-2', 'ring-nv-400');
            var check = el.querySelector('.teacher-check');
            if (check) {
                check.innerHTML = '';
                check.classList.remove('bg-nv-500', 'border-nv-500');
                check.classList.add('border-g-300');
            }
        });
        updateStep('멘토 선택', '4/7', 57);
        updateNextButton();
    } else if (bookingState.time) {
        // 시간 선택 해제 → 캘린더+시간 목록 복원, 멘토 숨김
        bookingState.time = null;
        bookingState.roomIdx = null;
        showSection('calendar-section', true);
        showSection('time-slots-area', true);
        showSection('teacher-list-area', false);
        document.getElementById('teacher-list-area').innerHTML = '';
        hideSelectedSummary();
        updateStep('시간 선택', '3/7', 42);
        updateNextButton();
    } else if (bookingState.date) {
        // 날짜 선택 해제 → 시간 영역 제거
        bookingState.date = null;
        document.getElementById('time-slots-area').innerHTML = '';
        document.querySelectorAll('.cal-day.selected').forEach(function(el) {
            el.classList.remove('selected', 'bg-nv-500', 'text-white', 'font-bold', 'shadow-md');
            el.classList.add('bg-nv-50', 'text-nv-700', 'font-medium');
        });
        updateStep('날짜 선택', '2/7', 28);
        updateNextButton();
    } else {
        window.location.href = '/booking/';
    }
}
