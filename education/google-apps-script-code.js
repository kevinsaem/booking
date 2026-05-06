// ============================================================
//  AI 단체교육 사전 설문 - Google Apps Script
//  구글 시트 자동 저장 + 이메일 알림
// ============================================================

// ★ 설문 응답을 받을 이메일 주소를 입력하세요
const NOTIFY_EMAIL = 'lgwanh1@gmail.com';

// ★ 이메일 제목 (원하는 대로 수정 가능)
const EMAIL_SUBJECT = '[AI교육 설문] 새로운 응답이 도착했습니다';

// 시트 컬럼 순서 (헤더)
const COLUMNS = [
  'submitted_at',
  'company', 'name', 'position', 'phone', 'email',
  'industry', 'headcount',
  'dept', 'age', 'it_level',
  'ai_usage', 'ai_tools', 'ai_perception',
  'purpose', 'topics',
  'pain_point', 'concerns',
  'format', 'duration', 'schedule', 'equipment', 'budget',
  'expectation', 'additional'
];

// 컬럼 한글 라벨
const LABELS = {
  submitted_at: '제출시간',
  company: '회사명',
  name: '담당자명',
  position: '직책',
  phone: '연락처',
  email: '이메일',
  industry: '업종',
  headcount: '교육인원',
  dept: '대상 직무/부서',
  age: '연령대',
  it_level: 'IT 활용 수준',
  ai_usage: 'AI 사용 현황',
  ai_tools: '사용 중 AI 도구',
  ai_perception: 'AI 인식(1~5)',
  purpose: '교육 목적',
  topics: '희망 학습 분야',
  pain_point: '반복 업무 고충',
  concerns: 'AI 우려사항',
  format: '교육 형태',
  duration: '교육 시간',
  schedule: '희망 일정',
  equipment: '실습 환경',
  budget: '예산 범위',
  expectation: '기대 변화',
  additional: '추가 요청'
};

// ─── POST 요청 처리 ───
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);

    // 1) 구글 시트에 저장
    saveToSheet(data);

    // 2) 이메일 알림 발송
    sendNotification(data);

    return ContentService
      .createTextOutput(JSON.stringify({ result: 'success' }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    Logger.log('Error: ' + err.toString());
    return ContentService
      .createTextOutput(JSON.stringify({ result: 'error', message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// ─── 구글 시트 저장 ───
function saveToSheet(data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('설문응답');

  // 시트가 없으면 생성 + 헤더 추가
  if (!sheet) {
    sheet = ss.insertSheet('설문응답');
    const headers = COLUMNS.map(col => LABELS[col] || col);
    sheet.appendRow(headers);

    // 헤더 스타일링
    const headerRange = sheet.getRange(1, 1, 1, headers.length);
    headerRange.setBackground('#1B2A4A');
    headerRange.setFontColor('#FFFFFF');
    headerRange.setFontWeight('bold');
    sheet.setFrozenRows(1);
  }

  // 데이터 행 추가
  const row = COLUMNS.map(col => data[col] || '');
  sheet.appendRow(row);
}

// ─── 이메일 알림 ───
function sendNotification(data) {
  let body = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n';
  body += '  📋 AI 단체교육 사전 설문 응답\n';
  body += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';

  // 섹션별 정리
  const sections = [
    {
      title: '📌 기본 정보',
      fields: ['company', 'name', 'position', 'phone', 'email', 'industry', 'headcount']
    },
    {
      title: '👥 교육 대상자',
      fields: ['dept', 'age', 'it_level']
    },
    {
      title: '🤖 AI 활용 현황',
      fields: ['ai_usage', 'ai_tools', 'ai_perception']
    },
    {
      title: '🎯 교육 목적',
      fields: ['purpose', 'topics']
    },
    {
      title: '💬 고충 및 우려',
      fields: ['pain_point', 'concerns']
    },
    {
      title: '📅 교육 운영',
      fields: ['format', 'duration', 'schedule', 'equipment', 'budget']
    },
    {
      title: '📝 추가 사항',
      fields: ['expectation', 'additional']
    }
  ];

  sections.forEach(section => {
    body += '▸ ' + section.title + '\n';
    body += '──────────────────────────\n';
    section.fields.forEach(field => {
      const label = LABELS[field] || field;
      const value = data[field] || '-';
      body += '  ' + label + ': ' + value + '\n';
    });
    body += '\n';
  });

  body += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n';
  body += '제출 시간: ' + (data['submitted_at'] || new Date().toLocaleString('ko-KR')) + '\n';
  body += '※ 이 메일은 설문 시스템에서 자동 발송되었습니다.\n';

  // HTML 버전 (보기 좋은 이메일)
  let html = '<div style="font-family:\'Apple SD Gothic Neo\',\'Noto Sans KR\',sans-serif;max-width:600px;margin:0 auto;">';
  html += '<div style="background:linear-gradient(135deg,#1B2A4A,#2A4070);padding:28px 32px;border-radius:12px 12px 0 0;">';
  html += '<h1 style="color:white;font-size:20px;margin:0;">📋 AI 단체교육 사전 설문 응답</h1>';
  html += '<p style="color:rgba(255,255,255,0.7);font-size:13px;margin:8px 0 0;">새로운 교육 의뢰가 접수되었습니다</p>';
  html += '</div>';
  html += '<div style="background:#ffffff;border:1px solid #E5E7EB;border-top:none;padding:24px 32px;border-radius:0 0 12px 12px;">';

  sections.forEach(section => {
    html += '<h3 style="font-size:15px;color:#1B2A4A;margin:20px 0 12px;padding-bottom:8px;border-bottom:2px solid #EFF6FF;">' + section.title + '</h3>';
    html += '<table style="width:100%;border-collapse:collapse;">';
    section.fields.forEach(field => {
      const label = LABELS[field] || field;
      const value = data[field] || '<span style="color:#9CA3AF;">미입력</span>';
      html += '<tr>';
      html += '<td style="padding:6px 8px;font-size:13px;color:#6B7280;width:120px;vertical-align:top;white-space:nowrap;">' + label + '</td>';
      html += '<td style="padding:6px 8px;font-size:14px;color:#111827;">' + value + '</td>';
      html += '</tr>';
    });
    html += '</table>';
  });

  html += '<div style="margin-top:24px;padding-top:16px;border-top:1px solid #E5E7EB;font-size:12px;color:#9CA3AF;">';
  html += '제출 시간: ' + (data['submitted_at'] || '') + '<br>';
  html += '이 메일은 설문 시스템에서 자동 발송되었습니다.';
  html += '</div></div></div>';

  MailApp.sendEmail({
    to: NOTIFY_EMAIL,
    subject: EMAIL_SUBJECT + ' - ' + (data['company'] || '(미입력)'),
    body: body,
    htmlBody: html
  });
}

// ─── GET 요청 (테스트용) ───
function doGet(e) {
  return ContentService
    .createTextOutput('✅ AI 교육 설문 스크립트가 정상 작동 중입니다.')
    .setMimeType(ContentService.MimeType.TEXT);
}
