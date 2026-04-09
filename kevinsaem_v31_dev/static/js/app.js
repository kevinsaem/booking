/* static/js/app.js */
/* 케빈샘 AI코딩 - 공통 JavaScript */
/* HTMX 이벤트 핸들링, 토스트 메시지, 유틸리티 함수 */

// ===== 토스트 메시지 =====
function showToast(message) {
    window.dispatchEvent(new CustomEvent('toast', {
        detail: { message: message }
    }));
}

// ===== HTMX 전역 이벤트 =====
// 요청 시작 시 로딩 표시
document.addEventListener('htmx:beforeRequest', function(evt) {
    // 로딩 인디케이터가 있으면 표시
    const indicator = evt.detail.elt.querySelector('.htmx-indicator');
    if (indicator) indicator.style.display = 'inline-flex';
});

// 요청 완료 시 로딩 숨김
document.addEventListener('htmx:afterRequest', function(evt) {
    const indicator = evt.detail.elt.querySelector('.htmx-indicator');
    if (indicator) indicator.style.display = 'none';
});

// HTMX 에러 발생 시 토스트
document.addEventListener('htmx:responseError', function(evt) {
    showToast('네트워크 오류가 발생했습니다. 다시 시도해주세요.');
});

// ===== 날짜 유틸리티 =====
const DAYS_KO = ['일', '월', '화', '수', '목', '금', '토'];

function formatDate(date) {
    const d = new Date(date);
    return d.getFullYear() + '.' + (d.getMonth() + 1) + '.' + d.getDate();
}

function formatDateWithDay(date) {
    const d = new Date(date);
    return (d.getMonth() + 1) + '/' + d.getDate() + '(' + DAYS_KO[d.getDay()] + ')';
}

function getDDay(dateStr) {
    const target = new Date(dateStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const diff = Math.ceil((target - today) / (1000 * 60 * 60 * 24));
    if (diff === 0) return 'D-Day';
    if (diff > 0) return 'D-' + diff;
    return 'D+' + Math.abs(diff);
}

// ===== 인증 유틸리티 =====
function getToken() {
    // JWT는 httponly 쿠키에 저장되므로 JS에서 직접 접근 불가
    // 서버에서 Depends(get_current_user)로 처리
    return document.cookie.split('; ')
        .find(row => row.startsWith('token='))
        ?.split('=')[1];
}

// ===== 확인 다이얼로그 =====
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// ===== 숫자 포맷 =====
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// ===== 모바일 감지 =====
function isMobile() {
    return window.innerWidth <= 430;
}

// ===== 페이지 로드 완료 =====
document.addEventListener('DOMContentLoaded', function() {
    // 활성 탭 표시
    const currentPath = window.location.pathname;
    document.querySelectorAll('.tab-item').forEach(tab => {
        const href = tab.getAttribute('href');
        if (currentPath === href || (href !== '/booking/' && currentPath.startsWith(href))) {
            tab.classList.add('active');
        }
    });
});
