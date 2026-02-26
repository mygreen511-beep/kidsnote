/**
 * 키즈노트백업 라이선스 관리 - Google Apps Script
 *
 * 설정 방법:
 * 1. Google Sheets 새 문서 생성
 * 2. 시트 이름을 "licenses" 로 변경
 * 3. A1~F1에 헤더 입력: license_key | used_count | max_count | status | created_at | last_used
 * 4. 메뉴 > 확장 프로그램 > Apps Script 클릭
 * 5. 이 코드를 전체 복사하여 붙여넣기
 * 6. 배포 > 새 배포 > 웹 앱 선택
 *    - 실행 권한: 본인
 *    - 액세스 권한: 모든 사용자
 * 7. 배포 후 나오는 URL을 kidsnote_app.py의 LICENSE_API_URL에 입력
 */

function doGet(e) {
  var action = e.parameter.action;
  var key = e.parameter.key;

  if (!action || !key) {
    return jsonResponse({ok: false, error: "missing parameters"});
  }

  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("licenses");
  var data = sheet.getDataRange().getValues();

  // 헤더 행 건너뛰고 키 찾기
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] === key) {
      var usedCount = data[i][1];
      var maxCount = data[i][2];
      var status = data[i][3];

      if (status !== "active") {
        return jsonResponse({ok: false, error: "비활성화된 라이선스입니다."});
      }

      if (action === "verify") {
        if (usedCount >= maxCount) {
          return jsonResponse({ok: false, error: "사용 횟수를 초과했습니다. (" + maxCount + "회)"});
        }
        return jsonResponse({ok: true, remaining: maxCount - usedCount, max: maxCount, used: usedCount});
      }

      if (action === "use") {
        if (usedCount >= maxCount) {
          return jsonResponse({ok: false, error: "사용 횟수를 초과했습니다."});
        }
        // 사용 횟수 +1
        sheet.getRange(i + 1, 2).setValue(usedCount + 1);
        // 마지막 사용일 업데이트
        sheet.getRange(i + 1, 6).setValue(new Date().toISOString().slice(0, 10));
        return jsonResponse({ok: true, remaining: maxCount - usedCount - 1});
      }
    }
  }

  return jsonResponse({ok: false, error: "유효하지 않은 라이선스 키입니다."});
}

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
