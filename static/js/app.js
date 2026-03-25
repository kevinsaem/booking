/* static/js/app.js */
/* 케빈샘랩 - 공통 JavaScript */
/* 토스트 메시지, HTMX 이벤트, 날짜 유틸리티 */

// ===== 토스트 메시지 =====
function showToast(message) {
    window.dispatchEvent(new CustomEvent('toast', {
        detail: { message: message }
    }));
}

// ===== HTMX 전역 이벤트 =====
// 요청 시작 시 로딩 표시
document.addEventListener('htmx:beforeRequest', function(evt) {
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

// HTMX 응답 후 토스트 트리거 (서버에서 HX-Trigger: toast 헤더 보낼 때)
document.addEventListener('htmx:afterSettle', function(evt) {
    var trigger = evt.detail.xhr && evt.detail.xhr.getResponseHeader('HX-Trigger');
    if (trigger) {
        try {
            var parsed = JSON.parse(trigger);
            if (parsed.toast) {
                showToast(parsed.toast);
            }
        } catch (e) {
            // 단순 문자열 트리거인 경우 무시
        }
    }
});

// ===== 날짜 유틸리티 =====
var DAYS_KO = ['일', '월', '화', '수', '목', '금', '토'];

function formatDate(date) {
    var d = new Date(date);
    return d.getFullYear() + '.' + (d.getMonth() + 1) + '.' + d.getDate();
}

function formatDateWithDay(date) {
    var d = new Date(date);
    return (d.getMonth() + 1) + '/' + d.getDate() + '(' + DAYS_KO[d.getDay()] + ')';
}

function getDDay(dateStr) {
    var target = new Date(dateStr);
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var diff = Math.ceil((target - today) / (1000 * 60 * 60 * 24));
    if (diff === 0) return 'D-Day';
    if (diff > 0) return 'D-' + diff;
    return 'D+' + Math.abs(diff);
}

// ===== 인증 유틸리티 =====
function getToken() {
    return document.cookie.split('; ')
        .find(function(row) { return row.startsWith('token='); })
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

// ===== 페이지 로드 완료 =====
document.addEventListener('DOMContentLoaded', function() {
    // 활성 탭 표시 (tab.on 클래스와 중복되지 않도록)
    var currentPath = window.location.pathname;
    document.querySelectorAll('.tab').forEach(function(tab) {
        var href = tab.getAttribute('href');
        if (href && (currentPath === href || (href !== '/booking/' && currentPath.startsWith(href)))) {
            tab.classList.add('on');
        }
    });
});
