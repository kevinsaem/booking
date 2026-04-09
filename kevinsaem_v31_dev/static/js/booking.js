/* static/js/booking.js */
/* 예약 페이지 전용 JavaScript */
/* 캘린더 날짜 클릭 → 시간 로드 → 강사 로드 단계 전환 처리 */

// ===== 상태 관리 =====
let bookingState = {
    date: null,
    time: null,
    roomIdx: null,
    teacherId: null,
    teacherName: null
};

// ===== 날짜 선택 =====
function selectDate(date, element) {
    // 이전 선택 해제
    document.querySelectorAll('.cal-day.selected').forEach(el => {
        el.classList.remove('selected', 'bg-green-500', 'text-white', 'font-bold');
        el.classList.add('bg-green-50', 'text-green-700', 'font-medium');
    });

    // 새 선택
    element.classList.remove('bg-green-50', 'text-green-700', 'font-medium');
    element.classList.add('selected', 'bg-green-500', 'text-white', 'font-bold');

    bookingState.date = date;
    bookingState.time = null;
    bookingState.roomIdx = null;
    bookingState.teacherId = null;

    // 시간 슬롯 로드 (HTMX)
    htmx.ajax('GET', '/booking/partials/time-slots?date=' + date, {
        target: '#time-slots-area',
        swap: 'innerHTML'
    });

    // 강사 영역 초기화
    document.getElementById('teacher-list-area').innerHTML = '';

    // 단계 업데이트
    updateStep('시간 선택', '3/7', 42);
    updateNextButton();
}

// ===== 시간 선택 =====
function selectTime(time, roomIdx, element) {
    // 이전 선택 해제
    document.querySelectorAll('.time-slot.selected').forEach(el => {
        el.classList.remove('selected', 'ring-2', 'ring-green-400');
    });

    // 새 선택
    element.classList.add('selected', 'ring-2', 'ring-green-400');

    bookingState.time = time;
    bookingState.roomIdx = roomIdx;
    bookingState.teacherId = null;

    // 강사 목록 로드 (HTMX)
    htmx.ajax('GET', '/booking/partials/teacher-list?date=' + bookingState.date + '&time=' + time + '&room_idx=' + roomIdx, {
        target: '#teacher-list-area',
        swap: 'innerHTML'
    });

    // 단계 업데이트
    updateStep('강사 선택', '4/7', 57);
    updateNextButton();
}

// ===== 강사 선택 =====
function selectTeacher(teacherId, teacherName, element) {
    // 이전 선택 해제
    document.querySelectorAll('.teacher-card.selected').forEach(el => {
        el.classList.remove('selected', 'ring-2', 'ring-green-400');
        el.querySelector('.teacher-check').innerHTML = '';
    });

    // 새 선택
    element.classList.add('selected', 'ring-2', 'ring-green-400');
    element.querySelector('.teacher-check').innerHTML = '✓';

    bookingState.teacherId = teacherId;
    bookingState.teacherName = teacherName;

    // 폼 값 설정
    document.getElementById('selected-date').value = bookingState.date;
    document.getElementById('selected-time').value = bookingState.time;
    document.getElementById('selected-room-idx').value = bookingState.roomIdx;
    document.getElementById('selected-teacher-id').value = teacherId;

    // 버튼 활성화
    updateStep('강사 선택', '4/7', 57);
    updateNextButton();
}

// ===== UI 업데이트 =====
function updateStep(title, num, progress) {
    document.getElementById('step-title').textContent = title;
    document.getElementById('step-num').textContent = num;
    document.getElementById('progress-bar').style.width = progress + '%';
}

function updateNextButton() {
    const btn = document.getElementById('next-btn');
    if (bookingState.teacherId) {
        btn.disabled = false;
        btn.textContent = '다음 단계 →';
    } else if (bookingState.time) {
        btn.disabled = true;
        btn.textContent = '강사를 선택하세요';
    } else if (bookingState.date) {
        btn.disabled = true;
        btn.textContent = '시간을 선택하세요';
    } else {
        btn.disabled = true;
        btn.textContent = '날짜를 선택하세요';
    }
}
