/**
 * 캔버스 기반 서명 패드
 * PC 마우스 + 모바일 터치 모두 지원
 */
var hasSignature = false;  // 전역 변수 (인라인 스크립트와 공유)

const canvas = document.getElementById('signature-canvas');
if (!canvas) { console.error('signature-canvas not found'); }
const ctx = canvas.getContext('2d');
let isDrawing = false;
let lastX = 0;
let lastY = 0;

// 캔버스 크기 설정 (Retina 대응)
function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  _setStrokeStyle();
}

function _setStrokeStyle() {
  ctx.strokeStyle = '#1a1a1a';
  ctx.lineWidth = 2.5;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
}

resizeCanvas();
window.addEventListener('resize', function() {
  // resize 시 서명 초기화 (크기 변경되면 기존 그림 왜곡됨)
  hasSignature = false;
  resizeCanvas();
  if (typeof updateSubmitButton === 'function') updateSubmitButton();
});

// 좌표 계산
function getPos(e) {
  const rect = canvas.getBoundingClientRect();
  if (e.touches && e.touches.length > 0) {
    return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
  }
  return { x: e.clientX - rect.left, y: e.clientY - rect.top };
}

// 그리기 시작
function startDrawing(e) {
  // 터치 이벤트만 preventDefault (마우스는 기본 동작 유지)
  if (e.type.startsWith('touch')) e.preventDefault();
  isDrawing = true;
  const pos = getPos(e);
  lastX = pos.x;
  lastY = pos.y;
  // 점 찍기 (클릭만 하고 안 움직일 때도 표시)
  ctx.beginPath();
  ctx.arc(pos.x, pos.y, 1, 0, Math.PI * 2);
  ctx.fill();
}

// 그리기
function draw(e) {
  if (e.type.startsWith('touch')) e.preventDefault();
  if (!isDrawing) return;
  const pos = getPos(e);
  ctx.beginPath();
  ctx.moveTo(lastX, lastY);
  ctx.lineTo(pos.x, pos.y);
  ctx.stroke();
  lastX = pos.x;
  lastY = pos.y;
  hasSignature = true;
  if (typeof updateSubmitButton === 'function') updateSubmitButton();
}

// 그리기 종료
function stopDrawing() {
  isDrawing = false;
}

// 마우스 이벤트 (PC)
canvas.addEventListener('mousedown', startDrawing);
canvas.addEventListener('mousemove', draw);
canvas.addEventListener('mouseup', stopDrawing);
canvas.addEventListener('mouseleave', stopDrawing);

// 터치 이벤트 (모바일)
canvas.addEventListener('touchstart', startDrawing, { passive: false });
canvas.addEventListener('touchmove', draw, { passive: false });
canvas.addEventListener('touchend', stopDrawing);

// 서명 지우기
function clearSignature() {
  const dpr = window.devicePixelRatio || 1;
  ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr);
  hasSignature = false;
  _setStrokeStyle();
  if (typeof updateSubmitButton === 'function') updateSubmitButton();
}

// 서명 데이터 URL 반환 (캔버스에 실제 그려진 내용이 있는지 직접 확인)
function getSignatureDataUrl() {
  var dpr = window.devicePixelRatio || 1;
  var imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  var hasContent = false;
  for (var i = 3; i < imgData.data.length; i += 4) {
    if (imgData.data[i] > 0) { hasContent = true; break; }
  }
  if (!hasContent) return null;
  return canvas.toDataURL('image/png');
}
